"""Synthetic offline tests of selection, freezing and one-request/two-block usage."""
from copy import deepcopy
from decimal import Decimal
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diagnostic_eval as diag
import length_cap_followup as followup
from test_diagnostic_eval import FakeModel, Message, arguments, fake_messages, runtime


class FakeChunkGuard:
    def __init__(self, policy): self.policy = policy
    def policy_snapshot(self): return deepcopy(self.policy)
    def chunk_policy_snapshot(self): return {'effective_max_output_tokens': 1024, 'reservation_blocks': 2}


def fixture(root, truncated=None, prediction='A'):
    root.mkdir(parents=True, exist_ok=True)
    images = root / 'images'; images.mkdir()
    (images / 'image.png').write_bytes(b'synthetic image, never inferred')
    rows = [{'question_id': f'q{i:02}', 'question': 'synthetic question', 'images': ['image.png']} for i in range(50)]
    input_path = root / 'inputs.jsonl'
    input_path.write_bytes(b''.join(diag.canonical(row) for row in rows))
    ledger = root / 'original-ledger.json'; ledger.write_text('synthetic path fixture; never opened by MoneyGuard')
    plan = {'kind': followup.BASELINE_KIND, 'planned_question_count': 50, 'model': diag.MODEL,
        'max_output_tokens': 512, 'max_model_calls': 4, 'max_tool_calls': 2,
        'temperature': 0.2, 'top_p': 0.95, 'provider_retries': 0, 'arms': ['direct', 'agent'],
        'question_ids': [row['question_id'] for row in rows],
        'schedule': diag.make_schedule([row['question_id'] for row in rows]),
        'input_sha256': diag.smoke.classifier_utils.sha256_file(input_path),
        'records': [diag.inspect_input(row, images.resolve())[0] for row in rows],
        'monetary_ledger_path': str(ledger.resolve()), 'upstream_repo_path': str((root / 'repo').resolve()),
        'images_root': str(images.resolve()), 'device': 'cpu', 'image_detail': 'auto',
        'provider_base_url': 'https://example.invalid/v1', 'max_case_seconds': 180,
        'request_timeout_seconds': 60, 'monetary_policy': {'budget_cny': '100'},
        'source_sha256': {'source.py': 'synthetic-source-digest'}, 'package_versions': {'package': 'fixture'},
        'prompts': {'agent_system': 'synthetic official prompt'}, 'source': {'commit': 'fixture'},
        'protocol_deviations': ['synthetic baseline']}
    journal = diag.RunJournal(root / 'baseline', plan)
    truncated = set(truncated or [])
    for item in plan['schedule']:
        start = journal.start(item['question_id'], item['arm'])
        tags = ['model_output_truncated'] if item['question_id'] in truncated and item['arm'] == 'agent' else []
        journal.finish({'question_id': item['question_id'], 'arm': item['arm'], 'thread_id': start['thread_id'],
                        'status': 'completed', 'answer_letter': prediction, 'issue_tags': tags})
    journal.summary('complete'); journal.close()
    return root / 'baseline', input_path, ledger, plan


