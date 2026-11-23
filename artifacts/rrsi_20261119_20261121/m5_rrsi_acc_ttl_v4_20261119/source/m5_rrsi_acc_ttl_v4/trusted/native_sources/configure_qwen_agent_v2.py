"""Freeze the authorized Qwen-only agent-v2 stages 0, 1 and 2.

This configurator never calls a model, opens credentials/account ledgers, or
reads reference answers. It keeps the old multimodel prepared run intact and
uses its frozen, label-free tuning input. Generation and offline scoring remain
separate commands; later tools/models/held-out stages are outside this CLI.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from decimal import Decimal
import json
import math
import os
from pathlib import Path

from configure_vote_gain import dump_new, profile
from configure_vote_tune import at, completed, metric, read, rel
from run_sampled_vlm import validate_cfg
from run_vote_phase import validate_manifest


NAME = 'qwen_agent_v2_20261102'
REL = Path('runs') / NAME
OLD_REL = Path('runs/multimodel_vote_gain_20261102')
TUNE = OLD_REL / 'split_inputs/tune.inputs.jsonl'
N = 402
NORMAL_REQUESTS = 62 + 804 + 3618
EXTRA_REQUESTS = 6 + 1 + 21 + 21 + 181
HARD_REQUESTS = NORMAL_REQUESTS + EXTRA_REQUESTS
AUTHORIZED_BUDGET = Decimal('200')
INPUT_FIELDS = {'question_id', 'case_id', 'question', 'images', 'figure_labels'}


def visual_rows(path, count):
    rows = [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    if len(rows) != count or len({str(r['question_id']) for r in rows}) != count:
        raise ValueError('fixed_unique_visual_input_count_required')
    if any(set(r) - INPUT_FIELDS or not r.get('case_id') or not r.get('images') or not r.get('question') for r in rows):
        raise ValueError('label_free_case_bound_visual_input_required')
    return rows


def write_rows(path, rows):
    path = Path(path)
    text = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows)
    if path.exists() and path.read_text(encoding='utf-8') != text:
        raise ValueError('refusing_to_replace_frozen_input')
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')


def roots(root, code):
    root = Path(root).resolve()
    code = at(root, code)
    rel(root, code)
    return root, code / 'configs' / NAME


def request_policy(cfg):
    """Keep every phase on the same bounded Qwen-only authorization."""
    if cfg['model'] != 'qwen3-vl-plus' or cfg['credential_slot'] != 'dashscope':
        raise ValueError('qwen_only_scope_required')
    if cfg['prompt_variant'] != 'answer' or cfg.get('extra_body', {}).get('enable_thinking') is not False:
        raise ValueError('answer_without_thinking_required')
    if (cfg['global_max_requests'], cfg['global_max_extra_requests']) != (HARD_REQUESTS, EXTRA_REQUESTS):
        raise ValueError('fixed_4714_total_230_extra_request_bounds_required')
    if Decimal(str(cfg['new_experiment_budget_cny'])) != AUTHORIZED_BUDGET:
        raise ValueError('existing_200_cny_authorization_required')
    if not cfg['run_id'].startswith(NAME + '_') or not cfg['ledger'].startswith(REL.as_posix() + '/'):
        raise ValueError('new_isolated_v2_run_namespace_required')
    if cfg['global_request_counter'] != (REL / 'global_requests.json').as_posix():
        raise ValueError('isolated_v2_global_counter_required')
    validate_cfg(cfg)


def freeze_phase(root, config_dir, phase, inherited, specifications, previous,
                 score_arms, baseline, score_fields=None, provenance=None):
    first_ledger = previous
    arms = []
    for arm_id, cfg, count in specifications:
        cfg['root'] = str(root)
        cfg['inherit_ledger'] = previous
        request_policy(cfg)
        path = config_dir / f'p{phase}_{arm_id}.json'
        dump_new(path, cfg)
        arms.append({'id': arm_id, 'config': rel(root, path),
                     'out': (REL / f'phase{phase}' / arm_id).as_posix()})
        previous = cfg['ledger']
    manifest = {k: inherited[k] for k in ('cap_cny', 'new_experiment_budget_cny',
        'budget_authorization', 'global_request_counter')}
    manifest.update(root=str(root), out=(REL / f'phase{phase}').as_posix(), phase=int(phase), arms=arms,
        inherit_ledger=first_ledger, authorized_scope='Qwen-only stages 0 through 2; no automatic launch',
        reused_runs=[a['id'] for a in score_arms if a.get('reuse')], provenance=provenance or {},
        normal_requests_total=NORMAL_REQUESTS, technical_extra_requests_total=EXTRA_REQUESTS,
        hard_requests_total=HARD_REQUESTS,
        next_phase='Stop after this phase; score offline before freezing the next stage. Stop after stage 2.')
    for key in ('inherited_committed_snapshot_cny', 'original_cap_cny'):
        if key in inherited:
            manifest[key] = inherited[key]
    validate_manifest(manifest)
    manifest_path = config_dir / f'phase{phase}.json'
    score_path = config_dir / f'phase{phase}.score.json'
    score = {'phase': int(phase), 'split': 'regression' if int(phase) == 0 else 'tune',
        'baseline': baseline, 'ks': list(range(1, 10)), 'seed': 20261102,
        'bootstrap_repeats': 2000, 'subsample_repeats': 200,
        'arms': [{k: v for k, v in arm.items() if k not in ('out', 'reuse')} |
            {'run': Path(os.path.relpath(arm['out'], config_dir)).as_posix()} for arm in score_arms],
        'provenance': provenance or {}}
    if score_fields:
        score.update(score_fields)
    dump_new(manifest_path, manifest)
    dump_new(score_path, score)
    return {'phase_manifest': rel(root, manifest_path), 'scoring_manifest': rel(root, score_path),
        'new_planned_requests': sum(count * cfg['samples'] for _, cfg, count in specifications),
        'normal_requests_total': NORMAL_REQUESTS, 'hard_requests_total': HARD_REQUESTS,
        'new_paid_calls_started': 0, 'cap_cny': manifest['cap_cny']}


def phase0(root, code, new_budget_cny, inherited_committed_cny, original_cap_cny,
           inherit_ledger, budget_authorization):
    root, config_dir = roots(root, code)
    budget = Decimal(new_budget_cny)
    baseline = Decimal(inherited_committed_cny)
    original_cap = Decimal(original_cap_cny)
    if not all(x.is_finite() for x in (budget, baseline, original_cap)) or baseline < 0:
        raise ValueError('finite_nonnegative_budget_snapshot_required')
    cap = baseline + budget
    if budget != AUTHORIZED_BUDGET or cap > original_cap or not budget_authorization.strip():
        raise ValueError('existing_200_cny_budget_within_original_cap_required')
    source = root / OLD_REL / 'inputs/regression60.jsonl'
    if not source.exists():
        source = root / 'runs/v4_validation60/inputs.jsonl'
    # The prepared source already has explicit case IDs. Never open reference
    # metadata merely to reconstruct IDs; a missing binding must be supplied.
    rows = visual_rows(source, 60)
    write_rows(root / REL / 'inputs/regression60.jsonl', rows)
    write_rows(root / REL / 'inputs/capabilities2.jsonl', rows[:2])
    inherited = {'cap_cny': str(cap), 'new_experiment_budget_cny': str(budget),
        'budget_authorization': budget_authorization,
        'global_request_counter': (REL / 'global_requests.json').as_posix(),
        'inherited_committed_snapshot_cny': str(baseline), 'original_cap_cny': str(original_cap)}
    specifications = []
    for arm_id, count, hires in [('D_regression60', 60, False), ('qwen_highres_smoke', 2, True)]:
        extra = {'enable_thinking': False}
        if hires:
            extra['vl_high_resolution_images'] = True
        cfg = {'root': str(root), 'run_id': f'{NAME}_p0_{arm_id}', 'model': 'qwen3-vl-plus',
            'prompt_variant': 'answer', 'credential_slot': 'dashscope',
            'input': (REL / 'inputs' / ('regression60.jsonl' if count == 60 else 'capabilities2.jsonl')).as_posix(),
            'image_root': 'data/memory_v1/images', 'samples': 1,
            'temperature': .2, 'top_p': .95, 'max_output_tokens': 2048,
            'request_timeout_seconds': 120, 'stream': False, 'extra_body': extra,
            'figure_labels': hires, 'high_resolution': hires,
            'capability_smoke': count == 2, 'capability_confirmed': False,
            'profile': profile('qwen3-vl-plus', 8192),
            'ledger': (REL / 'private_ledgers' / f'p0_{arm_id}.json').as_posix(),
            'inherit_ledger': inherit_ledger, **{k: inherited[k] for k in ('cap_cny',
                'new_experiment_budget_cny', 'budget_authorization', 'global_request_counter')},
            'max_requests': count + (6 if count == 60 else 1),
            'max_extra_requests': 6 if count == 60 else 1, 'max_attempts_per_sample': 2,
            'global_max_requests': HARD_REQUESTS, 'global_max_extra_requests': EXTRA_REQUESTS}
        specifications.append((arm_id, cfg, count))
    result = freeze_phase(root, config_dir, 0, inherited, specifications, inherit_ledger,
        [{'id': 'D_regression60', 'out': root / REL / 'phase0/D_regression60'}], 'D_regression60',
        score_fields={'generation_gate': Path(os.path.relpath(root / REL / 'phase0/status.json', config_dir)).as_posix()},
        provenance={'regression_input_source': rel(root, source), 'labels_read_by_configurator': False,
                    'old_prepared_run_preserved': True})
    dump_new(config_dir / 'phase0.smokes.export.json', {'phase': 0, 'split': 'capability_smoke',
        'arms': [{'id': 'qwen_highres_smoke', 'run': Path(os.path.relpath(
            root / REL / 'phase0/qwen_highres_smoke', config_dir)).as_posix()}]})
    return result


def phase0_gate(manifest_path, metrics_path, root):
    names = {'D_regression60': 60, 'qwen_highres_smoke': 2}
    manifest, arms = completed(manifest_path, root, names, 1)
    if set(arms) != set(names):
        raise ValueError('exact_qwen_v2_two_arm_phase0_required')
    values = metric(metrics_path, 0, 60)
    if values.get('baseline') != 'D_regression60':
        raise ValueError('original_regression_D_metrics_required')
    total = values['totals']['D_regression60']
    if total.get('planned_n') != 60 or not 40 <= total.get('correct', -1) <= 44 or total.get('missing') != 0:
        raise ValueError('phase0_regression_gate_requires_40_to_44_and_zero_missing')
    for name, arm in arms.items():
        request_policy(arm['cfg'])
        if any(r['status'] != 'completed' or not r.get('answer') for r in arm['run']['records']):
            raise ValueError('phase0_missing_or_failed_output:' + name)
    smoke = arms['qwen_highres_smoke']['cfg']
    if not all(smoke.get(k) for k in ('capability_smoke', 'high_resolution', 'figure_labels')):
        raise ValueError('highres_and_figure_binding_not_smoked')
    return manifest, arms


def selected_phase1(metrics_path):
    values = metric(metrics_path, 1, N)
    if values.get('baseline') != 'D' or set(values['totals']) != {'D', 'HiRes'}:
        raise ValueError('exact_D_HiRes_tuning_metrics_required')
    totals = values['totals']
    if any(totals[k].get('planned_n') != N for k in ('D', 'HiRes')):
        raise ValueError('complete_402_denominator_required')
    gain = Decimal(100) * Decimal(totals['HiRes']['correct'] - totals['D']['correct']) / Decimal(N)
    expected = 'HiRes' if gain >= Decimal('1.5') else 'D'
    choice = values.get('tuning_decisions', values.get('decisions', {})).get('phase1', {}).get('selected')
    if choice != expected:
        raise ValueError('phase1_decision_conflicts_with_fixed_1p5_point_gate')
    return choice


def arm_config(template, phase, arm_id, previous, samples=1, temperature=.2):
    cfg = deepcopy(template)
    cfg.update(run_id=f'{NAME}_p{phase}_{arm_id}', input=TUNE.as_posix(), samples=samples,
        capability_smoke=False, capability_confirmed=True, temperature=temperature,
        ledger=(REL / 'private_ledgers' / f'p{phase}_{arm_id}.json').as_posix(), inherit_ledger=previous,
        max_requests=N * samples + math.ceil(N * samples * .05),
        max_extra_requests=math.ceil(N * samples * .05), max_attempts_per_sample=2)
    request_policy(cfg)
    return cfg


def materialize(phase, root, code, phase0_manifest, phase0_metrics, phase1_metrics=None):
    if str(phase) not in ('1', '2'):
        raise ValueError('only_authorized_qwen_stages_1_and_2')
    phase = str(phase)
    root, config_dir = roots(root, code)
    qids = [str(r['question_id']) for r in visual_rows(root / TUNE, N)]
    p0, templates = phase0_gate(at(root, phase0_manifest), at(root, phase0_metrics), root)
    last0 = templates[p0['arms'][-1]['id']]['cfg']['ledger']
    provenance = {'phase0_manifest': rel(root, at(root, phase0_manifest)),
        'phase0_metrics': rel(root, at(root, phase0_metrics)), 'labels_read_by_configurator': False,
        'tuning_input_source': TUNE.as_posix()}
    if phase == '1':
        specifications = []
        for name, template in [('D', 'D_regression60'), ('HiRes', 'qwen_highres_smoke')]:
            specifications.append((name, arm_config(templates[template]['cfg'], 1, name, last0), N))
        return freeze_phase(root, config_dir, 1, p0, specifications, last0,
            [{'id': name, 'out': root / REL / 'phase1' / name} for name in ('D', 'HiRes')], 'D',
            score_fields={'selection': {'candidates': ['HiRes'], 'minimum_gain_pp': 1.5}}, provenance=provenance)
    p1, runs = completed(config_dir / 'phase1.json', root, N, 1)
    if set(runs) != {'D', 'HiRes'} or any(r['run']['qids'] != qids for r in runs.values()):
        raise ValueError('exact_completed_D_HiRes_same_tune_order_required')
    for run in runs.values():
        request_policy(run['cfg'])
    chosen = selected_phase1(at(root, phase1_metrics))
    last1 = runs[p1['arms'][-1]['id']]['cfg']['ledger']
    cfg = arm_config(runs[chosen]['cfg'], 2, 'Qwen_SC9', last1, samples=9, temperature=.7)
    scoring = [{'id': 'D', 'out': runs['D']['out'], 'reuse': True}]
    selected_id = 'D'
    if chosen != 'D':
        selected_id = 'SelectedSingle'
        scoring.append({'id': selected_id, 'out': runs[chosen]['out'], 'reuse': True})
    scoring.append({'id': 'S0', 'out': root / REL / 'phase2/Qwen_SC9', 'direct_arm': 'D'})
    provenance.update(phase1_metrics=rel(root, at(root, phase1_metrics)), selected_phase1=chosen,
        tie_break_anchor='original D; only among tied leading options',
        selected_single_reused_without_new_requests=True)
    return freeze_phase(root, config_dir, 2, p0, [('Qwen_SC9', cfg, N)], last1, scoring, 'D',
        score_fields={'primary_voting_arm': 'S0', 'selected_single_arm': selected_id, 'fixed_primary_k': 9,
            'split_rule': {'k': 9, 'primary_max_top_votes': 6, 'sensitivity_max_top_votes': [5, 7],
                           'denominator': 'planned_samples'}}, provenance=provenance)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, choices=('0', '1', '2'))
    parser.add_argument('--root', required=True)
    parser.add_argument('--code', required=True)
    for name in ('new-budget-cny', 'inherited-committed-cny', 'original-cap-cny', 'inherit-ledger',
                 'budget-authorization', 'phase0-manifest', 'phase0-metrics', 'phase1-metrics'):
        parser.add_argument('--' + name)
    args = parser.parse_args(argv)
    fields = ('new_budget_cny', 'inherited_committed_cny', 'original_cap_cny', 'inherit_ledger', 'budget_authorization')
    if args.phase == '0':
        for key in fields:
            if getattr(args, key) is None:
                parser.error('--' + key.replace('_', '-') + ' is required for phase 0')
        result = phase0(args.root, args.code, **{k: getattr(args, k) for k in fields})
    else:
        for key in ('phase0_manifest', 'phase0_metrics') + (('phase1_metrics',) if args.phase == '2' else ()):
            if getattr(args, key) is None:
                parser.error('--' + key.replace('_', '-') + ' is required after generation and offline scoring')
        result = materialize(args.phase, args.root, args.code, args.phase0_manifest, args.phase0_metrics, args.phase1_metrics)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
