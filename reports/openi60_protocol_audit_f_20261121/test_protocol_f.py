"""Offline fixtures for the shared OpenI60 action protocol."""
import copy
import importlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
NATIVE = Path(__import__('os').environ.get('OPENI60_NATIVE', str(HERE.parent / 'OpenI60_M5_L1_20261121/native')))
PACKAGE = Path(__import__('os').environ.get('OPENI60_PACKAGE', str(HERE.parent / 'OpenI60_M5_L1_20261121')))
sys.path[:0] = [str(HERE/'repair'), str(NATIVE), str(NATIVE/'code/M5/experiments'), str(NATIVE/'code/M5')]
import action_protocol_f as protocol
import toolsets_r54 as native_base
spec=importlib.util.spec_from_file_location('skill_services_r54',HERE/'repair/skill_services_r54.py')
executor=importlib.util.module_from_spec(spec)
sys.modules['skill_services_r54']=executor
spec.loader.exec_module(executor)
from skill_services_r55 import Services
from score_cxr_vqa_extension import grade

ROW = {'question_id':'offline_fixture', 'question':'Which supplied option describes the finding?',
       'options':{'A':'first finding', 'B':'second finding'}, 'images':['original.png']}
RUNTIME = {'arms':{'M':{'tools':['chest_xray_expert','roi_crop','medret','reflect','verify','maira2_grounded_report','xray_phrase_grounding']}},
           'tools':{}}
PLAN = {'calls':[{'tool':'chest_xray_expert','args':{'question':'Describe the visible finding.'}}], 'reason':'Check image evidence'}
FINAL = {'answer':'A', 'reason':'The original image supports this option.'}
ACTION, ANSWER = json.dumps(PLAN), json.dumps(FINAL)


class FixtureTools:
    def __init__(self):
        self.calls=[]
    def call(self,row,action,arm,ordinal):
        self.calls.append((copy.deepcopy(row),copy.deepcopy(action),ordinal))
        return {'tool':action['tool'],'status':'completed','observation':{'fixture':'returned evidence'},'derived_images':[]}


def fixture_service(folder, replies, row=ROW, on_call=None):
    service=Services.__new__(Services)
    service.out=Path(folder)
    service.runtime=copy.deepcopy(RUNTIME)
    service.candidates=[];service.activated=set();service.tools=FixtureTools()
    service.requests=[]
    original_content=[{'type':'text','text':row['question']},
                      *[{'type':'image_url','image_url':{'url':'fixture-bound-original:'+name}} for name in row['images']]]
    service.base=types.SimpleNamespace(
        agent_system=native_base.agent_system, ACTION=native_base.ACTION,
        content=lambda given,data:copy.deepcopy(original_content),
        evidence_catalog=lambda runtime,arm:[], validate_actions=native_base.validate_actions,
        resolve_action=native_base.resolve_action,append_observations=native_base.append_observations)
    replies=iter(replies)
    def call(given,arm,ordinal,messages):
        if on_call:on_call(service,given,ordinal,messages)
        raw=next(replies)
        service.requests.append(copy.deepcopy(messages))
        path=service.out/'calls'/arm/given['question_id']/str(ordinal);path.mkdir(parents=True)
        usage={'prompt_tokens':10*ordinal,'completion_tokens':ordinal,'total_tokens':11*ordinal}
        for name,value in [('request.json',{'messages':messages}),
                           ('response.json',{'choices':[{'message':{'content':raw},'finish_reason':'stop'}],'usage':usage}),
                           ('result.json',{'usage':usage,'settlement':{'charged_cny':ordinal/100}})]:
            (path/name).write_text(json.dumps(value),encoding='utf-8')
        return raw
    service.call=call
    return service


