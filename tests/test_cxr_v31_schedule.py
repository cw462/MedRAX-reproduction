import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from test_cxr_skill_v2 import card
ROOT=Path(__file__).resolve().parents[1]
class ScheduleTests(unittest.TestCase):
    def test_only_skill_then_ablation_no_baseline_rerun(self):
        with tempfile.TemporaryDirectory() as d:
            t=Path(d)
            (t/'runtime.json').write_text(json.dumps({'arms':{'M':{'tools':[],'ready':True}},'tools':{}}))
            (t/'protocol.json').write_text(json.dumps({'main_call_limits':{'M':4},'model':'test-model'}))
            (t/'config.json').write_text(json.dumps({'runtime':str(t/'runtime.json'),'protocol':str(t/'protocol.json')}))
            (t/'bank.json').write_text(json.dumps({'schema':'cxr_skill_v2','source_only':True,'frozen':True,'items':[card()]}))
            subprocess.run([sys.executable,str(ROOT/'experiments/prepare_cxr_gain_v31.py'),'--base-config',str(t/'config.json'),'--bank',str(t/'bank.json'),'--out',str(t/'out'),'--experiment-id','gain_v31_test'],check=True,capture_output=True)
            r=json.loads((t/'out/runtime.json').read_text());p=json.loads((t/'out/protocol.json').read_text())
            self.assertEqual(list(r['arms']),['M-AS','M-A'])
            self.assertEqual(p['main_call_limits'],{'M-AS':4,'M-A':4})
            self.assertNotIn('bank_path',r['arms']['M-A'])
            self.assertIn('bank_path',r['arms']['M-AS'])
            self.assertNotIn('M',r['arms'])
if __name__=='__main__':unittest.main()
