"""Known failed tool becomes an explicit missing case; never a hidden retry."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from cxr_image_memory_r44 import write,read
from recover_cxr_image_memory_r45 import record_known_stop,finalize_known_failures


class RecoveryBoundaries(unittest.TestCase):
    def fixture(self,root):
        run=root/'generation';q='q0'
        write(run/'progress.json',{'status':'stopped','question_id':q,'error':'tool_unhealthy_stop:outer_status_not_completed'})
        for ordinal in [1,2]:
            folder=run/'calls/M43-IM'/q/str(ordinal)
            write(folder/'started.json',{});write(folder/'response.json',{})
            write(folder/'result.json',{'error':None,'response_received':True})
        healthy={'tool':'expert','status':'completed','observation':{'response':'observed'},'cache_key':'good'}
        bad={'tool':'classifier','status':'failed','observation':None,'cache_key':'bad','error':'backend_exit_-11'}
        for ordinal,obs in [(1,healthy),(2,bad)]:
            write(run/'tool_selections/M43-IM'/q/(str(ordinal)+'.json'),obs)
            write(run/'tool_cache'/obs['cache_key']/'result.json',obs)
        frozen={'inputs':[{'question_id':'q'+str(i)} for i in range(618)],
            'policy':{'q'+str(i):'C41' for i in range(618)},'new_main_ceiling':644,'new_tool_ceiling':384}
        return run,frozen

    def test_missing_response_cannot_be_terminalized(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);run,frozen=self.fixture(root)
            (run/'calls/M43-IM/q0/2/response.json').unlink()
            with self.assertRaisesRegex(ValueError,'unknown_sent_no_recovery'):record_known_stop(root,frozen,'q0')
            self.assertFalse((run/'predictions/M43-IM/q0.json').exists())

    def test_known_stop_full_accounting_and_no_later_failure_swallowing(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);run,frozen=self.fixture(root)
            note=record_known_stop(root,frozen,'q0')
            terminal=read(run/'predictions/M43-IM/q0.json')
            self.assertIsNone(terminal['answer']);self.assertIsNone(terminal['elapsed_s'])
            self.assertEqual([x['tool'] for x in terminal['observations']],['expert'])
            self.assertEqual(note['main_calls'],2)
            log=root/'child.log';log.write_text('ValueError: frozen_execution_changed\n')
            with self.assertRaisesRegex(ValueError,'expected_final_tool_audit'):finalize_known_failures(root,frozen,1,log)
            for i in range(618):
                q='q'+str(i)
                if i:write(run/'predictions/M43-IM'/(q+'.json'),{'answer':'A','reused_M43':True})
                write(run/'memory_context'/(q+'.json'),{})
            log.write_text('ValueError: unhealthy_tool_selection\n')
            result=finalize_known_failures(root,frozen,1,log)
            self.assertEqual(result['known_technical_missing_ids'],['q0'])
            self.assertEqual((run/'generation.effective.exitcode').read_text().strip(),'0')
            terminal['answer']='A'
            (run/'predictions/M43-IM/q0.json').write_text(__import__('json').dumps(terminal))
            with self.assertRaisesRegex(ValueError,'failure_filled_with_answer'):finalize_known_failures(root,frozen,1,log)
            terminal['answer']=None
            (run/'predictions/M43-IM/q0.json').write_text(__import__('json').dumps(terminal))
            folder=run/'calls/M43-IM/q0/3'
            write(folder/'started.json',{});write(folder/'response.json',{})
            write(folder/'result.json',{'error':None,'response_received':True})
            with self.assertRaisesRegex(ValueError,'inference_reissued_after_failure'):finalize_known_failures(root,frozen,1,log)


if __name__=='__main__':unittest.main()