class ContractTests(unittest.TestCase):
    def test_native_r55_inherits_repaired_executor(self):
        self.assertIs(Services.__mro__[1],executor.Services)

    def check_error(self,raw,stage):
        with self.assertRaises(protocol.ProtocolError) as caught:
            protocol.decision(raw,ROW,native_base,RUNTIME)
        self.assertEqual(caught.exception.stage,stage)

    def test_pure_calls(self):
        kind,calls=protocol.decision(ACTION,ROW,native_base,RUNTIME)
        self.assertEqual(kind,'calls');self.assertEqual(calls,PLAN['calls'])
    def test_pure_final(self):
        kind,value=protocol.decision(ANSWER,ROW,native_base,RUNTIME)
        self.assertEqual(kind,'answer');self.assertEqual(value['answer'],FINAL['answer'])
    def test_text_plus_calls(self):self.check_error('Plan:\n'+ACTION,'parse')
    def test_fenced_calls(self):self.check_error('```json\n'+ACTION+'\n```','parse')
    def test_multiple_json_objects(self):self.check_error(ACTION+'\n'+ANSWER,'parse')
    def test_calls_and_answer(self):self.check_error(json.dumps({**PLAN,**FINAL}),'contract')
    def test_unknown_tool(self):
        obj=copy.deepcopy(PLAN);obj['calls'][0]['tool']='unknown_tool'
        self.check_error(json.dumps(obj),'validate_actions')
    def test_non_dict_args(self):
        obj=copy.deepcopy(PLAN);obj['calls'][0]['args']='question'
        self.check_error(json.dumps(obj),'validate_actions')
    def test_wrong_inner_argument_type(self):
        obj=copy.deepcopy(PLAN);obj['calls'][0]['args']['question']=123
        self.check_error(json.dumps(obj),'validate_actions')
    def test_unknown_inner_argument(self):
        obj=copy.deepcopy(PLAN);obj['calls'][0]['args']['image_path']='other.png'
        self.check_error(json.dumps(obj),'validate_actions')
    def test_extra_call_reason(self):
        obj=copy.deepcopy(PLAN);obj['calls'][0]['reason']='wrong level'
        self.check_error(json.dumps(obj),'validate_actions')
    def test_duplicate_keys(self):self.check_error('{"answer":"A","answer":"B","reason":"x"}','parse')
    def test_nonfinite_json(self):self.check_error('{"calls":NaN,"reason":"x"}','parse')
    def test_invalid_original_answer_domain(self):self.check_error('{"answer":"Z","reason":"x"}','contract')
    def test_empty_calls(self):self.check_error('{"calls":[],"reason":"x"}','validate_actions')
    def test_multi_image_binding_requires_original_index(self):
        row={**ROW,'images':['first.png','second.png']}
        with self.assertRaises(protocol.ProtocolError):protocol.decision(ACTION,row,native_base,RUNTIME)
        obj=copy.deepcopy(PLAN);obj['calls'][0]['image_index']=2
        self.assertEqual(protocol.decision(json.dumps(obj),row,native_base,RUNTIME)[1],obj['calls'])
        obj['calls'][0]['image_index']=3
        with self.assertRaises(protocol.ProtocolError):protocol.decision(json.dumps(obj),row,native_base,RUNTIME)
    def test_roi_validation_remains_strict(self):
        for args in ({'box':[0,0,2,1]}, {'box':[0,0,1,1],'zoom':5}, {'box':[0,0,1,1],'extra':1}):
            obj={'calls':[{'tool':'roi_crop','args':args}], 'reason':'inspect'}
            self.check_error(json.dumps(obj),'validate_actions')
    def test_r55_argument_validation(self):
        for name,args in [('reflect',{'reasoning':''}),('verify',{'proposed_answer':'A'}),('medret',{'query':'clinical concept','top_k':4})]:
            self.check_error(json.dumps({'calls':[{'tool':name,'args':args}],'reason':'inspect'}),'validate_actions')
    def test_guard_is_exact_attachment(self):
        self.assertEqual(protocol.FORMAT_GUARD,(HERE/'FORMAT_GUARD.txt').read_text(encoding='utf-8'))


