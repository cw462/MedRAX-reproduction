"""Matched two-stage direct/classifier-Agent diagnostics; never reads labels.

Every model request requires a shared monetary guard. Defaults are intentionally
fixed: gpt-4o-2024-11-20, 512 output tokens, 4 model / 2 tool calls, zero retries.
CLI requires exactly 50 preselected inference-only rows. Resume never repeats a
started (question_id, arm), including work interrupted before its terminal log.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import mimetypes
import os
from pathlib import Path
import random
import sys
import time
from types import SimpleNamespace
from urllib.parse import urlsplit
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import single_tool_agent_smoke as smoke

MODEL = 'gpt-4o-2024-11-20'
MAX_OUTPUT_TOKENS = 512
MAX_INPUT_TOKENS = 128000
MAX_MODEL_CALLS = 4
MAX_TOOL_CALLS = 2
PLANNED_QUESTIONS = 50
API_ERROR_TYPES = frozenset({
    'APIError', 'APIStatusError', 'APITimeoutError', 'APIConnectionError', 'AuthenticationError',
    'PermissionDeniedError', 'RateLimitError', 'InternalServerError', 'ServiceUnavailableError',
    'BadRequestError', 'UnprocessableEntityError', 'NotFoundError', 'TimeoutError', 'ConnectionError',
    'ConnectionResetError', 'ConnectionAbortedError', 'BrokenPipeError', 'OSError', 'HTTPError',
    'HTTPStatusError', 'TransportError', 'ModelIdentityMismatch',
})
IMMEDIATE_API_ERRORS = frozenset({'AuthenticationError', 'PermissionDeniedError', 'ModelIdentityMismatch'})
COMMON_PREFIX = ('Answer this question correctly using chain of thought reasoning and '
                 'carefully evaluating choices. Solve using your own vision and reasoning')
DIRECT_PREFIX = COMMON_PREFIX + '.'
AGENT_PREFIX = COMMON_PREFIX + (' and then use tools to complement your reasoning. '
                                'Trust your own judgement over any tools.')


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def hash_value(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def durable_line(handle, value):
    handle.write(canonical(value).decode())
    handle.flush()
    try:
        os.fsync(handle.fileno())
    except (AttributeError, io.UnsupportedOperation):
        pass  # In-memory test streams only; real I/O failures must propagate.


def load_rows(path, planned_count=PLANNED_QUESTIONS):
    def no_duplicate_keys(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError('Duplicate input JSON field')
            out[key] = value
        return out
    rows, seen = [], set()
    with Path(path).open(encoding='utf-8-sig') as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line, object_pairs_hook=no_duplicate_keys)
            if type(row) is not dict or set(row) != {'question_id', 'question', 'images'}:
                raise ValueError('Inference input must contain exactly question_id, question, images')
            if type(row['question_id']) not in (str, int) or not str(row['question_id']).strip():
                raise ValueError('Invalid question_id')
            if type(row['question']) is not str or not row['question'].strip():
                raise ValueError('Invalid question text')
            if type(row['images']) is not list or any(type(x) is not str or not x for x in row['images']):
                raise ValueError('Invalid image paths')
            row['question_id'] = str(row['question_id'])
            if row['question_id'] in seen:
                raise ValueError('Duplicate question_id')
            seen.add(row['question_id']); rows.append(row)
    if len(rows) != planned_count:
        raise ValueError(f'Expected the complete preselected {planned_count}-question input')
    return rows


def inspect_input(row, root):
    """Preserve missing/bad-image questions in the planned denominator."""
    issues, images, paths = [], [], []
    if not row['images']:
        issues.append('missing_image')
    if len(row['images']) > 4 or len(row['question']) > 32000:
        issues.append('input_size_limit')
    total_bytes = 0
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
            try:
                entry.update(sha256=smoke.classifier_utils.sha256_file(path), bytes=path.stat().st_size)
                total_bytes += entry['bytes']; paths.append(path)
            except OSError:
                issues.append('unreadable_image')
        images.append(entry)
    if total_bytes > 20 * 1024 * 1024:
        issues.append('input_size_limit')
    return {'question_id': row['question_id'], 'question_sha256': hash_value(row['question']),
            'images': images, 'preflight_issues': sorted(set(issues))}, paths


def make_schedule(question_ids, arms=('direct', 'agent'), seed=None):
    if not arms or len(set(arms)) != len(arms) or any(x not in ('direct', 'agent') for x in arms):
        raise ValueError('Arms must be unique direct and/or agent')
    order_bits = [i % 2 for i in range(len(question_ids))]
    if seed is not None:
        random.Random(seed).shuffle(order_bits)
    schedule = []
    for qid, bit in zip(question_ids, order_bits):
        ordered = arms if bit == 0 else tuple(reversed(arms))
        schedule.extend({'question_id': qid, 'arm': arm} for arm in ordered)
    return schedule


def build_plan(rows, input_path, root, repo, args, policy, official_prompt):
    records = [inspect_input(row, root)[0] for row in rows]
    source_files = {'diagnostic_eval.py': Path(__file__), 'single_tool_agent_smoke.py': Path(smoke.__file__),
                    'classifier_smoke.py': Path(smoke.classifier_utils.__file__),
                    'money_guard.py': Path(__file__).resolve().parent / 'money_guard.py',
                    'r0.py': Path(__file__).resolve().parents[1] / 'runner/r0.py',
                    'official_agent.py': repo / 'medrax/agent/agent.py',
                    'official_classifier.py': repo / 'medrax/tools/classification.py',
                    'official_utils.py': repo / 'medrax/utils/utils.py'}
    versions = {}
    for package in ('langgraph', 'langchain-openai', 'openai', 'langchain-core', 'python-dotenv'):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    direct_system = official_prompt.splitlines()[0].strip()
    if not direct_system:
        raise ValueError('Official system prompt is empty')
    plan = {
        'schema_version': 1, 'kind': 'matched_diagnostic_direct_vs_restricted_classifier_agent',
        'planned_question_count': len(rows), 'question_ids': [r['question_id'] for r in rows],
        'arms': list(args.arms), 'schedule': make_schedule([r['question_id'] for r in rows], args.arms, args.arm_order_seed),
        'arm_order_seed': args.arm_order_seed, 'input_sha256': smoke.classifier_utils.sha256_file(input_path),
        'selection_sha256': hash_value(records), 'records': records, 'model': MODEL,
        'max_output_tokens': MAX_OUTPUT_TOKENS, 'max_model_calls': MAX_MODEL_CALLS, 'max_tool_calls': MAX_TOOL_CALLS,
        'monetary_reservation_input_tokens': MAX_INPUT_TOKENS, 'provider_retries': 0,
        'temperature': 0.2, 'top_p': 0.95, 'image_detail': args.image_detail,
        'request_timeout_seconds': args.request_timeout_seconds, 'max_case_seconds': args.max_case_seconds,
        'recursion_limit': 12, 'device': args.device, 'tool_model_name': smoke.classifier_utils.MODEL_NAME,
        'provider_base_url': args.base_url, 'monetary_policy': policy,
        'monetary_ledger_path': str(args.ledger.resolve()),
        'api_failure_policy': {'consecutive_arm_limit': 3, 'immediate_error_types': sorted(IMMEDIATE_API_ERRORS)},
        'images_root': str(root), 'upstream_repo_path': str(repo),
        'source_sha256': {name: smoke.classifier_utils.sha256_file(path) for name, path in source_files.items()},
        'source': smoke.classifier_utils.git_info(repo), 'package_versions': versions,
        'prompts': {'agent_system': official_prompt, 'direct_system': direct_system,
                    'agent_first_prefix': AGENT_PREFIX, 'direct_first_prefix': DIRECT_PREFIX, 'followup': smoke.FOLLOWUP},
        'protocol_deviations': [
            'Matched diagnostic direct uses official system first line and the shared reasoning prefix, with tool instructions removed.',
            'Direct is two-stage with 512 output tokens, not the author quickstart single-stage baseline.',
            'Agent uses only the official DenseNet classifier, with the adapted first user prompt from single_tool_agent_smoke.',
            'Both arms use the same question, image data URLs, local paths, model, sampling settings and letter-only second phase.',
            'Each question and arm has a fresh thread; this differs from the author notebook shared case threads.',
            'Call/output limits can truncate behavior; model snapshot provenance cannot be proved through a proxy.',
            'No labels, scoring, cross-case memory or automatic retries are used.',
            'Started arms interrupted before a terminal record are never repeated on resume.',
        ]}
    return plan


class RunJournal:
    def __init__(self, output, plan, *, resume=False):
        self.output, self.plan = Path(output).resolve(), plan
        self.plan_hash = hash_value(plan)
        self.starts, self.terminals = {}, {}
        self.allowed = {(r['question_id'], r['arm']) for r in plan['schedule']}
        if resume:
            manifest = json.loads((self.output / 'manifest.json').read_text(encoding='utf-8'))
            if manifest.get('plan_sha256') != self.plan_hash or hash_value(manifest.get('plan')) != self.plan_hash:
                raise ValueError('Resume plan/configuration/input/source/monetary policy mismatch')
            self.manifest = manifest
            raw = (self.output / 'results.jsonl').read_text(encoding='utf-8')
            if raw and not raw.endswith('\n'):
                raise ValueError('Incomplete journal tail; refusing unsafe automatic replay')
            for line in raw.splitlines():
                self._accept(json.loads(line))
        else:
            self.output.mkdir(parents=True, exist_ok=False)
            (self.output / '.gitignore').write_text('*\n', encoding='utf-8')
            self.manifest = {'run_id': str(uuid.uuid4()), 'created_utc': utc_now(),
                             'plan_sha256': self.plan_hash, 'plan': plan}
            with (self.output / 'manifest.json').open('x', encoding='utf-8') as handle:
                durable_line(handle, self.manifest)
            (self.output / 'results.jsonl').touch(exist_ok=False)
        self.handle = (self.output / 'results.jsonl').open('a', encoding='utf-8')
        for key, start in list(self.starts.items()):
            if key not in self.terminals:
                self.finish({'question_id': key[0], 'arm': key[1], 'thread_id': start['thread_id'],
                    'status': 'interrupted_no_retry', 'answer_letter': None, 'issue_tags': ['interrupted_started_arm'],
                    'actual_model_calls': None, 'actual_tool_attempts': None, 'validated_tool_returns': None,
                    'observed_usage_sum': None, 'usage_complete': False, 'final_finish_reason': None,
                    'stop_run': False})

    def _accept(self, record):
        key = (record.get('question_id'), record.get('arm'))
        if key not in self.allowed:
            raise ValueError('Journal includes an unplanned question/arm')
        kind = record.get('record_type')
        if kind == 'started':
            if key in self.starts:
                raise ValueError('Duplicate started question/arm')
            self.starts[key] = record
        elif kind == 'terminal':
            if key not in self.starts or key in self.terminals or record.get('thread_id') != self.starts[key].get('thread_id'):
                raise ValueError('Duplicate or unpaired terminal record')
            self.terminals[key] = record
        else:
            raise ValueError('Unknown journal record type')

    def start(self, qid, arm):
        record = {'record_type': 'started', 'question_id': qid, 'arm': arm,
                  'thread_id': str(uuid.uuid4()), 'started_utc': utc_now()}
        self._accept(record); durable_line(self.handle, record)
        return record

    def finish(self, result):
        record = dict(result, record_type='terminal', finished_utc=utc_now())
        self._accept(record); durable_line(self.handle, record)
        return record

    def summary(self, reason='running', ledger=None):
        results = []
        for item in self.plan['schedule']:
            key = (item['question_id'], item['arm'])
            result = self.terminals.get(key)
            if result is None:
                result = dict(item, status='not_run_' + reason, answer_letter=None, issue_tags=['not_run'])
            results.append(result)
        report = {'run_id': self.manifest['run_id'], 'plan_sha256': self.plan_hash,
                  'planned_question_count': self.plan['planned_question_count'],
                  'planned_arm_results': len(self.plan['schedule']), 'terminal_count': len(self.terminals),
                  'stop_reason': reason, 'ledger': ledger, 'question_results': results,
                  'clinical_correctness_verified': False, 'updated_utc': utc_now()}
        temp = self.output / 'summary.json.tmp'
        with temp.open('w', encoding='utf-8') as handle:
            durable_line(handle, report)
        os.replace(temp, self.output / 'summary.json')
        return report

    def close(self):
        self.handle.close()


class TaggedTrace:
    def __init__(self, target, ctx):
        self.target, self.ctx = target, ctx

    def write(self, line):
        value = json.loads(line)
        value.update(question_id=self.ctx['question_id'], arm=self.ctx['arm'],
                     thread_id=self.ctx['thread_id'], phase=self.ctx['phase'])
        self.target.write(canonical(value).decode())

    def flush(self):
        self.target.flush()


class MonetaryStop(RuntimeError):
    pass


class ModelIdentityMismatch(RuntimeError):
    pass


def event(ctx, **fields):
    smoke.write_line(ctx['trace'], fields)


class DiagnosticModel:
    def __init__(self, wrapped, guard, ctx, limit_errors=()):
        if guard is None or not callable(getattr(guard, 'reserve', None)) or not callable(getattr(guard, 'settle', None)):
            raise ValueError('A shared monetary reserve/settle guard is mandatory')
        self.wrapped, self.guard, self.ctx, self.limit_errors = wrapped, guard, ctx, limit_errors

    def invoke(self, *args, **kwargs):
        ctx = self.ctx
        ctx['budget'].reserve('model', 'llm')
        ordinal = ctx['budget'].counts['model']
        request_id = f"{ctx['run_id']}:{ctx['thread_id']}:{ordinal}"
        metadata = {'request_id': request_id, 'question_id': ctx['question_id'], 'arm': ctx['arm'],
                    'phase': ctx['phase'], 'model_call': ordinal, 'model': MODEL}
        try:
            reservation = self.guard.reserve(metadata=metadata, request_id=request_id, model=MODEL,
                                             max_input_tokens=MAX_INPUT_TOKENS, max_output_tokens=MAX_OUTPUT_TOKENS)
        except Exception as exc:
            ctx['stop_run'] = True
            ctx['money_status'] = 'monetary_budget_exceeded' if isinstance(exc, self.limit_errors) else 'monetary_guard_error'
            ctx['issues'].add(ctx['money_status'])
            event(ctx, node='money_reserve', status='blocked', error_type=type(exc).__name__, model_call=ordinal)
            raise MonetaryStop(ctx['money_status']) from exc
        started, response, error_type, usage = time.monotonic(), None, None, None
        ctx['actual_model_calls'] += 1
        ctx['returned_model'] = None
        ctx['last_finish_reason'] = None
        try:
            response = self.wrapped.invoke(*args, **kwargs)
            usage = smoke.numeric_usage(response)
            if usage is not None:
                ctx['usage_records'].append(usage)
            if usage is None or not all(k in usage for k in ('input_tokens', 'output_tokens', 'total_tokens')):
                ctx['issues'].add('token_usage_incomplete')
            meta = getattr(response, 'response_metadata', None) or {}
            finish = meta.get('finish_reason')
            ctx['last_finish_reason'] = finish
            returned_model = meta.get('model_name')
            ctx['returned_model'] = returned_model
            if returned_model and returned_model != MODEL:
                ctx['issues'].add('model_identity_mismatch')
                raise ModelIdentityMismatch('Returned model differs from the frozen diagnostic model')
            if not returned_model:
                ctx['issues'].add('model_identity_unreported')
            if finish == 'length':
                ctx['issues'].add('model_output_truncated')
            elif finish is None:
                ctx['issues'].add('finish_reason_missing')
            tool_calls = []
            for call in (getattr(response, 'tool_calls', None) or []):
                name = call.get('name')
                if name not in ctx['allowed_tool_names']:
                    ctx['issues'].add('unknown_tool_requested')
                tool_calls.append({'id': call.get('id'), 'name': name,
                    'argument_keys': sorted(call.get('args', {})) if isinstance(call.get('args'), dict) else []})
            if getattr(response, 'invalid_tool_calls', None):
                ctx['issues'].add('invalid_tool_call_schema')
            event(ctx, node='model', model_call=ordinal, request_id=request_id,
                  usage=usage, finish_reason=finish, returned_model=meta.get('model_name'),
                  tool_calls=tool_calls, content_summary=smoke.summarize(getattr(response, 'content', '')))
            return response
        except BaseException as exc:
            error_type = type(exc).__name__
            ctx['issues'].add('model_exception')
            error_names = {cls.__name__ for cls in type(exc).__mro__}
            if error_names & API_ERROR_TYPES:
                ctx['api_error'] = True; ctx['api_error_type'] = error_type
            if error_names & IMMEDIATE_API_ERRORS:
                ctx['stop_run'] = True; ctx['stop_reason'] = 'api_error'
                ctx['issues'].add('immediate_api_failure_stop')
            event(ctx, node='model', model_call=ordinal, request_id=request_id,
                  status='exception', error_type=error_type, usage=usage,
                  returned_model=ctx.get('returned_model'), finish_reason=ctx.get('last_finish_reason'))
            raise
        finally:
            complete = usage is not None and all(k in usage for k in ('input_tokens', 'output_tokens')) and error_type is None
            billed_usage = {'prompt_tokens': usage['input_tokens'], 'completion_tokens': usage['output_tokens']} if complete else None
            try:
                settlement = self.guard.settle(reservation, usage=billed_usage,
                                               response_received=response is not None, error_type=error_type)
                ctx['ledger_settlements'].append(settlement)
                event(ctx, node='money_settle', model_call=ordinal, request_id=request_id,
                      settlement=settlement, elapsed_ms=round((time.monotonic() - started) * 1000))
            except Exception as exc:
                ctx['stop_run'] = True; ctx['money_status'] = 'monetary_guard_error'
                ctx['issues'].add('monetary_guard_error')
                recorded_settlement = getattr(exc, 'settlement', None)
                if isinstance(recorded_settlement, dict):
                    ctx['ledger_settlements'].append(recorded_settlement)
                event(ctx, node='money_settle', model_call=ordinal, status='failed',
                      error_type=type(exc).__name__, settlement=recorded_settlement)
                raise MonetaryStop('monetary_guard_error') from exc


class DiagnosticTool:
    def __init__(self, wrapped, ctx, labels):
        self.wrapped, self.ctx, self.labels = wrapped, ctx, labels

    def invoke(self, params):
        ctx = self.ctx; ctx['budget'].reserve('tool', self.wrapped.name)
        started = time.monotonic()
        details = {'node': 'tool', 'tool_name': self.wrapped.name, 'execution': 'exception'}
        try:
            if type(params) is not dict or set(params) != {'image_path'} or type(params['image_path']) is not str:
                ctx['issues'].add('invalid_tool_arguments'); raise ValueError('Invalid tool arguments')
            path = Path(params['image_path']).resolve()
            if path not in ctx['allowed_images']:
                ctx['issues'].add('unauthorized_tool_image'); raise ValueError('Tool image outside question')
            fingerprint = hash_value({'tool': self.wrapped.name, 'path': str(path)})
            repeated = fingerprint in ctx['tool_fingerprints']
            ctx['tool_fingerprints'].add(fingerprint)
            if repeated:
                ctx['repeated_tool_calls'] += 1; ctx['issues'].add('repeated_tool_call')
            details.update(argument_sha256=fingerprint, repeated=repeated,
                           image_sha256=smoke.classifier_utils.sha256_file(path))
            ctx['actual_tool_attempts'] += 1
            result = self.wrapped.invoke(params)
            try:
                details['scores'] = smoke.classifier_utils.validate_scores(result, self.labels)
                details['tool_analysis_status'] = 'completed'; ctx['validated_tool_returns'] += 1
            except (ValueError, TypeError, OverflowError):
                details['tool_analysis_status'] = 'failed_or_invalid'
                ctx['failed_tool_returns'] += 1; ctx['issues'].add('tool_failed_or_invalid')
            details.update(execution='returned', observation_summary=smoke.summarize(result), clinical_evidence='unknown')
            return result
        except Exception as exc:
            details['error_type'] = type(exc).__name__; ctx['issues'].add('tool_exception')
            raise
        finally:
            details['elapsed_ms'] = round((time.monotonic() - started) * 1000)
            event(ctx, **details)


def initial_messages(runtime, row, paths, detail, arm):
    # Start from the tested smoke's exact image/path formatting for both arms.
    messages = smoke.initial_messages(row, paths, detail)
    if arm == 'direct':
        content = messages[0].content
        text = content[0]['text']
        if not text.startswith(AGENT_PREFIX):
            raise ValueError('Smoke prompt changed; matched-arm adaptation requires review')
        content[0]['text'] = DIRECT_PREFIX + text[len(AGENT_PREFIX):]
    return messages


def run_arm(runtime, guard, row, paths, arm, start, run_id, args, trace, *, limit_errors=(),
            message_builder=initial_messages):
    ctx = {'question_id': row['question_id'], 'arm': arm, 'thread_id': start['thread_id'], 'run_id': run_id,
        'phase': 0, 'issues': set(), 'usage_records': [], 'ledger_settlements': [], 'actual_model_calls': 0,
        'actual_tool_attempts': 0, 'validated_tool_returns': 0, 'failed_tool_returns': 0, 'repeated_tool_calls': 0,
        'allowed_images': set(paths), 'tool_fingerprints': set(), 'stop_run': False, 'last_finish_reason': None,
        'allowed_tool_names': {runtime.tool.name} if arm == 'agent' else set()}
    ctx['trace'] = TaggedTrace(trace, ctx)
    ctx['budget'] = smoke.CaseBudget(MAX_TOOL_CALLS, MAX_MODEL_CALLS, args.max_case_seconds, ctx['trace'])
    ctx['budget'].case_hash = hash_value(row['question_id']); ctx['budget'].thread_id = start['thread_id']
    report = {'question_id': row['question_id'], 'arm': arm, 'thread_id': start['thread_id'],
              'answer_letter': None, 'final_content_summary': None, 'phase_outcomes': []}
    began, final = time.monotonic(), None
    try:
        messages = message_builder(runtime, row, paths, args.image_detail, arm)
        if arm == 'agent':
            agent = runtime.Agent(runtime.model, tools=[runtime.tool], checkpointer=runtime.MemorySaver(),
                                  system_prompt=runtime.agent_system, log_tools=False)
            agent.model = DiagnosticModel(agent.model, guard, ctx, limit_errors)
            agent.tools = {runtime.tool.name: DiagnosticTool(runtime.tool, ctx, runtime.tool.model.pathologies)}
        else:
            guarded = DiagnosticModel(runtime.model, guard, ctx, limit_errors)
            history = [runtime.SystemMessage(content=runtime.direct_system)]
        for phase, batch in enumerate((messages, [runtime.HumanMessage(content=smoke.FOLLOWUP)]), 1):
            ctx['phase'] = phase; final = None
            if arm == 'direct':
                history.extend(batch); response = guarded.invoke(history); history.append(response)
                final = response.content
            else:
                for step in agent.workflow.stream({'messages': batch},
                        {'configurable': {'thread_id': start['thread_id']}, 'recursion_limit': 12}):
                    for node, values in step.items():
                        for message in values.get('messages', []):
                            if node == 'process' and not (getattr(message, 'tool_calls', None) or []):
                                final = message.content
                            elif node == 'execute':
                                event(ctx, node='tool_message', tool_call_id=getattr(message, 'tool_call_id', None),
                                      tool_name=getattr(message, 'name', None),
                                      observation_summary=smoke.summarize(getattr(message, 'content', '')))
            report['phase_outcomes'].append({'phase': phase, 'finish_reason': ctx['last_finish_reason'],
                'content_summary': smoke.summarize(final), 'strict_answer_letter': smoke.answer_letter(final)})
        report['answer_letter'] = smoke.answer_letter(final)
        report['final_content_summary'] = smoke.summarize(final)
        report['status'] = 'completed' if report['answer_letter'] else 'invalid_answer'
        if report['answer_letter'] is None:
            ctx['issues'].add('invalid_answer')
    except MonetaryStop:
        report['status'] = ctx['money_status']
    except smoke.BudgetExceeded as exc:
        report.update(status='case_budget_exceeded', error_type=type(exc).__name__)
        ctx['issues'].add('case_call_or_time_limit')
    except Exception as exc:
        report.update(status='tool_error' if 'tool_exception' in ctx['issues'] else 'model_error' if 'model_exception' in ctx['issues'] else 'failed',
                      error_type=type(exc).__name__)
        ctx['issues'].add(report['status'])
    if arm == 'agent' and ctx['actual_tool_attempts'] == 0:
        ctx['issues'].add('no_tool_call')
    elif arm == 'agent' and ctx['validated_tool_returns'] == 0:
        ctx['issues'].add('no_valid_tool_return')
    report.update(issue_tags=sorted(ctx['issues']), call_counts=dict(ctx['budget'].counts),
        actual_model_calls=ctx['actual_model_calls'], actual_tool_attempts=ctx['actual_tool_attempts'],
        validated_tool_returns=ctx['validated_tool_returns'], failed_tool_returns=ctx['failed_tool_returns'],
        repeated_tool_calls=ctx['repeated_tool_calls'], tool_execution_verified=ctx['validated_tool_returns'] > 0,
        final_finish_reason=ctx['last_finish_reason'], usage_records=ctx['usage_records'],
        ledger_settlements=ctx['ledger_settlements'], stop_run=ctx['stop_run'], elapsed_seconds=time.monotonic() - began)
    report.update(api_error=ctx.get('api_error', False), api_error_type=ctx.get('api_error_type'),
                  stop_reason=ctx.get('stop_reason', 'budget' if ctx['stop_run'] else None))
    report['observed_usage_sum'], report['usage_complete'] = smoke.aggregate_usage(ctx['usage_records'], ctx['actual_model_calls'])
    return report


def build_runtime(repo, args, key, prompt):
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
    from langgraph.checkpoint.memory import MemorySaver
    tool, Agent = None, None
    if 'agent' in args.arms:
        Agent = smoke.module_from_file('_diagnostic_official_agent', repo / 'medrax/agent/agent.py').Agent
        cls = smoke.module_from_file('_diagnostic_official_classifier', repo / 'medrax/tools/classification.py').ChestXRayClassifierTool
        tool = cls(model_name=smoke.classifier_utils.MODEL_NAME, device=args.device)
    model = ChatOpenAI(model=MODEL, base_url=args.base_url, api_key=key, temperature=0.2, top_p=0.95,
                       max_tokens=MAX_OUTPUT_TOKENS, max_retries=0, timeout=args.request_timeout_seconds)
    return SimpleNamespace(model=model, tool=tool, Agent=Agent, MemorySaver=MemorySaver,
                           HumanMessage=HumanMessage, SystemMessage=SystemMessage,
                           agent_system=prompt, direct_system=prompt.splitlines()[0].strip())


def ledger_summary(guard):
    policy = guard.policy_snapshot()
    remaining = guard.remaining
    from decimal import Decimal
    cap = Decimal(str(policy.get('budget_cny', policy.get('cap_cny', '100'))))
    return {'remaining_cny': str(remaining), 'conservative_spent_cny': str(cap - remaining)}


def execute_schedule(journal, runtime, guard, rows, root, args, trace, *, limit_errors=(), runner=run_arm):
    lookup = {row['question_id']: row for row in rows}
    preflight = {r['question_id']: r for r in journal.plan['records']}
    ordinal = {qid: i + 1 for i, qid in enumerate(journal.plan['question_ids'])}
    reason = 'complete'
    failure_streak = 0
    for previous in journal.terminals.values():
        failure_streak = failure_streak + 1 if previous.get('api_error') else 0
        if previous.get('stop_reason') == 'api_error' or failure_streak >= 3:
            return journal.summary('api_error', ledger_summary(guard))
    journal.summary('running', ledger_summary(guard))
    for item in journal.plan['schedule']:
        qid, arm = item['question_id'], item['arm']
        if (qid, arm) in journal.terminals:
            continue
        start = journal.start(qid, arm)
        row = lookup[qid]
        current, paths = inspect_input(row, root)
        issues = current['preflight_issues']
        if current != preflight[qid]:
            issues = sorted(set(issues + ['input_changed_since_manifest']))
        if issues:
            result = {'question_id': qid, 'arm': arm, 'thread_id': start['thread_id'],
                'status': 'missing_image' if 'missing_image' in issues else 'invalid_input', 'answer_letter': None,
                'issue_tags': issues, 'actual_model_calls': 0, 'actual_tool_attempts': 0,
                'validated_tool_returns': 0, 'usage_complete': False, 'observed_usage_sum': None, 'stop_run': False}
        else:
            with open(os.devnull, 'w') as sink, redirect_stdout(sink), redirect_stderr(sink):
                result = runner(runtime, guard, row, paths, arm, start, journal.manifest['run_id'], args, trace,
                                limit_errors=limit_errors)
        failure_streak = failure_streak + 1 if result.get('api_error') else 0
        if failure_streak >= 3:
            result.update(stop_run=True, stop_reason='api_error')
            result['issue_tags'] = sorted(set(result['issue_tags']) | {'consecutive_api_failure_stop'})
        journal.finish(result)
        money = ledger_summary(guard)
        print(json.dumps({'progress': ordinal[qid], 'planned': journal.plan['planned_question_count'],
            'arm': arm, 'status': result['status'], 'model_calls': result.get('actual_model_calls'),
            'tool_calls': result.get('actual_tool_attempts'), **money}), flush=True)
        reason = (result.get('stop_reason') or 'budget') if result.get('stop_run') else 'running'
        journal.summary(reason, money)
        if result.get('stop_run'):
            break
    else:
        reason = 'complete'
    return journal.summary(reason, ledger_summary(guard))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'input', 'images-root', 'output', 'ledger'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--base-url', default=os.environ.get('OPENAI_BASE_URL', 'https://api.apiyi.com/v1'))
    parser.add_argument('--api-key-stdin', action='store_true')
    parser.add_argument('--arms', default='direct,agent', help='direct,agent or one of these arms')
    parser.add_argument('--arm-order-seed', type=int)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--device', default='cuda:0')
    parser.add_argument('--image-detail', choices=('auto', 'low', 'high'), default='auto')
    parser.add_argument('--max-case-seconds', type=float, default=180)
    parser.add_argument('--request-timeout-seconds', type=float, default=60)
    args = parser.parse_args(argv)
    args.arms = tuple(args.arms.split(','))
    make_schedule([], args.arms, args.arm_order_seed)
    import math
    if any(not math.isfinite(x) or x <= 0 for x in (args.max_case_seconds, args.request_timeout_seconds)):
        parser.error('Timeouts must be finite and positive')
    url = urlsplit(args.base_url)
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        parser.error('API base URL must use HTTPS without credentials/query/fragment')
    key = sys.stdin.readline().strip() if args.api_key_stdin else os.environ.get('OPENAI_API_KEY', '')
    if not key:
        parser.error('API key absent')
    os.environ['OPENAI_API_KEY'] = key
    repo, root = args.repo.resolve(), args.images_root.resolve()
    rows = load_rows(args.input)
    utils = smoke.module_from_file('_diagnostic_official_utils', repo / 'medrax/utils/utils.py')
    prompt = utils.load_prompts_from_file(str(repo / 'medrax/docs/system_prompts.txt'))['MEDICAL_ASSISTANT']
    # This import and locked guard are mandatory: there is no unbudgeted fallback.
    from money_guard import MoneyGuard, BudgetExceeded as MonetaryBudgetExceeded
    with MoneyGuard(args.ledger.resolve(), budget_cny='100', model=MODEL,
                    max_input_tokens=MAX_INPUT_TOKENS, max_output_tokens=MAX_OUTPUT_TOKENS) as guard:
        plan = build_plan(rows, args.input, root, repo, args, guard.policy_snapshot(), prompt)
        journal = RunJournal(args.output, plan, resume=args.resume)
        try:
            journal.summary('initializing', ledger_summary(guard))
            with open(os.devnull, 'w') as sink, redirect_stdout(sink), redirect_stderr(sink):
                runtime = build_runtime(repo, args, key, prompt)
            with (journal.output / 'trace.jsonl').open('a', encoding='utf-8') as trace:
                summary = execute_schedule(journal, runtime, guard, rows, root, args, trace,
                                           limit_errors=(MonetaryBudgetExceeded,))
            return 0 if summary['stop_reason'] == 'complete' else 2
        except BaseException as exc:
            journal.summary('run_error', ledger_summary(guard))
            print(json.dumps({'status': 'run_error', 'error_type': type(exc).__name__}), flush=True)
            return 1
        finally:
            journal.close(); key = ''


if __name__ == '__main__':
    raise SystemExit(main())
