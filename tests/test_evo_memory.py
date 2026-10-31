import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evo_memory.feedback import PredictionJournal,FeedbackBroker
from evo_memory.store import MemoryStore
from evo_memory.io import jsonl
from evo_memory.prompts import answer_payload
from experiments.r1_evidence import explicit_answer


def episode(case='seed_case',eid='seed:q',step=0):
    return {'id':eid,'source_case_id':case,'source_phase':'seed_train','available_after_step':step,'actionable':True,
            'modality':'CXR','inspection_action':'Inspect the lateral chest wall and count visible adjacent ribs.'}


class MemoryBoundary(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def broker(self,case_map):
        rows=[{'question_id':q,'question':'Question\nA) alpha\nB) beta','images':['synthetic.png']} for q in case_map]
        labels=self.root/'labels.jsonl';jsonl(labels,[{'question_id':q,'answer':'A'} for q in case_map])
        journal=PredictionJournal(self.root/'predictions')
        return FeedbackBroker(labels,rows,case_map,journal,self.root/'feedback'),journal
    def commit(self,journal,q,arm):journal.commit({'question_id':q,'arm':arm,'status':'completed','answer':'B'})
    def test_feedback_requires_both_saved_arm_predictions(self):
        broker,journal=self.broker({'q1':'case1'})
        with self.assertRaises(ValueError):broker.release('case1',1)
        self.commit(journal,'q1','E')
        with self.assertRaises(ValueError):broker.release('case1',1)
        self.commit(journal,'q1','ES');self.assertEqual(broker.release('case1',1)['references']['q1']['answer'],'A')
    def test_same_case_batch_has_no_early_feedback(self):
        broker,journal=self.broker({'q1':'case1','q2':'case1'})
        for arm in ('E','ES'):self.commit(journal,'q1',arm)
        with self.assertRaises(ValueError):broker.release('case1',1)
        for arm in ('E','ES'):self.commit(journal,'q2',arm)
        with self.assertRaises(ValueError):broker.release('case1',1)
        self.assertEqual(len(broker.release('case1',2)['references']),2)
    def test_future_and_current_case_memory_unreadable(self):
        store=MemoryStore(self.root/'state.json',episodes=[episode('past','e1',1),episode('future','e2',0),episode('current','e3',0)])
        values,_=store.visible(step=2,current_case='current',seed_cases=set(),past_cases={'past'})
        self.assertEqual([e['id'] for e in values],['e1'])
        values,_=store.visible(step=1,current_case='current',seed_cases=set(),past_cases={'past'})
        self.assertEqual(values,[])
    def test_E_ES_states_are_independent(self):
        initial=[episode()];left=MemoryStore(self.root/'E.json',episodes=initial,enable_rules=False);right=MemoryStore(self.root/'ES.json',episodes=initial)
        right.state['episodes'][0]['inspection_action']='changed'
        self.assertNotEqual(left.state['episodes'][0]['inspection_action'],right.state['episodes'][0]['inspection_action'])
        self.assertNotEqual(initial[0]['inspection_action'],'changed')
    def test_resume_does_not_reapply_episode_or_rule_patch(self):
        path=self.root/'state.json';store=MemoryStore(path)
        reflection={'episode':{'modality':'CXR','inspection_action':'Inspect the lateral chest wall and count adjacent visible ribs.',
                    'decisive_difference':'Distinguish rib count from the numbered intercostal space.'},
                    'procedure_patch':{'op':'add','condition':'When intercostal positions compete','action':'Inspect the lateral chest wall and count adjacent visible ribs.','limitation':'No calibrated distance from rib spacing.'}}
        kwargs=dict(case_id='case1',qid='q1',phase='past_stream',step=1,previous_choice_text='wrong choice',correct_choice_text='correct choice')
        store.apply('event1',reflection,**kwargs)
        resumed=MemoryStore(path);resumed.apply('event1',reflection,**kwargs)
        self.assertEqual(resumed.state['version'],1);self.assertEqual(len(resumed.state['episodes']),1);self.assertEqual(len(resumed.state['rules']),1)
    def test_explicit_choice_with_text_and_answer_input_whitelist(self):
        self.assertEqual(explicit_answer('Answer: B) complete option\nReason: brief',{'A','B'}),'B')
        self.assertIsNone(explicit_answer('Answer: A\nAnswer: B',{'A','B'}))
        with self.assertRaises(ValueError):answer_payload({'question_id':'q','question':'x','images':[],'reference':'A'},'')


if __name__=='__main__':unittest.main()
