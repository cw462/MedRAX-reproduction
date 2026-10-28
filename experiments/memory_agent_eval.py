"""Memory-assisted multi-tool MedRAX runs with a configurable central model.

This is the experiment entry point for R0 (no cross-case memory) and R1-R3
(retrieved training trajectories injected into the first prompt). It reuses the
audited upstream Agent, the original classifier/report/segmentation tools and
their provenance hashes, and it writes exactly the run format that
`memory_pipeline.compile_run` accepts.

Design constraints kept from the earlier diagnostics:
  * inputs are inference-only three-field rows and never contain labels;
  * every model request is reserved in a locked CNY ledger before it is sent;
  * tool arguments/images are checked against the question before execution;
  * traces hold hashes and whitelisted shapes, never raw report text or paths;
  * a tool being registered is not evidence that it was selected or executed.

Memory injection is the only intended behavioural difference between arms. The
injected block is built from `memory_pipeline.injection` and contains no answer,
option, patient identifier or raw report text.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import diagnostic_eval as diag  # noqa: E402
import tool_variants as variants  # noqa: E402
from provider_ledger import BudgetExceeded as LedgerBudgetExceeded  # noqa: E402
from provider_ledger import LedgerIntegrityError, ProviderLedger  # noqa: E402
from provider_profile import get_profile  # noqa: E402

MODEL_KINDS = {'classification', 'report', 'segmentation'}
ARMS = ('r0', 'r1', 'r2', 'r3')
MAX_CASES_DEFAULT = 500


class ModelIdentityMismatch(RuntimeError):
    pass


# --------------------------------------------------------------------- inputs
def load_rows(path, max_cases):
    rows, seen = [], set()
    with Path(path).open(encoding='utf-8-sig') as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if type(row) is not dict or set(row) != {'question_id', 'question', 'images'}:
                raise ValueError(f'Line {line_no}: exactly question_id, question, images are required')
            if type(row['question_id']) not in (str, int) or not str(row['question_id']).strip():
                raise ValueError(f'Line {line_no}: invalid question_id')
            if type(row['question']) is not str or not row['question'].strip():
                raise ValueError(f'Line {line_no}: invalid question text')
            if type(row['images']) is not list or any(type(x) is not str or not x for x in row['images']):
                raise ValueError(f'Line {line_no}: invalid image list')
            row['question_id'] = str(row['question_id'])
            if row['question_id'] in seen:
                raise ValueError(f'Line {line_no}: duplicate question_id')
            seen.add(row['question_id'])
            rows.append(row)
    if not rows:
        raise ValueError('No questions in input')
    if max_cases and len(rows) > max_cases:
        rows = rows[:max_cases]
    return rows


def inspect_input(row, root):
    issues, entries, paths = [], [], []
    if not row['images']:
        issues.append('missing_image')
    total = 0
    for raw in row['images']:
        path = (root / raw).resolve()
        entry = {'relative_path': raw, 'sha256': None, 'bytes': None}
        if not path.is_relative_to(root):
            issues.append('image_path_escape')
        elif not path.is_file():
            issues.append('missing_image')
        elif mimetypes.guess_type(path.name)[0] not in ('image/jpeg', 'image/png'):
            issues.append('unsupported_image_format')
        else:
            entry.update(sha256=diag.smoke.classifier_utils.sha256_file(path), bytes=path.stat().st_size)
            total += entry['bytes']
            paths.append(path)
        entries.append(entry)
    if total > 24 * 1024 * 1024:
        issues.append('input_size_limit')
    return ({'question_id': row['question_id'], 'question_sha256': diag.hash_value(row['question']),
             'images': entries, 'preflight_issues': sorted(set(issues))}, paths)


def initial_messages(row, paths, detail, memory_text=None):
    """Same formatting as the audited smoke, with an optional memory prelude."""
    from langchain_core.messages import HumanMessage
    image_text = '\n'.join(f'Image located at {path}' for path in paths)
    prompt = (diag.AGENT_PREFIX + '\n')
    if memory_text:
        prompt += memory_text.rstrip() + '\n\n'
    prompt += row['question'] + '\n' + image_text
    content = [{'type': 'text', 'text': prompt}]
    for path in paths:
        mime = mimetypes.guess_type(path.name)[0]
        if mime not in ('image/jpeg', 'image/png'):
            raise ValueError('Only JPEG and PNG images are supported')
        content.append({'type': 'image_url', 'image_url': {
            'url': f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode('ascii'),
            'detail': detail}})
    return [HumanMessage(content=content)]


def relaxed_letter(content):
    """Conservative fallback parser recorded next to the audited strict matcher.

    The strict matcher is the protocol metric. The relaxed parser only accepts an
    explicit 'answer/option/choice X' phrase or a whole final line that is a
    single bracketed letter, so a free-text diagnosis cannot masquerade as a
    choice.
    """
    strict = diag.smoke.answer_letter(content)
    if strict:
        return strict
    if not isinstance(content, str) or not content.strip():
        return None
    match = re.search(r'(?i)\b(?:final\s+)?(?:answer|option|choice)\b[^A-Fa-f]{0,12}([A-F])\b', content)
    if match:
        return match.group(1).upper()
    tail = content.strip().splitlines()[-1].strip()
    match = re.fullmatch(r'[\(\*\s]*([A-F])[\)\*\s.]*', tail)
    return match.group(1) if match else None


def estimate_input_tokens(messages):
    """Conservative prompt bound: characters, images and bound tool schemas."""
    chars, images = 0, 0
    for message in messages:
        content = getattr(message, 'content', None)
        if isinstance(content, str):
            chars += len(content)
        elif isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get('type') == 'text':
                    chars += len(part.get('text') or '')
                elif part.get('type') == 'image_url':
                    images += 1
    return int(chars / 2.2) + images * 1200 + 2600


# ----------------------------------------------------------------- budget model
class BudgetedModel:
    def __init__(self, wrapped, ledger, ctx, profile):
        self.wrapped, self.ledger, self.ctx, self.profile = wrapped, ledger, ctx, profile

    def invoke(self, messages, *args, **kwargs):
        ctx, profile = self.ctx, self.profile
        ctx['budget'].reserve('model', 'llm')
        ordinal = ctx['budget'].counts['model']
        request_id = f"{ctx['run_id']}:{ctx['thread_id']}:{ordinal}"
        estimate = min(estimate_input_tokens(messages), profile.max_input_tokens)
        reservation = None
        started, response, usage, error_type = time.monotonic(), None, None, None
        try:
            reservation = self.ledger.reserve(
                metadata={'request_id': request_id, 'question_id': ctx['question_id'][:128],
                          'arm': ctx['arm'], 'phase': ctx['phase'], 'model_call': ordinal,
                          'model': profile.model},
                request_id=request_id, estimated_input_tokens=estimate,
                max_output_tokens=ctx['max_output_tokens'], model=profile.model)
        except LedgerBudgetExceeded as exc:
            ctx['stop_run'] = True
            ctx['money_status'] = 'monetary_budget_exceeded'
            ctx['issues'].add('monetary_budget_exceeded')
            diag.event(ctx, node='money_reserve', status='blocked', reason='budget',
                       model_ordinal=ordinal)
            raise diag.MonetaryStop('monetary_budget_exceeded') from exc
        except LedgerIntegrityError as exc:
            ctx['stop_run'] = True
            ctx['money_status'] = 'monetary_guard_error'
            ctx['issues'].add('monetary_guard_error')
            diag.event(ctx, node='money_reserve', status='blocked', reason='integrity',
                       model_ordinal=ordinal)
            raise diag.MonetaryStop('monetary_guard_error') from exc
        ctx['actual_model_calls'] += 1
        try:
            response = self.wrapped.invoke(messages, *args, **kwargs)
            usage = diag.smoke.numeric_usage(response)
            if usage is not None:
                ctx['usage_records'].append(usage)
            if usage is None or not all(k in usage for k in ('input_tokens', 'output_tokens', 'total_tokens')):
                ctx['issues'].add('token_usage_incomplete')
            meta = getattr(response, 'response_metadata', None) or {}
            finish = meta.get('finish_reason')
            returned = meta.get('model_name')
            ctx['last_finish_reason'] = finish
            ctx['returned_model'] = returned
            if not returned:
                ctx['issues'].add('model_identity_unreported')
            elif not profile.identity_ok(returned):
                ctx['issues'].add('model_identity_mismatch')
                raise ModelIdentityMismatch('Returned model differs from the frozen profile')
            if finish == 'length':
                ctx['issues'].add('model_output_truncated')
            calls = []
            for call in (getattr(response, 'tool_calls', None) or []):
                name = call.get('name')
                if name not in ctx['allowed_tool_names']:
                    ctx['issues'].add('unknown_tool_requested')
                calls.append({'id': call.get('id'), 'name': name,
                              'argument_keys': sorted(call.get('args', {})) if isinstance(call.get('args'), dict) else []})
            if getattr(response, 'invalid_tool_calls', None):
                ctx['issues'].add('invalid_tool_call_schema')
            diag.event(ctx, node='model', model_call=ordinal, request_id=request_id, usage=usage,
                       finish_reason=finish, returned_model=returned, tool_calls=calls,
                       estimated_input_tokens=estimate,
                       content_summary=diag.smoke.summarize(getattr(response, 'content', '')))
            return response
        except BaseException as exc:
            error_type = type(exc).__name__
            status_code = getattr(exc, 'status_code', None)
            ctx['issues'].add('model_exception')
            ctx['api_error'] = True
            ctx['api_error_type'] = error_type
            ctx['api_status_code'] = status_code
            if status_code in (401, 402, 403) or error_type in ('AuthenticationError', 'PermissionDeniedError'):
                # A dead or unpaid credential must not be retried across the
                # remaining denominator: every attempt would consume a full
                # reservation while the provider rejects it.
                ctx['stop_run'] = True
                ctx['stop_reason'] = 'api_auth_or_billing_error'
                ctx['issues'].add('immediate_api_failure_stop')
            diag.event(ctx, node='model', model_call=ordinal, request_id=request_id,
                       status='exception', error_type=error_type, status_code=status_code, usage=usage)
            raise
        finally:
            complete = usage is not None and all(k in usage for k in ('input_tokens', 'output_tokens')) and error_type is None
            billed = ({'prompt_tokens': usage['input_tokens'], 'completion_tokens': usage['output_tokens']}
                      if complete else None)
            try:
                settlement = self.ledger.settle(reservation, usage=billed,
                                                response_received=response is not None,
                                                error_type=error_type)
                ctx['ledger_settlements'].append(settlement)
                diag.event(ctx, node='money_settle', model_call=ordinal, request_id=request_id,
                           settlement=settlement,
                           elapsed_ms=round((time.monotonic() - started) * 1000))
            except LedgerIntegrityError as exc:
                ctx['stop_run'] = True
                ctx['money_status'] = 'monetary_guard_error'
                ctx['issues'].add('monetary_guard_error')
                diag.event(ctx, node='money_settle', status='failed', error_type=type(exc).__name__)
                raise diag.MonetaryStop('monetary_guard_error') from exc


class TrackedTool:
    """Validated proxy that records execution facts for the memory compiler."""

    def __init__(self, wrapped, provenance, context):
        self.wrapped, self.provenance, self.ctx = wrapped, provenance, context
        self.kind = provenance['kind']
        self.version = diag.hash_value(provenance)

    def invoke(self, params):
        ctx, name = self.ctx, self.wrapped.name
        counts = ctx['tool_counts'][name]
        counts['requested'] += 1
        ctx['budget'].reserve('tool', name)
        began = time.monotonic()
        detail = {'node': 'tool', 'tool_name': name, 'tool_kind': self.kind,
                  'tool_version_sha256': self.version, 'execution': 'exception',
                  'clinical_evidence': 'unknown', 'step_credit': None, 'raw_content_logged': False}
        try:
            clean, image = validate_parameters(self.wrapped, self.kind, params, ctx['allowed_images'])
            fingerprint = diag.hash_value({'tool': name, 'arguments': clean})
            repeated = fingerprint in ctx['tool_fingerprints']
            ctx['tool_fingerprints'].add(fingerprint)
            if repeated:
                counts['repeated'] += 1
                ctx['repeated_tool_calls'] += 1
                ctx['issues'].add('repeated_tool_call')
            detail.update(arguments_sha256=fingerprint, argument_keys=sorted(clean), repeated=repeated,
                          image_sha256=diag.smoke.classifier_utils.sha256_file(image))
            ctx['actual_tool_attempts'] += 1
            counts['attempted'] += 1
            result = self.wrapped.invoke(clean)
            checked = variants.validate_observation(
                self.kind, result,
                **({'artifact_dir': self.wrapped.temp_dir} if self.kind == 'segmentation' else {}))
            detail.update(output_contract=checked, output_summary=diag.smoke.summarize(result),
                          execution='returned')
            if checked['valid']:
                ctx['validated_tool_returns'] += 1
                counts['validated_returns'] += 1
            else:
                ctx['failed_tool_returns'] += 1
                counts['failed_returns'] += 1
                ctx['issues'].add('tool_failed_or_invalid')
            return result
        except Exception as exc:
            counts['exceptions'] += 1
            ctx['issues'].add('tool_exception')
            detail['error_type'] = type(exc).__name__
            raise
        finally:
            detail['elapsed_ms'] = round((time.monotonic() - began) * 1000)
            diag.event(ctx, **detail)


def validate_parameters(tool, kind, params, allowed_images):
    """Copy of the audited multi-tool schema/image check (kept local, no import)."""
    if type(params) is not dict:
        raise ValueError('Tool arguments must be an object')
    schema = tool.args_schema
    description = schema.model_json_schema() if hasattr(schema, 'model_json_schema') else schema.schema()
    fields, required = set(description.get('properties', {})), set(description.get('required', []))
    expected = {'image_path', 'organs'} if kind == 'segmentation' else {'image_path'}
    if fields != expected or 'image_path' not in required:
        raise ValueError('Tool schema differs from the supported fixed tool')
    if not required <= set(params) or not set(params) <= fields or type(params.get('image_path')) is not str:
        raise ValueError('Invalid or extra tool arguments')
    image = Path(params['image_path']).resolve()
    if image not in allowed_images:
        raise ValueError('Tool image is outside the current question')
    if kind == 'segmentation' and params.get('organs') is not None:
        organs = params['organs']
        valid = set(tool.organ_map)
        if (type(organs) is not list or not organs
                or any(type(x) is not str or x not in valid for x in organs)
                or len(set(organs)) != len(organs)):
            raise ValueError('Segmentation organs must be distinct valid advertised names')
    if hasattr(schema, 'model_validate'):
        schema.model_validate(params)
    else:
        schema.parse_obj(params)
    return dict(params, image_path=str(image)), image


# ------------------------------------------------------------------------ runs
def run_arm(runtime, ledger, profile, row, paths, arm, start, run_id, args, trace,
            memory=None, memory_ids=()):
    ctx = {'question_id': row['question_id'], 'arm': 'agent', 'thread_id': start['thread_id'],
           'run_id': run_id, 'phase': 0, 'issues': set(), 'usage_records': [],
           'ledger_settlements': [], 'actual_model_calls': 0, 'actual_tool_attempts': 0,
           'validated_tool_returns': 0, 'failed_tool_returns': 0, 'repeated_tool_calls': 0,
           'allowed_images': set(paths), 'tool_fingerprints': set(), 'stop_run': False,
           'last_finish_reason': None, 'max_output_tokens': args.max_output_tokens,
           'allowed_tool_names': set(runtime.tools),
           'tool_counts': {name: dict(requested=0, attempted=0, validated_returns=0,
                                      failed_returns=0, exceptions=0, repeated=0)
                           for name in runtime.tools}}
    ctx['trace'] = diag.TaggedTrace(trace, ctx)
    ctx['budget'] = diag.smoke.CaseBudget(args.max_tool_calls, args.max_model_calls,
                                          args.max_case_seconds, ctx['trace'])
    ctx['budget'].case_hash = diag.hash_value(row['question_id'])
    ctx['budget'].thread_id = start['thread_id']
    report = {'question_id': row['question_id'], 'arm': 'agent', 'experiment_arm': arm,
              'thread_id': start['thread_id'], 'answer_letter': None, 'final_content_summary': None,
              'phase_outcomes': [], 'available_tool_names': sorted(runtime.tools),
              'memory_ids': list(memory_ids), 'memory_injected': bool(memory),
              'memory_chars': len(memory or ''), 'tools_forced': False,
              'clinical_evidence': 'unknown', 'step_credit': None}
    began, final = time.monotonic(), None
    try:
        messages = initial_messages(row, paths, args.image_detail, memory)
        agent = runtime.Agent(runtime.model, tools=list(runtime.tools.values()),
                              checkpointer=runtime.MemorySaver(),
                              system_prompt=runtime.agent_system, log_tools=False)
        agent.model = BudgetedModel(agent.model, ledger, ctx, profile)
        agent.tools = {name: TrackedTool(tool, runtime.tool_provenance[name], ctx)
                       for name, tool in runtime.tools.items()}
        for phase, batch in enumerate((messages, [runtime.HumanMessage(content=diag.smoke.FOLLOWUP)]), 1):
            ctx['phase'] = phase
            final = None
            for step in agent.workflow.stream({'messages': batch},
                                              {'configurable': {'thread_id': start['thread_id']},
                                               'recursion_limit': 12}):
                for node, values in step.items():
                    for message in values.get('messages', []):
                        if node == 'process' and not (getattr(message, 'tool_calls', None) or []):
                            final = message.content
                        elif node == 'execute':
                            diag.event(ctx, node='tool_message',
                                       tool_call_id=getattr(message, 'tool_call_id', None),
                                       tool_name=getattr(message, 'name', None),
                                       observation_summary=diag.smoke.summarize(getattr(message, 'content', '')),
                                       clinical_evidence='unknown', step_credit=None)
            report['phase_outcomes'].append({'phase': phase, 'finish_reason': ctx['last_finish_reason'],
                'content_summary': diag.smoke.summarize(final),
                'strict_answer_letter': diag.smoke.answer_letter(final)})
        report['answer_letter'] = diag.smoke.answer_letter(final)
        report['answer_letter_relaxed'] = relaxed_letter(final)
        report['final_content_summary'] = diag.smoke.summarize(final)
        report['status'] = 'completed' if report['answer_letter'] else 'invalid_answer'
        if report['answer_letter'] is None:
            ctx['issues'].add('invalid_answer')
    except diag.MonetaryStop:
        report['status'] = ctx.get('money_status', 'monetary_budget_exceeded')
    except diag.smoke.BudgetExceeded as exc:
        report.update(status='case_budget_exceeded', error_type=type(exc).__name__)
        ctx['issues'].add('case_call_or_time_limit')
    except Exception as exc:
        report.update(status='tool_error' if 'tool_exception' in ctx['issues'] else
                      'model_error' if 'model_exception' in ctx['issues'] else 'failed',
                      error_type=type(exc).__name__)
        ctx['issues'].add(report['status'])
    if ctx['actual_tool_attempts'] == 0:
        ctx['issues'].add('no_tool_call')
    elif ctx['validated_tool_returns'] == 0:
        ctx['issues'].add('no_valid_tool_return')
    report.update(issue_tags=sorted(ctx['issues']), call_counts=dict(ctx['budget'].counts),
                  actual_model_calls=ctx['actual_model_calls'],
                  actual_tool_attempts=ctx['actual_tool_attempts'],
                  validated_tool_returns=ctx['validated_tool_returns'],
                  failed_tool_returns=ctx['failed_tool_returns'],
                  repeated_tool_calls=ctx['repeated_tool_calls'],
                  tool_execution_verified=ctx['validated_tool_returns'] > 0,
                  final_finish_reason=ctx['last_finish_reason'],
                  usage_records=ctx['usage_records'],
                  ledger_settlements=ctx['ledger_settlements'],
                  stop_run=ctx['stop_run'],
                  elapsed_seconds=round(time.monotonic() - began, 3),
                  tool_counts=ctx['tool_counts'],
                  selected_tool_names=sorted(n for n, c in ctx['tool_counts'].items() if c['attempted']))
    report['observed_usage_sum'], report['usage_complete'] = diag.smoke.aggregate_usage(
        ctx['usage_records'], ctx['actual_model_calls'])
    report['stop_reason'] = ctx.get('stop_reason', 'budget' if ctx['stop_run'] else None)
    report['api_error'] = ctx.get('api_error', False)
    report['api_error_type'] = ctx.get('api_error_type')
    report['api_status_code'] = ctx.get('api_status_code')
    return report


# ---------------------------------------------------------------------- runtime
def build_runtime(args, profile, key, prompt, temporary_artifacts):
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
    from langgraph.checkpoint.memory import MemorySaver
    tools, provenance = {}, {}
    factories = [variants.create_classifier_tool(args.repo, checkpoint=args.classifier_checkpoint,
                                                 device=args.device, mode='original'),
                 variants.create_report_tool(args.repo, cache_dir=args.report_cache,
                                             device=args.device, mode='original')]
    if args.segmentation_checkpoint is not None:
        factories.append(variants.create_segmentation_tool(
            args.repo, checkpoint=args.segmentation_checkpoint, device=args.device,
            temp_dir=temporary_artifacts / 'segmentation'))
    for tool, recorded in factories:
        if tool.name in tools:
            raise ValueError('Duplicate tool name')
        tools[tool.name], provenance[tool.name] = tool, recorded
    Agent = diag.smoke.module_from_file('_memory_official_agent',
                                        args.repo / 'medrax/agent/agent.py').Agent
    model = ChatOpenAI(model=profile.model, base_url=profile.base_url, api_key=key,
                       temperature=args.temperature, top_p=args.top_p,
                       max_tokens=args.max_output_tokens, max_retries=0,
                       timeout=args.request_timeout_seconds)
    return SimpleNamespace(model=model, tools=tools, tool_provenance=provenance, Agent=Agent,
                           MemorySaver=MemorySaver, HumanMessage=HumanMessage,
                           SystemMessage=SystemMessage, agent_system=prompt)


def build_plan(args, rows, records, runtime, profile, prompt, policy, protocol_sha256):
    versions = {name: diag.hash_value(value) for name, value in runtime.tool_provenance.items()}
    files = {'memory_agent_eval.py': Path(__file__), 'tool_variants.py': Path(variants.__file__),
             'provider_profile.py': Path(__file__).with_name('provider_profile.py'),
             'provider_ledger.py': Path(__file__).with_name('provider_ledger.py'),
             'memory_injection.py': Path(__file__).resolve().parents[1] / 'memory_pipeline/injection.py',
             'official_agent.py': args.repo / 'medrax/agent/agent.py',
             'official_classifier.py': args.repo / 'medrax/tools/classification.py',
             'official_report.py': args.repo / 'medrax/tools/report_generation.py',
             'official_utils.py': args.repo / 'medrax/utils/utils.py'}
    if 'chest_xray_segmentation' in versions:
        files['official_segmentation.py'] = args.repo / 'medrax/tools/segmentation.py'
    packages = {}
    for package in ('langgraph', 'langchain-openai', 'openai', 'langchain-core', 'torch',
                    'transformers', 'torchxrayvision'):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = None
    plan = {
        'schema_version': 1,
        'kind': 'memory_agent_available_original_tools_v1',
        'planned_question_count': len(rows),
        'question_ids': [row['question_id'] for row in rows],
        'schedule': [{'question_id': row['question_id'], 'arm': 'agent'} for row in rows],
        'arms': ['agent'],
        'input_sha256': diag.smoke.classifier_utils.sha256_file(args.input),
        'selection_sha256': diag.hash_value(records),
        'records': records,
        'model': profile.model,
        'provider_base_url': profile.base_url,
        'provider_profile': profile.policy_snapshot(),
        'prompts': {'agent_system': prompt, 'agent_first_prefix': diag.AGENT_PREFIX,
                    'followup': diag.smoke.FOLLOWUP},
        'max_output_tokens': args.max_output_tokens,
        'max_model_calls': args.max_model_calls,
        'max_tool_calls': args.max_tool_calls,
        'temperature': args.temperature,
        'top_p': args.top_p,
        'provider_retries': 0,
        'image_detail': args.image_detail,
        'request_timeout_seconds': args.request_timeout_seconds,
        'max_case_seconds': args.max_case_seconds,
        'recursion_limit': 12,
        'device': args.device,
        'source_sha256': {name: diag.smoke.classifier_utils.sha256_file(path)
                          for name, path in files.items()},
        'package_versions': packages,
        'tool_registry': runtime.tool_provenance,
        'available_tool_names': sorted(runtime.tools),
        'available_tool_versions': versions,
        'protocol_sha256': protocol_sha256,
        'monetary_policy': policy,
        'memory': {'arm': args.arm, 'pool': str(args.pool) if args.pool else None,
                   'pool_sha256': args.pool_sha256, 'top_k': args.top_k,
                   'min_score': args.min_score, 'include_failures': args.arm == 'r3',
                   'summary_mode': args.arm in ('r2', 'r3'),
                   'max_chars': args.memory_max_chars,
                   'injection_template': 'memory_pipeline.injection.build_memory_block'},
        'images_root': str(args.images_root.resolve()),
        'upstream_repo_path': str(args.repo),
        'protocol_deviations': [
            'Central model is a DashScope-hosted Qwen VLM, not GPT-4o; every arm shares it.',
            'Only the original classifier and report tools (plus optional segmentation) are available; this is not the six-tool paper set.',
            'Each question/arm uses a fresh thread and the two-stage prompt from the audited smoke.',
            f'Memory arm {args.arm}: retrieved training execution facts are injected before the question; no answer or option text is injected.',
            'The ledger is a conservative internal bound at assumed prices, not the provider bill.',
        ],
    }
    return plan


def compute_protocol(plan, family='multitool_original'):
    from memory_pipeline.core import _protocol
    return _protocol(plan, family)[0]


# -------------------------------------------------------------------------- main
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'input', 'images-root', 'output', 'ledger'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--inherit-ledger', type=Path,
                        help='Completed GPT-4o ledger whose committed total is inherited')
    parser.add_argument('--profile', default='qwen3-vl-plus')
    parser.add_argument('--arm', choices=ARMS, default='r0')
    parser.add_argument('--pool', type=Path)
    parser.add_argument('--pool-sha256')
    parser.add_argument('--top-k', type=int, default=3)
    parser.add_argument('--min-score', type=float, default=0.0)
    parser.add_argument('--memory-max-chars', type=int, default=1400)
    parser.add_argument('--classifier-checkpoint', type=Path, required=True)
    parser.add_argument('--report-cache', type=Path, required=True)
    parser.add_argument('--segmentation-checkpoint', type=Path)
    parser.add_argument('--api-key-stdin', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--max-cases', type=int, default=0)
    parser.add_argument('--max-tool-calls', type=int, default=3)
    parser.add_argument('--max-model-calls', type=int, default=4)
    parser.add_argument('--max-output-tokens', type=int, default=1024)
    parser.add_argument('--max-case-seconds', type=float, default=240)
    parser.add_argument('--request-timeout-seconds', type=float, default=120)
    parser.add_argument('--device', default='cuda:0')
    parser.add_argument('--image-detail', choices=('auto', 'low', 'high'), default='auto')
    parser.add_argument('--temperature', type=float, default=0.2)
    parser.add_argument('--top-p', type=float, default=0.95)
    parser.add_argument('--plan-only', action='store_true',
                        help='Build inputs/runtime/protocol, print them and exit without a journal or API call')
    parser.add_argument('--max-consecutive-failures', type=int, default=3,
                        help='Stop a resumable run after this many consecutive model/tool failures')
    args = parser.parse_args(argv)

    if args.arm != 'r0' and (args.pool is None or not args.pool_sha256):
        parser.error('Memory arms require --pool and --pool-sha256')
    if args.top_k not in (1, 3, 5):
        parser.error('top-k must be one of the calibrated values 1, 3, 5')
    if any(not math.isfinite(x) or x <= 0 for x in (args.max_case_seconds, args.request_timeout_seconds)):
        parser.error('Timeouts must be finite and positive')
    if args.max_cases <= 0:
        args.max_cases = MAX_CASES_DEFAULT
    profile = get_profile(args.profile)
    if args.max_output_tokens > profile.max_output_tokens:
        parser.error('max-output-tokens exceeds the frozen profile bound')

    key = sys.stdin.readline().strip() if args.api_key_stdin else os.environ.get('OPENAI_API_KEY', '')
    if not key:
        parser.error('API key absent')
    os.environ['OPENAI_API_KEY'] = key

    rows = load_rows(args.input, args.max_cases)
    records, paths_by_qid = [], {}
    for row in rows:
        record, paths = inspect_input(row, args.images_root.resolve())
        records.append(record)
        paths_by_qid[row['question_id']] = paths
    broken = [r['question_id'] for r in records if r['preflight_issues']]
    if broken:
        # A compilation denominator cannot contain unrunnable questions, so stop
        # before any paid call instead of journaling a placeholder terminal.
        raise SystemExit(f'Preflight failed for {len(broken)} question(s): {broken[:10]}')

    utils = diag.smoke.module_from_file('_memory_official_utils', args.repo / 'medrax/utils/utils.py')
    prompt = utils.load_prompts_from_file(str(args.repo / 'medrax/docs/system_prompts.txt'))['MEDICAL_ASSISTANT']

    output = args.output.resolve()
    journal = None
    with ProviderLedger(args.ledger, profile, cap_cny='100',
                        inherit_ledger_path=args.inherit_ledger) as ledger, \
            tempfile.TemporaryDirectory(prefix='medrax-tool-init-') as temporary:
        with open(os.devnull, 'w') as sink, redirect_stdout(sink), redirect_stderr(sink):
            runtime = build_runtime(args, profile, key, prompt, Path(temporary))
        # Protocol hash is computed from a plan with a placeholder protocol field,
        # then frozen into the real plan so runs and pools can be compared.
        probe_plan = build_plan(args, rows, records, runtime, profile, prompt,
                                ledger.policy_snapshot(), None)
        protocol = compute_protocol(probe_plan)
        plan = build_plan(args, rows, records, runtime, profile, prompt,
                          ledger.policy_snapshot(), protocol)
        if compute_protocol(plan) != protocol:
            raise RuntimeError('Protocol hash is not stable across plan construction')
        pool = None
        if args.pool is not None:
            from memory_pipeline.core import FrozenPool
            pool = FrozenPool.load(args.pool, expected_sha256=args.pool_sha256)
            if pool.payload()['protocol_sha256'] != protocol:
                raise ValueError('Pool protocol differs from this run configuration')
        if args.plan_only:
            print(json.dumps({'protocol_sha256': protocol,
                              'questions': len(rows),
                              'available_tools': plan['available_tool_versions'],
                              'arm': args.arm,
                              'pool_loaded': pool is not None,
                              'pool_protocol_matches': bool(pool) and
                              pool.payload()['protocol_sha256'] == protocol,
                              'max_tool_calls': plan['max_tool_calls'],
                              'max_model_calls': plan['max_model_calls'],
                              'max_output_tokens': plan['max_output_tokens']}, indent=1))
            return 0
        journal = diag.RunJournal(output, plan, resume=args.resume)
        reason = 'complete'
        failure_streak = 0
        try:
            journal.summary('initializing', diag.ledger_summary(ledger))
            retrieval_handle = (journal.output / 'retrieval.jsonl').open('a', encoding='utf-8')
            with retrieval_handle as retrieval, (journal.output / 'trace.jsonl').open('a', encoding='utf-8') as trace:
                for item in plan['schedule']:
                    qid = item['question_id']
                    if (qid, 'agent') in journal.terminals:
                        continue
                    start = journal.start(qid, 'agent')
                    row = next(r for r in rows if r['question_id'] == qid)
                    paths = paths_by_qid[qid]
                    block, memory_ids, retrieval_record = '', [], {'question_id': qid,
                        'arm': args.arm, 'pool_sha256': args.pool_sha256, 'pool_loaded': pool is not None,
                        'queried': pool is not None, 'returned': 0, 'memory_ids': [], 'scores': [],
                        'injected_chars': 0, 'injected_sha256': None}
                    if pool is not None:
                        from memory_pipeline.injection import build_memory_block
                        query = {'question_id': qid, 'question': row['question'], 'images': row['images'],
                                 'available_tools': plan['available_tool_versions'],
                                 'protocol_sha256': protocol}
                        hits = pool.search(query, top_k=args.top_k, min_score=args.min_score,
                                           include_failures=args.arm == 'r3',
                                           summary_mode=args.arm in ('r2', 'r3'))
                        block, audit = build_memory_block(hits, max_chars=args.memory_max_chars)
                        memory_ids = [hit['memory_id'] for hit in hits]
                        retrieval_record.update(audit, returned=len(hits), memory_ids=memory_ids,
                                                scores=[round(hit['score'], 6) for hit in hits])
                        diag.durable_line(retrieval, retrieval_record)
                    with open(os.devnull, 'w') as sink, redirect_stdout(sink), redirect_stderr(sink):
                        result = run_arm(runtime, ledger, profile, row, paths, args.arm, start,
                                         journal.manifest['run_id'], args, trace,
                                         memory=block or None, memory_ids=memory_ids)
                    journal.finish(result)
                    money = diag.ledger_summary(ledger)
                    print(json.dumps({'qid': qid, 'arm': args.arm, 'status': result['status'],
                                      'answer': result.get('answer_letter'),
                                      'model_calls': result.get('actual_model_calls'),
                                      'tool_calls': result.get('actual_tool_attempts'),
                                      'memory': len(memory_ids), **money}), flush=True)
                    journal.summary('running', money)
                    failed = (result.get('status') in ('model_error', 'tool_error')
                              and (result.get('actual_tool_attempts') or 0) == 0)
                    failure_streak = failure_streak + 1 if failed else 0
                    if result.get('stop_run'):
                        reason = result.get('stop_reason') or 'budget'
                        break
                    if failure_streak >= args.max_consecutive_failures:
                        # A dead credential or upstream outage must not consume the
                        # whole denominator; the run is left resumable instead.
                        reason = 'consecutive_failure_stop'
                        print(json.dumps({'stop': reason, 'streak': failure_streak}), flush=True)
                        break
        except BaseException:
            journal.summary('run_error', diag.ledger_summary(ledger))
            raise
        finally:
            journal.close()
        final = journal.summary(reason, diag.ledger_summary(ledger))
        print(json.dumps({'stop_reason': final['stop_reason'],
                          'terminals': final['terminal_count'],
                          'planned': final['planned_question_count'],
                          **diag.ledger_summary(ledger)}), flush=True)
        return 0 if final['stop_reason'] == 'complete' else 2


if __name__ == '__main__':
    raise SystemExit(main())
