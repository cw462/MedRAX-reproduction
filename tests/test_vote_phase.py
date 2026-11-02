"""Offline phase-0 wiring tests: synthetic sources, no network or real ledger."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
import configure_vote_gain as configure
import run_vote_phase as phase
import run_sampled_vlm as sampled


class PhaseWiring(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        path=self.root/'runs/v4_validation60/inputs.jsonl';path.parent.mkdir(parents=True)
        rows=[{'question_id':f'unrelated_{i}','question':'Choose.\nA) Alpha\nB) Beta','images':['image.png']} for i in range(60)]
        path.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
        metadata=self.root/'data/chest-agent-bench/metadata.jsonl.new';metadata.parent.mkdir(parents=True)
        metadata.write_text(''.join(json.dumps({'full_question_id':r['question_id'],
            'case_id':f'actual_case_{i//2}','answer':'DO_NOT_COPY'})+'\n' for i,r in enumerate(rows)),encoding='utf-8')
        self.args=SimpleNamespace(root=str(self.root),code='code_vote_gain',new_budget_cny='200',
            inherited_committed_cny='194.252828',original_cap_cny='1000000',
            inherit_ledger='reports/old_ledger.json',budget_authorization='Synthetic approved 200 CNY test')
        with contextlib.redirect_stdout(io.StringIO()):configure.phase0(self.args)
        self.path=self.root/'code_vote_gain/configs/multimodel_vote_gain_20261102/phase0.json'
        self.manifest=sampled.read(self.path)

    def test_all_five_arm_configs_prepare_with_same_cumulative_cap(self):
        arms=phase.validate_manifest(self.manifest)
        previous=self.args.inherit_ledger
        for arm in arms:
            cfg=sampled.read(Path(arm['config']))
            self.assertEqual(cfg['cap_cny'],'394.252828')
            self.assertEqual(cfg['inherit_ledger'],previous);previous=cfg['ledger']
            thinking=cfg['prompt_variant']=='think' or cfg['model'].startswith('kimi/')
            self.assertEqual(cfg['profile']['max_output_tokens'],16384 if thinking else 8192)
            self.assertEqual(cfg['max_output_tokens'],8192 if thinking else 2048)
            rows=sampled.prepare(cfg,Path(arm['out']))
            self.assertEqual(len(rows),60 if arm['id']=='D_regression60' else 2)
            self.assertEqual(rows[0]['case_id'],'actual_case_0')
            self.assertNotIn('answer',rows[0])
        self.assertFalse((self.root/'reports/old_ledger.json').exists())

    def test_root_and_global_request_policy_cannot_drift(self):
        target=Path(self.manifest['arms'][1]['config']);cfg=sampled.read(target)
        cfg['global_max_requests']+=1;sampled.write(target,cfg)
        with self.assertRaisesRegex(ValueError,'global_request_policy'):phase.validate_manifest(self.manifest)
        cfg['global_max_requests']-=1;cfg['root']=str(self.root/'elsewhere');sampled.write(target,cfg)
        with self.assertRaisesRegex(ValueError,'runtime_root'):phase.validate_manifest(self.manifest)

    def test_new_ledger_cannot_replace_inherited_ledger(self):
        target=Path(self.manifest['arms'][0]['config']);cfg=sampled.read(target)
        cfg['ledger']=self.args.inherit_ledger;sampled.write(target,cfg)
        with self.assertRaisesRegex(ValueError,'distinct_new_ledgers'):phase.validate_manifest(self.manifest)

    def test_phase_snapshot_freezes_arm_content_not_just_paths(self):
        argv=['run_vote_phase','--manifest',str(self.path),'--prepare-only']
        with patch.object(sys,'argv',argv),patch.object(phase.subprocess,'run',return_value=SimpleNamespace(returncode=0)):
            self.assertEqual(phase.main(),0)
            target=Path(self.manifest['arms'][0]['config']);cfg=sampled.read(target)
            cfg['temperature']=.7;sampled.write(target,cfg)
            with self.assertRaisesRegex(ValueError,'immutable_record_conflict'):phase.main()

    def test_smoke_failure_stops_before_any_later_arm(self):
        argv=['run_vote_phase','--manifest',str(self.path),'--api-key-stdin']
        stdin=SimpleNamespace(buffer=io.BytesIO(b'synthetic-test-key\n'))
        with patch.object(sys,'argv',argv),patch.object(sys,'stdin',stdin),patch.object(phase.subprocess,'run',
             side_effect=[SimpleNamespace(returncode=0),SimpleNamespace(returncode=2)]) as run:
            self.assertEqual(phase.main(),2)
        self.assertEqual(run.call_count,2)
        state=sampled.read(Path(self.manifest['out'])/'status.json')
        self.assertEqual(state['active_arm'],'qwen_max_smoke')
        self.assertEqual(state['completed_arms'],['D_regression60'])

    def test_missing_explicit_case_mapping_is_rejected(self):
        source=self.root/'data/chest-agent-bench/metadata.jsonl.new'
        source.write_text('',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'missing_explicit_case_binding'):configure.phase0(self.args)


if __name__=='__main__':unittest.main()
