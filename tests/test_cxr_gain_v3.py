import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from cxr_evidence_v3 import episode,parse_decision,strip_json_fence

def decision(answer='A',tool=None,source='original:1',args=None):
    return {'answer':answer,'reason':'Short reason.','evidence':[{'source':source,'finding':'A visible attribute.','effect':'supports'}],
            'check':None if tool is None else {'attribute':'laterality','alternatives':['unilateral','bilateral'],
            'question':'Inspect the contralateral lung.','tool':tool,'args':args or {},'image_index':1}}

class Base:
    @staticmethod
    def content(row,data):return [{'type':'text','text':row['question']}]
    @staticmethod
    def evidence_catalog(runtime,arm):return {'qa':'args={}', 'report':'args={}'}
    @staticmethod
    def resolve_action(action,observations):return action
    @staticmethod
    def append_observations(messages,observations,out,arm):
        messages.append({'role':'user','content':'observations:'+json.dumps(observations)})

class Paid:
    def __init__(self,seq):self.seq=seq;self.calls=[]
    def call(self,row,arm,ordinal,messages):
        self.calls.append(copy.deepcopy(messages));x=self.seq[ordinal-1]
        return x if isinstance(x,str) else json.dumps(x)
class Tools:
    def __init__(self,failed=False):self.calls=[];self.failed=failed
    def call(self,row,action,arm,ordinal):
        self.calls.append(action)
        return {'tool':action['tool'],'status':'failed' if self.failed else 'completed',
                'observation':None if self.failed else {'finding':'tool claim'},'derived_images':[]}

class EvidenceEpisodeTests(unittest.TestCase):
    def run_case(self,seq,tools=None):
        paid=Paid(seq);tools=tools or Tools();row={'question_id':'q','question':'Which side?','images':['a'],'options':{'A':'unilateral','B':'bilateral'}}
        with tempfile.TemporaryDirectory() as temp:
            result=episode(Base,row,'M-A',Path(temp),{'main_call_limits':{'M-A':4}}, {},Path(temp),paid,tools)
        return result,paid,tools
    def test_easy_question_stops_one_call(self):
        r,p,t=self.run_case([decision()]);self.assertEqual((r['answer'],len(p.calls),len(t.calls)),('A',1,0))
    def test_valid_new_evidence_can_correct_first_answer(self):
        r,p,t=self.run_case([decision(tool='qa'),decision('B',source='tool:T1')])
        self.assertEqual(r['answer'],'B');self.assertTrue(r['revised']);self.assertEqual(r['tool_calls'],1)
    def test_disagreeing_tool_need_not_change_answer(self):
        r,_,_=self.run_case([decision(tool='qa'),decision('A')]);self.assertFalse(r['revised'])
    def test_conflict_resolves_second_check(self):
        r,p,t=self.run_case([decision(tool='qa'),decision(tool='report',source='tool:T1'),decision('B',source='tool:T2')])
        self.assertEqual((r['answer'],r['main_calls'],r['tool_calls']),('B',3,2))
        last=p.calls[-1]
        obs=[x for x in last if isinstance(x['content'],str) and x['content'].startswith('observations:')]
        self.assertEqual(len(obs),2)
        self.assertEqual(len(json.loads(obs[-1]['content'].split(':',1)[1])),1)
    def test_no_third_tool_even_if_requested(self):
        r,p,t=self.run_case([decision(tool='qa'),decision(tool='report'),decision(tool='qa',args={'x':1}),decision('B')])
        self.assertEqual(len(t.calls),2);self.assertLessEqual(len(p.calls),4)
    def test_no_repeated_identical_check(self):
        r,p,t=self.run_case([decision(tool='qa'),decision(tool='qa'),decision('B')]);self.assertEqual(len(t.calls),1)
    def test_format_repair_within_budget(self):
        r,p,t=self.run_case(['bad json',decision()]);self.assertEqual(r['answer'],'A');self.assertEqual(len(p.calls),2)
    def test_all_invalid_never_fabricates_answer(self):
        r,p,t=self.run_case(['bad']*4);self.assertIsNone(r['answer']);self.assertEqual(len(p.calls),4)
    def test_unknown_evidence_id_rejected(self):
        with self.assertRaises(ValueError):parse_decision(json.dumps(decision(source='tool:T7')),1,[],['qa'])
    def test_failed_tool_stops_before_paid_continuation(self):
        p=Paid([decision(tool='qa'),decision('B')]);t=Tools(True)
        with self.assertRaises(RuntimeError):episode(Base,{'question':'Q','question_id':'q','images':['a']},'M-A',Path('.'),{'main_call_limits':{'M-A':4}}, {},Path('.'),p,t)
        self.assertEqual(len(p.calls),1)
    def test_fence_is_mechanical_only(self):
        raw=json.dumps(decision());self.assertEqual(strip_json_fence('```json\n'+raw+'\n```'),raw)
        self.assertEqual(strip_json_fence('The answer is A'),'The answer is A')
    def test_duplicate_json_keys_not_accepted(self):
        with self.assertRaises(ValueError):parse_decision('{"answer":"A","answer":"B"}',1,[],[])
    def test_nonexistent_image_binding(self):
        d=decision(tool='qa');d['check']['image_index']=2
        with self.assertRaises(ValueError):parse_decision(json.dumps(d),1,[],['qa'])
    def test_optional_skill_enters_context_only_when_supplied(self):
        p=Paid([decision()]);t=Tools()
        episode(Base,{'question':'Q','question_id':'q','images':['a']},'M-AS',Path('.'),{'main_call_limits':{'M-AS':4}}, {},Path('.'),p,t,conditioning='OPTIONAL CARD')
        self.assertTrue(any(m['content']=='OPTIONAL CARD' for m in p.calls[0]))

if __name__=='__main__':unittest.main()
