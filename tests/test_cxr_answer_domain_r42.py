"""Real observed counterexamples and budget boundaries for the R4.2 gate."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
from cxr_answer_domain_r42 import decision, parse_restatement


class DomainContinuationTest(unittest.TestCase):
    def prediction(self, answer='small', main=2):
        return {'answer': answer, 'reason': 'The silhouette appears small.', 'status': 'completed',
                'main_calls': main, 'tool_calls': 1,
                'observations': [{'status': 'completed', 'observation': 'Small'}]}

    def test_binary_candidate_and_original_budget(self):
        row = {'question': 'is the cardiac silhouette small/stretched'}
        self.assertEqual(decision(row, self.prediction()), 'continue_once')
        self.assertEqual(decision(row, self.prediction(main=4)), 'main_budget_exhausted')
        self.assertEqual(decision(row, self.prediction(answer='Yes.')), 'already_in_domain')
        self.assertEqual(decision(row, self.prediction(answer='TRUE')), 'already_in_domain')

    def test_correct_enumerated_answer_must_not_be_changed(self):
        row = {'question': 'Are the abnormalities on the left or right side?'}
        self.assertEqual(decision(row, self.prediction(answer='Right side')), 'outside_binary_scope')
        self.assertEqual(decision({'question': 'What do the two hyperintensities indicate?'},
                                  self.prediction(answer='Nodules')), 'outside_binary_scope')
        self.assertEqual(decision({'question': 'Is this abnormal?', 'options': {'A': 'Yes', 'B': 'No'}},
                                  self.prediction(answer='A')), 'outside_binary_scope')

    def test_failed_tool_is_never_sent_forward(self):
        prediction = self.prediction()
        prediction['observations'][0] = {'status': 'failed', 'observation': None}
        self.assertEqual(decision({'question': 'Is this small?'}, prediction), 'unhealthy_historical_tool')

    def test_reason_or_prose_never_supplies_answer(self):
        for raw in ['Yes. {"answer":"Yes"}', '{"reason":"Yes"}', '{"answer":"The trachea is midline"}',
                    '{"answer":"Yes","reason":"Small","calls":[]}',
                    '```json\n{"answer":"Yes","reason":"Small"}\n```',
                    '{"answer":"Yes","reason":null}',
                    '{"answer":"Yes' + '!' * 300 + '","reason":"Small"}']:
            with self.assertRaises(ValueError):
                parse_restatement(raw)
        self.assertEqual(parse_restatement('{"answer":"No","reason":"Yes"}')['answer'], 'No')


if __name__ == '__main__':
    unittest.main()
