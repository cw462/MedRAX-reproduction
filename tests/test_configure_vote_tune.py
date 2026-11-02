"""Synthetic offline phase 0→3 configuration contracts; no API or ledger access."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
import configure_vote_gain as phase0
import configure_vote_tune as tune


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value),encoding='utf-8')


class TuningConfiguration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.code=self.root/'code_vote_gain'
        self.config=self.code/'configs'/tune.NAME
        old=[{'question_id':f'old_{i}','case_id':f'old_case_{i//2}',
              'question':'Choose.\nA) Alpha\nB) Beta','images':['figure_1.png']} for i in range(60)]
        path=self.root/'runs/v4_validation60/inputs.jsonl';path.parent.mkdir(parents=True)
        path.write_text(''.join(json.dumps(r)+'\n' for r in old),encoding='utf-8')
        rows=[dict(old[0],question_id=f'tune_{i}',case_id=f'new_case_{i//2}',figure_labels=['Figure 1']) for i in range(402)]
        path=self.root/tune.TUNE;path.parent.mkdir(parents=True)
        path.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
        self.gpt_profile=self.root/'gpt4o.public.json'
        write(self.gpt_profile,{'model':'gpt-4o','credential_slot':'apiyi',
            'base_url':'https://example.invalid/v1','identity_prefixes':['gpt-4o'],
            'input_cny_per_million':'1','output_cny_per_million':'2',
            'price_basis':'synthetic fixture only','max_input_tokens':120000,'max_output_tokens':8192})
        with contextlib.redirect_stdout(io.StringIO()):
            phase0.phase0(SimpleNamespace(root=str(self.root),code='code_vote_gain',
                new_budget_cny='200',inherited_committed_cny='194.252828',original_cap_cny='1000000',
                inherit_ledger='reports/old.json',budget_authorization='synthetic 200 CNY',
                gpt4o_profile=str(self.gpt_profile)))
        self.p0metrics=self.root/'reports/p0/metrics.json'
        self.p1metrics=self.root/'reports/p1/metrics.json'
        self.p3metrics=self.root/'reports/p3a/metrics.json'
        self.finish('0')
        write(self.p0metrics,{'status':'completed','phase':0,'planned_n':60,'baseline':'D',
            'totals':{'D':{'planned_n':60,'correct':42,'missing':0}}})

    def finish(self,phase):
        manifest=tune.read(self.config/f'phase{phase}.json')
        for arm in manifest['arms']:
            cfg=tune.read(tune.at(self.root,arm['config']))
            rows=[json.loads(line) for line in tune.at(self.root,cfg['input']).read_text(encoding='utf-8').splitlines()]
            out=tune.at(self.root,arm['out'])
            write(out/'protocol.json',cfg);write(out/'selection.json',{'rows':rows})
            write(out/'status.json',{'status':'generation_complete'})
            records=[{'question_id':r['question_id'],'case_id':r['case_id'],'sample_index':i,
                      'answer':'A','status':'completed'} for r in rows for i in range(1,cfg['samples']+1)]
            (out/'predictions.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records),encoding='utf-8')
        write(tune.at(self.root,manifest['out'])/'status.json',{'status':'generation_complete'})

    def run_phase(self,phase):
        return tune.materialize(phase,str(self.root),'code_vote_gain',
            str(self.config/'phase0.json'),str(self.p0metrics),str(self.p1metrics),str(self.p3metrics))

    def through_two(self):
        self.run_phase('1');self.finish('1')
        values={'D':280,'TextOnly':350,'HiRes':290,'CoT':281,'Think':287}
        write(self.p1metrics,{'status':'completed','phase':1,'split':'tune','planned_n':402,
            'totals':{k:{'correct':v,'planned_n':402} for k,v in values.items()},
            'tuning_decisions':{'phase1':{'selected':'HiRes'}}})
        self.run_phase('2');self.finish('2')

    def through_three_a(self,strongest='QwenMax_B0'):
        self.through_two();self.run_phase('3a');self.finish('3a')
        values={k:300 for k in tune.DIRECT_IDS};values[strongest]=320
        write(self.p3metrics,{'status':'completed','phase':'3a','split':'tune','planned_n':402,
            'totals':{k:{'correct':v,'planned_n':402} for k,v in values.items()}})

    def test_full_configuration_chain_reuses_Qwen_and_preserves_cumulative_budget(self):
        self.through_three_a()
        result=self.run_phase('3b')
        self.assertEqual(result['new_planned_requests'],402*12)
        self.assertEqual(result['new_paid_calls_started'],0)
        manifest=tune.read(self.config/'phase3b.json')
        self.assertEqual(len(manifest['arms']),2)
        previous=manifest['inherit_ledger']
        counts={}
        for arm in manifest['arms']:
            self.assertFalse(Path(arm['config']).is_absolute())
            self.assertFalse(Path(arm['out']).is_absolute())
            cfg=tune.read(self.root/arm['config']);counts[arm['id']]=cfg['samples']
            self.assertEqual(cfg['cap_cny'],'394.252828')
            self.assertEqual(cfg['new_experiment_budget_cny'],'200')
            self.assertEqual(cfg['inherit_ledger'],previous);previous=cfg['ledger']
            self.assertEqual(cfg['global_max_requests'],59082)
        self.assertEqual(counts,{'QwenMax_samples':9,'GPT4o_samples':3})
        score=tune.read(self.config/'phase3b.score.json')
        self.assertEqual(score['ensemble']['strongest_member'],'S1')
        self.assertEqual(score['ensemble']['primary_vote_rule'],'tune_accuracy_weighted_model_majorities')
        self.assertEqual(score['ensemble']['weights']['S1'],320/402)
        qwen=next(a for a in score['arms'] if a['id']=='S0')
        self.assertEqual((self.config/qwen['run']).resolve(),self.root/tune.REL/'phase2/Qwen_SC9')
        self.assertEqual(qwen['direct_arm'],'Qwen_B0')
        self.assertEqual(self.run_phase('3b'),result)  # identical configuration is reusable, no append/rewrite
        self.assertFalse((self.root/'reports/old.json').exists())

    def test_phase1_has_five_arms_but_text_only_cannot_win_selection(self):
        result=self.run_phase('1');self.assertEqual(result['new_planned_requests'],402*5)
        score=tune.read(self.config/'phase1.score.json')
        self.assertEqual(score['selection']['candidates'],['HiRes','CoT','Think'])
        self.through_two()
        values=tune.read(self.p1metrics);values['tuning_decisions']['phase1']['selected']='TextOnly'
        write(self.p1metrics,values)
        with self.assertRaisesRegex(ValueError,'text_only_is_diagnostic'):self.run_phase('3a')

    def test_regression_and_capability_gates_fail_closed(self):
        values=tune.read(self.p0metrics);values['totals']['D']['correct']=45;write(self.p0metrics,values)
        with self.assertRaisesRegex(ValueError,'40_to_44'):self.run_phase('1')
        values['totals']['D']['correct']=42;values['totals']['D']['missing']=1;write(self.p0metrics,values)
        with self.assertRaisesRegex(ValueError,'zero_missing'):self.run_phase('1')
        values['totals']['D']['missing']=0;write(self.p0metrics,values)
        manifest=tune.read(self.config/'phase0.json');arm=manifest['arms'][-1]
        write(tune.at(self.root,arm['out'])/'status.json',{'status':'stopped'})
        with self.assertRaisesRegex(ValueError,'generation_not_complete'):self.run_phase('1')

    def test_phase2_requires_completed_phase1_and_consistent_fixed_gate(self):
        self.run_phase('1')
        write(self.root/tune.REL/'phase1/status.json',{'status':'running'})
        with self.assertRaisesRegex(ValueError,'predecessor_phase_not_complete'):self.run_phase('2')
        self.through_two()
        values=tune.read(self.p1metrics);values['totals']['HiRes']['correct']=281
        values['totals']['Think']['correct']=281;write(self.p1metrics,values)
        with self.assertRaisesRegex(ValueError,'fixed_1p5'):self.run_phase('3a')

    def test_cross_model_only_supported_flags_and_gpt4o_sampling(self):
        self.through_three_a('GPT4o_B0');self.run_phase('3b')
        manifests=[tune.read(self.config/f'phase{p}.json') for p in ('3a','3b')]
        for manifest in manifests:
            for arm in manifest['arms']:
                cfg=tune.read(self.root/arm['config'])
                self.assertTrue(cfg['figure_labels']);self.assertFalse(cfg['high_resolution'])
                self.assertNotIn('vl_high_resolution_images',cfg['extra_body'])
                if cfg['model']=='gpt-4o':
                    self.assertEqual(cfg['temperature'],.2 if manifest['phase']=='3a' else .7)
                    self.assertEqual(cfg['extra_body'],{})
                    self.assertEqual(cfg['max_output_tokens'],2048)
                    self.assertEqual(cfg['credential_slot'],'apiyi')
                    self.assertEqual(cfg['profile']['input_cny_per_million'],'1')
                    self.assertEqual(cfg['profile']['max_input_tokens'],120000)
                    self.assertEqual(cfg['profile']['base_url'],'https://example.invalid/v1')
                else:
                    self.assertEqual(cfg['credential_slot'],'dashscope')
                    self.assertEqual(cfg['profile']['max_input_tokens'],131072)
        score=tune.read(self.config/'phase3b.score.json')
        self.assertEqual(score['ensemble']['strongest_member'],'S2')
        cfg=tune.read(self.root/manifests[-1]['arms'][-1]['config'])
        self.assertEqual(cfg['samples'],9)

    def test_public_gpt4o_profile_rejects_credentials_and_nonpositive_rates(self):
        values=tune.read(self.gpt_profile)
        for key,value in [('api_key','synthetic-credential'),('input_cny_per_million','0')]:
            changed=dict(values);changed[key]=value;write(self.gpt_profile,changed)
            with self.assertRaises(ValueError) as caught:phase0.load_gpt4o_profile(self.gpt_profile)
            self.assertNotIn('synthetic-credential',str(caught.exception))
        with self.assertRaisesRegex(ValueError,'explicit_gpt4o'):phase0.load_gpt4o_profile(None)

    def test_when_Qwen_is_strongest_only_three_new_samples_per_other_model(self):
        self.through_three_a('Qwen_B0');result=self.run_phase('3b')
        self.assertEqual(result['new_planned_requests'],402*6)
        score=tune.read(self.config/'phase3b.score.json')
        self.assertEqual(score['ensemble']['strongest_member'],'S0')
        self.assertTrue(score['ensemble']['Qwen_nine_samples_reused_without_new_requests'])

    def test_phase3a_scoring_is_B0_only_and_phase5_is_not_generated(self):
        self.through_two();self.run_phase('3a')
        score=tune.read(self.config/'phase3a.score.json')
        self.assertNotIn('ensemble',score)
        self.assertEqual([x['id'] for x in score['arms']],list(tune.DIRECT_IDS))
        self.assertFalse((self.config/'phase5.json').exists())
        with self.assertRaises(SystemExit):tune.main(['--phase','5'])


if __name__=='__main__':unittest.main()
