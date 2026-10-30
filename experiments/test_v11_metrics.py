import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from . import v11_metrics as metrics
except ImportError:
    import v11_metrics as metrics


class V11MetricsTests(unittest.TestCase):
    def fixture(self):
        ids = list('abcde')
        selection = {'planned_n': 5, 'rows': [{'question_id': q,
            'official_group': 'detection,classification,reasoning'} for q in ids]}
        labels = dict(zip(ids, ['A', 'B', 'C', 'D', 'B']))
        initials = dict(zip(ids, ['A', 'A', None, 'D', 'A']))
        candidates = dict(zip(ids, ['B', 'B', 'C', 'E', 'B']))
        finals = dict(zip(ids, ['A', 'B', 'C', 'D', 'A']))
        p0 = [{'question_id': q, 'initial': initials[q], 'status': 'completed'} for q in ids]
        source = [{'question_id': q, 'group': 'VKE', 'initial': initials[q],
            'candidate': candidates[q], 'final': initials[q] or candidates[q]} for q in ids]
        results = [{'question_id': q, 'group': 'VKE', 'stage': 'S1',
            'initial': initials[q], 'candidate': candidates[q], 'final': finals[q],
            'route': 'selector' if q != 'c' else 'p0_missing',
            'selector': {'choice': 'X', 'needs_followup': q == 'e'},
            'selector_error': 'APIError' if q in 'de' else None,
            'fallback': 'anonymous_X' if q in 'de' else None,
            'accounting': {'model_calls': 0 if q == 'c' else 1, 'tool_calls': 0,
                'logical_cost_cny': '0' if q == 'c' else '.01'},
            'timing': {'elapsed_s': 0 if q == 'c' else 1}} for q in ids]
        return selection, p0, source, results, labels

    def test_recovery_separate_and_fallback_not_successful_selection(self):
        payload = metrics.score(*self.fixture())
        group = payload['groups']['VKE']
        self.assertEqual(payload['p0']['correct'], 2)
        self.assertEqual(group['final']['correct'], 4)
        self.assertEqual(group['paired']['corrections_from_wrong_answer'], 1)
        self.assertEqual(group['paired']['recovered_from_p0_failure'], 1)
        self.assertEqual(group['paired']['net'], 2)
        self.assertEqual(group['paired']['net_without_failure_recovery'], 1)
        opportunities = group['selection_opportunities']
        self.assertEqual(opportunities['corrective_candidates'], 2)
        self.assertEqual(opportunities['corrections_kept_by_selection'], 1)
        self.assertEqual(opportunities['corrections_lost_to_error'], 1)
        self.assertEqual(opportunities['harmful_candidates'], 2)
        self.assertEqual(opportunities['harms_blocked_by_selection'], 1)
        self.assertEqual(opportunities['harms_blocked_by_fallback'], 1)
        self.assertEqual(payload['new_resources']['model_calls']['sum_observed'], 4)
        self.assertEqual(payload['new_resources']['logical_cost_cny']['sum_observed'], .04)
        self.assertNotIn('reference', group['representative_changes'][0])

    def test_frozen_candidates_and_complete_results_required(self):
        for mutation in ('initial', 'candidate', 'third', 'duplicate', 'missing'):
            args = list(copy.deepcopy(self.fixture()))
            results = args[3]
            if mutation == 'initial': results[0]['initial'] = 'F'
            elif mutation == 'candidate': results[0]['candidate'] = 'F'
            elif mutation == 'third': results[0]['final'] = 'F'
            elif mutation == 'duplicate': results.append(copy.deepcopy(results[0]))
            else: results.pop()
            with self.assertRaises(ValueError): metrics.score(*args)

    def test_s2_can_include_s1_without_charging_previous_calls(self):
        args = list(copy.deepcopy(self.fixture()))
        previous = copy.deepcopy(args[3])
        for row in args[3]:
            row['stage'] = 'S2'
            row['accounting'] = {'model_calls': 0, 'tool_calls': 0, 'logical_cost_cny': '0'}
        payload = metrics.score(*args, previous_rows=previous)
        self.assertEqual(payload['groups']['VKE']['S1']['final']['correct'], 4)
        self.assertEqual(payload['new_resources']['model_calls']['sum_observed'], 0)
        self.assertIn('VKE/S1', metrics._markdown(payload))
        self.assertIn('VKE/S2', metrics._markdown(payload))

    def test_no_labels_opened_before_generation_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, run = root/'source', root/'run'
            source.mkdir(); run.mkdir()
            selection = {'planned_n': 60, 'rows': [{'question_id': str(i),
                'official_group': 'detection'} for i in range(60)]}
            (source/'selection.json').write_text(json.dumps(selection), encoding='utf-8')
            rows = [{'question_id': str(i), 'group': 'VKE', 'stage': 'S1'} for i in range(60)]
            (run/'results.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows), encoding='utf-8')
            (run/'status.json').write_text('{"status":"running","planned_n":60}', encoding='utf-8')
            with patch.object(metrics.base, '_labels', side_effect=AssertionError('labels opened early')) as labels:
                with self.assertRaisesRegex(ValueError, 'labels have not been opened'):
                    metrics.generate_report(run, source, root/'labels.jsonl')
                labels.assert_not_called()


if __name__ == '__main__':
    unittest.main()
