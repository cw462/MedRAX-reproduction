import unittest,sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from skill_lifecycle_r49 import *
C={'name':'Check region','description':'Inspect evidence','applicable_conditions':'When region matters','branch':'task_level','tool_name':None,'task_category':'location','required_tools':[],'risk_level':'low','core_action':'Inspect original region and stop after resolving laterality.'}
class Tests(unittest.TestCase):
 def setup_repo(self):
  r=initial();sid=commit(r,'CREATE',copy.deepcopy(C),[1.,0.],['s'],[]);return r,sid
 def test_create_patch_history(self):
  r,s=self.setup_repo();c=dict(C,core_action='New source supported action');commit(r,'PATCH',c,[1.,0.],['t'],[],s);self.assertEqual(len(r['skills'][s]['versions']),1)
 def test_frozen_write_rejected(self):
  r,s=self.setup_repo();r['frozen']=True
  with self.assertRaises(ValueError):commit(r,'CREATE',C,[1.,0.],['s'],[])
 def test_task_routing(self):
  r,s=self.setup_repo();self.assertEqual(retrieve(r,[1.,0.],'presence',[],DEFAULTS),[]);self.assertEqual(retrieve(r,[1.,0.],'location',[],DEFAULTS)[0]['id'],s)
 def test_negative_credit(self):
  r,s=self.setup_repo();t={'id':'t','category':'location','reward':0,'injected':[s],'steps':[{}]}
  a={'t':{'skill_adoption':[{'skill_id':s,'status':'ADOPTED_NEGATIVE','step_index':0,'evidence':'used wrong location'}]}}
  assess(r,[t],a,DEFAULTS);self.assertLess(r['skills'][s]['u'],.5)
 def test_ignored_no_credit(self):
  r,s=self.setup_repo();t={'id':'t','category':'location','reward':1,'injected':[s],'steps':[{}]}
  assess(r,[t],{'t':{'skill_adoption':[{'skill_id':s,'status':'IGNORED'}]}},DEFAULTS);self.assertEqual(r['skills'][s]['u'],.5)
 def test_adoption_requires_actual_injection(self):
  r,s=self.setup_repo();t={'id':'t','category':'location','reward':1,'injected':[],'steps':[{}]}
  with self.assertRaises(ValueError):assess(r,[t],{'t':{'skill_adoption':[{'skill_id':s,'status':'IGNORED'}]}},DEFAULTS)
 def test_buffer_filters_and_balance(self):
  ts=[{'id':str(i),'category':'location','reward':i%2,'injected':[],'steps':[{'n':j} for j in range(3)]} for i in range(30)]
  chosen=buffer_select(ts,DEFAULTS);self.assertEqual(len(chosen),20);self.assertEqual(sum(x['reward'] for x in chosen),10)
  self.assertFalse(gate(dict(ts[0],technical_failure=True)));self.assertFalse(gate(dict(ts[0],reward=1,steps=[{}])))
 def test_govern_merge_and_deprecate(self):
  r,s=self.setup_repo();other=commit(r,'CREATE',dict(C,name='Another'),[1.,0.],['t'],[])
  events=govern(r,DEFAULTS,lambda *args:(dict(C),[1.,0.]));self.assertTrue(any(x[0]=='merge' for x in events))
  active=[m for m in r['skills'].values() if m['status']=='active'][0];active.update(u=.1,usage=2)
  govern(r,DEFAULTS,lambda *x:None);self.assertEqual(active['status'],'deprecated')
 def test_lr(self):self.assertAlmostEqual(learning_rate(5,DEFAULTS),.2);self.assertAlmostEqual(learning_rate(25,DEFAULTS),.05)
 def test_capacity(self):
  r=initial()
  for i in range(10):commit(r,'CREATE',dict(C,name=str(i)),[1.,0.],['s'],[])
  govern(r,DEFAULTS,lambda *x:None);self.assertEqual(sum(m['status']=='active' for m in r['skills'].values()),8)
 def test_duplicate_adoption_cannot_double_count_credit(self):
  r,s=self.setup_repo();t={'id':'t','category':'location','reward':1,'injected':[s],'steps':[{}]}
  item={'skill_id':s,'status':'ADOPTED_POSITIVE','step_index':0,'evidence':'actual action'}
  with self.assertRaises(ValueError):assess(r,[t],{'t':{'skill_adoption':[item,item]}},DEFAULTS)
 def test_two_local_patches_preserve_each_others_unrelated_fields(self):
  import tempfile
  from skill_evolve_r49 import evolve
  from skill_prompts_r49 import ANALYZE,MUTATE,REVIEW
  r,s=self.setup_repo()
  class Patcher:
   def embed(self,text):return [0.,1.]
   def meta(self,event,system,payload,*args):
    if system==ANALYZE:return {'output_intent':'PATCH','skill_adoption':[]}
    if system==MUTATE:
     section='description' if event=='mutation_a' else 'core_action'
     return {'operation':'PATCH','patch_target_id':s,'patch_section':section,'patch_content':'updated '+section}
    if system==REVIEW:return {'quality':True,'duplicate_of':None}
    raise AssertionError(event)
  batch=[{'id':q,'row':{'question_id':q},'category':'location','reward':0,'injected':[],
          'steps':[{'n':j} for j in range(3)]} for q in ('a','b')]
  with tempfile.TemporaryDirectory() as d:
   updated=evolve(Patcher(),r,batch,0,Path(d),Path(d),[],dict(DEFAULTS,govern_every=99))
  self.assertEqual(updated['skills'][s]['c']['description'],'updated description')
  self.assertEqual(updated['skills'][s]['c']['core_action'],'updated core_action')
  self.assertEqual(len(updated['skills'][s]['versions']),2)
if __name__=='__main__':unittest.main()

class ExecutorTests(unittest.TestCase):
 def test_more_than_six_main_and_four_tools_allowed(self):
  import types,json
  from unittest.mock import patch
  from skill_services_r49 import Services
  service=Services.__new__(Services);service.runtime={};service.out=Path('/tmp/test_r49')
  count={'main':0,'tools':0}
  def paid(row,arm,n,messages):
   count['main']+=1
   return json.dumps({'calls':[{'tool':'t','args':{'region':n}}]}) if n<=7 else json.dumps({'answer':'Yes','reason':'evidence'})
  def tool(*args):count['tools']+=1;return {'status':'completed','observation':'seen'}
  service.paid=types.SimpleNamespace(call=paid);service.tools=types.SimpleNamespace(call=tool)
  service.base=types.SimpleNamespace(agent_system=lambda a:'base',content=lambda *x:[],ACTION='tool catalog:',evidence_catalog=lambda *x:{},
    validate_actions=lambda o,*x:o['calls'],resolve_action=lambda x,o:x,append_observations=lambda *x:None)
  parsing=types.ModuleType('run_cxr_action_r41');parsing.parse=json.loads;parsing.answer=lambda x:dict(x,status='completed') if 'answer' in x else None
  completion=types.ModuleType('cxr_task_completion_r43');completion.prompt=lambda r:'final';completion.unscorable=lambda *x:False
  with patch.dict(sys.modules,{'run_cxr_action_r41':parsing,'cxr_task_completion_r43':completion}):
   result,steps=service.execute({'question_id':'q','question':'x','images':['a']},'unbounded','.',None)
  self.assertEqual(result['main_calls'],8);self.assertEqual(result['tool_calls'],7)
