import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from cxr_skill_v2 import load_bank, select, validate_card
from normalize_cxr_q_v2 import normalize


def card():
    return {'id':'s1','source_ids':['s1'],'topic':'Left lung opacity location',
            'tasks':['location','presence'],'requires_pair':False,'required_question_terms':[],
            'actions':[{'observe':'Inspect the left lung opacity boundary.','tool':'none',
                        'when':'An opacity is visible.','stop':'Stop if the asked side is supported by the original.'}],
            'avoid':'Do not transfer the old answer.','source_evidence':'Source feedback and recorded finding disagree on side.'}

def row(q='Is there opacity in the left lung?',images=None):
    return {'question_id':'q1','question':q,'images':images or ['a.png'],'options':{}}

class RetrievalTests(unittest.TestCase):
    def test_relevant_card(self):
        text,trace=select(row(),[card()],[])
        self.assertEqual(trace['selected_ids'],['s1']); self.assertIn('Inspect',text)
    def test_generic_chest_match_abstains(self):
        self.assertIsNone(select(row('What is shown in this chest image?'),[card()],[])[0])
    def test_pair_requires_images_and_temporal_question(self):
        c=card();c['requires_pair']=True;c['tasks']=['comparison'];c['topic']='interval left lung opacity'
        self.assertIsNone(select(row('Has the left opacity increased?'),[c],[])[0])
        self.assertIsNotNone(select(row('Has the left opacity increased?',['a','b']),[c],[])[0])
    def test_history_unknown_blocks(self):
        c=card();c['required_question_terms']=['postoperative']
        self.assertIsNone(select(row(),[c],[])[0])
    def test_option_cannot_supply_history(self):
        c=card();c['required_question_terms']=['postoperative'];r=row();r['options']={'A':'postoperative opacity'}
        self.assertIsNone(select(r,[c],[])[0])
    def test_unregistered_tool_rejected(self):
        c=card();c['actions'][0]['tool']='invented'
        with self.assertRaises(ValueError):validate_card(c,[])
    def test_max_two(self):
        cs=[]
        for i in range(4):
            c=card();c['id']=str(i);cs.append(c)
        self.assertEqual(len(select(row(),cs,[])[1]['selected_ids']),2)
    def test_source_answer_not_injected(self):
        c=card();c['source_evidence']='SECRET_SOURCE_ANSWER'
        self.assertNotIn('SECRET_SOURCE_ANSWER',select(row(),[c],[])[0])
    def test_labels_cannot_change_selection(self):
        r=row();old=select(r,[card()],[]);r['answer']='A';r['reference']='B';r['correct']=True
        self.assertEqual(old,select(r,[card()],[]))
    def test_hash_frozen(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bank.json';p.write_text(json.dumps({'schema':'cxr_skill_v2','source_only':True,'frozen':True,'items':[card()]}))
            sha=hashlib.sha256(p.read_bytes()).hexdigest();self.assertEqual(len(load_bank(p,sha,[])),1)
            p.write_text(p.read_text()+' ')
            with self.assertRaises(ValueError):load_bank(p,sha,[])
    def test_input_not_mutated(self):
        r=row();c=card();before=copy.deepcopy((r,c));select(r,[c],[]);self.assertEqual((r,c),before)

class FormatTests(unittest.TestCase):
    def test_wrapped_and_direct_equal(self):
        obj={'q':{'answer':'Yes','reason':'visible'}}
        self.assertEqual(normalize('```json\n'+json.dumps({'answers':obj})+'\n```',['q']),normalize(json.dumps(obj),['q']))
    def test_no_reason_answer_inference(self):
        with self.assertRaises(ValueError):normalize('{"q":{"reason":"answer yes"}}',['q'])
    def test_duplicate_keys_rejected(self):
        with self.assertRaises(ValueError):normalize('{"q":{},"q":{}}',['q'])
    def test_wrong_id_rejected(self):
        with self.assertRaises(ValueError):normalize('{"x":{"answer":"yes","reason":"ok"}}',['q'])
    def test_prose_not_extracted(self):
        with self.assertRaises(ValueError):normalize('Answer: yes',['q'])

class RunnerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Simulate the actual upstream contract without importing API clients or GPU libraries.
        fake=types.ModuleType('run_cxr_vqa_toolsets')
        fake.agent_system=lambda arm:'Rules. No cross-case skills, sibling question context or additional patient history is available.'
        class Tools:
            def call(self,*args):return self.result
        fake.Tools=Tools
        cls.previous=sys.modules.get('run_cxr_vqa_toolsets');sys.modules['run_cxr_vqa_toolsets']=fake
        spec=importlib.util.spec_from_file_location('runner_under_test',ROOT/'experiments/run_cxr_skill_v2.py')
        cls.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.module)
    @classmethod
    def tearDownClass(cls):
        if cls.previous is None:sys.modules.pop('run_cxr_vqa_toolsets',None)
        else:sys.modules['run_cxr_vqa_toolsets']=cls.previous
    def test_memory_system_not_contradictory(self):
        self.assertNotIn('No cross-case skills',self.module.system('M-S'))
        self.assertIn('No cross-case skills',self.module.system('M'))
    def test_failed_tool_stops(self):
        x=self.module.HealthyTools();x.result={'status':'failed','observation':None}
        with self.assertRaises(RuntimeError):x.call({}, {'tool':'report'},'M-S',1)
    def test_unknown_tool_stops(self):
        x=self.module.HealthyTools();x.result={'status':'started_unknown','observation':None}
        with self.assertRaises(RuntimeError):x.call({}, {'tool':'report'},'M',1)
    def test_valid_tool_passes(self):
        x=self.module.HealthyTools();x.result={'status':'completed','observation':{'finding':'unknown'}}
        self.assertEqual(x.call({}, {'tool':'report'},'M',1),x.result)

if __name__=='__main__':unittest.main()
