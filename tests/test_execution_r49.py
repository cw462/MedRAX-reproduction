"""R49 execution boundary regressions; no network, real tool, or target labels."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from cxr_online_primitives_r49 import schedule,read,tool_failure_reason
from online_memory_r49 import save_once,ReferenceVault,memory_entry
from skill_services_r49 import Services


class Tests(unittest.TestCase):
    def test_declared_partition_without_image_byte_access(self):
        inputs=[{'question_id':'a','images':['one.jpg']},{'question_id':'b','images':['two.jpg']}]
        old=[{'question_id':'a','image_key':'old_opaque','previous_ids':[]},
             {'question_id':'b','image_key':'old_opaque','previous_ids':['a']}]
        with patch.object(Path,'read_bytes',side_effect=AssertionError('must not inspect bytes')):
            result=schedule(inputs,'does_not_exist',old)
        self.assertEqual(result[1]['previous_ids'],['a'])
        self.assertEqual(result[0]['image_key'],'original_group_1')
        old[1]['previous_ids']=[]
        with self.assertRaises(ValueError):schedule(inputs,historical_order=old)

    def test_canonical_group_conflicting_path_stops(self):
        with self.assertRaises(ValueError):schedule([
            {'question_id':'a','image_id':'same','images':['one.jpg']},
            {'question_id':'b','image_id':'same','images':['two.jpg']}])

    def test_reference_requires_prediction_event_and_semantic_binding(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);pred=root/'predictions'/'ARM'/'q.json'
            save_once(pred,{'question_id':'q','answer':'Yes'})
            save_once(root/'refs/q.json',{'question_id':'q','answer':'No'})
            vault=ReferenceVault(root/'refs',{'q':{'file':'q.json'}})
            with self.assertRaises(ValueError):vault.after_prediction('q',pred)
            save_once(root/'prediction_events/q.json',{'question_id':'q','saved_prediction':read(pred)})
            self.assertEqual(vault.after_prediction('q',pred)['answer'],'No')
            pred.write_text('{"question_id":"q","answer":"No"}')
            with self.assertRaises(ValueError):vault.after_prediction('q',pred)

    def test_nested_failed_tool_excluded_but_completed_no_finding_kept(self):
        failed={'status':'completed','observation':[{'error':''},{'analysis_status':'failed'}],'tool':'ground'}
        healthy={'status':'completed','observation':[{'analysis_status':'completed_no_finding'}],'tool':'ground'}
        self.assertTrue(tool_failure_reason(failed));self.assertIsNone(tool_failure_reason(healthy))
        event={'question_id':'q','reference_annotation':{'answer':'Yes'}}
        entry=memory_entry({'question_id':'q','question':'Q'},
            {'question_id':'q','observations':[failed,healthy]},event)
        self.assertEqual(len(entry['tool_evidence']),1)

    def fake_service(self,tool_observation,replies):
        service=Services.__new__(Services);service.out=Path('.')
        service.runtime={'arms':{'M':{'tools':['ground']}}}
        service.base=SimpleNamespace(agent_system=lambda arm:'system',content=lambda *a:[],
            ACTION='action',evidence_catalog=lambda *a:[],validate_actions=lambda obj,*a:obj['calls'],
            resolve_action=lambda action,obs:action,append_observations=lambda *a:None)
        service.tools=SimpleNamespace(call=lambda *a:copy.deepcopy(tool_observation))
        queue=list(replies);service.paid=SimpleNamespace(call=lambda *a:queue.pop(0))
        return service,queue

    def test_nested_failure_stops_before_downstream_paid_call(self):
        failed={'status':'completed','observation':[{'error':''},{'analysis_status':'failed'}]}
        service,queue=self.fake_service(failed,['{"calls":[{"tool":"ground","args":{}}]}','must not send'])
        fake_completion=SimpleNamespace(prompt=lambda row:'final',unscorable=lambda *a:False)
        with patch.dict(sys.modules,{'cxr_task_completion_r43':fake_completion}):
            with self.assertRaisesRegex(RuntimeError,'nested_backend_error'):
                service.execute({'question_id':'q','images':['one.jpg']},'r49_unbounded','.',None)
        self.assertEqual(queue,['must not send'])

    def test_embedding_semantic_cache_and_unknown_send(self):
        with tempfile.TemporaryDirectory() as d:
            service=Services.__new__(Services);service.out=Path(d);service.embed_model='embedding-test'
            calls=[]
            def create(**request):
                calls.append(request)
                return SimpleNamespace(model_dump=lambda:{'model':'embedding-test','data':[{'embedding':[1.,0.]}],'usage':{'prompt_tokens':2}})
            service.embedding_client=SimpleNamespace(embeddings=SimpleNamespace(create=create))
            self.assertEqual(service.embed('text'),[1.,0.]);self.assertEqual(service.embed('text'),[1.,0.])
            self.assertEqual(len(calls),1)
            self.assertEqual(read(Path(d)/'embeddings/000001/result.json')['usage']['prompt_tokens'],2)
            folder=Path(d)/'embeddings/000002'
            save_once(folder/'request.json',{'model':'embedding-test','input':'unknown'})
            save_once(folder/'started.json',{'sent_intent':True})
            with self.assertRaisesRegex(RuntimeError,'unknown_embedding_send'):service.embed('unknown')
            self.assertEqual(len(calls),1)


if __name__=='__main__':unittest.main()
