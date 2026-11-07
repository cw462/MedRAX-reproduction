import sys,unittest,tempfile,json,copy
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from cxr_action_skill_r41 import select
from run_cxr_action_r41 import episode,dispatch_frozen,answer,parse

ROW={'question_id':'q','image_id':'i','question':'Is there an abnormality?','images':['a']}
CARD={'id':'c','source_ids':['s'],'topic':'Inspect bilateral regions','tasks':['presence'],'requires_pair':False,'required_question_terms':[],
'actions':[{'observe':'Inspect corresponding regions','tool':'none','when':'Relevant anatomy visible','stop':'Sufficient observation'}],
'avoid':'Do not infer absence from unavailable regions','source_evidence':'Source review supports comparison','kind':'task'}
class Tests(unittest.TestCase):
    def test_task_card_no_lexical_gate(self):self.assertEqual(select(ROW,[CARD],[])['selected_ids'],['c'])
    def test_specific_not_generalized(self):self.assertEqual(select(ROW,[dict(CARD,kind='specific')],[])['selected_ids'],[])
    def test_labels_do_not_change_mask(self):self.assertEqual(select(ROW,[CARD],[]),select(dict(ROW,answer='secret',correct=True),[CARD],[]))
    def test_requirements(self):
        self.assertFalse(select(ROW,[dict(CARD,required_question_terms=['postoperative'])],[])['selected_ids'])
        self.assertFalse(select(ROW,[dict(CARD,requires_pair=True)],[])['selected_ids'])
    def test_one_card(self):self.assertEqual(len(select(ROW,[CARD,dict(CARD,id='d')],[])['selected_ids']),1)
    def test_auxiliary_not_reject_answer(self):self.assertEqual(answer(parse('```json\n{"answer":"No","evidence":{"effect":"contradicts normal x ray"}}\n```'))['answer'],'No')
    def test_reuse_never_calls(self):
        frozen={'mask':{'q':{'selected_ids':[]}},'history':{'q':{'answer':'Yes','reason':'old'}},'historical_sha256':'hash'}
        for arm in ['M-S41','M-C41']:
            r=dispatch_frozen(None,frozen,ROW,arm,None,None,None,None,None,None)
            self.assertEqual((r['answer'],r['main_calls'],r['tool_calls']),('Yes',0,0))
    def test_historical_null_reused(self):
        frozen={'mask':{'q':{'selected_ids':[]}},'history':{'q':{'answer':None,'status':'missing_invalid_final_json'}},'historical_sha256':'hash'}
        r=dispatch_frozen(None,frozen,ROW,'M-S41',None,None,None,None,None,None)
        self.assertIsNone(r['answer']);self.assertEqual(r['status'],'missing_invalid_final_json')
    def test_added_task_recognition(self):
        import cxr_skill_r41_base as b
        self.assertIn('count',b.infer_tasks('How many lesions?'))
        self.assertIn('morphology',b.infer_tasks('Describe the opacity pattern'))
        self.assertIn('relation',b.infer_tasks('Is the trachea displaced?'))
    def fake(self,raws):
        sent=[];calls=[]
        base=SimpleNamespace(agent_system=lambda arm:'zero, one or two registered tools',content=lambda *x:'image',ACTION='At most two selectable tool calls total.',
            evidence_catalog=lambda *x:[],resolve_action=lambda a,o:a,append_observations=lambda m,o,*x:m.append({'role':'user','content':str(o)}))
        def validate(o,r,a,remaining,images):
            c=o['calls']
            if len(c)>remaining:raise ValueError('budget')
            return c
        base.validate_actions=validate
        def call(*args):sent.append(copy.deepcopy(args[-1]));return raws[len(sent)-1]
        def tool(*args):calls.append(args);return {'status':'completed','observation':{'finding':'x'}}
        return base,SimpleNamespace(call=call),SimpleNamespace(call=tool),sent,calls
    def run_loop(self,raws):
        b,p,t,s,c=self.fake(raws);r=episode(b,ROW,'M-S41',None,{'main_call_limits':{'M-S41':6},'tool_call_limits':{'M-S41':4}},None,None,p,t,'skill')
        return r,s,c
    def test_direct_early_stop(self):
        r,s,c=self.run_loop(['{"answer":"Yes","reason":"image"}']);self.assertEqual((r['main_calls'],len(c)),(1,0))
    def test_four_tool_cap_and_final(self):
        plan=json.dumps({'calls':[{'tool':'t','args':{}}]})
        r,s,c=self.run_loop([plan]*4+['{"answer":"Yes"}'])
        self.assertEqual((r['main_calls'],len(c)),(5,4));self.assertIn('no further tools',s[-1][-1]['content'])
    def test_six_main_cap(self):
        r,s,c=self.run_loop(['{"calls":[]}']*5+['{"answer":"No"}']);self.assertEqual(r['main_calls'],6)
    def test_no_duplicate_observations(self):
        plan=json.dumps({'calls':[{'tool':'t','args':{}}]})
        r,s,c=self.run_loop([plan]*2+['{"answer":"Yes"}'])
        obs=[x for x in s[-1] if x['role']=='user' and 'finding' in str(x['content'])]
        self.assertEqual(len(obs),2)
    def test_overbudget_plan_not_executed(self):
        r,s,c=self.run_loop([json.dumps({'calls':[{'tool':'t'}]*5})]);self.assertEqual(len(c),0)
if __name__=='__main__':unittest.main()
