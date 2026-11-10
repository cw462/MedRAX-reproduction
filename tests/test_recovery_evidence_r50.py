"""Synthetic policy checks for original failure/final continuation separation."""
import json
from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
import r50_recovery_evidence as evidence

def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value),encoding='utf-8')

def registry():
    return {'schema':'r50_known_medvlm_pre_generate_recovery_v1','adopted_retry_id':evidence.RECOVERY,
      'question_id':evidence.QID,'ordinal':105,'selection_ordinal':5,'cache_key':evidence.CACHE,'tool':'medvlm_r1',
      'failed_archive':'technical_failures/'+evidence.RECOVERY,'successful_attempt':'technical_recovery/'+evidence.RECOVERY,
      'original_generation_exit':1,'final_generation_exit_file':'generation.recovery001.exitcode',
      'original_controller_exit':1,'original_runner_exit':1,'original_saved_prefix':104,
      'failed_attempt_model_events':[],'exact_image_args_revision_unchanged':True,
      'completed_predictions_modified':False,'unknown_sends_reissued':False,'own_GT_read_before_adoption':False,
      'model_environment_or_generation_parameters_changed':False,
      'adoption_is_technical_not_answer_quality_selection':True,'successful_attempt_mirrored_for_publication':True}

class RecoveryPolicy(unittest.TestCase):
    def test_second_continuation_retains_both_nonzero_phases(self):
        with tempfile.TemporaryDirectory() as value:
            root=Path(value);put(root/'technical_recovery.json',registry())
            second=registry();second.update(schema='r50_known_medgemma_pre_generate_recovery_v2',
              adopted_retry_id=evidence.RECOVERY2,question_id=evidence.QID2,ordinal=184,selection_ordinal=1,
              cache_key=evidence.CACHE2,tool='medgemma',failed_archive='technical_failures/'+evidence.RECOVERY2,
              successful_attempt='technical_recovery/'+evidence.RECOVERY2,original_saved_prefix=183,
              final_generation_exit_file='generation.recovery002.exitcode',prior_generation_exit_file='generation.recovery001.exitcode',
              prior_continuation_exit=1,parent_recovery_id=evidence.RECOVERY)
            put(root/'technical_recovery002.json',second)
            for name,code in [('generation.exitcode',1),('generation.recovery001.exitcode',1),('generation.recovery002.exitcode',0)]:
                (root/name).write_text(str(code)+'\n')
            self.assertEqual(evidence.generation_completion(root)['prior_failed_exits'],[1,1])
            jobs=root/'jobs';jobs.mkdir()
            mapping={'schema':'r50_explicit_technical_continuation_v2','arm':evidence.ARM,'recovery_id':evidence.RECOVERY2,
              'original_controller':'controller','active_controller':'controller_recovery002','active_queue_status':'queue_status.recovery002.json',
              'dataset_jobs':{'chexbench':'chexbench_recovery002','slake':'slake','vqarad':'vqarad'},
              'generation_exit_files':{'chexbench':'generation.recovery002.exitcode','slake':'generation.exitcode','vqarad':'generation.exitcode'},
              'original_controller_exit':1,'original_chexbench_exit':1,'prior_controller_exit':1,'prior_chexbench_exit':1,
              'parent_recovery_id':evidence.RECOVERY,'original_failed_records_retained':True,
              'original_producer_modules_modified':False,'saved_predictions_modified':False,'automatic_retry':False}
            put(jobs/'technical_continuation002.json',mapping);put(jobs/'technical_continuation001.json',{'historical_synthetic_marker':True})
            put(jobs/'queue_status.recovery002.json',{'state':'all_three_datasets_exited_zero'})
            for prefix in ('controller','chexbench','controller_recovery001','chexbench_recovery001'):
                (jobs/(prefix+'.exitcode')).write_text('1\n')
            for prefix in ('controller_recovery002','chexbench_recovery002'):(jobs/(prefix+'.exitcode')).write_text('0\n')
            self.assertEqual(evidence.job_completion(jobs)['prior_failed_exits'],[1,1])
            self.assertEqual(evidence.job_completion(jobs,'chexbench')['job_prefix'],'chexbench_recovery002')
            (root/'generation.recovery001.exitcode').write_text('0\n')
            with self.assertRaises(ValueError):evidence.generation_completion(root)

    def test_initial_failure_is_retained_after_final_zero(self):
        with tempfile.TemporaryDirectory() as value:
            root=Path(value);(root/'generation.exitcode').write_text('1\n')
            put(root/'technical_recovery.json',registry())
            (root/'generation.recovery001.exitcode').write_text('0\n')
            result=evidence.generation_completion(root)
            self.assertEqual((result['original_exit'],result['final_exit']),(1,0))
            self.assertEqual((root/'generation.exitcode').read_text(),'1\n')

    def test_unknown_registration_or_unfinished_continuation_refused(self):
        with tempfile.TemporaryDirectory() as value:
            root=Path(value);(root/'generation.exitcode').write_text('1\n')
            with self.assertRaises(ValueError):evidence.generation_completion(root)
            changed=registry();changed['unknown_sends_reissued']=True
            put(root/'technical_recovery.json',changed)
            with self.assertRaises(ValueError):evidence.generation_completion(root)
            put(root/'technical_recovery.json',registry())
            (root/'generation.recovery001.exitcode').write_text('1\n')
            with self.assertRaises(ValueError):evidence.generation_completion(root)

    def test_failure_cost_counted_and_poor_success_not_rejected(self):
        with tempfile.TemporaryDirectory() as value:
            root=Path(value);reg=registry();put(root/'technical_recovery.json',reg)
            failed_root=root/reg['failed_archive'];success=root/reg['successful_attempt']
            active=root/'services/tool_cache'/evidence.CACHE
            identity={'backend':'medvlm_r1','args':{'question':'Synthetic question'},'revision':'synthetic'}
            failed={'status':'failed','error_type':'ImportError','actual_model_events':[],'identity':identity,'elapsed_s':10}
            result={'status':'completed','identity':identity,'observation':{'answer':'nonsensical output retained'},
              'actual_model_events':[{'kind':'generate','status':'completed'}],'elapsed_s':26}
            request={'backend':'medvlm_r1','image':'synthetic.png','args':identity['args'],'artifact_dir':'new'}
            put(failed_root/'tool_cache/result.json',failed)
            put(failed_root/'selection.json',{'status':'failed','cache_key':evidence.CACHE,'tool':'medvlm_r1'})
            put(failed_root/'tool_cache/request.json',dict(request,artifact_dir='original'))
            put(success/'request.json',request);put(success/'result.json',result)
            put(active/'request.json',request);put(active/'result.json',result)
            put(success/'completed.json',{'status':'completed_healthy','native_worker_exit_code':0})
            for name in ('worker.exitcode','attempt.exitcode'):(success/name).write_text('0\n')
            attempts,history=evidence.tool_recovery_attempts(root)
            self.assertEqual(len(attempts),1);self.assertEqual(history[0]['failed_elapsed_s'],10)
            failed['actual_model_events']=[{'kind':'generate','status':'started_unknown'}]
            put(failed_root/'tool_cache/result.json',failed)
            with self.assertRaises(ValueError):evidence.tool_recovery_attempts(root)

if __name__=='__main__':unittest.main()
