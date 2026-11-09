import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from . import v12_metrics as metrics
except ImportError:
    import v12_metrics as metrics


class V12MetricsTests(unittest.TestCase):
    def fixture(self, n=5):
        selection={'planned_n':n,'rows':[{'question_id':str(i),'official_group':','.join(metrics.CATEGORIES)} for i in range(n)]}
        labels={str(i):'C' for i in range(n)}
        first=['C','C','A',None,'A']
        answers={'B':['D',None,'C','C',None], 'A':['C','C','A','D','A']}
        resource={'model_calls':1,'tool_calls':0,'input_tokens':10,'output_tokens':3,'logical_cost_cny':'0.01'}
        initial=[{'question_id':str(i),'first_answer':first[i%5], 'status':'completed' if first[i%5] else 'failed',
                  'accounting':dict(resource),'timing':{'elapsed_s':1}} for i in range(n)]
        branches=[{'question_id':str(i),'group':g,'answer':answers[g][i%5],
                   'solver_answer':answers[g][i%5], 'candidate_answer':None,
                   'status':'completed' if answers[g][i%5] else 'failed',
                   'accounting':dict(resource),'timing':{'elapsed_s':2}} for g in metrics.GROUPS for i in range(n)]
        return selection,initial,branches,labels

    def test_distinguishes_legal_correction_recovery_and_missing_harm(self):
        s,i,b,l=self.fixture();result,rows=metrics.score(s,i,b,l)
        pair=result['groups']['B']['paired']
        self.assertEqual(pair['corrections_from_legal_wrong'],1)
        self.assertEqual(pair['initial_failure_recoveries'],1)
        self.assertEqual(pair['harms_to_legal_wrong'],1)
        self.assertEqual(pair['correct_to_missing'],1)
        self.assertEqual(pair['total_net'],0)
        self.assertEqual(pair['net_excluding_failure_recovery'],-1)
        self.assertEqual(pair['transitions']['legal_wrong_to_missing'],1)
        self.assertEqual(sum(pair['transitions'].values()),5)
        self.assertEqual(rows[3]['B']['transition_from_initial'],'initial_missing_to_correct')
        self.assertEqual(result['groups']['B']['final']['correct'],2)
        self.assertEqual(result['groups']['B']['final']['missing'],2)

    def test_all_options_rematching_not_restricted_to_initial(self):
        s,i,b,l=self.fixture();b[0]['answer']=b[0]['solver_answer']='F'
        result,rows=metrics.score(s,i,b,l)
        self.assertEqual(rows[0]['B']['answer'],'F')
        self.assertEqual(result['groups']['B']['final']['planned_n'],5)

    def test_candidate_stage_and_explicit_fallback_are_not_new_solver_success(self):
        s,i,b,l=self.fixture()
        for record,candidate in zip(b[:5],['D','C','C',None,'C']):
            record['candidate_answer']=candidate
        for index in (0,2):
            b[index].update(status='fallback_initial', fallback_to_initial=True,
                answer=i[index]['first_answer'], solver_answer=None, error='Synthetic final failure')
        result,rows=metrics.score(s,i,b,l);g=result['groups']['B']
        self.assertEqual(g['candidate']['correct'],3)
        self.assertEqual(g['candidate']['planned_n'],5)
        self.assertEqual(g['candidate']['missing'],1)
        self.assertEqual(g['candidate_paired']['corrections_from_legal_wrong'],2)
        self.assertEqual(g['candidate_paired']['harms_to_legal_wrong'],1)
        self.assertEqual(g['candidate_paired']['total_net'],1)
        self.assertEqual(g['final']['correct'],2)
        self.assertEqual(g['solver']['correct'],1)
        self.assertEqual(g['solver']['planned_n'],5)
        self.assertEqual(g['execution']['fallback_count'],2)
        self.assertEqual(g['execution']['fallback_correct_count'],1)
        self.assertEqual(g['execution']['solver_completed_count'],1)
        self.assertEqual(g['paired']['initial_failure_recoveries'],1)
        self.assertEqual(g['paired']['corrections_from_legal_wrong'],0)
        self.assertTrue(rows[0]['B']['fallback_to_initial'])
        self.assertIsNone(rows[0]['B']['solver_answer'])
        self.assertEqual(rows[0]['B']['candidate_answer'],'D')
        self.assertEqual(rows[0]['B']['transition_from_initial'],'correct_to_correct')
        self.assertIn('取证后候选',metrics.markdown(result))
        self.assertIn('回退不计作新的求解成功',metrics.markdown(result))

    def test_fallback_requires_legal_unchanged_initial_and_no_solver_answer(self):
        for index,answer,solver in [(3,'C',None),(0,'A',None),(0,'C','C')]:
            with self.subTest(index=index,answer=answer,solver=solver):
                s,i,b,l=self.fixture()
                b[index].update(status='fallback_initial',fallback_to_initial=True,
                    answer=answer,solver_answer=solver,error='synthetic')
                with self.assertRaisesRegex(ValueError,'Fallback must preserve'):
                    metrics.score(s,i,b,l)

    def test_shared_cost_once_and_overlapping_categories(self):
        s,i,b,l=self.fixture();r,_=metrics.score(s,i,b,l)
        self.assertEqual(r['total_new_resources']['model_calls']['sum_observed'],15)
        self.assertEqual(r['total_new_resources']['logical_cost_cny']['sum_observed'],0.15)
        self.assertEqual(r['initial_resources']['model_calls']['sum_observed'],5)
        self.assertEqual(r['groups']['A']['resources']['model_calls']['sum_observed'],5)
        self.assertEqual(sum(r['category_denominators'].values()),35)
        self.assertEqual(r['paired_B_vs_A']['both_correct'],0)
        self.assertEqual(r['paired_B_vs_A']['A_only_correct'],2)
        self.assertEqual(r['paired_B_vs_A']['B_only_correct'],2)

    def test_duplicate_missing_unknown_group_and_order_refused(self):
        s,i,b,l=self.fixture()
        for changed in (b+[copy.deepcopy(b[0])], b[:-1], list(reversed(b))):
            with self.assertRaises(ValueError):metrics.score(s,i,changed,l)
        bad=copy.deepcopy(b);bad[0]['group']='VKE'
        with self.assertRaisesRegex(ValueError,'Unknown V12 group'):metrics.score(s,i,bad,l)

    def test_no_labels_opened_before_all_sixty_and_order_complete(self):
        s,i,b,l=self.fixture(60)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'selection.json').write_text(json.dumps(s),encoding='utf-8')
            def write(name,rows): (root/name).write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
            write('initial_results.jsonl',i);write('branch_results.jsonl',b)
            (root/'status.json').write_text('{"status":"running"}')
            with patch.object(metrics.base,'_labels',side_effect=AssertionError('labels opened early')) as read:
                with self.assertRaisesRegex(ValueError,'labels have not been opened'):
                    metrics.generate_report(root,root/'labels.jsonl')
                (root/'status.json').write_text('{"status":"generation_complete"}')
                write('branch_results.jsonl',b[:-1])
                with self.assertRaisesRegex(ValueError,'labels have not been opened'):
                    metrics.generate_report(root,root/'labels.jsonl')
                write('branch_results.jsonl',list(reversed(b)))
                with self.assertRaisesRegex(ValueError,'all B terminals before'):
                    metrics.generate_report(root,root/'labels.jsonl')
                read.assert_not_called()
            write('branch_results.jsonl',b)
            write('labels.jsonl',[{'question_id':q,'answer':a} for q,a in l.items()])
            old=root/'old_v10';old.mkdir()
            (old/'selection.json').write_text(json.dumps(s))
            summary={'planned_n':60,'correct':1}
            (old/'paired_metrics.json').write_text(json.dumps({'run_status':'completed','planned_n':60,'p0':summary,
                'groups':{g:{'final':summary} for g in ['V','VK','VKE']},'total_resources':{'logical_cost_cny':99999}}))
            result=metrics.generate_report(root,root/'labels.jsonl',v10_run=old)
            self.assertEqual(result['planned_n'],60)
            self.assertEqual(result['total_new_resources']['logical_cost_cny']['sum_observed'],1.8)
            self.assertTrue(result['historical_v10']['historical_resources_excluded_from_v12_total'])
            self.assertEqual(result['historical_v10']['results']['P0']['correct'],1)
            self.assertTrue((root/'metrics.md').exists())
            self.assertEqual(len(json.loads((root/'per_question.json').read_text())['records']),60)


if __name__=='__main__':unittest.main()
