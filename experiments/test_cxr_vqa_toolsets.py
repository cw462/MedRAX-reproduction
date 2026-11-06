"""Offline protocol simulations: no paid or medical backend requests."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from run_cxr_vqa_toolsets import episode,parse_final,Tools
from score_cxr_vqa_toolsets import normalize,score
from cxr_vqa_extended_backends import geometry


class FakePaid:
    def __init__(self,answers):self.answers=iter(answers);self.n=0;self.system=None
    def call(self,*args):self.n+=1;self.system=args[-1][0]['content'];return json.dumps(next(self.answers))


class FakeTools:
    def __init__(self):self.names=[]
    def call(self,row,call,arm,ordinal):
        self.names.append(call['tool'])
        return {'tool':call['tool'],'status':'completed','observation':{'measurement_applicable':False}}


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        Image.new('RGB',(12,14),'gray').save(self.root/'image.jpg')
        self.row={'question_id':'q1','question':'Is there a finding?','images':['image.jpg'],'image_id':'i1'}
        self.protocol={'main_call_limits':{'D':1,'M':4,'C':4,'X':2}}
        self.runtime={'tools':{'t':{'description':'mock backend'}},'arms':{a:{'tools':['t']} for a in 'DMCX'}}
    def tearDown(self):self.tmp.cleanup()
    def test_exact_answers_only(self):
        self.assertNotEqual(normalize('no evidence'),normalize('no'))
        self.assertEqual(normalize(' YES. '),'yes')
        self.assertIsNone(parse_final('{"reason":"yes"}')['answer'])
        self.assertIsNone(parse_final('{"answer":"yes","reason":"x"}{"answer":"no"}')['answer'])
    def test_direct_one_call(self):
        paid=FakePaid([{'answer':'yes','reason':'visible'}]);tools=FakeTools()
        r=episode(self.row,'D',self.root,self.protocol,self.runtime,self.root,paid,tools)
        self.assertEqual((paid.n,tools.names,r['answer']),(1,[],'yes'))
    def test_c_edv_expert_and_arbitration_count(self):
        paid=FakePaid([{'calls':[{'tool':'t','args':{}}]}, {'validation':[],'collaboration_needed':True,'expert_task':'localization'},
                       {'findings':'uncertain'}, {'answer':'no','reason':'visible'}]);tools=FakeTools()
        r=episode(self.row,'C',self.root,self.protocol,self.runtime,self.root,paid,tools)
        self.assertEqual((paid.n,len(tools.names),r['answer']),(4,1,'no'))
        self.assertIn('Intermediate planning',paid.system)
        self.assertIn('Only at the FINAL ANSWERING stage',paid.system)
    def test_x_failed_gate_never_zero_fills_or_measures(self):
        paid=FakePaid([{'calls':[]}, {'answer':'no','reason':'pixels'}]);tools=FakeTools()
        episode(self.row,'X',self.root,self.protocol,self.runtime,self.root,paid,tools)
        self.assertEqual((paid.n,tools.names),(2,['view_check']))
    def test_more_than_two_actions_is_missing(self):
        paid=FakePaid([{'calls':[{'tool':'t','args':{}}]*3}]);tools=FakeTools()
        r=episode(self.row,'M',self.root,self.protocol,self.runtime,self.root,paid,tools)
        self.assertEqual(r['status'],'missing_invalid_tool_plan');self.assertEqual(tools.names,[])
    def test_uncached_tool_sends_selected_name_to_worker(self):
        runtime = {'tools': {'t': {'backend': 'backend', 'python': 'python'}}, 'backend_config': {}}
        tools = Tools(runtime, self.root, self.root)
        with patch('run_cxr_vqa_toolsets.subprocess.run') as worker:
            worker.return_value.returncode = 0
            worker.return_value.stdout = 'CXR_VQA_RESULT={"status":"completed"}'
            worker.return_value.stderr = ''
            result = tools.call(self.row, {'tool': 't'}, 'M', 1)
        self.assertEqual(json.loads(worker.call_args.kwargs['input'])['tool'], 't')
        self.assertEqual(result['status'], 'completed')
    def test_scoring_requires_all_arms(self):
        (self.root/'inputs.jsonl').write_text(json.dumps(self.row)+'\n')
        (self.root/'references.jsonl').write_text(json.dumps({'question_id':'q1','answer':'yes'})+'\n')
        with self.assertRaisesRegex(ValueError,'generation_not_complete'):score(self.root,self.root,self.root/'analysis')
    def test_geometry_known_rectangle_ratio(self):
        import numpy as np
        masks=np.zeros((4,100,100),dtype=bool)
        masks[0,20:80,10:40]=True;masks[1,20:80,60:90]=True
        masks[2,40:65,35:65]=True;masks[3,10:70,48:52]=True
        info={'original_size':[100,100],'labels':{'0':'lung left','1':'lung right','2':'heart','3':'trachea'}}
        result=geometry(masks,info)
        self.assertTrue(result['measurement_available']);self.assertEqual(result['values']['CTR'],30/80)
        masks[3]=False;result=geometry(masks,info)
        self.assertFalse(result['measurement_available']);self.assertIsNone(result['values'])


if __name__=='__main__':unittest.main()
