"""Offline tests for the provider ledger and the prompt-block renderer."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from provider_ledger import BudgetExceeded, LedgerIntegrityError, ProviderLedger  # noqa: E402
from provider_profile import PROFILES, get_profile  # noqa: E402
from memory_pipeline.injection import build_memory_block  # noqa: E402


class ProviderLedgerTests(unittest.TestCase):
    def profile(self):
        return get_profile('qwen3-vl-plus')

    def open(self, directory, **kwargs):
        return ProviderLedger(Path(directory) / 'ledger.json', self.profile(), **kwargs)

    def test_reserve_then_settle_charges_actual_usage(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.open(temp) as ledger:
                token = ledger.reserve(request_id='run:1', estimated_input_tokens=1000,
                                       max_output_tokens=100)
                self.assertEqual(ledger.remaining, Decimal('100') - Decimal('0.0052'))
                settlement = ledger.settle(token, usage={'prompt_tokens': 900, 'completion_tokens': 50})
                self.assertEqual(settlement['status'], 'settled')
                self.assertEqual(Decimal(settlement['charged_cny']), Decimal('0.0042'))
                self.assertEqual(ledger.remaining, Decimal('100') - Decimal('0.0042'))

    def test_unknown_usage_is_charged_in_full(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.open(temp) as ledger:
                token = ledger.reserve(request_id='run:1', estimated_input_tokens=1000,
                                       max_output_tokens=100)
                settlement = ledger.settle(token, usage=None, response_received=False,
                                           error_type='TimeoutError')
                self.assertEqual(settlement['status'], 'unknown')
                self.assertEqual(ledger.remaining, Decimal('100') - Decimal('0.0052'))

    def test_duplicate_request_id_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.open(temp) as ledger:
                ledger.reserve(request_id='run:1', estimated_input_tokens=100, max_output_tokens=10)
                with self.assertRaises(LedgerIntegrityError):
                    ledger.reserve(request_id='run:1', estimated_input_tokens=100, max_output_tokens=10)

    def test_actual_above_reservation_is_charged_without_blocking(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.open(temp) as ledger:
                token = ledger.reserve(request_id='run:1', estimated_input_tokens=100,
                                       max_output_tokens=10)
                settlement = ledger.settle(token, usage={'prompt_tokens': 5000, 'completion_tokens': 900})
                self.assertEqual(settlement['status'], 'settled_over_reservation')
                second = ledger.reserve(request_id='run:2', estimated_input_tokens=100,
                                        max_output_tokens=10)
                self.assertTrue(second)

    def test_usage_above_profile_ceiling_blocks_the_ledger(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.open(temp) as ledger:
                token = ledger.reserve(request_id='run:1', estimated_input_tokens=100,
                                       max_output_tokens=10)
                with self.assertRaises(LedgerIntegrityError):
                    ledger.settle(token, usage={'prompt_tokens': 40000, 'completion_tokens': 10})
                with self.assertRaises(LedgerIntegrityError):
                    ledger.reserve(request_id='run:2', estimated_input_tokens=100,
                                   max_output_tokens=10)

    def test_inherits_the_shared_cap_from_the_completed_gpt_ledger(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp) / 'gpt.json'
            from provider_ledger import _digest
            state = {'schema_version': 1, 'ledger_id': 'a' * 32, 'policy': {'x': 1}, 'generation': 1,
                     'created_utc': 'now', 'updated_utc': 'now', 'blocked': False,
                     'blocked_reason': None, 'reservations': [], 'committed_cny': '21.02928'}
            state['integrity_sha256'] = _digest(state)
            parent.write_text(json.dumps(state), encoding='utf-8')
            with ProviderLedger(Path(temp) / 'ledger.json', self.profile(),
                                inherit_ledger_path=parent) as ledger:
                self.assertEqual(ledger.remaining, Decimal('100') - Decimal('21.02928'))
                self.assertEqual(ledger.policy_snapshot()['inherited_cny'], '21.02928')

    def test_locked_ledger_refuses_a_second_writer(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.open(temp) as first:
                with self.assertRaises(LedgerIntegrityError):
                    self.open(temp)

    def test_budget_exceeded_when_remaining_is_too_small(self):
        with tempfile.TemporaryDirectory() as temp:
            with ProviderLedger(Path(temp) / 'ledger.json', self.profile(), cap_cny='0.1') as ledger:
                with self.assertRaises(BudgetExceeded):
                    ledger.reserve(request_id='big', estimated_input_tokens=32000,
                                   max_output_tokens=2048)


class InjectionTests(unittest.TestCase):
    hit = {'memory_id': 'b' * 64, 'score': 1.5, 'context': {
        'representation': 'observed_structured_execution_trajectory',
        'task_features': ['diagnosis', 'single_image', 'vqa'],
        'steps': [{'tool': 'chest_xray_classifier', 'execution': 'returned_valid',
                   'output_structure': {'score_count': 18}},
                  {'tool': 'chest_xray_report_generator', 'execution': 'returned_valid',
                   'output_structure': {'report_chars': 812}}],
        'clinical_evidence': 'unknown', 'step_credit': None}}

    def test_renders_tools_without_identifiers(self):
        text, audit = build_memory_block([self.hit])
        self.assertIn('chest_xray_classifier', text)
        self.assertIn('score_count=18', text)
        self.assertNotIn(self.hit['memory_id'], text)
        self.assertNotIn('question_id', text)
        self.assertEqual(audit['rendered'], 1)
        self.assertEqual(audit['memory_ids'], [self.hit['memory_id']])

    def test_empty_hits_inject_nothing(self):
        text, audit = build_memory_block([])
        self.assertEqual(text, '')
        self.assertEqual(audit['injected_chars'], 0)

    def test_character_budget_drops_low_ranked_memories(self):
        many = [self.hit] * 40
        text, audit = build_memory_block(many, max_chars=600)
        self.assertLessEqual(len(text), 600)
        self.assertLess(audit['rendered'], 40)
        self.assertGreaterEqual(audit['rendered'], 1)

    def test_failure_header_is_explicit(self):
        failure = json.loads(json.dumps(self.hit))
        failure['context']['task_outcome'] = 'incorrect'
        text, audit = build_memory_block([failure])
        self.assertIn('whole-question failures', text)
        self.assertIn('outcome: incorrect', text)
        self.assertEqual(audit['header_kind'], 'failure_aware')

    def test_unknown_context_structure_is_rejected(self):
        with self.assertRaises(ValueError):
            build_memory_block([{'memory_id': 'x', 'score': 1.0, 'context': {}}])
        with self.assertRaises(ValueError):
            build_memory_block([{'memory_id': 'x', 'score': 1.0, 'context': {'representation': 'r'} }],
                               max_chars=100)


if __name__ == '__main__':
    unittest.main()
