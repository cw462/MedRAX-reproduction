"""Post-baseline 1024-token diagnostic variant, selected without reference labels.

Requires the 50-question, two-arm 512-token baseline to be complete. Select the
first <=10 questions in original input order with model_output_truncated in either
arm. Both arms are rerun with their original relative order and all other settings
fixed. No protocol repair is imported. Shared ledger must already exist at the
baseline's frozen path; each actual model request reserves two old 512-token blocks.
The selected subset is a post hoc diagnostic subset, not an unbiased new benchmark.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diagnostic_eval as diag

FOLLOWUP_OUTPUT_TOKENS = 1024
SELECTION_LIMIT = 10
BASELINE_KIND = 'matched_diagnostic_direct_vs_restricted_classifier_agent'


def _json_bytes(path):
    raw = Path(path).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def load_completed_baseline(directory, input_path):
    """Read isolated inference and run artifacts only; never locates label files."""
    directory = Path(directory).resolve()
    manifest, manifest_hash = _json_bytes(directory / 'manifest.json')
    summary, summary_hash = _json_bytes(directory / 'summary.json')
    plan = manifest.get('plan', {})
    plan_hash = diag.hash_value(plan)
    if (plan_hash != manifest.get('plan_sha256') or summary.get('plan_sha256') != plan_hash
            or summary.get('run_id') != manifest.get('run_id')):
        raise ValueError('Baseline manifest or summary fingerprint mismatch')
    required = {'kind': BASELINE_KIND, 'planned_question_count': 50, 'model': diag.MODEL,
                'max_output_tokens': 512, 'max_model_calls': 4, 'max_tool_calls': 2,
                'temperature': 0.2, 'top_p': 0.95, 'provider_retries': 0}
    if any(plan.get(key) != value for key, value in required.items()) or set(plan.get('arms', [])) != {'direct', 'agent'}:
        raise ValueError('Only the frozen two-arm 512-token diagnostic baseline is eligible')
    if summary.get('stop_reason') != 'complete' or summary.get('terminal_count') != 100:
        raise ValueError('Baseline must finish all 50 question pairs before follow-up')
    rows = diag.load_rows(input_path, planned_count=50)
    if diag.smoke.classifier_utils.sha256_file(input_path) != plan.get('input_sha256'):
        raise ValueError('Follow-up inference input differs from baseline')
    question_ids = [row['question_id'] for row in rows]
    if plan.get('question_ids') != question_ids:
        raise ValueError('Question order differs from baseline')
    expected_keys = {(qid, arm) for qid in question_ids for arm in ('direct', 'agent')}
    schedule = plan.get('schedule', [])
    if len(schedule) != 100 or {(x.get('question_id'), x.get('arm')) for x in schedule} != expected_keys:
        raise ValueError('Baseline schedule is not the complete planned two-arm comparison')
    results_path = directory / 'results.jsonl'
    raw = results_path.read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Baseline result journal has an incomplete tail')
    starts, terminals = {}, {}
    for line in raw.decode('utf-8').splitlines():
        value = json.loads(line)
        key = (value.get('question_id'), value.get('arm'))
        if key not in expected_keys:
            raise ValueError('Unplanned baseline question/arm')
        if value.get('record_type') == 'started':
            if key in starts:
                raise ValueError('Duplicate baseline start')
            starts[key] = value
        elif value.get('record_type') == 'terminal':
            if key not in starts or key in terminals or value.get('thread_id') != starts[key].get('thread_id'):
                raise ValueError('Duplicate or unpaired baseline terminal')
            tags = value.get('issue_tags')
            if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
                raise ValueError('Baseline issue tags are malformed')
            terminals[key] = value
        else:
            raise ValueError('Unknown baseline journal record')
    if set(terminals) != expected_keys:
        raise ValueError('Baseline journal is not complete')
    summary_rows = summary.get('question_results')
    if not isinstance(summary_rows, list) or len(summary_rows) != 100:
        raise ValueError('Baseline summary does not retain its full denominator')
    summary_keys = set()
    for result in summary_rows:
        key = (result.get('question_id'), result.get('arm'))
        if key in summary_keys or key not in terminals or result != terminals[key]:
            raise ValueError('Baseline summary and durable journal disagree')
        summary_keys.add(key)
    # Selection deliberately ignores answer_letter, correctness, scores and labels.
    eligible = [qid for qid in question_ids if any(
        'model_output_truncated' in terminals[(qid, arm)]['issue_tags'] for arm in ('direct', 'agent'))]
    selected_ids = eligible[:SELECTION_LIMIT]
    selected_set = set(selected_ids)
    return {'manifest': manifest, 'plan': plan, 'rows': rows,
            'selected_rows': [row for row in rows if row['question_id'] in selected_set],
            'selected_ids': selected_ids, 'eligible_ids': eligible,
            'schedule': [x for x in schedule if x['question_id'] in selected_set],
            'provenance': {'directory': str(directory), 'run_id': manifest['run_id'],
                'plan_sha256': plan_hash, 'manifest_file_sha256': manifest_hash,
                'results_file_sha256': hashlib.sha256(raw).hexdigest(), 'summary_file_sha256': summary_hash}}


def frozen_settings(baseline, *, ledger_path, repo=None, images_root=None):
    plan = baseline['plan']
    ledger_path = Path(ledger_path).resolve()
    expected_ledger = Path(plan['monetary_ledger_path']).resolve()
    if ledger_path != expected_ledger or not ledger_path.is_file():
        raise ValueError('Must use the existing baseline monetary ledger at its frozen path')
    expected_repo = Path(plan['upstream_repo_path']).resolve()
    expected_images = Path(plan['images_root']).resolve()
    if repo is not None and Path(repo).resolve() != expected_repo:
        raise ValueError('Upstream repository path differs from baseline')
    if images_root is not None and Path(images_root).resolve() != expected_images:
        raise ValueError('Image root differs from baseline')
    return SimpleNamespace(ledger=ledger_path, repo=expected_repo, images_root=expected_images,
        arms=tuple(plan['arms']), arm_order_seed=plan.get('arm_order_seed'),
        device=plan['device'], image_detail=plan['image_detail'], base_url=plan['provider_base_url'],
        max_case_seconds=plan['max_case_seconds'], request_timeout_seconds=plan['request_timeout_seconds'])


def make_followup_plan(baseline, input_path, args, guard, prompt):
    base = baseline['plan']
    if guard.policy_snapshot() != base['monetary_policy']:
        raise ValueError('Shared monetary policy differs from baseline')
    plan = diag.build_plan(baseline['selected_rows'], input_path, args.images_root, args.repo,
                           args, guard.policy_snapshot(), prompt)
    if plan['source_sha256'] != base['source_sha256'] or plan['package_versions'] != base['package_versions']:
        raise ValueError('Baseline source or installed package versions changed')
    if plan['prompts'] != base['prompts'] or plan['source'] != base['source']:
        raise ValueError('Baseline prompts or upstream checkout changed')
    old_records = {record['question_id']: record for record in base['records']}
    if any(record != old_records.get(record['question_id']) for record in plan['records']):
        raise ValueError('Selected question/image content differs from baseline')
    plan.update(kind='length_cap_followup_1024_on_baseline_truncation_subset',
                max_output_tokens=FOLLOWUP_OUTPUT_TOKENS, schedule=baseline['schedule'],
                baseline=baseline['provenance'],
                selection={'rule': 'first_10_in_original_input_order_with_model_output_truncated_in_either_arm',
                    'selection_limit': SELECTION_LIMIT, 'eligible_question_count': len(baseline['eligible_ids']),
                    'selected_question_ids': baseline['selected_ids'], 'uses_reference_labels': False,
                    'uses_correctness': False, 'requires_baseline_complete': True},
                variant_factors={'max_output_tokens': {'baseline': 512, 'followup': 1024},
                                 'protocol_repair_enabled': False, 'original_arm_order_preserved': True},
                chunked_budget_policy=guard.chunk_policy_snapshot())
    plan['source_sha256'] = dict(plan['source_sha256'], **{
        'length_cap_followup.py': diag.smoke.classifier_utils.sha256_file(Path(__file__)),
        'chunked_budget.py': diag.smoke.classifier_utils.sha256_file(Path(__file__).with_name('chunked_budget.py'))})
    plan['protocol_deviations'] = [
        text.replace('Direct is two-stage with 512 output tokens', 'Direct is two-stage with 1024 output tokens')
        for text in plan['protocol_deviations']
    ] + [
        'Post hoc diagnostic subset selected only by baseline truncation issue tags, without reference labels or correctness.',
        'Both arms use 1024 output tokens; all baseline prompt, model, sampling, tool and per-case call/time limits remain fixed.',
        'Each actual API request prepays two old 512-token ledger blocks; these are accounting blocks, not extra API calls.',
        'No invalid-tool-call or pending-tool-reply repair is enabled in this cap-only variant.',
        'Results on this selected subset are not an unbiased estimate over the original 50 questions or full benchmark.',
    ]
    return plan


def build_runtime(repo, args, key, prompt):
    runtime = diag.build_runtime(repo, args, key, prompt)
    # ChatOpenAI is a Pydantic model; copy changes only this explicit generation cap.
    runtime.model = runtime.model.model_copy(update={'max_tokens': FOLLOWUP_OUTPUT_TOKENS})
    if runtime.model.max_tokens != 1024:
        raise ValueError('Runtime output cap was not set to the frozen 1024-token variant')
    return runtime


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-run', 'input', 'output', 'ledger'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--repo', type=Path)
    parser.add_argument('--images-root', type=Path)
    parser.add_argument('--api-key-stdin', action='store_true')
    parser.add_argument('--resume', action='store_true')
    options = parser.parse_args(argv)
    journal, key = None, ''
    try:
        baseline = load_completed_baseline(options.baseline_run, options.input)
        args = frozen_settings(baseline, ledger_path=options.ledger, repo=options.repo, images_root=options.images_root)
        key = sys.stdin.readline().strip() if options.api_key_stdin else os.environ.get('OPENAI_API_KEY', '')
        if not key:
            raise ValueError('API key absent')
        os.environ['OPENAI_API_KEY'] = key
        from money_guard import MoneyGuard, BudgetExceeded
        from chunked_budget import ChunkedBudgetGuard
        utils = diag.smoke.module_from_file('_length_followup_official_utils', args.repo / 'medrax/utils/utils.py')
        prompt = utils.load_prompts_from_file(str(args.repo / 'medrax/docs/system_prompts.txt'))['MEDICAL_ASSISTANT']
        # frozen_settings rejects missing paths before MoneyGuard can initialize one.
        with MoneyGuard(args.ledger, budget_cny=baseline['plan']['monetary_policy']['budget_cny'], model=diag.MODEL) as shared:
            guard = ChunkedBudgetGuard(shared, max_output_tokens=1024)
            plan = make_followup_plan(baseline, options.input, args, guard, prompt)
            journal = diag.RunJournal(options.output, plan, resume=options.resume)
            try:
                journal.summary('initializing', diag.ledger_summary(guard))
                if not baseline['selected_rows']:
                    journal.summary('complete', diag.ledger_summary(guard))
                    print(json.dumps({'status': 'no_eligible_truncation_questions', 'selected': 0}), flush=True)
                    return 0
                with open(os.devnull, 'w') as sink, redirect_stdout(sink), redirect_stderr(sink):
                    runtime = build_runtime(args.repo, args, key, prompt)
                with (journal.output / 'trace.jsonl').open('a', encoding='utf-8') as trace:
                    summary = diag.execute_schedule(journal, runtime, guard, baseline['selected_rows'],
                        args.images_root, args, trace, limit_errors=(BudgetExceeded,))
                return 0 if summary['stop_reason'] == 'complete' else 2
            except BaseException:
                journal.summary('run_error', diag.ledger_summary(guard))
                raise
    except BaseException as exc:
        # Never expose provider bodies, prompt arguments, paths or credentials here.
        print(json.dumps({'status': 'followup_error', 'error_type': type(exc).__name__}), file=sys.stderr, flush=True)
        return 1
    finally:
        if journal is not None:
            journal.close()
        key = ''


if __name__ == '__main__':
    raise SystemExit(main())
