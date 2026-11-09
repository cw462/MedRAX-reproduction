import unittest,tempfile,sys,copy,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from run_online_skill_r49 import run_stream,ARM
from online_memory_r49 import ReferenceVault,save_once,read
from skill_lifecycle_r49 import DEFAULTS,commit
C={'name':'Inspect location','description':'Inspect the named region','applicable_conditions':'Location question','branch':'task_level','tool_name':None,'task_category':'location','required_tools':[],'risk_level':'low','core_action':'Inspect original region, resolve laterality before answering.'}
class FakeService:
 def __init__(self,root,fail=None):self.root=root;self.calls=[];self.fail=fail
 def embed(self,text):return [1.,0.]
 def execute(self,row,policy,data,conditioning):
  q=row['question_id'];self.calls.append((q,conditioning))
  assert not (self.root/'feedback'/(q+'.json')).exists()
  if q==self.fail:raise RuntimeError('simulated interruption')
  return {'answer':'Yes','reason':'observed','status':'completed','terminal_raw':'{"answer":"Yes"}',
          'main_calls':3,'tool_calls':0,'observations':[]},[{'step_index':i,'response':str(i)} for i in range(3)]
 def meta(self,*a,**k):raise AssertionError('not needed')
def evolve_fake(service,snapshot,batch,wi,window,data,tools,config):
 r=copy.deepcopy(snapshot);r['clock']+=len(batch);r['window']=wi+1
 if not r['skills']:commit(r,'CREATE',C,[1.,0.],[batch[0]['id']],[])
 return r
def reward(row,result,ref):return int(result['answer']==ref['answer'])
class Tests(unittest.TestCase):
 def fixture(self,root,n=31):
  inputs=[{'question_id':f'q{i:03}','question':'Where is the finding?','images':['same.png']} for i in range(n)]
  order=[{'question_id':r['question_id'],'image_key':'same' if i%2==0 else 'other',
          'previous_ids':[inputs[j]['question_id'] for j in range(i) if j%2==i%2]} for i,r in enumerate(inputs)]
  refs=root/'refs'
  for r in inputs:save_once(refs/(r['question_id']+'.json'),{'question_id':r['question_id'],'answer':'Yes'})
  return inputs,order,ReferenceVault(refs,{r['question_id']:{'file':r['question_id']+'.json'} for r in inputs})
 def test_online_timing_window_and_same_image(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);inputs,order,vault=self.fixture(root);out=root/'run';s=FakeService(out)
   run_stream(inputs,order,root,out,s,vault,[],evolver=evolve_fake,reward_fn=reward)
   self.assertEqual(len(s.calls),31)
   self.assertIsNone(s.calls[0][1]);self.assertIsNone(s.calls[1][1])
   ctx=read(out/'contexts/q002.json');self.assertEqual(ctx['same_image_ids'],['q000'])
   self.assertEqual(read(out/'contexts/q029.json')['selected_skills'],[])
   self.assertEqual(len(read(out/'contexts/q030.json')['selected_skills']),1)
   self.assertNotIn('q001',ctx['same_image_context'])
   self.assertIn('reference_annotation',ctx['same_image_context'])
   s2=FakeService(out)
   run_stream(inputs,order,root,out,s2,vault,[],evolver=evolve_fake,reward_fn=reward)
   self.assertEqual(s2.calls,[])
 def test_real_window_evolution_is_visible_only_next_window(self):
  from skill_evolve_r49 import evolve
  from skill_prompts_r49 import ANALYZE,MUTATE,REVIEW
  class Distiller(FakeService):
   def meta(self,event,system,payload,*args):
    if system==ANALYZE:
     injected=payload['trajectory']['injected']
     return {'output_intent':'NONE' if injected else 'CREATE','extracted_pattern':'check location','branch':'task_level',
             'skill_adoption':[{'skill_id':sid,'status':'IGNORED'} for sid in injected]}
    if system==MUTATE:return {'operation':'CREATE','content':copy.deepcopy(C)}
    if system==REVIEW:return {'quality':True,'duplicate_of':None}
    raise AssertionError(event)
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);inputs,order,vault=self.fixture(root,2);out=root/'run';cfg=dict(DEFAULTS,window=1,govern_every=10)
   run_stream(inputs,order,root,out,Distiller(out),vault,[],cfg,evolver=evolve,reward_fn=reward)
   self.assertEqual(read(out/'contexts/q000.json')['selected_skills'],[])
   self.assertEqual(len(read(out/'contexts/q001.json')['selected_skills']),1)
   self.assertEqual(read(out/'final_repo.json')['window'],2)
 def test_reference_requires_saved_prediction(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);inputs,order,vault=self.fixture(root,1)
   with self.assertRaises(ValueError):vault.after_prediction('q000',root/'missing.json')
 def test_resume_after_prediction_before_feedback(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);inputs,order,vault=self.fixture(root,3);out=root/'run'
   class InterruptVault:
    def after_prediction(self,q,p):raise RuntimeError('crash before feedback')
   with self.assertRaises(RuntimeError):run_stream(inputs,order,root,out,FakeService(out),InterruptVault(),[],evolver=evolve_fake,reward_fn=reward)
   self.assertTrue((out/'predictions'/ARM/'q000.json').exists())
   s=FakeService(out);run_stream(inputs,order,root,out,s,vault,[],evolver=evolve_fake,reward_fn=reward)
   self.assertEqual([q for q,c in s.calls],['q001','q002'])
 def test_evolution_failure_does_not_rerun_questions(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);inputs,order,vault=self.fixture(root,3);out=root/'run'
   def fail(*a):raise RuntimeError('evolution interruption')
   with self.assertRaises(RuntimeError):run_stream(inputs,order,root,out,FakeService(out),vault,[],evolver=fail,reward_fn=reward)
   s=FakeService(out);run_stream(inputs,order,root,out,s,vault,[],evolver=evolve_fake,reward_fn=reward);self.assertEqual(s.calls,[])
 def test_future_prediction_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);inputs,order,vault=self.fixture(root,3);out=root/'run'
   save_once(out/'predictions'/ARM/'q002.json',{})
   with self.assertRaises(ValueError):run_stream(inputs,order,root,out,FakeService(out),vault,[],evolver=evolve_fake,reward_fn=reward)
 def test_only_current_label_opens_after_both_prediction_records(self):
  import online_memory_r49 as memory_module
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);inputs,order,vault=self.fixture(root,4);out=root/'run';opened=[]
   original=memory_module.read
   def observe(path):
    path=Path(path)
    if path.parent==root/'refs':
     q=path.stem
     self.assertTrue((out/'predictions'/ARM/(q+'.json')).is_file())
     self.assertTrue((out/'prediction_events'/(q+'.json')).is_file())
     self.assertEqual(q,inputs[len(opened)]['question_id']);opened.append(q)
    return original(path)
   with patch.object(memory_module,'read',side_effect=observe):
    run_stream(inputs,order,root,out,FakeService(out),vault,[],evolver=evolve_fake,reward_fn=reward)
   self.assertEqual(opened,[r['question_id'] for r in inputs])
 def test_window_failure_never_advances_to_future_question(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);inputs,order,vault=self.fixture(root,3);out=root/'run';service=FakeService(out)
   def fail(*args):raise RuntimeError('window not committed')
   with self.assertRaises(RuntimeError):
    run_stream(inputs,order,root,out,service,vault,[],dict(DEFAULTS,window=1),evolver=fail,reward_fn=reward)
   self.assertEqual([q for q,_ in service.calls],['q000'])
   self.assertFalse((out/'contexts/q001.json').exists())
if __name__=='__main__':unittest.main()
