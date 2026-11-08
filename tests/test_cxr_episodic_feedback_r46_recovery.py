"""Regression with immutable save: reproduce real failure and prove no reissue."""
import contextlib,io,json,sys,tempfile,types,unittest
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from test_cxr_episodic_feedback_r46 import Boundaries
import cxr_episodic_feedback_r46 as core
import run_cxr_episodic_feedback_r46 as original
import recover_cxr_episodic_feedback_r46 as recovery


def immutable_save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(value,f)


class Recovery(unittest.TestCase):
    def setup_prefix(self,root):
        data,source,dev=Boundaries().fixture(root);out=root/'generation';cfg=root/'config.json';immutable_save(cfg,{})
        calls=[]
        class FakePaid:
            def __init__(self,cfg,spec,*args,**kwargs):self.spec=spec
            def call(self,row,arm,ordinal,messages):
                q=row['question_id'];calls.append((arm,q));folder=out/'calls'/arm/q/'1'
                value={'answer':'model answer','reason':'recorded reason','case_description':'source chest image'}
                if arm=='SOURCE_REFLECT':value={'sigma':'Compare the source answer and dataset feedback.','gamma':'If applicable, inspect the named attribute.'}
                for name,obj in [('request.json',recovery.payload(self.spec,messages)),('started.json',{'utc':datetime.now(timezone.utc).isoformat()}),
                    ('result.json',{'response_received':True,'error':None}),('response.json',{'choices':[{'finish_reason':'stop','message':{'content':json.dumps(value)}}]})]:immutable_save(folder/name,obj)
        transport=types.SimpleNamespace(PaidCalls=FakePaid,exclusive_lock=lambda x:contextlib.nullcontext(),
           freeze_protocol=lambda o,s:immutable_save(o/'protocol.json',s),now=lambda:datetime.now(timezone.utc).isoformat(),save=immutable_save)
        argv=['runner','--phase','source','--data',str(data),'--out',str(out),'--config',str(cfg),'--execute','--api-key-stdin']
        with patch.dict(sys.modules,{'run_cxr_vqa_toolsets':transport}),patch.object(sys,'argv',argv),patch.object(sys,'stdin',io.StringIO('TEST_ONLY\n')),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(FileExistsError):original.main()
        (root/'jobs').mkdir();(root/'jobs/source.exitcode').write_text('1\n');(root/'jobs/source.log').write_text('FileExistsError: source_progress.json')
        immutable_save(root/'RECOVERY_REVIEW_READY.json',{'review_completed':True,'verdict':'ready'})
        self.assertEqual(len(calls),4)
        return data,out,cfg,transport,calls

    def test_missing_response_refuses_recovery_without_new_calls(self):
        with tempfile.TemporaryDirectory() as name:
            data,out,cfg,transport,calls=self.setup_prefix(Path(name))
            (out/'calls/SOURCE/s1/1/response.json').unlink()
            with self.assertRaises(AssertionError):recovery.validate_prefix(out,data)
            self.assertEqual(len(calls),4)

    def test_only_remaining_twenty_calls_and_original_records_preserved(self):
        with tempfile.TemporaryDirectory() as name:
            data,out,cfg,transport,calls=self.setup_prefix(Path(name));prefix=(out/'predictions/SOURCE/s0.json').read_bytes()
            recovery.validate_prefix(out,data)
            argv=['recover','--data',str(data),'--out',str(out),'--config',str(cfg),'--execute','--api-key-stdin']
            with patch.dict(sys.modules,{'run_cxr_vqa_toolsets':transport}),patch.object(sys,'argv',argv),patch.object(sys,'stdin',io.StringIO('TEST_ONLY\n')),contextlib.redirect_stdout(io.StringIO()):recovery.main()
            self.assertEqual(len(calls),24);self.assertTrue(all(n==1 for n in Counter(calls).values()))
            self.assertEqual(prefix,(out/'predictions/SOURCE/s0.json').read_bytes())
            self.assertEqual(core.read(out/'source_progress.json')['processed'],1)
            self.assertEqual(len(list((out/'source_progress_events').glob('*.json'))),10)
            self.assertEqual((out/'source.effective.exitcode').read_text().strip(),'0')
            self.assertEqual((out.parent/'jobs/source.exitcode').read_text().strip(),'1')
            self.assertEqual(core.read(out/'source.complete.json')['main_calls'],24)


if __name__=='__main__':unittest.main()
