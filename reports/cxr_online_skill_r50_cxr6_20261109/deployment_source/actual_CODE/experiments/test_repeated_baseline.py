"""Offline ordering, crash-boundary and global-stop tests; no model requests."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import repeated_baseline as repeated
import diagnostic_eval as diag
from test_diagnostic_eval import FakeGuard
from test_length_cap_followup import fixture, FakeChunkGuard


def experiment(root):
    directory, inputs, ledger, base_plan = fixture(root / 'source', ['q20'])
    baseline = repeated.previous.load_completed_baseline(directory, inputs)
    settings = repeated.previous.frozen_settings(baseline, ledger_path=ledger)
    with patch.object(diag, 'build_plan', return_value=deepcopy(base_plan)):
        plan = repeated.build_plan(baseline, inputs, settings,
            FakeChunkGuard(base_plan['monetary_policy']), FakeChunkGuard(base_plan['monetary_policy']), 'prompt')
    return plan, baseline['rows'][:10], settings, baseline, inputs, base_plan


def result_for(start, *, api_error=False, immediate=False):
    return {'question_id': start['question_id'], 'arm': start['arm'], 'thread_id': start['thread_id'],
        'status': 'model_error' if api_error else 'completed', 'answer_letter': None if api_error else 'A',
        'issue_tags': ['model_exception'] if api_error else [], 'api_error': api_error,
        'stop_run': immediate, 'stop_reason': 'api_error' if immediate else None,
        'actual_model_calls': 1, 'actual_tool_attempts': 0, 'validated_tool_returns': 0}


class RepeatedTests(unittest.TestCase):
    def test_balanced_deterministic_global_schedule_seed_only_orders(self):
        ids = [f'q{i:02}' for i in range(10)]
        schedule = repeated.make_schedule(ids)
        self.assertEqual(schedule, repeated.make_schedule(ids))
        self.assertEqual(len(schedule), 120)
        self.assertEqual([x['schedule_index'] for x in schedule], list(range(1, 121)))
        for offset in range(0, 120, 4):
            group = schedule[offset:offset + 4]
            self.assertEqual({(x['cap'], x['arm']) for x in group},
                {(512, 'direct'), (512, 'agent'), (1024, 'direct'), (1024, 'agent')})
            self.assertEqual({x['question_id'] for x in group}, {ids[(offset // 4) % 10]})
            self.assertEqual({x['replicate'] for x in group}, {offset // 40 + 1})
        self.assertEqual(len({(x['slice_id'], x['question_id'], x['arm']) for x in schedule}), 120)

    def test_first_ten_are_independent_of_truncation_and_all_50_sources_are_frozen(self):
        with TemporaryDirectory() as temp:
            plan, rows, settings, baseline, inputs, current = experiment(Path(temp))
            self.assertEqual(plan['question_ids'], [f'q{i:02}' for i in range(10)])
            self.assertEqual(baseline['selected_ids'], ['q20'])
            self.assertIsNone(plan['provider_seed'])
            self.assertEqual(plan['schedule_seed'], 20261027)
            self.assertEqual(len(plan['condition_plans']), 6)
            self.assertTrue(all(len(p['schedule']) == 20 for p in plan['condition_plans'].values()))
            self.assertFalse(plan['selection']['uses_truncation'])
            changed = deepcopy(current); changed['records'][40]['images'][0]['sha256'] = 'changed-even-outside-first10'
            with patch.object(diag, 'build_plan', return_value=changed):
                with self.assertRaises(ValueError):
                    repeated.build_plan(baseline, inputs, settings, FakeChunkGuard(current['monetary_policy']),
                                        FakeChunkGuard(current['monetary_policy']), 'prompt')

    def test_root_start_before_slice_crash_is_never_retried(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); plan, *_ = experiment(root)
            output = root / 'run'; journal = repeated.RepeatedJournal(output, plan)
            item = plan['global_schedule'][0]
            journal._append(dict(item, record_type='started', started_utc=diag.utc_now()))
            journal.close()
            recovered = repeated.RepeatedJournal(output, plan, resume=True)
            self.assertEqual(recovered.terminals[1]['status'], 'interrupted_no_retry')
            self.assertEqual(recovered.terminals[1]['recovery_origin'], 'root_started_before_slice_start')
            with self.assertRaises(ValueError): recovered.start(item)
            summary = recovered.summary('run_error')
            self.assertEqual(summary['terminal_count'], 1)
            self.assertEqual(len(summary['question_results']), 120)
            self.assertTrue(all(len(x['question_results']) == 20 for x in summary['condition_summaries'].values()))
            marker = json.loads((output / 'finalization.json').read_text())
            self.assertEqual(marker['summary_file_sha256'], diag.smoke.classifier_utils.sha256_file(output / 'summary.json'))
            recovered.summary('initializing')
            self.assertFalse((output / 'finalization.json').exists())
            recovered.close()

    def test_slice_crash_and_completed_slice_unmirrored_to_root_recover_once(self):
        for finished in (False, True):
            with self.subTest(finished=finished), TemporaryDirectory() as temp:
                root = Path(temp); plan, *_ = experiment(root)
                output = root / 'run'; journal = repeated.RepeatedJournal(output, plan)
                item = plan['global_schedule'][0]; start = journal.start(item)
                if finished:
                    journal.slices[item['slice_id']].finish(result_for(start))
                journal.close()
                recovered = repeated.RepeatedJournal(output, plan, resume=True)
                self.assertEqual(recovered.terminals[1]['status'], 'completed' if finished else 'interrupted_no_retry')
                thread = recovered.terminals[1]['thread_id']; recovered.close()
                twice = repeated.RepeatedJournal(output, plan, resume=True)
                self.assertEqual(len(twice.terminals), 1)
                self.assertEqual(twice.terminals[1]['thread_id'], thread)
                twice.close()

    def test_three_api_errors_stop_across_slices_and_resume_sends_nothing(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); plan, rows, settings, *_ = experiment(root)
            output = root / 'run'; journal = repeated.RepeatedJournal(output, plan)
            calls, guard = [], FakeGuard()
            def runner(runtime, money, row, paths, arm, start, *args, **kwargs):
                calls.append((row['question_id'], arm, runtime)); return result_for(start, api_error=True)
            with redirect_stdout(io.StringIO()):
                summary = repeated.execute(journal, {512: 512, 1024: 1024}, {512: guard, 1024: guard},
                    rows, settings, runner=runner)
            self.assertEqual(len(calls), 3)
            self.assertEqual(summary['stop_reason'], 'api_error')
            self.assertEqual(summary['terminal_count'], 3)
            self.assertEqual(len({x['slice_id'] for x in summary['question_results'][:3]}), 2)
            self.assertEqual(sum(x['status'].startswith('not_run') for x in summary['question_results']), 117)
            journal.close()
            recovered = repeated.RepeatedJournal(output, plan, resume=True)
            with redirect_stdout(io.StringIO()):
                repeated.execute(recovered, {512: 512, 1024: 1024}, {512: guard, 1024: guard},
                    rows, settings, runner=runner)
            self.assertEqual(len(calls), 3)
            recovered.close()

    def test_global_failure_streak_survives_slice_changes_and_unknown_interruptions(self):
        previous = [{'api_error': True}, {'status': 'interrupted_no_retry'}, {'api_error': True}]
        self.assertEqual(repeated.global_stop(previous), (None, 2))
        self.assertEqual(repeated.global_stop(previous + [{'api_error': True}])[0], 'api_error')
        self.assertEqual(repeated.global_stop(previous + [{'status': 'invalid_answer'}]), (None, 0))
        self.assertEqual(repeated.global_stop([{'stop_run': True, 'stop_reason': 'budget'}])[0], 'budget')

    def test_immediate_stop_preserves_all_six_denominators(self):
        for reason in ('api_error', 'budget'):
            with self.subTest(reason=reason), TemporaryDirectory() as temp:
                root = Path(temp); plan, rows, settings, *_ = experiment(root)
                journal = repeated.RepeatedJournal(root / 'run', plan); calls = []
                def runner(runtime, money, row, paths, arm, start, *args, **kwargs):
                    calls.append(start)
                    result = result_for(start, api_error=(reason == 'api_error'), immediate=True)
                    result['stop_reason'] = reason; return result
                guard = FakeGuard()
                with redirect_stdout(io.StringIO()):
                    summary = repeated.execute(journal, {512: None, 1024: None}, {512: guard, 1024: guard},
                                               rows, settings, runner=runner)
                self.assertEqual(len(calls), 1)
                self.assertEqual(summary['stop_reason'], reason)
                self.assertEqual(sum(x['planned_arm_results'] for x in summary['condition_summaries'].values()), 120)
                journal.close()

    def test_pending_shared_money_survives_journal_recovery(self):
        from money_guard import MoneyGuard
        with TemporaryDirectory() as temp:
            root = Path(temp); plan, *_ = experiment(root)
            ledger = root / 'synthetic-ledger.json'
            journal = repeated.RepeatedJournal(root / 'run', plan)
            journal.start(plan['global_schedule'][0])
            with MoneyGuard(ledger) as guard:
                guard.reserve(request_id='synthetic-interrupted-provider-request')
                reserved_remaining = guard.remaining
            journal.close()
            recovered = repeated.RepeatedJournal(root / 'run', plan, resume=True)
            with MoneyGuard(ledger) as guard:
                self.assertEqual(guard.remaining, reserved_remaining)
            self.assertEqual(recovered.terminals[1]['status'], 'interrupted_no_retry')
            recovered.close()

    def test_changed_schedule_or_ledger_and_truncated_root_journal_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); plan, *_ = experiment(root)
            output = root / 'run'; repeated.RepeatedJournal(output, plan).close()
            for field, replacement in [('schedule_seed', 1), ('monetary_ledger_path', 'different')]:
                changed = deepcopy(plan); changed[field] = replacement
                with self.assertRaises(ValueError): repeated.RepeatedJournal(output, changed, resume=True)
            (output / 'results.jsonl').write_text('{"record_type":')
            with self.assertRaises(ValueError): repeated.RepeatedJournal(output, plan, resume=True)

    def test_two_runtimes_differ_only_in_model_output_cap(self):
        class Model:
            max_tokens = 512
            def model_copy(self, *, update):
                self.update = update
                return SimpleNamespace(max_tokens=update['max_tokens'])
        original = SimpleNamespace(model=Model(), tool=object(), Agent=object(), direct_system='fixed')
        with patch.object(diag, 'build_runtime', return_value=original):
            runtimes = repeated.build_runtimes(None, None, 'synthetic-noncredential', 'prompt')
        self.assertIs(runtimes[512], original)
        self.assertEqual(original.model.update, {'max_tokens': 1024})
        self.assertIs(runtimes[512].tool, runtimes[1024].tool)
        self.assertEqual(runtimes[512].direct_system, runtimes[1024].direct_system)


if __name__ == '__main__':
    unittest.main()