class LengthFollowupTests(unittest.TestCase):
    def test_first_ten_selection_uses_input_order_and_either_arm_not_answers(self):
        eligible = [f'q{i:02}' for i in range(1, 26, 2)]
        with TemporaryDirectory() as temp:
            one = fixture(Path(temp) / 'one', eligible, prediction='A')
            two = fixture(Path(temp) / 'two', eligible, prediction='F')
            first = followup.load_completed_baseline(one[0], one[1])
            second = followup.load_completed_baseline(two[0], two[1])
            self.assertEqual(first['selected_ids'], eligible[:10])
            self.assertEqual(first['selected_ids'], second['selected_ids'])
            self.assertEqual(len(first['schedule']), 20)
            self.assertEqual(first['schedule'][0], {'question_id': 'q01', 'arm': 'agent'})
            self.assertEqual(first['schedule'][1], {'question_id': 'q01', 'arm': 'direct'})
            self.assertEqual(len(first['eligible_ids']), 13)

    def test_running_baseline_and_journal_summary_disagreement_are_rejected(self):
        with TemporaryDirectory() as temp:
            directory, input_path, _, _ = fixture(Path(temp), ['q00'])
            summary_path = directory / 'summary.json'
            summary = json.loads(summary_path.read_text())
            summary['stop_reason'] = 'running'; summary_path.write_bytes(diag.canonical(summary))
            with self.assertRaises(ValueError): followup.load_completed_baseline(directory, input_path)
            summary['stop_reason'] = 'complete'; summary['question_results'][0]['issue_tags'] = ['tampered']
            summary_path.write_bytes(diag.canonical(summary))
            with self.assertRaises(ValueError): followup.load_completed_baseline(directory, input_path)

    def test_ledger_must_exist_at_exact_original_path(self):
        with TemporaryDirectory() as temp:
            directory, input_path, ledger, _ = fixture(Path(temp), ['q00'])
            base = followup.load_completed_baseline(directory, input_path)
            settings = followup.frozen_settings(base, ledger_path=ledger)
            self.assertEqual(settings.ledger, ledger.resolve())
            replacement = Path(temp) / 'other-ledger.json'; replacement.write_text('synthetic')
            with self.assertRaises(ValueError): followup.frozen_settings(base, ledger_path=replacement)
            # Simulate a missing original without deleting any user asset.
            with patch.object(Path, 'is_file', return_value=False):
                with self.assertRaises(ValueError): followup.frozen_settings(base, ledger_path=ledger)
            with self.assertRaises(ValueError): followup.frozen_settings(base, ledger_path=ledger, images_root=Path(temp) / 'different')

    def test_new_manifest_locks_cap_selection_baseline_hashes_and_unchanged_sources(self):
        with TemporaryDirectory() as temp:
            directory, input_path, ledger, plan = fixture(Path(temp), ['q01', 'q04'])
            base = followup.load_completed_baseline(directory, input_path)
            settings = followup.frozen_settings(base, ledger_path=ledger)
            selected = deepcopy(plan)
            selected['question_ids'] = base['selected_ids']; selected['planned_question_count'] = 2
            selected['records'] = [x for x in plan['records'] if x['question_id'] in base['selected_ids']]
            original = deepcopy(base)
            with patch.object(diag, 'build_plan', return_value=selected):
                result = followup.make_followup_plan(base, input_path, settings, FakeChunkGuard(plan['monetary_policy']), 'prompt')
            self.assertEqual(base, original)
            self.assertEqual(result['max_output_tokens'], 1024)
            self.assertEqual(result['schedule'], base['schedule'])
            self.assertFalse(result['variant_factors']['protocol_repair_enabled'])
            self.assertFalse(result['selection']['uses_correctness'])
            self.assertFalse(result['selection']['uses_reference_labels'])
            self.assertIn('results_file_sha256', result['baseline'])
            self.assertIn('length_cap_followup.py', result['source_sha256'])
            self.assertIn('chunked_budget.py', result['source_sha256'])
            changed = deepcopy(plan); changed['source_sha256']['source.py'] = 'different'
            with patch.object(diag, 'build_plan', return_value=changed):
                with self.assertRaises(ValueError):
                    followup.make_followup_plan(base, input_path, settings, FakeChunkGuard(plan['monetary_policy']), 'prompt')

    def test_runtime_copy_changes_only_max_tokens(self):
        class CopyableModel:
            def __init__(self):
                self.max_tokens = 512; self.temperature = 0.2; self.model_name = diag.MODEL; self.updates = []
            def model_copy(self, *, update):
                self.updates.append(update)
                return SimpleNamespace(max_tokens=update['max_tokens'], temperature=self.temperature, model_name=self.model_name)
        original = CopyableModel()
        with patch.object(diag, 'build_runtime', return_value=SimpleNamespace(model=original)):
            copied = followup.build_runtime(Path('/synthetic'), arguments(), 'synthetic-noncredential', 'prompt')
        self.assertEqual(original.updates, [{'max_tokens': 1024}])
        self.assertEqual(original.max_tokens, 512)
        self.assertEqual(copied.model.max_tokens, 1024)
        self.assertEqual(copied.model.temperature, 0.2)
        self.assertEqual(copied.model.model_name, diag.MODEL)

    def test_original_reserve_512_uses_two_blocks_for_one_1024_model_request(self):
        from money_guard import MoneyGuard, BudgetExceeded
        from chunked_budget import ChunkedBudgetGuard
        first = Message('synthetic reasoning')
        first.usage_metadata = {'input_tokens': 10, 'output_tokens': 900, 'total_tokens': 910}
        model = FakeModel([first, Message('A')])
        with TemporaryDirectory() as temp:
            ledger = Path(temp) / 'synthetic-shared.json'
            with MoneyGuard(ledger) as shared:
                guard = ChunkedBudgetGuard(shared, max_output_tokens=1024)
                result = diag.run_arm(runtime(model), guard,
                    {'question_id': 'q0', 'question': 'fixture', 'images': []}, [], 'direct',
                    {'thread_id': 'new-followup-thread'}, 'new-followup-run', arguments(), io.StringIO(),
                    limit_errors=(BudgetExceeded,), message_builder=fake_messages)
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(result['actual_model_calls'], 2)
                self.assertEqual(len(model.histories), 2)
                self.assertEqual(len(result['ledger_settlements']), 2)
                self.assertTrue(all(x['logical_api_requests'] == 1 and x['reservation_blocks'] == 2 for x in result['ledger_settlements']))
                self.assertEqual(shared.remaining, Decimal('99.37802'))
            state = json.loads(ledger.read_text())
            self.assertEqual(len(state['reservations']), 4)

    def test_empty_eligible_set_remains_empty(self):
        with TemporaryDirectory() as temp:
            directory, input_path, _, _ = fixture(Path(temp))
            base = followup.load_completed_baseline(directory, input_path)
            self.assertEqual(base['selected_rows'], [])
            self.assertEqual(base['schedule'], [])

    def test_followup_resume_never_repeats_started_arms_and_rejects_config_changes(self):
        with TemporaryDirectory() as temp:
            directory, input_path, ledger, plan = fixture(Path(temp), ['q00'])
            base = followup.load_completed_baseline(directory, input_path)
            settings = followup.frozen_settings(base, ledger_path=ledger)
            selected = deepcopy(plan)
            selected.update(question_ids=base['selected_ids'], planned_question_count=1,
                            records=[plan['records'][0]])
            with patch.object(diag, 'build_plan', return_value=selected):
                frozen = followup.make_followup_plan(base, input_path, settings,
                    FakeChunkGuard(plan['monetary_policy']), 'prompt')
            output = Path(temp) / 'followup'
            journal = diag.RunJournal(output, frozen)
            first = journal.start('q00', 'direct')
            journal.finish(dict(first, status='completed', answer_letter='A', issue_tags=[]))
            journal.start('q00', 'agent')
            journal.close()
            resumed = diag.RunJournal(output, frozen, resume=True)
            self.assertEqual(set(resumed.terminals), {('q00', 'direct'), ('q00', 'agent')})
            self.assertEqual(resumed.terminals[('q00', 'agent')]['status'], 'interrupted_no_retry')
            with self.assertRaises(ValueError): resumed.start('q00', 'agent')
            resumed.close()
            altered = deepcopy(frozen); altered['max_output_tokens'] = 2048
            with self.assertRaises(ValueError): diag.RunJournal(output, altered, resume=True)


if __name__ == '__main__':
    unittest.main()
