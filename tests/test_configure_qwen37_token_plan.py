"""Synthetic configuration contracts for the Token Plan Qwen3.7 run; no APIs/ledgers."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
import configure_qwen37_token_plan as v2


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


class Qwen37TokenPlanConfiguration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.code = 'code_qwen37_token_plan'
        self.config = self.root / self.code / 'configs' / v2.NAME
        old = [{'question_id': f'old_{i}', 'case_id': f'old_case_{i // 2}',
                'question': 'Choose.\nA) Alpha\nB) Beta', 'images': ['figure_1.png'],
                'figure_labels': ['Figure 1']} for i in range(60)]
        self.old_input = self.root / v2.OLD_REL / 'inputs/regression60.jsonl'
        v2.write_rows(self.old_input, old)
        self.old_bytes = self.old_input.read_bytes()
        rows = [dict(old[0], question_id=f'tune_{i}', case_id=f'new_case_{i % 99}') for i in range(402)]
        v2.write_rows(self.root / v2.TUNE, rows)
        write(self.config.parent / 'qwen37_token_plan_profile.json', {
            'model': 'qwen3.7-plus', 'credential_slot': 'token_plan',
            'base_url': v2.TOKEN_PLAN_BASE_URL, 'identity_prefixes': ['qwen3.7-plus'],
            'input_cny_per_million': '4', 'output_cny_per_million': '12',
            'max_input_tokens': 131072, 'max_output_tokens': 8192,
            'price_basis': 'Synthetic conservative proxy, not an invoice.'})
        self.args = dict(root=str(self.root), code=self.code, new_budget_cny='200',
            inherited_committed_cny='197.416240', original_cap_cny='394.252828',
            cumulative_cap_cny='394.252828', inherit_ledger=v2.INHERITED_LEDGER, budget_authorization='synthetic already authorized 200 CNY')
        self.p0 = v2.phase0(**self.args)
        self.p0metrics = self.root / 'reports/p0/metrics.json'
        self.p1metrics = self.root / 'reports/p1/metrics.json'
        self.finish(0)
        write(self.p0metrics, {'status': 'completed', 'phase': 0, 'planned_n': 60,
            'baseline': 'D_regression60',
            'totals': {'D_regression60': {'planned_n': 60, 'correct': 42, 'missing': 0}}})

    def finish(self, phase):
        manifest = v2.read(self.config / f'phase{phase}.json')
        for arm in manifest['arms']:
            cfg = v2.read(v2.at(self.root, arm['config']))
            rows = [json.loads(line) for line in v2.at(self.root, cfg['input']).read_text(encoding='utf-8').splitlines()]
            out = v2.at(self.root, arm['out'])
            write(out / 'protocol.json', cfg)
            write(out / 'selection.json', {'rows': rows})
            write(out / 'status.json', {'status': 'generation_complete'})
            records = [{'question_id': r['question_id'], 'case_id': r['case_id'], 'sample_index': i,
                'answer': 'A', 'status': 'completed'} for r in rows for i in range(1, cfg['samples'] + 1)]
            if arm['id'] == 'qwen_highres_smoke':
                for row in rows:
                    folder = out / 'checkpoints' / row['question_id'] / 'sample_1'
                    write(folder / 'request.json', {'model': 'qwen3.7-plus',
                        'extra_body': {'vl_high_resolution_images': True},
                        'messages': [{'role': 'user', 'content': [
                            {'type': 'text', 'text': 'Figure 1:'},
                            {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,Zml4dHVyZQ=='}}]}]})
                    write(folder / 'image_metadata.json', {'native_bytes_sent': True, 'images': [{'figure_label': 'Figure 1'}]})
            (out / 'predictions.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in records), encoding='utf-8')
        write(v2.at(self.root, manifest['out']) / 'status.json', {'status': 'generation_complete'})

    def run_phase(self, phase):
        return v2.materialize(str(phase), str(self.root), self.code, str(self.config / 'phase0.json'),
            str(self.p0metrics), str(self.p1metrics))

    def ready_phase1(self, extra_correct=7):
        self.run_phase(1)
        self.finish(1)
        write(self.p1metrics, {'status': 'completed', 'phase': 1, 'split': 'tune',
            'planned_n': 402, 'baseline': 'D',
            'totals': {'D': {'planned_n': 402, 'correct': 280},
                       'HiRes': {'planned_n': 402, 'correct': 280 + extra_correct}},
            'tuning_decisions': {'phase1': {'selected': 'HiRes' if extra_correct >= 7 else 'D'}}})

    def test_phase0_is_isolated_two_arm_qwen_only_and_requires_no_gpt_profile(self):
        self.assertEqual(self.p0['new_planned_requests'], 62)
        manifest = v2.read(self.config / 'phase0.json')
        self.assertEqual([a['id'] for a in manifest['arms']], ['D_regression60', 'qwen_highres_smoke'])
        self.assertEqual(manifest['remaining_authorized_budget_snapshot_cny'], '196.836588')
        self.assertIn('never inherited spend plus another 200', manifest['budget_policy'])
        previous = self.args['inherit_ledger']
        for arm in manifest['arms']:
            cfg = v2.read(self.root / arm['config'])
            self.assertEqual(cfg['model'], 'qwen3.7-plus')
            self.assertEqual(cfg['credential_slot'], 'token_plan')
            self.assertEqual(cfg['inherit_ledger'], previous)
            previous = cfg['ledger']
            self.assertTrue(cfg['run_id'].startswith(v2.NAME))
            self.assertEqual(cfg['cap_cny'], '394.252828')
            self.assertEqual(cfg['global_max_requests'], 4714)
            self.assertEqual(cfg['global_max_extra_requests'], 230)
        self.assertEqual(self.old_input.read_bytes(), self.old_bytes)
        self.assertFalse((self.root / self.args['inherit_ledger']).exists())
        self.assertFalse((self.root / v2.REL / 'private_ledgers').exists())
        self.assertFalse((self.root / v2.REL / 'global_requests.json').exists())

    def test_phase_chain_preserves_original_D_tie_anchor_and_budget(self):
        self.ready_phase1(7)
        result = self.run_phase(2)
        self.assertEqual(result['new_planned_requests'], 3618)
        self.assertEqual(result['new_paid_calls_started'], 0)
        self.assertEqual(result['normal_requests_total'], 4484)
        self.assertEqual(result['hard_requests_total'], 4714)
        all_cfgs = []
        for phase in (0, 1, 2):
            manifest = v2.read(self.config / f'phase{phase}.json')
            all_cfgs.extend(v2.read(self.root / a['config']) for a in manifest['arms'])
        self.assertEqual(sum(c['max_requests'] for c in all_cfgs), 4714)
        self.assertEqual(sum(c['max_extra_requests'] for c in all_cfgs), 230)
        previous = self.args['inherit_ledger']
        for cfg in all_cfgs:
            self.assertEqual(cfg['inherit_ledger'], previous)
            previous = cfg['ledger']
            self.assertEqual(cfg['cap_cny'], '394.252828')
        sample_cfg = all_cfgs[-1]
        self.assertTrue(sample_cfg['high_resolution'])
        self.assertTrue(sample_cfg['figure_labels'])
        self.assertEqual(sample_cfg['temperature'], .7)
        self.assertEqual(sample_cfg['input'], v2.TUNE.as_posix())
        score = v2.read(self.config / 'phase2.score.json')
        self.assertEqual(score['baseline'], 'D')
        self.assertEqual(score['selected_single_arm'], 'SelectedSingle')
        self.assertEqual(score['primary_voting_arm'], 'S0')
        self.assertEqual(score['fixed_primary_k'], 9)
        self.assertEqual(score['ks'], list(range(1, 10)))
        arms = {a['id']: a for a in score['arms']}
        self.assertEqual(arms['S0']['direct_arm'], 'D')
        self.assertEqual((self.config / arms['D']['run']).resolve(), self.root / v2.REL / 'phase1/D')
        self.assertEqual((self.config / arms['SelectedSingle']['run']).resolve(), self.root / v2.REL / 'phase1/HiRes')
        self.assertEqual(score['split_rule'], {'k': 9, 'primary_max_top_votes': 6,
            'sensitivity_max_top_votes': [5, 7], 'denominator': 'planned_samples'})
        self.assertEqual(self.run_phase(2), result)

    def test_six_extra_correct_does_not_clear_exact_1p5_point_gate(self):
        self.ready_phase1(6)
        self.assertEqual(v2.selected_phase1(self.p1metrics), 'D')
        self.run_phase(2)
        score = v2.read(self.config / 'phase2.score.json')
        self.assertEqual(score['selected_single_arm'], 'D')
        self.assertEqual([a['id'] for a in score['arms']], ['D', 'S0'])
        manifest = v2.read(self.config / 'phase2.json')
        cfg = v2.read(self.root / manifest['arms'][0]['config'])
        self.assertFalse(cfg['high_resolution'])
        values = v2.read(self.p1metrics)
        values['tuning_decisions']['phase1']['selected'] = 'HiRes'
        write(self.p1metrics, values)
        with self.assertRaisesRegex(ValueError, 'fixed_1p5'):
            v2.selected_phase1(self.p1metrics)

    def test_phase1_has_only_D_and_HiRes_and_804_new_calls(self):
        result = self.run_phase(1)
        self.assertEqual(result['new_planned_requests'], 804)
        score = v2.read(self.config / 'phase1.score.json')
        self.assertEqual([a['id'] for a in score['arms']], ['D', 'HiRes'])
        self.assertEqual(score['selection'], {'candidates': ['HiRes'], 'minimum_gain_pp': 1.5})

    def test_phase2_requires_complete_generation_not_just_metrics(self):
        self.ready_phase1()
        write(self.root / v2.REL / 'phase1/status.json', {'status': 'running'})
        with self.assertRaisesRegex(ValueError, 'predecessor_phase_not_complete'):
            self.run_phase(2)

    def test_stage0_is_technical_and_never_filters_changed_model_by_accuracy(self):
        values = v2.read(self.p0metrics)
        for score in (0, 39, 45, 60):
            values['totals']['D_regression60']['correct'] = score
            write(self.p0metrics, values)
            v2.phase0_gate(self.config / 'phase0.json', self.p0metrics, self.root)
        values['totals']['D_regression60']['missing'] = 1
        write(self.p0metrics, values)
        with self.assertRaisesRegex(ValueError, 'technical_gate'):
            self.run_phase(1)

    def test_smoke_missing_illegal_answer_or_missing_visual_payload_fails(self):
        path = self.root / v2.REL / 'phase0/qwen_highres_smoke/predictions.jsonl'
        records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        records[0].update(status='completed', answer='Z')
        path.write_text(''.join(json.dumps(r) + '\n' for r in records), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'phase0_missing_or_failed_output'):
            self.run_phase(1)
        self.finish(0)
        folder = self.root / v2.REL / 'phase0/qwen_highres_smoke/checkpoints/old_0/sample_1'
        payload = v2.read(folder / 'request.json')
        payload['messages'][0]['content'] = [{'type': 'text', 'text': 'No actual image'}]
        write(folder / 'request.json', payload)
        with self.assertRaisesRegex(ValueError, 'saved_native_visual_payload'):
            self.run_phase(1)

    def test_frozen_configuration_cannot_be_rewritten_and_inputs_stay_old(self):
        self.assertEqual(v2.phase0(**self.args), self.p0)
        changed = dict(self.args, budget_authorization='different authorization')
        with self.assertRaisesRegex(ValueError, 'refusing_to_replace_frozen_config'):
            v2.phase0(**changed)
        self.assertEqual(self.old_input.read_bytes(), self.old_bytes)

    def test_budget_cannot_expand_or_bypass_original_cap(self):
        for changes in ({'new_budget_cny': '201'}, {'original_cap_cny': '390'},
                        {'new_budget_cny': 'NaN'}, {'inherited_committed_cny': '-1'},
                        {'inherited_committed_cny': '400'}, {'cumulative_cap_cny': '397.416240'},
                        {'original_cap_cny': '1000000'}, {'inherit_ledger': 'private/reset.json'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                v2.phase0(**dict(self.args, **changes))

    def test_public_profile_rejects_wrong_provider_or_rates(self):
        path = self.config.parent / 'qwen37_token_plan_profile.json'
        original = v2.read(path)
        for field, value in [('model', 'qwen3-vl-plus'), ('input_cny_per_million', '0'), ('base_url', 'https://example.org/v1'), ('api_key', 'fixture-secret')]:
            write(path, dict(original, **{field: value}))
            with self.subTest(field=field), self.assertRaises(ValueError):
                v2.load_profile(path)

    def test_missing_case_or_label_fields_rejected_without_metadata_fallback(self):
        path = self.root / v2.TUNE
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        rows[0]['answer'] = 'A'
        path.write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'label_free_case_bound'):
            self.run_phase(1)

    def test_later_stages_cannot_be_materialized(self):
        with self.assertRaisesRegex(ValueError, 'only_authorized_qwen'):
            self.run_phase(3)
        with self.assertRaises(SystemExit):
            v2.main(['--phase', '3', '--root', str(self.root), '--code', self.code])
        self.assertFalse((self.config / 'phase3.json').exists())


if __name__ == '__main__':
    unittest.main()
