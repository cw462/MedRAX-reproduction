"""Offline phase-0 wiring tests: synthetic sources, no network or real ledger."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import traceback
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
        metadata.write_text(''.join(json.dumps({'question_id':r['question_id'],
            'full_question_id':'explicit_full_'+r['question_id'],
            'case_id':f'actual_case_{i//2}','answer':'DO_NOT_COPY'})+'\n' for i,r in enumerate(rows)),encoding='utf-8')
        self.gpt4o_profile=self.root/'gpt4o-profile.json'
        self.gpt4o_profile.write_text(json.dumps({'model':'gpt-4o','credential_slot':'apiyi',
            'base_url':'https://example.invalid/v1','identity_prefixes':['gpt-4o'],
            'input_cny_per_million':'1','output_cny_per_million':'2',
            'price_basis':'synthetic fixture','max_input_tokens':120000,
            'max_output_tokens':8192}),encoding='utf-8')
        self.args=SimpleNamespace(root=str(self.root),code='code_vote_gain',new_budget_cny='200',
            inherited_committed_cny='194.252828',original_cap_cny='1000000',
            inherit_ledger='reports/old_ledger.json',budget_authorization='Synthetic approved 200 CNY test',
            gpt4o_profile=self.gpt4o_profile)
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
            thinking=cfg['prompt_variant']=='think'
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
        argv=['run_vote_phase','--manifest',str(self.path),'--credentials-json-stdin']
        stdin=SimpleNamespace(buffer=io.BytesIO(b'{"dashscope":"test-dashscope","apiyi":"test-apiyi"}\n'))
        with patch.object(sys,'argv',argv),patch.object(sys,'stdin',stdin),patch.object(phase.subprocess,'run',
             side_effect=[SimpleNamespace(returncode=0),SimpleNamespace(returncode=2)]) as run:
            self.assertEqual(phase.main(),2)
        self.assertEqual(run.call_count,2)
        state=sampled.read(Path(self.manifest['out'])/'status.json')
        self.assertEqual(state['active_arm'],'qwen_max_smoke')
        self.assertEqual(state['completed_arms'],['D_regression60'])

    def test_mixed_keys_are_routed_only_to_the_selected_child_stdin(self):
        target=Path(self.manifest['arms'][0]['config']);cfg=sampled.read(target)
        cfg.update(model='qwen3.7-plus',credential_slot='token_plan')
        cfg['profile'].update(base_url=sampled.TOKEN_PLAN_BASE_URL,identity_prefixes=['qwen3.7-plus'])
        sampled.write(target,cfg)
        keys={'dashscope':'synthetic-dashscope-secret','apiyi':'synthetic-apiyi-secret',
              'token_plan':'synthetic-token-plan-secret'}
        stdin=SimpleNamespace(buffer=io.BytesIO(json.dumps(keys).encode()))
        output=io.StringIO()
        argv=['run_vote_phase','--manifest',str(self.path),'--credentials-json-stdin']
        with patch.object(sys,'argv',argv),patch.object(sys,'stdin',stdin),contextlib.redirect_stdout(output),\
             patch.object(phase.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as run:
            self.assertEqual(phase.main(),0)
        self.assertEqual(run.call_count,5)
        for arm,call in zip(self.manifest['arms'],run.call_args_list):
            cfg=sampled.read(Path(arm['config']))
            self.assertEqual(call.kwargs['input'],keys[cfg['credential_slot']].encode()+b'\n')
            self.assertIn('--api-key-stdin',call.args[0])
            for key in keys.values():
                self.assertNotIn(key,' '.join(call.args[0]))
                self.assertNotIn(key,json.dumps(cfg))
        gpt_arm=next(a for a in self.manifest['arms'] if a['id']=='gpt4o_smoke')
        self.assertEqual(sampled.read(Path(gpt_arm['config']))['credential_slot'],'apiyi')
        public_text=(Path(self.manifest['out'])/'phase_protocol.json').read_text(encoding='utf-8')+output.getvalue()
        for key in keys.values():self.assertNotIn(key,public_text)

    def test_token_plan_only_phase_uses_single_stdin_key(self):
        self.manifest['arms']=self.manifest['arms'][:1]
        sampled.write(self.path,self.manifest)
        target=Path(self.manifest['arms'][0]['config']);cfg=sampled.read(target)
        cfg.update(model='qwen3.7-plus',credential_slot='token_plan')
        cfg['profile'].update(base_url=sampled.TOKEN_PLAN_BASE_URL,identity_prefixes=['qwen3.7-plus'])
        sampled.write(target,cfg)
        argv=['run_vote_phase','--manifest',str(self.path),'--api-key-stdin']
        stdin=SimpleNamespace(buffer=io.BytesIO(b'synthetic-token-plan-only\n'))
        with patch.object(sys,'argv',argv),patch.object(sys,'stdin',stdin),\
             patch.object(phase.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as run:
            self.assertEqual(phase.main(),0)
        self.assertEqual(run.call_count,1)
        self.assertEqual(run.call_args.kwargs['input'],b'synthetic-token-plan-only\n')

    def test_mixed_phase_rejects_single_key_before_read_or_execution(self):
        argv=['run_vote_phase','--manifest',str(self.path),'--api-key-stdin']
        with patch.object(sys,'argv',argv),patch.object(sys,'stdin',object()),\
             patch.object(phase.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'mixed_credential_slots_require_json_stdin'):phase.main()
        run.assert_not_called()

    def test_one_provider_phase_preserves_single_key_support(self):
        self.manifest['arms']=self.manifest['arms'][:2]
        sampled.write(self.path,self.manifest)
        argv=['run_vote_phase','--manifest',str(self.path),'--api-key-stdin']
        stdin=SimpleNamespace(buffer=io.BytesIO(b'synthetic-qwen-only\n'))
        with patch.object(sys,'argv',argv),patch.object(sys,'stdin',stdin),\
             patch.object(phase.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as run:
            self.assertEqual(phase.main(),0)
        self.assertEqual(run.call_count,2)
        self.assertTrue(all(c.kwargs['input']==b'synthetic-qwen-only\n' for c in run.call_args_list))

    def test_prepare_only_does_not_read_stdin_even_with_credential_flag(self):
        argv=['run_vote_phase','--manifest',str(self.path),'--prepare-only','--credentials-json-stdin']
        with patch.object(sys,'argv',argv),patch.object(sys,'stdin',object()),\
             patch.object(phase.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as run:
            self.assertEqual(phase.main(),0)
        self.assertTrue(all(c.kwargs['input'] is None for c in run.call_args_list))

    def test_invalid_credentials_never_expose_the_input_in_traceback(self):
        args=SimpleNamespace(prepare_only=False,api_key_stdin=False,credentials_json_stdin=True)
        secret='synthetic-private-value'
        malformed=[b'{"dashscope":"'+secret.encode()+b'",',
            json.dumps({'dashscope':secret}).encode(),
            json.dumps({'dashscope':secret,'apiyi':secret+'\n'}).encode(),
            json.dumps({'dashscope':secret,'apiyi':None}).encode(),
            json.dumps([secret]).encode()]
        for raw in malformed:
            with self.subTest(raw_type=type(raw).__name__),patch.object(sys,'stdin',SimpleNamespace(buffer=io.BytesIO(raw))):
                try:phase.load_credentials(args,{'dashscope','apiyi'})
                except ValueError:
                    result=traceback.format_exc()
                    self.assertIn('invalid_stdin_credentials',result)
                    self.assertNotIn(secret,result)
                else:self.fail('invalid credential payload was accepted')

    def test_invalid_slot_is_rejected_before_execution(self):
        target=Path(self.manifest['arms'][0]['config']);cfg=sampled.read(target)
        cfg['credential_slot']='unknown-provider';sampled.write(target,cfg)
        with self.assertRaisesRegex(ValueError,'credential_slot'):phase.validate_manifest(self.manifest)

    def test_missing_explicit_case_mapping_is_rejected(self):
        source=self.root/'data/chest-agent-bench/metadata.jsonl.new'
        source.write_text('',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'missing_explicit_case_binding'):configure.phase0(self.args)

    def stopped_gpt_phase(self):
        arms=phase.validate_manifest(self.manifest)
        out=Path(self.manifest['out']);target=arms[2]
        for arm in arms[:2]:sampled.write(Path(arm['out'])/'status.json',{'status':'generation_complete'})
        sampled.write(out/'status.json',{'status':'stopped','active_arm':target['id']})
        sampled.write(Path(target['out'])/'status.json',{'status':'stopped','stop_event_id':'stop-q1-s1'})
        sampled.write(Path(target['out'])/'stop_events/stop-q1-s1.json',{'reason':'synthetic failure'})
        return arms,out,target

    def test_recovery_acknowledgement_only_reaches_the_active_stopped_child(self):
        arms,out,target=self.stopped_gpt_phase()
        argv=['run_vote_phase','--manifest',str(self.path),'--credentials-json-stdin',
              '--acknowledge-stop','stop-q1-s1','--acknowledge-stop-arm',target['id']]
        stdin=SimpleNamespace(buffer=io.BytesIO(b'{"dashscope":"test-qwen","apiyi":"test-apiyi"}'))
        with patch.object(sys,'argv',argv),patch.object(sys,'stdin',stdin),\
             patch.object(phase.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as run:
            self.assertEqual(phase.main(),0)
        self.assertEqual(run.call_count,3)
        self.assertIn('--acknowledge-stop',run.call_args_list[0].args[0])
        self.assertEqual(run.call_args_list[0].kwargs['input'],b'test-apiyi\n')
        self.assertTrue(all('--acknowledge-stop' not in call.args[0] for call in run.call_args_list[1:]))

    def test_acknowledgement_rejects_wrong_target_event_reuse_and_prepare(self):
        arms,out,target=self.stopped_gpt_phase()
        args=SimpleNamespace(prepare_only=False,acknowledge_stop='stop-q1-s1',acknowledge_stop_arm=target['id'])
        self.assertEqual(phase.acknowledgement_target(args,arms,out),target['id'])
        args.acknowledge_stop_arm=arms[3]['id']
        with self.assertRaisesRegex(ValueError,'active_stopped'):phase.acknowledgement_target(args,arms,out)
        args.acknowledge_stop_arm=target['id'];args.acknowledge_stop='unrelated-event'
        with self.assertRaisesRegex(ValueError,'pending_stop'):phase.acknowledgement_target(args,arms,out)
        args.acknowledge_stop='stop-q1-s1';args.prepare_only=True
        with self.assertRaisesRegex(ValueError,'requires_execution'):phase.acknowledgement_target(args,arms,out)
        args.prepare_only=False
        sampled.write(Path(target['out'])/'stop_acknowledgements/stop-q1-s1.json',{'acknowledged':True})
        with self.assertRaisesRegex(ValueError,'already_acknowledged'):phase.acknowledgement_target(args,arms,out)


if __name__=='__main__':unittest.main()
