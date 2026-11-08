"""Protect accepted MCQ answers and the actual inherited M budget."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
from cxr_task_completion_r43 import accepted_reply, decision, unscorable


class TaskCompletionTest(unittest.TestCase):
    row = {'question': 'Which finding is present?', 'options': {'A': 'Left effusion', 'B': 'Right effusion'}}

    def prediction(self, answer='No'):
        return {'status': 'completed', 'answer': answer, 'reason': '', 'main_calls': 0,
                'tool_calls': 0, 'reused_historical_M': True}

    def actual(self, main=3):
        return {'status': 'completed', 'answer': 'No', 'reason': '', 'main_calls': main,
                'tool_calls': 1, 'observations': [{'status': 'completed', 'observation': 'No'}]}

    def test_all_original_accepted_option_forms_are_preserved(self):
        for answer in ['A', 'Left effusion', 'A. Left effusion', 'A) Left effusion']:
            self.assertEqual(decision(self.row, self.prediction(answer), self.actual()), 'preserve_accepted_answer')
        self.assertTrue(unscorable(self.row, self.prediction('A. Right effusion')))

    def test_real_prefix_budget_is_used_not_r41_zero(self):
        self.assertEqual(decision(self.row, self.prediction(), self.actual()), 'complete_once')
        self.assertEqual(decision(self.row, self.prediction(), self.actual(4)), 'actual_prefix_budget_exhausted')
        failed = self.actual()
        failed['observations'][0] = {'status': 'failed', 'observation': None}
        self.assertEqual(decision(self.row, self.prediction(), failed), 'unhealthy_actual_prefix')

    def test_reply_uses_explicit_option_and_exact_original_schema(self):
        self.assertEqual(accepted_reply(self.row, '{"answer":"B","reason":"Visible"}')['answer'], 'B')
        for raw in ['{"answer":"No","reason":"No finding"}', '{"answer":"B","reason":null}',
                    'First B. {"answer":"B","reason":"Visible"}']:
            with self.assertRaises(ValueError):
                accepted_reply(self.row, raw)


if __name__ == '__main__':
    unittest.main()
