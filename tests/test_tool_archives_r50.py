"""New observer archive witnesses, synthetic subprocesses only."""
import ast,json,os,subprocess,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'local_assets/r50_cxr6_preparation/support/run_cxr_vqa_toolsets.py'


def observer():
    source=ast.parse(SOURCE.read_text(encoding='utf-8'))
    cls=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='Tools')
    fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='observe')
    def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v),encoding='utf-8')
    ns=dict(__file__=str(SOURCE),Path=Path,json=json,os=os,subprocess=subprocess,time=time,save=save,
      read=lambda p:json.loads(p.read_text()),now=lambda:'synthetic-time')
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(SOURCE),'exec'),ns)
    return ns['observe']


class Archives(unittest.TestCase):
    def invoke(self,runner,name='medgemma'):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'cache';saved=folder/'result.json'
            this=type('Fixture',(),{'runtime':{'backend_config':{'fixture':True}}})()
            args={'question':'Synthetic archive fixture only'};image=Path(temp)/'not_loaded.jpg'
            identity={'backend':name,'args':args};spec={'backend':name,'python':'not_executed','gpu':'1'}
            with patch.object(subprocess,'run',side_effect=runner) as run:
                result,hit=observer()(this,name,spec,args,image,identity,folder,saved)
                again,cached=observer()(this,name,spec,args,image,identity,folder,saved)
            self.assertEqual(run.call_count,1);self.assertFalse(hit);self.assertTrue(cached);self.assertEqual(again,result)
            self.assertEqual(json.loads((folder/'request.json').read_text())['args'],args)
            self.assertEqual((folder/'backend.stdout.log').read_text(),'fixture stdout')
            self.assertEqual((folder/'backend.stderr.log').read_text(),'fixture stderr')
            self.assertFalse(json.loads((folder/'started.json').read_text())['automatic_retry'])
            if name=='xray_phrase_grounding':
                self.assertEqual(json.loads((folder/'started.json').read_text())['policy_id'],'maira_unclosed_tag_eos_guard_v1')
            return result

    def test_success_archives_exact_request_and_raw_output(self):
        stdout='CXR_VQA_RESULT='+json.dumps({'status':'completed','observation':{'answer':'fixture'}})
        # Raw protocol output is checked separately; a separate stdout literal
        # below exercises failed exits and timeouts without invoking any model.
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);saved=folder/'result.json';this=type('Fixture',(),{'runtime':{'backend_config':{}}})()
            with patch.object(subprocess,'run',return_value=subprocess.CompletedProcess([],0,stdout,'fixture stderr')) as run:
                result,hit=observer()(this,'xray_phrase_grounding',{'backend':'xray_phrase_grounding','python':'not_executed'},
                  {'phrase':'fixture'},Path(temp)/'not_loaded.jpg',{},folder,saved)
            self.assertEqual(run.call_count,1);self.assertEqual(result['status'],'completed')
            self.assertEqual((folder/'backend.stdout.log').read_text(),stdout)
            self.assertEqual(json.loads((folder/'request.json').read_text())['args'],{'phrase':'fixture'})
            self.assertEqual(json.loads((folder/'started.json').read_text())['policy_id'],'maira_unclosed_tag_eos_guard_v1')

    def test_failed_exit_preserves_logs_without_retry(self):
        result=self.invoke(lambda *a,**kw:subprocess.CompletedProcess([],7,'fixture stdout','fixture stderr'))
        self.assertEqual(result['status'],'failed');self.assertIn('backend_exit_7',result['error'])

    def test_timeout_preserves_available_partial_logs_without_retry(self):
        def timeout(*a,**kw):raise subprocess.TimeoutExpired('not_executed',1,output=b'fixture stdout',stderr=b'fixture stderr')
        result=self.invoke(timeout);self.assertEqual(result['status'],'failed');self.assertEqual(result['error_type'],'TimeoutExpired')


if __name__=='__main__':unittest.main()
