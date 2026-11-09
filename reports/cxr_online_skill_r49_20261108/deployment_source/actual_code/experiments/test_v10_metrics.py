import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from . import v10_metrics as metrics
except ImportError:
    import v10_metrics as metrics


class V10MetricsTests(unittest.TestCase):
    def fixture(self):
        selection = {'planned_n': 3, 'rows': [
            {'question_id': 'a', 'official_group': 'detection,localization,reasoning'},
            {'question_id': 'b', 'official_group': 'classification,diagnosis,reasoning'},
            {'question_id': 'c', 'official_group': 'comparison,relationship,characterization,reasoning'}]}
        labels = {'a': 'A', 'b': 'B', 'c': 'C'}
        resource = {'model_calls': 1, 'tool_calls': 0, 'input_tokens': 10, 'output_tokens': 2,
                    'total_tokens': 12, 'logical_cost_cny': '0.01', 'incremental_cost_cny': '0.01'}
        initials = {'a': 'A', 'b': 'A', 'c': None}
        p0 = [{'question_id': q, 'initial': x, 'status': 'completed' if x else 'failed',
               'accounting': dict(resource), 'timing': {'elapsed_s': 1}} for q,x in initials.items()]
        plans = [{'question_id': q, 'accounting': dict(resource), 'timing': {'elapsed_s': 1}} for q in initials]
        branches = []
        for g in metrics.GROUPS:
            for q in initials:
                # Harm a, correct b, recover missing c: net +1, not 0.
                candidate = {'a': 'B', 'b': 'B', 'c': 'C'}[q]
                branches.append({'question_id': q, 'group': g, 'initial': initials[q], 'candidate': candidate,
                    'final': candidate, 'candidate_error': None, 'gate_error': None,
                    'gate': {'decision': 'accept' if initials[q] else 'p0_missing'},
                    'accounting': dict(resource), 'timing': {'elapsed_s': 1}})
        return selection, p0, branches, labels, plans

    def test_paired_net_includes_missing_p0_recovery(self):
        s,p,b,l,plans = self.fixture()
        result = metrics.score(s,p,b,l,shared_plans=plans)
        for group in metrics.GROUPS:
            pair = result['groups'][group]['paired']
            self.assertEqual((pair['corrections'],pair['harms'],pair['net']), (2,1,1))
            self.assertEqual(pair['corrections_from_wrong_answer'], 1)
            self.assertEqual(pair['recovered_from_p0_failure'], 1)
            self.assertEqual(pair['net'], result['groups'][group]['final']['correct']-result['p0']['correct'])

    def test_overlapping_categories_and_shared_cost_once(self):
        s,p,b,l,plans = self.fixture()
        result = metrics.score(s,p,b,l,shared_plans=plans)
        self.assertEqual(result['p0']['planned_n'], 3)
        self.assertEqual(sum(result['category_denominators'].values()), 7)
        self.assertTrue(all(n==1 for n in result['category_denominators'].values()))
        self.assertEqual(result['shared_plan_resources']['model_calls']['sum_observed'], 3)
        self.assertEqual(result['total_resources']['model_calls']['sum_observed'], 15)
        self.assertEqual(result['total_resources']['logical_cost_cny']['sum_observed'], 0.15)

    def test_third_answer_or_duplicate_or_mismatched_p0_rejected(self):
        s,p,b,l,plans = self.fixture()
        for mutation in ('third', 'duplicate', 'p0'):
            bad=copy.deepcopy(b)
            if mutation=='third': bad[0]['final']='C'
            elif mutation=='duplicate': bad.append(copy.deepcopy(bad[0]))
            else: bad[0]['initial']='C'
            with self.assertRaises(ValueError): metrics.score(s,p,bad,l,shared_plans=plans)

    def test_partial_primary_pass_keeps_full_denominator(self):
        s,p,b,l,plans = self.fixture()
        primary=[r for r in b if r['group']=='VKE']
        result=metrics.score(s,p,primary,l,shared_plans=plans,allow_partial=True)
        self.assertEqual(result['groups']['V']['status'], '未运行')
        self.assertEqual(result['groups']['V']['final']['missing'], 3)
        self.assertIsNone(result['primary_decision']['minimum_development_goal_met'])
        self.assertEqual(result['groups']['VKE']['final']['planned_n'],3)

    def test_labels_not_opened_until_complete_status_and_terminals(self):
        s,p,b,l,plans = self.fixture()
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            (root/'selection.json').write_text(json.dumps(s),encoding='utf-8')
            for file, rows in [('p0_results.jsonl',p),('candidate_results.jsonl',b),('shared_plans.jsonl',plans)]:
                (root/file).write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
            (root/'status.json').write_text('{"status":"running"}',encoding='utf-8')
            with patch.object(metrics.base,'_labels',side_effect=AssertionError('labels opened early')) as read:
                with self.assertRaisesRegex(ValueError,'labels have not been opened'):
                    metrics.generate_report(root,root/'labels.jsonl')
                read.assert_not_called()
            (root/'status.json').write_text('{"status":"generation_complete"}',encoding='utf-8')
            (root/'labels.jsonl').write_text(''.join(json.dumps({'question_id':q,'answer':v})+'\n' for q,v in l.items()),encoding='utf-8')
            result=metrics.generate_report(root,root/'labels.jsonl')
            self.assertEqual(result['run_status'],'completed')
            self.assertIn('Shared option plan',(root/'paired_metrics.md').read_text(encoding='utf-8'))
            self.assertTrue((root/'case_review.md').exists())


if __name__=='__main__':
    unittest.main()
