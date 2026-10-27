"""Repeat the first ten frozen questions at 512/1024 output tokens, without labels.

Six conditions share the existing baseline ledger and are interleaved by one
frozen schedule. The schedule seed affects ordering only; no provider seed is
sent. No protocol repair, memory, prompt or tool-description change is enabled.
The root journal starts durably before any slice or API work. On recovery every
started arm is retained or marked interrupted, never repeated.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from copy import deepcopy
from decimal import Decimal
import json
import os
from pathlib import Path
import random
import sys
from types import SimpleNamespace
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diagnostic_eval as diag
import length_cap_followup as previous

CAPS = (512, 1024)
REPLICATES = (1, 2, 3)
SCHEDULE_SEED = 20261027
QUESTION_COUNT = 10
KIND = 'repeated_matched_baseline_first10_caps512_1024_three_replicates'
SCHEDULE_FIELDS = ('schedule_index', 'slice_id', 'cap', 'replicate', 'question_id', 'arm')
FINAL_REASONS = frozenset({'complete', 'budget', 'api_error', 'run_error', 'monetary_guard_error'})


def make_schedule(question_ids):
    if len(question_ids) != QUESTION_COUNT or len(set(question_ids)) != QUESTION_COUNT:
        raise ValueError('Exactly ten distinct frozen question IDs are required')
    generator, schedule = random.Random(SCHEDULE_SEED), []
    for replicate in REPLICATES:
        for qid in question_ids:
            combinations = [(cap, arm) for cap in CAPS for arm in ('direct', 'agent')]
            generator.shuffle(combinations)
            for cap, arm in combinations:
                schedule.append({'schedule_index': len(schedule) + 1,
                    'slice_id': f'cap{cap}_rep{replicate}', 'cap': cap, 'replicate': replicate,
                    'question_id': qid, 'arm': arm})
    return schedule


def build_plan(baseline, input_path, args, shared_guard, chunk_guard, prompt):
    """Freeze all original sources, packages and 50 image records before selection."""
    base = baseline['plan']
    if (shared_guard.policy_snapshot() != base['monetary_policy']
            or Decimal(str(base['monetary_policy']['budget_cny'])) != Decimal('100')):
        raise ValueError('The original shared 100 CNY monetary policy is required')
    current = diag.build_plan(baseline['rows'], input_path, args.images_root, args.repo,
                              args, shared_guard.policy_snapshot(), prompt)
    for field in ('source_sha256', 'package_versions', 'prompts', 'source', 'records', 'input_sha256'):
        if current[field] != base[field]:
            raise ValueError('Frozen baseline source/package/prompt/input/image changed')
    rows = baseline['rows'][:QUESTION_COUNT]
    ids = [row['question_id'] for row in rows]
    schedule = make_schedule(ids)
    source_hashes = dict(current['source_sha256'])
    for name in ('repeated_baseline.py', 'length_cap_followup.py', 'chunked_budget.py'):
        source_hashes[name] = diag.smoke.classifier_utils.sha256_file(Path(__file__).with_name(name))
    conditions = {}
    for cap in CAPS:
        for replicate in REPLICATES:
            slice_id = f'cap{cap}_rep{replicate}'
            plan = deepcopy(current)
            plan.update(kind=KIND + '_condition', slice_id=slice_id, cap=cap, replicate=replicate,
                planned_question_count=QUESTION_COUNT, question_ids=ids,
                records=current['records'][:QUESTION_COUNT],
                selection_sha256=diag.hash_value(current['records'][:QUESTION_COUNT]),
                max_output_tokens=cap, arm_order_seed=None, schedule_seed=SCHEDULE_SEED,
                provider_seed=None, source_sha256=source_hashes,
                schedule=[{'question_id': x['question_id'], 'arm': x['arm']}
                          for x in schedule if x['slice_id'] == slice_id],
                global_schedule_sha256=diag.hash_value(schedule), baseline=baseline['provenance'],
                selection={'rule': 'first_10_in_original_input_order', 'uses_reference_labels': False,
                           'uses_correctness': False, 'uses_truncation': False},
                protocol_repair_enabled=False, cross_case_memory_enabled=False)
            if cap == 1024:
                plan['chunked_budget_policy'] = chunk_guard.chunk_policy_snapshot()
            plan['protocol_deviations'] = [
                text.replace('Direct is two-stage with 512 output tokens', f'Direct is two-stage with {cap} output tokens')
                for text in current['protocol_deviations']
            ] + [
                'The first ten input questions are repeated three times per cap and arm; selection ignores predictions and labels.',
                'Schedule seed only randomizes within-question condition order; no provider seed is configured.',
                'The six conditions share one original monetary ledger and one global API-failure streak.',
                'No protocol, memory, prompt, tool-description or model-sampling change is applied.',
                'A 1024-token request reserves two existing 512-token accounting blocks but sends only one API request.',
            ]
            conditions[slice_id] = plan
    return {'schema_version': 1, 'kind': KIND, 'planned_question_count': QUESTION_COUNT,
        'planned_arm_results': len(schedule), 'question_ids': ids, 'input_sha256': base['input_sha256'],
        'caps': list(CAPS), 'replicates': list(REPLICATES), 'arms': ['direct', 'agent'],
        'schedule_seed': SCHEDULE_SEED, 'provider_seed': None,
        'schedule_seed_scope': 'ordering_only_within_each_question_and_replicate',
        'global_schedule': schedule, 'global_schedule_sha256': diag.hash_value(schedule),
        'baseline': baseline['provenance'], 'condition_plans': conditions,
        'monetary_ledger_path': str(args.ledger.resolve()), 'monetary_policy': shared_guard.policy_snapshot(),
        'chunked_budget_policy': chunk_guard.chunk_policy_snapshot(), 'source_sha256': source_hashes,
        'selection': {'rule': 'first_10_in_original_input_order', 'uses_reference_labels': False,
                      'uses_correctness': False, 'uses_truncation': False},
        'global_failure_policy': {'consecutive_api_arm_errors': 3,
            'immediate': sorted(diag.IMMEDIATE_API_ERRORS), 'any_monetary_stop': True,
            'interrupted_unknown_does_not_reset_failure_streak': True}}


def interrupted_result(start):
    return {'question_id': start['question_id'], 'arm': start['arm'], 'thread_id': start['thread_id'],
        'status': 'interrupted_no_retry', 'answer_letter': None, 'issue_tags': ['interrupted_started_arm'],
        'actual_model_calls': None, 'actual_tool_attempts': None, 'validated_tool_returns': None,
        'observed_usage_sum': None, 'usage_complete': False, 'final_finish_reason': None,
        'stop_run': False, 'recovery_origin': 'root_started_before_slice_start'}


class RepeatedJournal:
    """Root ordering authority plus six unmodified diagnostic RunJournal instances."""
    def __init__(self, output, plan, *, resume=False):
        self.output, self.plan = Path(output).resolve(), plan
        self.plan_hash = diag.hash_value(plan)
        self.items = {x['schedule_index']: x for x in plan['global_schedule']}
        self.starts, self.terminals, self.slices = {}, {}, {}
        self.handle = None
        try:
            if resume:
                self.manifest = json.loads((self.output / 'manifest.json').read_text(encoding='utf-8'))
                if (self.manifest.get('plan_sha256') != self.plan_hash
                        or diag.hash_value(self.manifest.get('plan')) != self.plan_hash):
                    raise ValueError('Repeated experiment resume fingerprint mismatch')
                raw = (self.output / 'results.jsonl').read_text(encoding='utf-8')
                if raw and not raw.endswith('\n'):
                    raise ValueError('Incomplete root journal tail; automatic replay prohibited')
                for line in raw.splitlines():
                    self._accept(json.loads(line))
            else:
                self.output.mkdir(parents=True, exist_ok=False)
                (self.output / '.gitignore').write_text('*\n', encoding='utf-8')
                self.manifest = {'run_id': str(uuid.uuid4()), 'created_utc': diag.utc_now(),
                                 'plan_sha256': self.plan_hash, 'plan': plan}
                with (self.output / 'manifest.json').open('x', encoding='utf-8') as handle:
                    diag.durable_line(handle, self.manifest)
                (self.output / 'results.jsonl').touch(exist_ok=False)
            self.handle = (self.output / 'results.jsonl').open('a', encoding='utf-8')
            for slice_id, subplan in plan['condition_plans'].items():
                path = self.output / slice_id
                # A crash during initial setup may leave an uncreated, unused slice.
                self.slices[slice_id] = diag.RunJournal(path, subplan, resume=path.exists())
            self._reconcile()
        except BaseException:
            self.close()
            raise

    def _accept(self, record):
        index = record.get('schedule_index')
        item = self.items.get(index)
        if item is None or any(record.get(field) != item[field] for field in SCHEDULE_FIELDS):
            raise ValueError('Unplanned root schedule item')
        if record.get('record_type') == 'started':
            # Only a prefix can be started. No later item may precede a pending arm.
            if index in self.starts or index != len(self.starts) + 1 or len(self.terminals) != index - 1:
                raise ValueError('Duplicate or out-of-order root start')
            self.starts[index] = record
        elif record.get('record_type') == 'terminal':
            if index not in self.starts or index in self.terminals or index != len(self.terminals) + 1:
                raise ValueError('Duplicate or out-of-order root terminal')
            self.terminals[index] = record
        else:
            raise ValueError('Unknown root journal record')

    def _append(self, record):
        self._accept(record)
        diag.durable_line(self.handle, record)
        return record

    def _root_terminal(self, item, result):
        return self._append(dict(result, **item, record_type='terminal', root_finished_utc=diag.utc_now()))

    def _reconcile(self):
        index_for = {(x['slice_id'], x['question_id'], x['arm']): x['schedule_index']
                     for x in self.items.values()}
        for slice_id, journal in self.slices.items():
            for qid, arm in journal.starts:
                if index_for[(slice_id, qid, arm)] not in self.starts:
                    raise ValueError('Slice started without a durable global start')
        for index, root_start in self.starts.items():
            item = self.items[index]
            journal = self.slices[item['slice_id']]
            key = (item['question_id'], item['arm'])
            if key not in journal.starts:
                if index in self.terminals:
                    raise ValueError('Root terminal is missing its slice records')
                start = journal.start(*key)
                journal.finish(interrupted_result(start))
            # RunJournal already marks any slice start lacking a terminal interrupted.
            result = journal.terminals[key]
            if index in self.terminals:
                root_result = self.terminals[index]
                if any(root_result.get(field) != value for field, value in result.items()):
                    raise ValueError('Root and condition terminal disagree')
            else:
                self._root_terminal(item, result)

    def start(self, item):
        self._append(dict(item, record_type='started', started_utc=diag.utc_now()))
        return self.slices[item['slice_id']].start(item['question_id'], item['arm'])

    def finish(self, item, result):
        recorded = self.slices[item['slice_id']].finish(result)
        return self._root_terminal(item, recorded)

    def summary(self, reason, ledger=None):
        conditions = {}
        for slice_id, journal in self.slices.items():
            slice_reason = 'complete' if len(journal.terminals) == len(journal.plan['schedule']) else reason
            conditions[slice_id] = journal.summary(slice_reason, ledger)
        results = [self.terminals.get(item['schedule_index'], dict(item,
            status='not_run_' + reason, answer_letter=None, issue_tags=['not_run']))
            for item in self.plan['global_schedule']]
        summary = {'run_id': self.manifest['run_id'], 'plan_sha256': self.plan_hash,
            'planned_question_count': QUESTION_COUNT, 'planned_arm_results': len(self.items),
            'terminal_count': len(self.terminals), 'stop_reason': reason, 'ledger': ledger,
            'question_results': results, 'condition_summaries': conditions,
            'clinical_correctness_verified': False, 'updated_utc': diag.utc_now()}
        temporary = self.output / 'summary.json.tmp'
        with temporary.open('w', encoding='utf-8') as handle:
            diag.durable_line(handle, summary)
        os.replace(temporary, self.output / 'summary.json')
        marker = self.output / 'finalization.json'
        if reason in FINAL_REASONS:
            finalized = {'run_id': self.manifest['run_id'], 'plan_sha256': self.plan_hash,
                'stop_reason': reason, 'results_file_sha256': diag.smoke.classifier_utils.sha256_file(self.output / 'results.jsonl'),
                'summary_file_sha256': diag.smoke.classifier_utils.sha256_file(self.output / 'summary.json')}
            temporary = self.output / 'finalization.json.tmp'
            with temporary.open('w', encoding='utf-8') as handle:
                diag.durable_line(handle, finalized)
            os.replace(temporary, marker)
        elif marker.exists():
            marker.unlink()
        return summary

    def close(self):
        for journal in self.slices.values():
            journal.close()
        self.slices = {}
        if self.handle is not None:
            self.handle.close(); self.handle = None


def global_stop(records):
    streak = 0
    for result in records:
        if result.get('stop_run'):
            return result.get('stop_reason') or 'budget', streak
        if result.get('api_error'):
            streak += 1
        elif result.get('status') != 'interrupted_no_retry':
            streak = 0
        if streak >= 3:
            return 'api_error', streak
    return None, streak


def build_runtimes(repo, args, key, prompt):
    standard = diag.build_runtime(repo, args, key, prompt)
    if standard.model.max_tokens != 512:
        raise ValueError('Original runtime no longer has its frozen output cap')
    extended = SimpleNamespace(**vars(standard))
    extended.model = standard.model.model_copy(update={'max_tokens': 1024})
    if extended.model.max_tokens != 1024:
        raise ValueError('Extended runtime output cap mismatch')
    return {512: standard, 1024: extended}


def safe_ledger_summary(guard):
    """Exception-path reporting only: do not fabricate available money on failure."""
    try:
        return diag.ledger_summary(guard)
    except Exception as exc:
        return {'remaining_cny': None, 'conservative_spent_cny': None,
                'ledger_snapshot_error': type(exc).__name__}


def execute(journal, runtimes, guards, rows, args, *, limit_errors=(), runner=diag.run_arm):
    lookup = {row['question_id']: row for row in rows}
    preflight = {x['question_id']: x for x in next(iter(journal.plan['condition_plans'].values()))['records']}
    stop, streak = global_stop(journal.terminals.values())
    money = lambda: diag.ledger_summary(guards[512])
    if stop:
        return journal.summary(stop, money())
    journal.summary('running', money())
    with ExitStack() as stack:
        traces = {name: stack.enter_context((part.output / 'trace.jsonl').open('a', encoding='utf-8'))
                  for name, part in journal.slices.items()}
        for item in journal.plan['global_schedule']:
            if item['schedule_index'] in journal.terminals:
                continue
            start = journal.start(item)
            row = lookup[item['question_id']]
            current, paths = diag.inspect_input(row, args.images_root)
            issues = current['preflight_issues']
            if current != preflight[item['question_id']]:
                issues = sorted(set(issues + ['input_changed_since_manifest']))
            if issues:
                result = {'question_id': row['question_id'], 'arm': item['arm'], 'thread_id': start['thread_id'],
                    'status': 'missing_image' if 'missing_image' in issues else 'invalid_input', 'answer_letter': None,
                    'issue_tags': issues, 'actual_model_calls': 0, 'actual_tool_attempts': 0,
                    'validated_tool_returns': 0, 'observed_usage_sum': None, 'usage_complete': False, 'stop_run': False}
            else:
                with open(os.devnull, 'w') as sink, redirect_stdout(sink), redirect_stderr(sink):
                    result = runner(runtimes[item['cap']], guards[item['cap']], row, paths,
                        item['arm'], start, journal.slices[item['slice_id']].manifest['run_id'], args,
                        traces[item['slice_id']], limit_errors=limit_errors)
            if result.get('api_error'):
                streak += 1
            elif result.get('status') != 'interrupted_no_retry':
                streak = 0
            if streak >= 3:
                result.update(stop_run=True, stop_reason='api_error')
                result['issue_tags'] = sorted(set(result['issue_tags']) | {'consecutive_api_failure_stop'})
            journal.finish(item, result)
            reason = (result.get('stop_reason') or 'budget') if result.get('stop_run') else 'running'
            print(json.dumps({'progress': item['schedule_index'], 'planned': len(journal.items),
                'slice_id': item['slice_id'], 'question_id': item['question_id'], 'arm': item['arm'],
                'status': result['status'], 'model_calls': result.get('actual_model_calls'),
                'tool_calls': result.get('actual_tool_attempts'), **money()}), flush=True)
            journal.summary(reason, money())
            if result.get('stop_run'):
                return journal.summary(reason, money())
    return journal.summary('complete', money())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-run', 'input', 'output', 'ledger'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--api-key-stdin', action='store_true')
    parser.add_argument('--resume', action='store_true')
    options = parser.parse_args(argv)
    journal, key = None, ''
    try:
        baseline = previous.load_completed_baseline(options.baseline_run, options.input)
        args = previous.frozen_settings(baseline, ledger_path=options.ledger)
        key = sys.stdin.readline().strip() if options.api_key_stdin else os.environ.get('OPENAI_API_KEY', '')
        if not key:
            raise ValueError('API key absent')
        os.environ['OPENAI_API_KEY'] = key
        from money_guard import MoneyGuard, BudgetExceeded
        from chunked_budget import ChunkedBudgetGuard
        utils = diag.smoke.module_from_file('_repeated_baseline_utils', args.repo / 'medrax/utils/utils.py')
        prompt = utils.load_prompts_from_file(str(args.repo / 'medrax/docs/system_prompts.txt'))['MEDICAL_ASSISTANT']
        with MoneyGuard(args.ledger, budget_cny='100', model=diag.MODEL) as shared:
            guards = {512: shared, 1024: ChunkedBudgetGuard(shared, max_output_tokens=1024)}
            plan = build_plan(baseline, options.input, args, shared, guards[1024], prompt)
            journal = RepeatedJournal(options.output, plan, resume=options.resume)
            try:
                journal.summary('initializing', diag.ledger_summary(shared))
                with open(os.devnull, 'w') as sink, redirect_stdout(sink), redirect_stderr(sink):
                    runtimes = build_runtimes(args.repo, args, key, prompt)
                report = execute(journal, runtimes, guards, baseline['rows'][:QUESTION_COUNT], args,
                                 limit_errors=(BudgetExceeded,))
                return 0 if report['stop_reason'] == 'complete' else 2
            except BaseException:
                money = safe_ledger_summary(shared)
                journal.summary('monetary_guard_error' if money.get('ledger_snapshot_error') else 'run_error', money)
                raise
    except BaseException as exc:
        print(json.dumps({'status': 'repeated_baseline_error', 'error_type': type(exc).__name__}), file=sys.stderr, flush=True)
        return 1
    finally:
        if journal is not None:
            journal.close()
        key = ''


if __name__ == '__main__':
    raise SystemExit(main())
