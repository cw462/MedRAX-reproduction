"""New public R50 boundaries with tiny synthetic files; no real scores/images."""
import json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'experiments'))
import verify_public_online_skill_r50 as public

def put(p,v,jsonl=False):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(('\n'.join(json.dumps(x) for x in v) if jsonl else json.dumps(v))+'\n',encoding='utf-8')

def raw_value():
    return {'prediction':{'answer':'wrong cached strict text','status':'completed'},
      'source':{'raw':'{"answer":"A","reason":"synthetic"}','call_path':'existing-public-archive','ordinal':'1',
        'reuse_chain':[],'evidence_status':'received_terminal_text','technical_stop':False}}

class PublicBoundaries(unittest.TestCase):
    def test_distinct_document_parents_share_correct_depth_mapping(self):
        with tempfile.TemporaryDirectory() as temp:
            evidence=Path(temp);asset=evidence/'assets/fixture.png';asset.parent.mkdir();asset.write_bytes(b'synthetic-not-decoded')
            put(evidence/'image_assets.json',[{'path':'assets/fixture.png'}])
            normalize=public.asset_normalizer(evidence)
            actual_relpath=os.path.relpath
            with patch.object(public.os.path,'relpath',wraps=actual_relpath) as calls:
                for name in ('a','b','c'):
                    doc=evidence/'cases'/name/'request.json'
                    sample={'path':'../../assets/fixture.png','nested':['text ../../assets/fixture.png','data:image/png;base64,aaaa']}
                    self.assertEqual(normalize(sample,doc),{'path':'PUBLIC_ASSET:0','nested':['text PUBLIC_ASSET:0','data:image/png;base64,aaaa']})
                self.assertEqual(calls.call_count,1)

    def test_comparator_uses_actual_raw_terminal_and_rejects_cached_labels(self):
        row={'question_id':'synthetic','options':{'A':'left','B':'right'}}
        bundle={'M43':{'synthetic':raw_value()}}
        result=public.projected_bundle(bundle,[row],'M43',{'M43'})['synthetic']
        self.assertEqual(result['strict_answer'],'wrong cached strict text');self.assertEqual(result['choice'],'A')
        bundle['M43']['synthetic']['prediction']['aligned_correct']=True
        with self.assertRaisesRegex(ValueError,'label_free_raw_projection'):
            public.projected_bundle(bundle,[row],'M43',{'M43'})

    def test_public_pipeline_adapts_all_three_bundles_before_any_labels(self):
        class StopBeforeLabels(Exception):pass
        with tempfile.TemporaryDirectory() as temp:
            evidence=Path(temp)/'evidence';evidence.mkdir();asset=evidence/'assets/fixture.png';asset.parent.mkdir();asset.write_bytes(b'fixture')
            put(evidence/'image_assets.json',[{'path':'assets/fixture.png'}])
            row={'question_id':'synthetic','question':'synthetic','options':{'A':'left','B':'right'},'images':['assets/fixture.png']}
            put(evidence/'inputs.jsonl',[row],jsonl=True)
            names={'M43','R47_online_GT','R49_online_GT_Skill'}
            put(evidence/'comparison_sources.json',{n:{'synthetic':raw_value()} for n in names})
            put(evidence/'publication_manifest.json',{'schema':'r50_semantic_public_evidence_v1','scope':'complete_scored_online_stream',
              'dataset':'chexbench','arm':public.ARM,'questions':618,'raw_generation_exit':0,'comparisons':sorted(names)})
            original_read=public.scorer.read;original_rows=public.scorer.rows;opened=[]
            def label_blind_read(p):
                p=Path(p);opened.append(p.name)
                if p.name.startswith('references') or 'scores' in p.parts:raise AssertionError('labels/scores opened during extraction')
                return original_read(p)
            def label_blind_rows(p):
                if Path(p).name!='inputs.jsonl':raise AssertionError('non-input rows read before extraction')
                return original_rows(p)
            def score_fixture(data,run,references,ds,**kwargs):
                # Call the actual public adapters installed by verify(), then
                # stop before any real grading or complete-cohort claim.
                for result in (public.scorer.adapt_historical([row],ds,'M43'),
                               public.scorer.adapt_r47([row],{},None,None),
                               public.scorer.adapt_saved_r49([row],None)[0]):
                    self.assertEqual(result['synthetic']['choice'],'A')
                raise StopBeforeLabels()
            with patch.object(public.scorer,'read',side_effect=label_blind_read),patch.object(public.scorer,'rows',side_effect=label_blind_rows), \
                 patch.object(public.scorer,'score',side_effect=score_fixture):
                with self.assertRaises(StopBeforeLabels):public.verify(evidence,Path(temp)/'out')
            self.assertEqual(opened.count('comparison_sources.json'),1)

if __name__=='__main__':unittest.main()
