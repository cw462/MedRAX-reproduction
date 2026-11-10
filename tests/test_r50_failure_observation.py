"""New amendment behavior only: synthetic terminal failure, no model/network."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
from cxr_online_primitives_r50 import tool_failure_reason
from online_memory_r50 import save_once
from r50_failure_observation import SCHEMA, POLICY_ID, ARM, delivered_failure, validate_delivered_failure
from r50_services_amended import Services
from r50_run_amended import run_stream
from skill_lifecycle_r50 import initial
from run_cxr_vqa_toolsets import Tools


class FailureObservationAmendment(unittest.TestCase):
    def fixture(self, root, status='failed'):
        out=root/'slake'; services=out/'services'; q='synthetic_failed_grounding'; key='a'*64
        policy={'schema':SCHEMA,'policy_id':POLICY_ID,'arm':ARM,'dataset':'slake',
                'explicit_user_approval':True,'user_reply':'那按照论文中的同样来吧',
                'saved_prefix':0,'all_remaining_questions':True,'regenerate_failed_output':False,
                'modify_original_producers':False,'change_model_EOS_or_token_parameters':False}
        save_once(out/'protocol_amendment.json',policy)
        row={'question_id':q,'question':'Synthetic question','images':['synthetic.png'],'options':{'A':'synthetic choice'}}
        order=[{'question_id':q,'image_key':'synthetic_image','previous_ids':[]}]
        save_once(out/'contexts'/(q+'.json'),{'question_id':q,'ordinal':1,'window':0,
            'skill_snapshot':initial(),'selected_skills':[],'same_image_ids':[],'same_image_context':None})
        physical={'status':status,'observation':None,'error':'parser_failure',
                  'actual_model_events':[{'kind':'generate','status':'completed','elapsed_s':48.2}],
                  'raw_output':'<obj>unclosed','original_image':'synthetic.png','generated_tokens':300,'eos_terminated':False}
        obs=dict(physical,tool='xray_phrase_grounding',cache_hit=False,cache_key=key)
        cache=services/'tool_cache'/key
        save_once(cache/'result.json',physical);save_once(cache/'started.json',{'known_physical_attempt':True})
        save_once(cache/'request.json',{'tool':'xray_phrase_grounding','args':{'phrase':'synthetic phrase'}})
        save_once(services/'tool_selections/R50-AGENT'/q/'1.json',obs)
        return out,row,order,obs

    def test_failed_cache_replay_then_prediction_before_feedback(self):
        with tempfile.TemporaryDirectory() as directory:
            out,row,order,obs=self.fixture(Path(directory)); services=out/'services'
            paths=list((services/'tool_cache').rglob('*.json'))+list((services/'tool_selections').rglob('*.json'))
            originals={p:p.read_bytes() for p in paths}; seen=[]; model_calls=[]
            service=object.__new__(Services);service.out=services;service.runtime={'arms':{'M':{}},'tools':{}}
            base=SimpleNamespace(ACTION='action',agent_system=lambda arm:'system',content=lambda r,d:'synthetic input',
                evidence_catalog=lambda rt,arm:[],validate_actions=lambda obj,rt,arm,n,images:obj['calls'],
                resolve_action=lambda action,observations:action,
                append_observations=lambda messages,fresh,path,arm:messages.append({'role':'user','content':copy.deepcopy(fresh)}))
            service.base=base
            service.tools=Tools(service.runtime,Path(directory),services)
            def forbid_backend(*args):self.fail('saved failed selection must not invoke a backend')
            service.tools.observe=forbid_backend
            def call(r,arm,n,messages):
                model_calls.append(n)
                if n==1:return json.dumps({'calls':[{'tool':'xray_phrase_grounding','args':{'phrase':'synthetic phrase'}}]})
                seen.extend(copy.deepcopy(messages[-2]['content']))
                return json.dumps({'answer':'A','reason':'Synthetic answer despite failed tool'})
            service.call=call
            result,calls=service.execute(row,'r50_unbounded',Path(directory),None)
            self.assertEqual(model_calls,[1,2])
            self.assertEqual(seen[0]['status'],'failed');self.assertIsNone(seen[0]['observation'])
            self.assertEqual(seen[0]['generated_tokens'],300);self.assertFalse(seen[0]['eos_terminated'])
            self.assertIsNotNone(tool_failure_reason(result['observations'][0]))
            self.assertTrue(validate_delivered_failure(out,row['question_id'],result['observations'][0])['tool_remains_failed'])
            class Vault:
                def after_prediction(self,qid,path):
                    self.called=True
                    assert path.is_file()
                    event=out/'prediction_events'/(qid+'.json')
                    assert event.is_file()
                    return {'answer':'A'}
            vault=Vault();vault.called=False
            fake_service=SimpleNamespace(execute=lambda *a:(copy.deepcopy(result),copy.deepcopy(calls)))
            trajectories=[]
            def evolver(svc,snapshot,batch,*args):
                trajectories.extend(batch);return snapshot
            run_stream([row],order,Path(directory),out,fake_service,vault,[],
                       evolver=evolver,reward_fn=lambda *args:0)
            self.assertTrue(vault.called);self.assertTrue(trajectories[0]['technical_failure'])
            self.assertEqual(json.loads((out/'complete.json').read_text())['failed_tool_selections_delivered'],1)
            self.assertEqual({p:p.read_bytes() for p in paths},originals)

    def test_unknown_attempt_remains_hard_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            out,row,order,obs=self.fixture(Path(directory),status='started_unknown')
            with self.assertRaisesRegex(RuntimeError,'unknown_tool_attempt'):
                delivered_failure(out/'services',row,1,{'tool':obs['tool'],'args':{'phrase':'synthetic phrase'}},obs)
            self.assertFalse((out/'failure_observations').exists())

    def test_delivery_cannot_change_action_or_raw_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            out,row,order,obs=self.fixture(Path(directory))
            with self.assertRaisesRegex(ValueError,'action_changed'):
                delivered_failure(out/'services',row,1,{'tool':obs['tool'],'args':{'phrase':'changed'}},obs)
            delivered=delivered_failure(out/'services',row,1,{'tool':obs['tool'],'args':{'phrase':'synthetic phrase'}},obs)
            delivered['raw_output']='repaired output'
            with self.assertRaisesRegex(ValueError,'changed'):
                validate_delivered_failure(out,row['question_id'],delivered)

    def test_new_final_zero_preserves_three_failures_and_unstarted_cohorts(self):
        import r50_recovery_evidence as evidence
        from test_recovery_evidence_r50 import registry
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);run=root/'chexbench';run.mkdir()
            policy={'schema':SCHEMA,'policy_id':POLICY_ID,'arm':ARM,'dataset':'chexbench','saved_prefix':316,
              'explicit_user_approval':True,'user_reply':'那按照论文中的同样来吧','all_remaining_questions':True,
              'regenerate_failed_output':False,'modify_original_producers':False,'change_model_EOS_or_token_parameters':False,
              'original_exit1_records_retained':True,'held_question':'chexbench_openi_0078',
              'held_cache_key':'65e65ea9f529a7ce811f54147a7c2326bf115aeaf0ddb2960ff9c3437d77626d',
              'new_execution_modules':['r50_failure_observation.py','r50_services_amended.py','r50_run_amended.py']}
            save_once(run/'protocol_amendment.json',policy);save_once(run/'technical_recovery.json',registry())
            second=registry();second.update(schema='r50_known_medgemma_pre_generate_recovery_v2',adopted_retry_id=evidence.RECOVERY2,
              question_id=evidence.QID2,ordinal=184,selection_ordinal=1,cache_key=evidence.CACHE2,tool='medgemma',
              failed_archive='technical_failures/'+evidence.RECOVERY2,successful_attempt='technical_recovery/'+evidence.RECOVERY2,
              original_saved_prefix=183,final_generation_exit_file='generation.recovery002.exitcode',
              prior_generation_exit_file='generation.recovery001.exitcode',prior_continuation_exit=1,parent_recovery_id=evidence.RECOVERY)
            save_once(run/'technical_recovery002.json',second)
            for name in ('generation.exitcode','generation.recovery001.exitcode','generation.recovery002.exitcode'):(run/name).write_text('1\n')
            (run/'generation.amendment003.exitcode').write_text('0\n')
            self.assertEqual(evidence.generation_completion(run)['prior_failed_exits'],[1,1,1])
            (run/'generation.recovery002.exitcode').write_text('0\n')
            with self.assertRaisesRegex(ValueError,'three_actual_prior'):evidence.generation_completion(run)
            slake=root/'slake';slake.mkdir();save_once(slake/'protocol_amendment.json',dict(policy,dataset='slake',saved_prefix=0))
            (slake/'generation.amendment003.exitcode').write_text('0\n')
            self.assertIsNone(evidence.generation_completion(slake)['original_exit'])
            self.assertFalse((slake/'generation.exitcode').exists())
            (slake/'generation.exitcode').write_text('0\n')
            with self.assertRaisesRegex(ValueError,'fake_exit'):evidence.generation_completion(slake)
            namespace={};exec(evidence.REMOTE_GATE_SOURCE,namespace)
            with self.assertRaisesRegex(ValueError,'fake_exit'):namespace['generation_completion'](slake)

    def test_public_failure_validation_uses_same_asset_normalizing_reader(self):
        with tempfile.TemporaryDirectory() as directory:
            out,row,order,obs=self.fixture(Path(directory))
            presented=delivered_failure(out/'services',row,1,{'tool':obs['tool'],'args':{'phrase':'synthetic phrase'}},obs)
            def normalize(value):
                if isinstance(value,dict):
                    return {k:('/canonical/public/asset.png' if k=='original_image' else normalize(v)) for k,v in value.items()}
                if isinstance(value,list):return [normalize(v) for v in value]
                return value
            def public_read(path):return normalize(json.loads(Path(path).read_text(encoding='utf-8')))
            normalized=normalize(presented)
            with self.assertRaises(ValueError):validate_delivered_failure(out,row['question_id'],normalized)
            self.assertTrue(validate_delivered_failure(out,row['question_id'],normalized,reader=public_read)['tool_remains_failed'])


if __name__=='__main__':unittest.main()
