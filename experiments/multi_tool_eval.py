"""Five-question matched direct/multiple-tool Agent execution smoke; no labels.

Original classifier and report tools are available; segmentation is optional.
Availability does not force selection. Each arm has a fresh thread, the same
1024-output model and 4-model/2-tool limits, and the original two-stage prompts.
All API calls use the existing baseline ledger, with two prepaid 512-token blocks.
Reports reach the Agent intact but only hashes/lengths enter trace/result files.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diagnostic_eval as diag
import length_cap_followup as previous
import tool_variants as variants

QUESTION_COUNT = 5
MAX_OUTPUT_TOKENS = 1024
KIND = 'first5_matched_direct_vs_available_original_classifier_report_agent'


def validate_parameters(tool, kind, params, allowed_images):
    """Apply the actual advertised schema plus strict image/organ authorization."""
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
        if (type(organs) is not list or not organs or any(type(x) is not str or x not in valid for x in organs)
                or len(set(organs)) != len(organs)):
            raise ValueError('Segmentation organs must be distinct valid advertised names')
    if hasattr(schema, 'model_validate'):
        schema.model_validate(params)
    else:
        schema.parse_obj(params)
    return dict(params, image_path=str(image)), image


class TrackedTool:
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
                counts['repeated'] += 1; ctx['repeated_tool_calls'] += 1
                ctx['issues'].add('repeated_tool_call')
            detail.update(arguments_sha256=fingerprint, argument_keys=sorted(clean), repeated=repeated,
                          image_sha256=diag.smoke.classifier_utils.sha256_file(image))
            ctx['actual_tool_attempts'] += 1; counts['attempted'] += 1
            result = self.wrapped.invoke(clean)
            checked = variants.validate_observation(self.kind, result,
                **({'artifact_dir': self.wrapped.temp_dir} if self.kind == 'segmentation' else {}))
            detail.update(output_contract=checked, output_summary=diag.smoke.summarize(result), execution='returned')
            if checked['valid']:
                ctx['validated_tool_returns'] += 1; counts['validated_returns'] += 1
            else:
                ctx['failed_tool_returns'] += 1; counts['failed_returns'] += 1
                ctx['issues'].add('tool_failed_or_invalid')
            # The actual upstream result, including report prose, remains available to the Agent.
            return result
        except Exception as exc:
            counts['exceptions'] += 1; ctx['issues'].add('tool_exception')
            detail['error_type'] = type(exc).__name__
            raise
        finally:
            detail['elapsed_ms'] = round((time.monotonic() - began) * 1000)
            diag.event(ctx, **detail)


def run_arm(runtime, guard, row, paths, arm, start, run_id, args, trace, *, limit_errors=(),
            message_builder=diag.initial_messages):
    """Same two-stage orchestration, replacing only the single-tool assumption."""
    ctx = {'question_id': row['question_id'], 'arm': arm, 'thread_id': start['thread_id'], 'run_id': run_id,
        'phase': 0, 'issues': set(), 'usage_records': [], 'ledger_settlements': [], 'actual_model_calls': 0,
        'actual_tool_attempts': 0, 'validated_tool_returns': 0, 'failed_tool_returns': 0, 'repeated_tool_calls': 0,
        'allowed_images': set(paths), 'tool_fingerprints': set(), 'stop_run': False, 'last_finish_reason': None,
        'allowed_tool_names': set(runtime.tools) if arm == 'agent' else set(),
        'tool_counts': {name: dict(requested=0, attempted=0, validated_returns=0, failed_returns=0,
                                  exceptions=0, repeated=0) for name in runtime.tools}}
    ctx['trace'] = diag.TaggedTrace(trace, ctx)
    ctx['budget'] = diag.smoke.CaseBudget(diag.MAX_TOOL_CALLS, diag.MAX_MODEL_CALLS, args.max_case_seconds, ctx['trace'])
    ctx['budget'].case_hash = diag.hash_value(row['question_id']); ctx['budget'].thread_id = start['thread_id']
    report = {'question_id': row['question_id'], 'arm': arm, 'thread_id': start['thread_id'],
        'answer_letter': None, 'final_content_summary': None, 'phase_outcomes': [],
        'available_tool_names': sorted(runtime.tools) if arm == 'agent' else [],
        'clinical_evidence': 'unknown', 'step_credit': None, 'tools_forced': False}
    began, final = time.monotonic(), None
    try:
        messages = message_builder(runtime, row, paths, args.image_detail, arm)
        if arm == 'agent':
            agent = runtime.Agent(runtime.model, tools=list(runtime.tools.values()), checkpointer=runtime.MemorySaver(),
                                  system_prompt=runtime.agent_system, log_tools=False)
            agent.model = diag.DiagnosticModel(agent.model, guard, ctx, limit_errors)
            agent.tools = {name: TrackedTool(tool, runtime.tool_provenance[name], ctx)
                           for name, tool in runtime.tools.items()}
        else:
            guarded = diag.DiagnosticModel(runtime.model, guard, ctx, limit_errors)
            history = [runtime.SystemMessage(content=runtime.direct_system)]
        for phase, batch in enumerate((messages, [runtime.HumanMessage(content=diag.smoke.FOLLOWUP)]), 1):
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
                                diag.event(ctx, node='tool_message', tool_call_id=getattr(message, 'tool_call_id', None),
                                    tool_name=getattr(message, 'name', None),
                                    observation_summary=diag.smoke.summarize(getattr(message, 'content', '')),
                                    clinical_evidence='unknown', step_credit=None)
            report['phase_outcomes'].append({'phase': phase, 'finish_reason': ctx['last_finish_reason'],
                'content_summary': diag.smoke.summarize(final), 'strict_answer_letter': diag.smoke.answer_letter(final)})
        report['answer_letter'] = diag.smoke.answer_letter(final)
        report['final_content_summary'] = diag.smoke.summarize(final)
        report['status'] = 'completed' if report['answer_letter'] else 'invalid_answer'
        if report['answer_letter'] is None:
            ctx['issues'].add('invalid_answer')
    except diag.MonetaryStop:
        report['status'] = ctx['money_status']
    except diag.smoke.BudgetExceeded as exc:
        report.update(status='case_budget_exceeded', error_type=type(exc).__name__)
        ctx['issues'].add('case_call_or_time_limit')
    except Exception as exc:
        report.update(status='tool_error' if 'tool_exception' in ctx['issues'] else
                      'model_error' if 'model_exception' in ctx['issues'] else 'failed', error_type=type(exc).__name__)
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
        ledger_settlements=ctx['ledger_settlements'], stop_run=ctx['stop_run'], elapsed_seconds=time.monotonic() - began,
        tool_counts=ctx['tool_counts'], selected_tool_names=sorted(name for name, count in ctx['tool_counts'].items() if count['attempted']),
        all_available_tools_executed=(arm == 'agent' and all(c['attempted'] > 0 for c in ctx['tool_counts'].values())),
        all_available_tools_validated=(arm == 'agent' and all(c['validated_returns'] > 0 for c in ctx['tool_counts'].values())))
    report.update(api_error=ctx.get('api_error', False), api_error_type=ctx.get('api_error_type'),
                  stop_reason=ctx.get('stop_reason', 'budget' if ctx['stop_run'] else None))
    report['observed_usage_sum'], report['usage_complete'] = diag.smoke.aggregate_usage(ctx['usage_records'], ctx['actual_model_calls'])
    return report


def build_runtime(repo, args, key, prompt, temporary_artifacts):
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
    from langgraph.checkpoint.memory import MemorySaver
    tools, provenance = {}, {}
    factories = [variants.create_classifier_tool(repo, checkpoint=args.classifier_checkpoint, device=args.device, mode='original'),
                 variants.create_report_tool(repo, cache_dir=args.report_cache, device=args.device, mode='original')]
    if args.segmentation_checkpoint is not None:
        factories.append(variants.create_segmentation_tool(repo, checkpoint=args.segmentation_checkpoint,
            device=args.device, temp_dir=temporary_artifacts / 'segmentation'))
    for tool, recorded in factories:
        if tool.name in tools:
            raise ValueError('Duplicate tool name')
        tools[tool.name], provenance[tool.name] = tool, recorded
    Agent = diag.smoke.module_from_file('_multi_official_agent', repo / 'medrax/agent/agent.py').Agent
    model = ChatOpenAI(model=diag.MODEL, base_url=args.base_url, api_key=key, temperature=0.2, top_p=0.95,
                       max_tokens=MAX_OUTPUT_TOKENS, max_retries=0, timeout=args.request_timeout_seconds)
    return SimpleNamespace(model=model, tools=tools, tool_provenance=provenance, Agent=Agent,
        MemorySaver=MemorySaver, HumanMessage=HumanMessage, SystemMessage=SystemMessage,
        agent_system=prompt, direct_system=prompt.splitlines()[0].strip())


def build_plan(baseline, input_path, args, guard, prompt, tool_provenance):
    base = baseline['plan']
    if guard.policy_snapshot() != base['monetary_policy']:
        raise ValueError('Monetary policy differs from the original shared ledger')
    current = diag.build_plan(baseline['rows'], input_path, args.images_root, args.repo,
                              args, guard.policy_snapshot(), prompt)
    for field in ('source_sha256', 'package_versions', 'prompts', 'source', 'records', 'input_sha256'):
        if current[field] != base[field]:
            raise ValueError('Original source, package, prompt, input or image differs from baseline')
    kinds = {p['kind'] for p in tool_provenance.values()}
    if kinds not in ({'classification', 'report'}, {'classification', 'report', 'segmentation'}):
        raise ValueError('This phase requires classifier and report, with optional segmentation')
    if any(p.get('mode') != 'original' for p in tool_provenance.values()):
        raise ValueError('Only original tool descriptions and generation parameters are allowed')
    plan = deepcopy(current)
    ids = current['question_ids'][:QUESTION_COUNT]
    plan.update(kind=KIND, planned_question_count=QUESTION_COUNT, question_ids=ids,
        records=current['records'][:QUESTION_COUNT], selection_sha256=diag.hash_value(current['records'][:QUESTION_COUNT]),
        schedule=[x for x in base['schedule'] if x['question_id'] in ids], max_output_tokens=MAX_OUTPUT_TOKENS,
        baseline=baseline['provenance'], tool_registry=tool_provenance, available_tool_names=sorted(tool_provenance),
        chunked_budget_policy=guard.chunk_policy_snapshot(),
        selection={'rule': 'first_5_in_original_input_order', 'uses_reference_labels': False,
                   'uses_correctness': False, 'uses_truncation': False},
        tool_selection={'policy': 'model_decides', 'force_each_tool': False,
                        'availability_is_not_execution': True, 'max_total_tool_calls_per_arm': diag.MAX_TOOL_CALLS},
        is_complete_paper_toolset=False, protocol_repair_enabled=False, cross_case_memory_enabled=False)
    files = {'multi_tool_eval.py': Path(__file__), 'tool_variants.py': Path(variants.__file__),
             'report_smoke.py': Path(variants.report_audit.__file__),
             'length_cap_followup.py': Path(previous.__file__),
             'chunked_budget.py': Path(__file__).with_name('chunked_budget.py'),
             'official_report.py': args.repo / 'medrax/tools/report_generation.py'}
    if 'segmentation' in kinds:
        files.update(segmentation_smoke=Path(__file__).with_name('segmentation_smoke.py'),
                     official_segmentation=args.repo / 'medrax/tools/segmentation.py')
    plan['source_sha256'].update({name: diag.smoke.classifier_utils.sha256_file(path) for name, path in files.items()})
    plan['protocol_deviations'] = [text.replace('Direct is two-stage with 512 output tokens', 'Direct is two-stage with 1024 output tokens')
        for text in plan['protocol_deviations'] if not text.startswith('Agent uses only the official DenseNet classifier')]
    plan['protocol_deviations'] += [
        'Original classifier and report tools are available; original segmentation is included only if explicitly configured.',
        'This is an initial multiple-tool execution smoke, not the complete six-tool paper Agent or validation-set benchmark.',
        'The model decides which tools to use; a tool being registered does not establish that it was selected or executed.',
        'Original classifier probability wording and original report no-EOS generation remain unchanged in this phase.',
        'Tool results reach the Agent unchanged, while logs retain safe hashes, lengths and output-contract checks.',
        'Both arms retain 4 model calls and 2 total tool calls; 1024 output tokens use two original ledger blocks per API request.',
    ]
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-run', 'input', 'output', 'ledger', 'classifier-checkpoint', 'report-cache'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--segmentation-checkpoint', type=Path)
    parser.add_argument('--api-key-stdin', action='store_true')
    parser.add_argument('--resume', action='store_true')
    options = parser.parse_args(argv)
    journal, key = None, ''
    try:
        if options.output.exists() and not options.resume:
            raise ValueError('Output already exists')
        baseline = previous.load_completed_baseline(options.baseline_run, options.input)
        args = previous.frozen_settings(baseline, ledger_path=options.ledger)
        args.classifier_checkpoint = options.classifier_checkpoint
        args.report_cache = options.report_cache
        args.segmentation_checkpoint = options.segmentation_checkpoint
        key = sys.stdin.readline().strip() if options.api_key_stdin else os.environ.get('OPENAI_API_KEY', '')
        if not key:
            raise ValueError('API key absent')
        os.environ['OPENAI_API_KEY'] = key
        from money_guard import MoneyGuard, BudgetExceeded
        from chunked_budget import ChunkedBudgetGuard
        utils = diag.smoke.module_from_file('_multi_official_utils', args.repo / 'medrax/utils/utils.py')
        prompt = utils.load_prompts_from_file(str(args.repo / 'medrax/docs/system_prompts.txt'))['MEDICAL_ASSISTANT']
        with MoneyGuard(args.ledger, budget_cny='100', model=diag.MODEL) as shared, \
                tempfile.TemporaryDirectory(prefix='medrax-tool-init-') as temporary:
            guard = ChunkedBudgetGuard(shared, max_output_tokens=MAX_OUTPUT_TOKENS)
            with open(os.devnull, 'w') as sink, redirect_stdout(sink), redirect_stderr(sink):
                runtime = build_runtime(args.repo, args, key, prompt, Path(temporary))
            plan = build_plan(baseline, options.input, args, guard, prompt, runtime.tool_provenance)
            journal = diag.RunJournal(options.output, plan, resume=options.resume)
            for name, tool in runtime.tools.items():
                if runtime.tool_provenance[name]['kind'] == 'segmentation':
                    tool.temp_dir = journal.output / 'private_segmentation_artifacts'
                    tool.temp_dir.mkdir(exist_ok=True)
            try:
                journal.summary('initializing', diag.ledger_summary(guard))
                with (journal.output / 'trace.jsonl').open('a', encoding='utf-8') as trace:
                    report = diag.execute_schedule(journal, runtime, guard, baseline['rows'][:QUESTION_COUNT],
                        args.images_root, args, trace, limit_errors=(BudgetExceeded,), runner=run_arm)
                return 0 if report['stop_reason'] == 'complete' else 2
            except BaseException:
                try:
                    money = diag.ledger_summary(guard)
                except Exception as exc:
                    money = {'remaining_cny': None, 'conservative_spent_cny': None, 'error_type': type(exc).__name__}
                journal.summary('run_error', money)
                raise
    except BaseException as exc:
        print(json.dumps({'status': 'multi_tool_error', 'error_type': type(exc).__name__}), file=sys.stderr, flush=True)
        return 1
    finally:
        if journal is not None:
            journal.close()
        key = ''


if __name__ == '__main__':
    raise SystemExit(main())
