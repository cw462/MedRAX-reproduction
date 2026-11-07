import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from test_cxr_gain_v3 import Base,Paid,Tools,decision
from test_cxr_skill_v2 import card
from cxr_evidence_v32 import episode
ROOT=Path(__file__).resolve().parents[1]
class BudgetTests(unittest.TestCase):
    def invoke(self,seq):
        p=Paid(seq);t=Tools()
        r=episode(Base,{'question_id':'q','question':'Which side?','images':['a']},'M-AS',Path('.'),
                  {'main_call_limits':{'M-AS':6},'tool_call_limits':{'M-AS':4}}, {},Path('.'),p,t)
        return r,p,t
    def test_four_tools_are_reachable(self):
        seq=[decision(tool='qa',args={'question':str(i)}) for i in range(4)]+[decision('B',source='tool:T4')]
        r,p,t=self.invoke(seq)
        self.assertEqual((len(p.calls),len(t.calls),r['answer']),(5,4,'B'))
    def test_sixth_main_used_after_format_error(self):
        seq=['bad']+[decision(tool='qa',args={'question':str(i)}) for i in range(4)]+[decision('B',source='tool:T4')]
        r,p,t=self.invoke(seq)
        self.assertEqual((len(p.calls),len(t.calls),r['answer']),(6,4,'B'))
    def test_no_fifth_tool(self):
        seq=[decision(tool='qa',args={'question':str(i)}) for i in range(5)]+[decision('B')]
        r,p,t=self.invoke(seq)
        self.assertEqual(len(t.calls),4);self.assertLessEqual(len(p.calls),6)
    def test_early_stop_still_one_call(self):
        r,p,t=self.invoke([decision()]);self.assertEqual((len(p.calls),len(t.calls)),(1,0))
    def test_format_errors_cannot_make_seventh_call(self):
        r,p,t=self.invoke(['bad']*6);self.assertEqual(len(p.calls),6);self.assertIsNone(r['answer'])
    def test_config_both_arms_six_four_no_M(self):
        with tempfile.TemporaryDirectory() as d:
            t=Path(d)
            (t/'rt.json').write_text(json.dumps({'arms':{'M':{'tools':[]}},'tools':{}}))
            (t/'p.json').write_text(json.dumps({'main_call_limits':{'M':4}}))
            (t/'cfg.json').write_text(json.dumps({'runtime':str(t/'rt.json'),'protocol':str(t/'p.json')}))
            (t/'bank.json').write_text(json.dumps({'schema':'cxr_skill_v2','source_only':True,'frozen':True,'items':[card()]}))
            subprocess.run([sys.executable,str(ROOT/'experiments/prepare_cxr_gain_v32.py'),'--base-config',str(t/'cfg.json'),'--bank',str(t/'bank.json'),'--out',str(t/'out'),'--experiment-id','gain_v32_test'],check=True,capture_output=True)
            p=json.loads((t/'out/protocol.json').read_text());r=json.loads((t/'out/runtime.json').read_text())
            self.assertEqual(p['main_call_limits'],{'M-AS':6,'M-A':6})
            self.assertEqual(p['tool_call_limits'],{'M-AS':4,'M-A':4})
            self.assertEqual(list(r['arms']),['M-AS','M-A'])
if __name__=='__main__':unittest.main()
