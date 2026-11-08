import sys,unittest,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from cxr_image_memory_r44 import *
class Tests(unittest.TestCase):
    def test_no_reference_in_memory(self):
        r={'answer':'A','reason':'guess','status':'completed','reference':'B','correct':False}
        e=memory_entry({'question_id':'q','question':'Where?'},r)
        self.assertNotIn('reference',e);self.assertNotIn('correct',e);self.assertEqual(e['previous_answer'],'A')
    def test_missing_preserved(self):self.assertIsNone(memory_entry({'question_id':'q','question':'x'},{'answer':None})['previous_answer'])
    def test_failed_tool_not_evidence(self):
        e=memory_entry({'question_id':'q','question':'x'},{'observations':[{'status':'failed','observation':'bad'}]})
        self.assertEqual(e['tool_evidence'],[])
    def test_inherited_evidence(self):
        e=memory_entry({'question_id':'q','question':'x'},{'inherited_observations':[{'tool':'t','status':'completed','observation':'seen'}]})
        self.assertEqual(e['tool_evidence'][0]['observation'],'seen')
    def test_chronological_recent_memory(self):
        es=[memory_entry({'question_id':str(i),'question':'x'},{'answer':'Yes'}) for i in range(10)]
        text,ids=context(es);self.assertEqual(ids,[str(i) for i in range(2,10)]);self.assertIn('fallible',text)
    def test_empty(self):self.assertEqual(context([]),(None,[]))
    def test_memory_uses_new_answer(self):
        row={'question_id':'q','question':'x'};e=memory_entry(row,{'answer':'new'})
        self.assertIn('new',context([e])[0])
    def test_exact_decoded_pixels_and_no_future(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);Image.new('RGB',(3,3),'white').save(p/'a.png');Image.new('RGB',(3,3),'white').save(p/'b.bmp');Image.new('RGB',(3,3),'black').save(p/'c.png')
            rs=[{'question_id':str(i),'images':[x]} for i,x in enumerate(['a.png','c.png','b.bmp'])]
            plan=schedule(rs,p);self.assertEqual(plan[0]['previous_ids'],[]);self.assertEqual(plan[1]['previous_ids'],[]);self.assertEqual(plan[2]['previous_ids'],['0'])
    def test_multi_image_order_binding(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);Image.new('RGB',(2,2),'white').save(p/'a.png');Image.new('RGB',(2,2),'black').save(p/'b.png')
            self.assertNotEqual(image_key({'images':['a.png','b.png']},p),image_key({'images':['b.png','a.png']},p))
class PolicyTests(unittest.TestCase):
    def test_policy_dispatch_and_completion(self):
        from types import SimpleNamespace
        from run_cxr_image_memory_r44 import run_episode
        seen=[]
        class Paid:
            def call(self,row,arm,n,messages,**kw):seen.append((arm,n));return '{"answer":"Yes","reason":"seen"}'
        def ep(*args,**kwargs):
            paid=args[6];paid.call(args[0],args[1],1,[{'role':'user','content':'image'}])
            return {'answer':None,'reason':None,'status':'missing_invalid_final_json','main_calls':1,'tool_calls':0,'observations':[]}
        base=SimpleNamespace(agent_system=lambda arm:'original',episode=ep)
        completion=SimpleNamespace(decision=lambda *x:'complete_once',prompt=lambda row:'final',accepted_reply=lambda row,raw:{'answer':'Yes','reason':'seen','status':'completed'})
        r41=SimpleNamespace(episode=lambda *x: {'answer':'A','status':'completed','main_calls':1,'tool_calls':0})
        r=run_episode(base,r41,completion,{'question_id':'q'},'M',None,{}, {},None,Paid(),None,'memory')
        self.assertEqual(seen,[('M43-IM',1),('M43-IM',2)]);self.assertEqual(r['answer'],'Yes');self.assertEqual(r['main_calls'],2)
        self.assertEqual(base.agent_system('M'),'original')
    def test_c41_does_not_use_M_completion(self):
        from types import SimpleNamespace
        from run_cxr_image_memory_r44 import run_episode
        def bad(*x,**k):raise AssertionError('wrong branch')
        base=SimpleNamespace(agent_system=lambda arm:'original',episode=bad)
        r41=SimpleNamespace(episode=lambda *a:{'answer':'B','status':'completed','main_calls':1,'tool_calls':0})
        r=run_episode(base,r41,SimpleNamespace(decision=bad),{},'C41',None,{}, {},None,None,None,'memory')
        self.assertEqual(r['answer'],'B')

class ActualHealthRegressions(unittest.TestCase):
    def test_nested_classifier_kernel_failure_is_not_memory(self):
        obs={'status':'completed','observation':{'finding_scores':{'error':'CUDA error: device kernel image is invalid'}},
             'actual_model_events':[{'status':'failed'}]}
        self.assertIsNotNone(tool_failure_reason(obs))
        self.assertEqual(memory_entry({'question_id':'q','question':'x'},{'answer':'A','observations':[obs]})['tool_evidence'],[])

    def test_maira_failed_empty_error_rejected_but_no_finding_valid(self):
        failed={'status':'completed','observation':[{'error':''},{'analysis_status':'failed','error_details':''}]}
        valid={'status':'completed','observation':[{'predictions':[]},{'analysis_status':'completed_no_finding'}]}
        self.assertIsNotNone(tool_failure_reason(failed));self.assertIsNone(tool_failure_reason(valid))

    def test_bound_tools_stops_before_next_inference(self):
        from run_cxr_image_memory_r44 import BoundTools
        from types import SimpleNamespace
        raw={'status':'completed','observation':[{'error':'missing DICOM metadata'},{'analysis_status':'failed'}]}
        bound=BoundTools(SimpleNamespace(call=lambda *args:raw))
        with self.assertRaisesRegex(RuntimeError,'tool_unhealthy_stop'):bound.call({}, {}, 'M',1)

    def test_saved_response_unknown_elapsed_preserved(self):
        from score_cxr_image_memory_r44 import resource_report
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);folder=root/'calls/M43-IM/q/1'
            write(folder/'started.json',{})
            write(folder/'response.json',{})
            write(folder/'result.json',{'elapsed_s':None,'usage':{'prompt_tokens':1,'completion_tokens':1},
                'settlement':{'charged_cny':'0.000016'},'model_returned':'qwen3.7-plus'})
            result=resource_report(root,[{'reused_M43':False,'elapsed_s':None}])
            self.assertEqual(result['model_request_elapsed_seconds_known'],0)
            self.assertEqual(result['unknown_request_elapsed_count'],1)
            self.assertEqual(result['unknown_episode_elapsed_count'],1)
if __name__=='__main__':unittest.main()
