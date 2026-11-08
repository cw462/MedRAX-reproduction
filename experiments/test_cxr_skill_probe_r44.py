"""Critical paid-run boundary: an unknown send stops both arms and cannot resume."""
from contextlib import nullcontext
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import run_cxr_skill_probe_r44 as runner

ROOT=Path(__file__).resolve().parents[1]


class UnknownSendBoundary(unittest.TestCase):
    def test_unknown_first_send_stops_cohort_and_refuses_reexecution(self):
        with tempfile.TemporaryDirectory() as name:
            out=Path(name)/'generation'
            def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
            def save(path,value):
                path.parent.mkdir(parents=True,exist_ok=True)
                with path.open('x',encoding='utf-8') as handle:json.dump(value,handle)
            def freeze(path,value):
                if (path/'protocol.json').exists():assert read(path/'protocol.json')==value
                else:save(path/'protocol.json',value)
            class FailedPaidCalls:
                attempted=0
                def __init__(self,*args):pass
                def call(self,row,arm,ordinal,messages):
                    FailedPaidCalls.attempted+=1
                    save(out/'calls'/arm/row['question_id']/'1/started.json',{'send_intent':True})
                    raise RuntimeError('unknown_sent_simulated')
            stub=SimpleNamespace(PaidCalls=FailedPaidCalls,exclusive_lock=lambda path:nullcontext(),
                                 freeze_protocol=freeze,now=lambda:'2026-11-08T00:00:00Z',read=read,save=save)
            config=Path(name)/'config.json';config.write_text('{}',encoding='utf-8')
            argv=['runner','--data',str(ROOT/'data/slake_skill_probe_r44'),
                  '--skill',str(ROOT/'reports/cxr_skill_probe_r44_20261108/SKILL.txt'),
                  '--out',str(out),'--config',str(config),'--execute','--api-key-stdin']
            from io import StringIO
            with patch.dict(sys.modules,{'run_cxr_vqa_toolsets':stub}),patch.object(sys,'argv',argv),patch.object(sys,'stdin',StringIO('dummy\n')):
                with self.assertRaisesRegex(RuntimeError,'unknown_sent_simulated'):runner.main()
            saved=list((out/'predictions').glob('*/*.json'))
            self.assertEqual(FailedPaidCalls.attempted,1)
            self.assertEqual(len(saved),1)
            self.assertEqual(read(saved[0])['status'],'technical_stop')
            self.assertFalse((out/'complete.json').exists())
            with patch.dict(sys.modules,{'run_cxr_vqa_toolsets':stub}),patch.object(sys,'argv',argv),patch.object(sys,'stdin',StringIO('dummy\n')):
                with self.assertRaisesRegex(AssertionError,'new_execution_only_no_resume'):runner.main()
            self.assertEqual(FailedPaidCalls.attempted,1)


if __name__ == '__main__':unittest.main()
