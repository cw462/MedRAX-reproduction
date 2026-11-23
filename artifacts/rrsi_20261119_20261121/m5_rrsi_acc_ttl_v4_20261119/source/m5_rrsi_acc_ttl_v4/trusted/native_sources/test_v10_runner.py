"""V10 integration without API calls: real crop tool, tracker, budgets and messages."""
import base64
import copy
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import memory_agent_eval as mae
import run_v10_accuracy as runner


class FakeBudgetedModel:
    def __init__(self, model, ledger, ctx, profile):
        self.model, self.ctx = model, ctx

    def invoke(self, messages):
        self.ctx['budget'].reserve('model', 'synthetic')
        self.ctx['actual_model_calls'] += 1
        self.ctx['usage_records'].append({'input_tokens':10,'output_tokens':5,'total_tokens':15})
        return self.model.invoke(messages)


class QueueModel:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.calls.append(copy.deepcopy(messages))
        result = self.replies.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def candidate(answer='B'):
    return {'answer':answer,'uncertain':True,'changed_attributes':['contour'],
            'evidence_refs':['image:1'],'observations':[],'missing_evidence':['fine detail']}


class V10IntegrationTests(unittest.TestCase):
    def prepare(self, folder, replies):
        from PIL import Image
        path=Path(folder)/'original.png'
        Image.new('RGB',(24,16),(23,49,71)).save(path)
        model=QueueModel(replies)
        runtime=SimpleNamespace(model=model,tools={},tool_provenance={})
        args=SimpleNamespace(run_id='synthetic_v10',artifact_root=Path(folder)/'artifacts',
            max_output_tokens=1024,max_case_seconds=120)
        row={'question_id':'synthetic_q','question':'Synthetic question\nA) first\nB) second','images':[path.name]}
        retriever=SimpleNamespace(retrieve=lambda *args,**kwargs:{'k_block':'','e_block':'','k_ids':[],'e_ids':[]})
        return path,model,runtime,args,row,retriever

    def run_branch(self, prepared, folder, initial='A'):
        path,model,runtime,args,row,retriever=prepared
        plan=runner.normalize_plan('',row,['image:1'])
        with patch.object(mae,'BudgetedModel',FakeBudgetedModel):
            result=runner.run_branch(runtime,None,None,args,row,[path],initial,[],plan,
                io.StringIO(),retriever,'V',Path(folder)/'branch')
        return result

    def test_two_real_crops_reach_next_request_and_gate_with_exact_model_cap(self):
        from langchain_core.messages import AIMessage
        from PIL import Image
        with TemporaryDirectory() as folder:
            path=Path(folder)/'original.png'
            replies=[AIMessage(content='',tool_calls=[{'name':'crop_current_image',
                'args':{'image_path':str(path),'box':[0,0,.5,.5]},'id':'crop1','type':'tool_call'}]),
                AIMessage(content='',tool_calls=[{'name':'crop_current_image',
                'args':{'image_path':str(path),'box':[.5,.5,1,1]},'id':'crop2','type':'tool_call'}]),
                AIMessage(content=json.dumps(candidate())),
                AIMessage(content=json.dumps({'decision':'accept','changed_attributes':['contour'],
                    'evidence_refs':['V:tool:1:image:1'],'unmet_requirements':[],
                    'reason':'Synthetic crop has the specified pixel pattern.'}))]
            prepared=self.prepare(folder,replies)
            result=self.run_branch(prepared,folder)
            model=prepared[1]
            self.assertEqual(result['candidate'],'B')
            self.assertEqual(result['final'],'B')
            self.assertIsNone(result['candidate_error'])
            self.assertIsNone(result['gate_error'])
            self.assertEqual(result['candidate_accounting']['tool_calls'],2)
            self.assertEqual(result['candidate_accounting']['model_calls'],3)
            self.assertEqual(result['gate_accounting']['model_calls'],1)
            self.assertEqual(result['shared_plan_slot'],1)
            self.assertEqual(len(model.calls),4)
            self.assertFalse(model.replies)
            def dimensions(messages):
                payloads=[p['image_url']['url'] for m in messages if isinstance(m.content,list)
                    for p in m.content if isinstance(p,dict) and p.get('type')=='image_url']
                return [Image.open(io.BytesIO(base64.b64decode(p.split(',',1)[1]))).size for p in payloads]
            self.assertEqual(dimensions(model.calls[0]),[(24,16)])
            self.assertEqual(dimensions(model.calls[1]),[(24,16),(12,8)])
            self.assertEqual(dimensions(model.calls[2]),[(24,16),(12,8),(12,8)])
            self.assertEqual(dimensions(model.calls[3]),[(24,16),(12,8),(12,8)])
            for messages in model.calls[:3]:
                self.assertNotIn('"initial": "A"','\n'.join(str(m.content) for m in messages))
            self.assertIn('"initial": "A"',model.calls[3][-1].content)

    def test_letter_repair_remains_inside_three_additional_requests(self):
        from langchain_core.messages import AIMessage
        with TemporaryDirectory() as folder:
            prepared=self.prepare(folder,[AIMessage(content='No further tool needed.'),
                AIMessage(content='{"answer":null}'),AIMessage(content='B')])
            result=self.run_branch(prepared,folder,initial='B')
            self.assertEqual(result['candidate'],'B')
            self.assertEqual(result['candidate_accounting']['model_calls'],3)
            self.assertEqual(result['candidate_recovery'],'letter_only_within_cap')
            self.assertEqual(result['gate']['decision'],'no_change')

    def test_plan_bad_optional_types_do_not_remove_visual_opportunity(self):
        row={'question':'A) first\nB) second'}
        for values in ({'option_labels':None,'image_ids':None},
                       {'option_labels':[{}],'image_ids':[{}]}):
            text=json.dumps({'option_differences':[dict(question='Compare contours',**values)]})
            plan=runner.normalize_plan(text,row,['image:1'])
            self.assertTrue(plan['option_differences'])
            self.assertEqual(plan['option_differences'][0]['image_ids'],['image:1'])

    def test_earlier_legal_independent_answer_survives_failed_final_and_repair(self):
        from langchain_core.messages import AIMessage
        with TemporaryDirectory() as folder:
            prepared=self.prepare(folder,[AIMessage(content=json.dumps(candidate('A'))),
                AIMessage(content='bad schema'),AIMessage(content='still no answer')])
            result=self.run_branch(prepared,folder,initial='A')
            self.assertEqual(result['candidate'],'A')
            self.assertEqual(result['final'],'A')
            self.assertIsNone(result['candidate_error'])
            self.assertEqual(result['candidate_accounting']['model_calls'],3)
            self.assertIn('previous_independent',result['candidate_recovery'])


if __name__=='__main__':
    unittest.main()
