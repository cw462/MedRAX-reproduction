"""New R50 composition boundaries; synthetic archives only."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'experiments'))
import score_online_skill_r50 as scoring


def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v),encoding='utf-8')


class Composition(unittest.TestCase):
    def test_all_compared_raw_arms_adapt_before_label_bearing_semantics(self):
        events=[]
        class StopBeforeLabels(Exception):pass
        def adapt_new(*a):events.append('current');return {},{},{}
        def adapt_baseline(*a):events.append('historical_direct');return {}
        def adapt_r49(*a):events.append('saved_R49_raw');return {},{}
        def semantics(*a):
            self.assertEqual(events,['current','historical_direct','saved_R49_raw']);raise StopBeforeLabels()
        with patch.object(scoring,'completed_gate',return_value=([],{'dataset':'slake'},{})), \
             patch.object(scoring,'adapt_current',side_effect=adapt_new), \
             patch.object(scoring,'adapt_historical',side_effect=adapt_baseline), \
             patch.object(scoring,'adapt_saved_r49',side_effect=adapt_r49), \
             patch.object(scoring,'check_semantics',side_effect=semantics), \
             patch.object(scoring,'rows',side_effect=AssertionError('evaluation labels opened too early')) as references:
            with self.assertRaises(StopBeforeLabels):
                scoring.score(Path('not_opened'),Path('not_opened'),Path('not_opened'),'slake',r49_run=Path('not_opened'))
        self.assertEqual(references.call_count,0)

    def test_unselected_tools_remain_zero_and_health_is_separate(self):
        with tempfile.TemporaryDirectory() as temp:
            run=Path(temp);call=run/'services/calls/R50-AGENT/q/1';call.mkdir(parents=True)
            write(run/'final_repo.json',{'skills':{}})
            started={'utc':'2026-01-01T00:00:00+00:00'}
            receipt={'utc':'2026-01-01T00:00:01+00:00','usage':None,'elapsed_s':1.,'model_returned':'fixture','settlement':{'charged_cny':None}}
            result=scoring.resources(run,{'q':[(call,started,receipt)]},[],{'physical':[],'healthy':0})
            self.assertEqual(len(result['tools']['per_tool']),6)
            self.assertTrue(all(v['logical_calls']==v['fresh_backend_attempts']==0 for v in result['tools']['per_tool'].values()))
            self.assertTrue(result['new3_health_probe_cost_time_excluded_from_production_totals'])
            self.assertEqual(result['agent']['cost_unknown_count'],1)
            self.assertEqual(result['prescreen']['requests'],0)

    def test_saved_R49_adapter_never_invokes_old_private_score(self):
        import score_online_skill_r49 as old
        from run_online_skill_r49 import ARM as OLD_ARM
        inputs=[{'question_id':'synthetic'}]
        with tempfile.TemporaryDirectory() as temp:
            run=Path(temp);(run/'generation.exitcode').write_text('0\n')
            write(run/'manifest.json',{'inputs':inputs});write(run/'predictions'/OLD_ARM/'synthetic.json',{})
            with patch.object(old,'score',side_effect=AssertionError('old private scorer invoked')) as old_score, \
                 patch.object(old,'adapt_current',return_value=({'synthetic':{'fixture':True}},{'synthetic':{'status':'completed'}},{})) as raw_adapter:
                result,provenance=scoring.adapt_saved_r49(inputs,run)
            self.assertEqual(raw_adapter.call_count,1);self.assertEqual(old_score.call_count,0)
            self.assertTrue(result['synthetic']['fixture']);self.assertFalse(provenance['private_R49_score_invoked'])


if __name__=='__main__':unittest.main()
