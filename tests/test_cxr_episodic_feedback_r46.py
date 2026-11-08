"""Meaningful label-timing, prefix retrieval and no-development-feedback tests."""
import contextlib,io,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
import cxr_episodic_feedback_r46 as core
import run_cxr_episodic_feedback_r46 as runner


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value),encoding='utf-8')


class Boundaries(unittest.TestCase):
    def fixture(self,p):
        data=p/'data';source=[];dev=[]
        for i in range(20):
            image=data/'images'/(str(i)+'.png');image.parent.mkdir(parents=True,exist_ok=True)
            Image.new('RGB',(18,19),(i*9,i*7,i*5)).save(image)
        for i in range(12):
            q={'question_id':'s'+str(i),'question':'Is this lung abnormal '+str(i)+'?',
               'images':['images/'+str(i)+'.png'],'image_id':'i'+str(i),'source':{'split':'train'}};source.append(q)
            save(data/'source_labels'/(q['question_id']+'.json'),{'question_id':q['question_id'],'image_id':q['image_id'],'answer':'SOURCE_GOLD_'+str(i)})
        for i in range(27):dev.append({'question_id':'d'+str(i),'question':'Is this lung abnormal?',
            'images':['images/'+str(12+i%8)+'.png'],'image_id':'i'+str(12+i%8),'source':{'split':'validation'}})
        for name,values in [('source_inputs.jsonl',source),('inputs.jsonl',dev)]:
            (data/name).write_text(''.join(json.dumps(x)+'\n' for x in values),encoding='utf-8')
        return data,source,dev

    def test_overlap_refused_before_any_api(self):
        with tempfile.TemporaryDirectory() as name:
            data,source,dev=self.fixture(Path(name));dev[0]['images']=source[0]['images']
            with self.assertRaisesRegex(AssertionError,'source_development_image_overlap'):core.make_protocol(source,dev,data)

    def test_retrieval_rank_ignores_gold_summary_and_guideline(self):
        row={'question_id':'current','question':'Is the lung healthy?'};info={'pixel_sha256':'new','image_vector':[1.,0.]}
        episode={'question_id':'past','question':'Is the lung healthy?','phi':'chest image','tau':[],
            'y_hat':'old answer','y':'SOURCE_GOLD','sigma':'summary','gamma':'guideline','image_pixel_sha256':'old','image_vector':[1.,0.]}
        a=core.retrieve(row,info,[episode]);episode.update(y='DIFFERENT_LABEL',sigma='totally different',gamma='other')
        b=core.retrieve(row,info,[episode]);self.assertEqual(a['included_ids'],b['included_ids'])
        self.assertEqual(a['examples'][0]['similarity'],b['examples'][0]['similarity'])
        episode['image_pixel_sha256']='new';self.assertEqual(core.retrieve(row,info,[episode])['included_ids'],[])

    def test_source_prediction_precedes_truth_and_dev_runs_without_reference_file(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);data,source,dev=self.fixture(root);out=root/'generation';cfg=root/'config.json';save(cfg,{})
            calls=[];label_reads=[];test=self
            class FakePaid:
                def __init__(self,*args,**kwargs):pass
                def call(self,row,arm,ordinal,messages):
                    q=row['question_id'];text=json.dumps(messages)
                    if arm=='SOURCE':test.assertNotIn('SOURCE_GOLD_'+q[1:]+'"',text)
                    if arm=='SOURCE_REFLECT':test.assertTrue((out/'predictions/SOURCE'/(q+'.json')).exists())
                    value={'answer':'model answer','reason':'recorded reason','case_description':'source chest image'}
                    if arm=='SOURCE_REFLECT':value={'sigma':'Recorded answer contrasted with its source annotation.','gamma':'When this question type applies, inspect the named attribute.'}
                    folder=out/'calls'/arm/q/'1';calls.append((arm,q))
                    for n,v in [('request.json',{'messages':messages}),('started.json',{}),('result.json',{'response_received':True,'error':None}),
                      ('response.json',{'choices':[{'finish_reason':'stop','message':{'content':json.dumps(value)}}]})]:save(folder/n,v)
            def spy_read(path):
                path=Path(path)
                if path.parent.name=='source_labels':
                    test.assertTrue((out/'predictions/SOURCE'/path.name).is_file());label_reads.append(path.stem)
                test.assertNotEqual(path.name,'references.jsonl')
                return core.read(path)
            transport=types.SimpleNamespace(PaidCalls=FakePaid,exclusive_lock=lambda x:contextlib.nullcontext(),
                freeze_protocol=lambda o,s:save(o/'protocol.json',s),now=lambda:'2026-11-08T00:00:00+00:00',save=save)
            def invoke(phase):
                argv=['runner','--phase',phase,'--data',str(data),'--out',str(out),'--config',str(cfg),'--execute','--api-key-stdin']
                with patch.dict(sys.modules,{'run_cxr_vqa_toolsets':transport}),patch.object(sys,'argv',argv),patch.object(sys,'stdin',io.StringIO('TEST_ONLY\n')),patch.object(runner,'read',spy_read),contextlib.redirect_stdout(io.StringIO()):runner.main()
            invoke('source');self.assertEqual(label_reads,[r['question_id'] for r in source]);self.assertEqual(len(calls),24)
            library=core.read(out/'frozen_E.json');save(out/'approved_E.json',library)
            save(out/'MEMORY_REVIEW_READY.json',{'source_only':True,'review_completed':True,'approved_library_sha256':core.sha(out/'approved_E.json')})
            self.assertFalse((data/'references.jsonl').exists());invoke('development');self.assertEqual(len(calls),78)
            self.assertFalse(core.read(out/'development.complete.json')['development_feedback'])
            for row in dev:
                self.assertFalse(core.read(out/'contexts/P0'/(row['question_id']+'.json'))['included_ids'])
                self.assertTrue(set(core.read(out/'contexts/P1'/(row['question_id']+'.json'))['included_ids'])<=set(label_reads))


if __name__=='__main__':unittest.main()
