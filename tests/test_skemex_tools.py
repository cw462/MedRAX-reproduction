"""Offline executor boundaries and actual evidence flow; never initialize a model."""
import json
from pathlib import Path
import sys
from contextlib import nullcontext
from types import SimpleNamespace
from unittest import TestCase,main
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from skemex_adapter.tool_episode import parse_plan,skill_rejection,episode,TOOLS,RealTools


class ToolBoundaries(TestCase):
    def setUp(self):
        self.row={'question_id':'q','case_id':'c','question':'Which finding? A) x B) y','images':['figures/c/cxr.jpg','figures/c/ct.jpg']}
        self.call={'tool':TOOLS[0],'source_filename':self.row['images'][0],'reason':'Check a candidate finding'}

    def test_only_current_confirmed_cxr_and_two_calls(self):
        for source in ('figures/other/x.jpg',self.row['images'][1],'C:/secret.jpg'):
            with self.assertRaises(ValueError):parse_plan(json.dumps({'calls':[dict(self.call,source_filename=source)]}),self.row,[self.row['images'][0]])
        for calls in ([self.call]*2,[self.call]*3):
            with self.assertRaises(ValueError):parse_plan(json.dumps({'calls':calls}),self.row,[self.row['images'][0]])

    def test_no_unimplemented_tool_or_arbitrary_arguments(self):
        for call in (dict(self.call,tool='shell'),dict(self.call,image_path='/outside')):
            with self.assertRaises(ValueError):parse_plan(json.dumps({'calls':[call]}),self.row,self.row['images'])

    def test_action_skill_requires_actual_attempt(self):
        draft={'branch':'action_level','required_tools':[TOOLS[0]],'core_action':'Inspect the returned score and compare with pixels.'}
        self.assertIsNotNone(skill_rejection(draft,self.row,[]))
        self.assertIsNone(skill_rejection(draft,self.row,[TOOLS[0]]))
        self.assertIsNotNone(skill_rejection(dict(draft,core_action='Read '+self.row['images'][0]),self.row,[TOOLS[0]]))

    def test_evidence_reaches_final_and_trajectory_without_labels(self):
        row=self.row;selected=self.call;seen=[]
        class Transport:
            factory=None
            def call(self,messages,**kwargs):
                seen.append((messages,kwargs))
                if not kwargs['actor']:return json.dumps({'calls':[selected]}),{'status':'completed'}
                return 'Answer: A\nReason: image supports x',{'answer':'A','status':'completed'}
        class Tools:
            def eligible(self,r):return [r['images'][0]]
            def invoke(self,r,c):
                return {'tool':c['tool'],'source_filename':c['source_filename'],'status':'returned','usable':True,
                        'same_round_cache_hit':False,'fresh_inference_attempted':True,'inference_invoked_in_original_record':True,
                        'model_observation':{'strong_findings':{'Effusion':.9}}}
        retrieval=SimpleNamespace(retrieved_skills_block='',injected_skill_ids=[],candidates=[])
        runtime={'store':SimpleNamespace(list_skills=lambda **kw:[]),'config':None,
                 'modules':{'categories':SimpleNamespace(DynamicTaskCategoryRegistry=lambda *a:SimpleNamespace(classify=lambda q:['finding'] ))},
                 'retriever':SimpleNamespace(retrieve=lambda *a,**kw:retrieval)}
        with patch('skemex_adapter.tool_episode.budgeted_llm_bindings',return_value=nullcontext()), \
             patch('skemex_adapter.tool_episode.request_for',return_value=([{'role':'system','content':'Answer/Reason'},{'role':'user','content':'pixels+question'}],[{'native':True}])), \
             patch('skemex_adapter.tool_episode.frozen_write'):
            result=episode(runtime,Transport(),row,{},Path('unused'),0,{},Tools())
        self.assertEqual(len(seen),2);self.assertIn('Effusion',seen[1][0][-1]['content'])
        self.assertEqual(result['trajectory_steps'][1]['action'],TOOLS[0]);self.assertTrue(result['tool_observations'][0]['usable'])
        self.assertEqual(seen[1][1]['images'],[{'native':True}]);self.assertNotIn('reference',result)
        self.assertTrue(all(isinstance(s['observation'],str) for s in result['trajectory_steps']))

    def test_no_execute_flag_never_reads_approval_or_credentials(self):
        from run_skemex_pipeline import run
        with patch('run_skemex_pipeline.read',side_effect=AssertionError('must not read approval/config')):
            run(Path('unused'),Path('unused'),execute=False)

    def test_real_executor_cache_and_unknown_call_are_not_reissued(self):
        import tempfile
        from build_case_tool_evidence import write
        counter={'invokes':0}
        def invoke(arguments):
            counter['invokes']+=1
            return ({'Effusion':.95},{'analysis_status':'completed'})
        tool=SimpleNamespace(args_schema=SimpleNamespace(model_json_schema=lambda:{'properties':{'image_path':{}}}),invoke=invoke)
        pool=SimpleNamespace(get=lambda name:(tool,{}))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=self.row['images'][0];path=root/'images'/source;path.parent.mkdir(parents=True);path.write_bytes(b'fake pixels for offline transport test')
            write(root/'modalities.json',{'schema_version':1,'images':[{'source_filename':source,'modality':'CXR','provenance':{'kind':'metadata','source':'test','quote':'CXR'}}]})
            cfg={'root':str(root),'tool_modality_manifest':'modalities.json','image_root':'images','tool_repo':'repo'}
            with patch('build_case_tool_evidence.LocalToolPool',return_value=pool),patch('experiments.tool_variants.validate_observation',return_value={'valid':True}):
                executor=RealTools(cfg,root/'new');first=executor.invoke(self.row,self.call);second=executor.invoke(self.row,self.call)
                self.assertEqual(counter['invokes'],1);self.assertTrue(first['fresh_inference_attempted']);self.assertTrue(second['same_round_cache_hit'])
                self.assertFalse(second['fresh_inference_attempted'])
                (root/'new/tool_cache'/first['record']).unlink()
                unknown=executor.invoke(self.row,self.call)
                self.assertEqual(unknown['status'],'interrupted_unknown');self.assertEqual(counter['invokes'],1)


if __name__=='__main__':main()