class ExecutorTests(unittest.TestCase):
    def run_episode(self,replies,row=ROW,on_call=None):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        service=fixture_service(temp.name,replies,row,on_call)
        result,steps=service.execute(copy.deepcopy(row),'r49_unbounded',Path(temp.name),None)
        return service,result,steps
    def test_normal_voluntary_direct_answer(self):
        service,result,steps=self.run_episode([ANSWER])
        self.assertEqual((result['status'],result['main_calls'],result['tool_calls']),('completed',1,0))
        self.assertEqual(result['protocol']['repair_calls'],0)
        self.assertEqual(service.tools.calls,[])
    def test_text_calls_repair_can_execute_tools(self):
        service,result,steps=self.run_episode(['Plan:\n'+ACTION,ACTION,ANSWER])
        self.assertEqual((result['main_calls'],result['tool_calls']),(3,1))
        self.assertEqual([s['protocol']['decision_index'] for s in steps],[1,1,2])
        self.assertEqual([s['protocol']['repair_attempt'] for s in steps],[0,1,0])
        self.assertEqual(len(result['observations']),1)
        self.assertIn('SAME decision stage',service.requests[1][-1]['content'])
        self.assertIn('request valid registered tools',service.requests[1][-1]['content'])
    def test_validation_error_repair_can_execute_tools(self):
        bad=copy.deepcopy(PLAN);bad['calls'][0]['reason']='extra'
        service,result,steps=self.run_episode([json.dumps(bad),ACTION,ANSWER])
        self.assertEqual(steps[0]['protocol']['error_stage'],'validate_actions')
        self.assertEqual(result['tool_calls'],1)
    def test_two_repairs_exhausted_is_protocol_failure(self):
        raw='Plan:\n'+ACTION
        service,result,steps=self.run_episode([raw,raw,raw])
        self.assertEqual((result['status'],result['main_calls']),('protocol_failure',3))
        self.assertIsNone(result['answer']);self.assertEqual(result['terminal_raw'],raw)
        self.assertEqual(result['protocol']['repair_calls'],2)
        self.assertEqual(result['protocol']['errors'],3)
        self.assertEqual(result['observations'],[]);self.assertEqual(service.tools.calls,[])
        self.assertTrue(grade(ROW,result,None)[1])
    def test_allow_success_on_second_repair(self):
        service,result,steps=self.run_episode(['bad','bad',ACTION,ANSWER])
        self.assertEqual(result['tool_calls'],1);self.assertEqual(result['status'],'completed')
        self.assertEqual(steps[2]['protocol']['repair_attempt'],2)
    def test_repair_budget_resets_after_executed_tools(self):
        service,result,steps=self.run_episode(['bad','bad',ACTION,'bad','bad',ANSWER])
        self.assertEqual((result['status'],result['main_calls']),('completed',6))
        self.assertEqual(result['protocol']['repair_calls'],4)
        self.assertEqual([s['protocol']['repair_attempt'] for s in steps],[0,1,2,0,1,2])
    def test_rejected_plan_never_becomes_observation(self):
        service,result,steps=self.run_episode(['Plan:\n'+ACTION,ANSWER])
        self.assertEqual(result['observations'],[]);self.assertEqual(service.tools.calls,[])
        self.assertNotIn('returned evidence',json.dumps(service.requests))
    def test_plan_is_rejected_as_a_whole(self):
        obj=copy.deepcopy(PLAN);obj['calls'].append({'tool':'unknown','args':{}})
        service,result,steps=self.run_episode([json.dumps(obj),ANSWER])
        self.assertEqual(service.tools.calls,[]);self.assertEqual(result['tool_calls'],0)
    def test_medical_content_not_rewritten(self):
        raw=json.dumps({'answer':'B','reason':'Fixture: right-sided finding, with uncertainty.'})
        service,result,steps=self.run_episode(['bad',raw])
        self.assertEqual(result['reason'],json.loads(raw)['reason'])
        self.assertEqual(steps[1]['response'],raw)
    def test_all_calls_and_repair_tokens_are_accounted(self):
        service,result,steps=self.run_episode(['bad','bad',ANSWER])
        self.assertEqual(result['protocol']['repair_usage'],{'prompt_tokens':50,'completion_tokens':5,'total_tokens':55})
        self.assertEqual(len(steps),3)
        for i,step in enumerate(steps,1):
            self.assertEqual(step['protocol']['settlement']['charged_cny'],i/100)
            self.assertTrue((service.out/'protocol_events'/ROW['question_id']/f'{i}.json').is_file())
    def test_original_image_payload_and_action_binding_preserved(self):
        row={**ROW,'images':['first.png','second.png']}
        obj=copy.deepcopy(PLAN);obj['calls'][0]['image_index']=2
        service,result,steps=self.run_episode(['bad',json.dumps(obj),ANSWER],row)
        self.assertEqual(service.tools.calls[0][1],obj['calls'][0])
        content=service.requests[0][1]
        self.assertTrue(all(req[1]==content for req in service.requests))
    def test_same_guard_and_original_suffix_for_both_arms(self):
        sys.path.insert(0,str(PACKAGE))
        from openi60.hook import patched_messages
        service,result,steps=self.run_episode([ANSWER])
        messages=service.requests[0]
        suffix=(PACKAGE/'prompts/L1_zh.txt').read_text(encoding='utf-8').strip()
        b0,_,_=patched_messages(messages,'');l1,_,_=patched_messages(messages,suffix)
        self.assertEqual(b0[0]['content'].count(protocol.FORMAT_GUARD),1)
        self.assertEqual(l1[0]['content'].count(protocol.FORMAT_GUARD),1)
        self.assertIn(suffix,l1[0]['content']);self.assertEqual(b0[1:],l1[1:])
    def test_repairs_do_not_repeat_skill_activation(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        service=fixture_service(temp.name,['bad',ANSWER]);activations=[]
        original=service.activate
        def activate(*args):activations.append(args[-1]);return original(*args)
        service.activate=activate
        service.execute(ROW,'r49_unbounded',Path(temp.name),None)
        self.assertEqual(activations,[1])
    def test_tool_failure_is_not_format_failure(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        service=fixture_service(temp.name,[ACTION,ANSWER])
        service.tools.call=lambda *args:{'tool':'chest_xray_expert','status':'failed','observation':None,'error':'fixture backend failure'}
        with patch('skill_services_r54.delivered_failure',side_effect=lambda out,row,used,actual,obs:{**obs,'delivered_to_main_model':True}):
            result,steps=service.execute(ROW,'r49_unbounded',Path(temp.name),None)
        self.assertEqual(result['tool_calls'],1);self.assertEqual(result['protocol']['repair_calls'],0)
        self.assertEqual(result['observations'][0]['status'],'failed')
    def test_native_scorer_preserves_explicit_answer_semantics(self):
        from r54_author_metrics import adapt
        raw='Commentary\n'+ANSWER
        service,result,steps=self.run_episode([raw,raw,raw])
        source={'raw':raw,'call_path':'fixture','ordinal':3,'reuse_chain':[],'evidence_status':'complete','technical_stop':False}
        adapted=adapt(ROW,result,source)
        self.assertEqual(result['status'],'protocol_failure')
        self.assertEqual(adapted['choice'],'A')
    def test_feedback_released_only_after_immutable_prediction(self):
        import run_online_skill_r54 as runner
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        out=Path(temp.name);feedback=[]
        def on_call(service,row,ordinal,messages):
            self.assertEqual(feedback,[])
            self.assertNotIn('reference_annotation',json.dumps(messages))
        service=fixture_service(out/'services',['Plan:\n'+ACTION,ANSWER],on_call=on_call)
        class Vault:
            def after_prediction(inner,qid,predpath):
                self.assertTrue(predpath.is_file())
                self.assertEqual(json.loads(predpath.read_text())['main_calls'],2)
                feedback.append(qid)
                return {'answer':'A','answer_text':'synthetic fixture label'}
        order=[{'question_id':ROW['question_id'],'image_key':'fixture_image','previous_ids':[]}]
        runner.run_stream([copy.deepcopy(ROW)],order,out,out,service,Vault(),[],
                          evolver=runner.disabled_evolve,reward_fn=lambda *args:0,external_memory=None)
        self.assertEqual(feedback,[ROW['question_id']])


if __name__=='__main__':unittest.main()
