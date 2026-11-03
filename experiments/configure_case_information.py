"""Freeze the six-arm case-information plan without inference or ledger access.

Reads only the prior arm configuration, public profiles/protocol, and frozen
label-free inputs. Approval is deliberately neither created nor implied here.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path

from configure_vote_gain import dump_new
from run_sampled_vlm import validate_cfg

EXPERIMENT_ID = 'case_information_20261103'
PLAN_VERSION = '1'
FIXED_CAP = Decimal('394.252828')
REL = Path('runs') / EXPERIMENT_ID
OLD_INPUTS = Path('runs/multimodel_vote_gain_20261102/split_inputs')
PRIOR_LEDGER = 'runs/qwen37_token_plan_20261102/private_ledgers/p2_Qwen_SC9.json'
BASELINE_RUN = 'runs/qwen37_token_plan_20261102/phase1/D'
MODELS = {'qwen3.7-plus', 'deepseek-v4.1-flash-1017', 'qwen3.8-flash'}
NORMAL_REQUESTS = 2709
EXTRA_REQUESTS = 140
HARD_REQUESTS = 2849
INPUT_FIELDS = {'question_id', 'case_id', 'question', 'images', 'figure_labels'}
ARM_SPECS = (
    ('E1_DeepSeek', 'deepseek-v4.1-flash-1017', 'independent', 'tune', 402, 99, 402, 21),
    ('E1_QwenFlash', 'qwen3.8-flash', 'independent', 'tune', 402, 99, 402, 21),
    ('E2_Batch', 'qwen3.7-plus', 'case_batch', 'tune', 402, 99, 99, 5),
    ('E2_Sequential', 'qwen3.7-plus', 'case_sequential', 'tune', 402, 99, 402, 21),
    ('E3_Evidence', 'qwen3.7-plus', 'case_evidence', 'tune', 402, 99, 402, 21),
    ('E0_Heldout', 'qwen3.7-plus', 'independent', 'test', 1002, 241, 1002, 51),
)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def inside(root, path):
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if not path.is_relative_to(root):
        raise ValueError('path_must_stay_within_experiment_root')
    return path


def relative(root, path):
    return inside(root, path).relative_to(root).as_posix()


def input_rows(path, questions, cases):
    text = Path(path).read_text(encoding='utf-8')
    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    if len(rows) != questions or len({str(r.get('question_id')) for r in rows}) != questions:
        raise ValueError('fixed_unique_question_count_required')
    if any(set(r) - INPUT_FIELDS or not r.get('case_id') or not r.get('question') or not r.get('images') for r in rows):
        raise ValueError('label_free_case_bound_visual_inputs_required')
    if len({str(r['case_id']) for r in rows}) != cases:
        raise ValueError('fixed_case_count_required')
    return rows, text


def copy_frozen_input(target, text):
    if target.exists() and target.read_text(encoding='utf-8') != text:
        raise ValueError('refusing_to_replace_frozen_input')
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(text, encoding='utf-8')


def configure(root, code, previous_arm_config, public_plan=None):
    root = Path(root).resolve()
    code = inside(root, code)
    config_dir = code / 'configs' / EXPERIMENT_ID
    plan_path = inside(root, public_plan or code/'configs/case_information_protocol.json')
    plan = read(plan_path)
    if (plan.get('experiment_id') != EXPERIMENT_ID or str(plan.get('plan_version')) != PLAN_VERSION
            or plan.get('status') != 'awaiting_user_confirmation'):
        raise ValueError('pending_public_protocol_required')
    if set(plan.get('models', [])) != MODELS:
        raise ValueError('exact_three_model_public_plan_required')
    expected_plan = [(a, m, mode, q, c, n, e) for a, m, mode, _, q, c, n, e in ARM_SPECS]
    actual_plan = [(a.get('id'), a.get('model'), a.get('mode'), a.get('questions'), a.get('cases'),
                    a.get('normal_requests'), a.get('technical_extra_requests')) for a in plan.get('arms', [])]
    if actual_plan != expected_plan:
        raise ValueError('public_plan_six_arm_contract_mismatch')
    previous_path = inside(root, previous_arm_config)
    old = read(previous_path)  # A configuration, never the ledger it references.
    if (old.get('model') != 'qwen3.7-plus' or old.get('credential_slot') != 'token_plan'
            or old.get('samples') != 9 or old.get('ledger') != PRIOR_LEDGER
            or Path(old.get('root', '')).resolve() != root
            or Decimal(str(old.get('cap_cny'))) != FIXED_CAP
            or Decimal(str(old.get('new_experiment_budget_cny'))) != Decimal('200')):
        raise ValueError('latest_completed_qwen37_arm_configuration_required_without_budget_reset')
    splits = {}
    for split, questions, cases in [('tune', 402, 99), ('test', 1002, 241)]:
        splits[split] = input_rows(root/OLD_INPUTS/f'{split}.inputs.jsonl', questions, cases)
    tune_cases = {str(r['case_id']) for r in splits['tune'][0]}
    test_cases = {str(r['case_id']) for r in splits['test'][0]}
    if tune_cases & test_cases:
        raise ValueError('tuning_and_heldout_cases_must_be_disjoint')
    if ({str(r['question_id']) for r in splits['tune'][0]}
            & {str(r['question_id']) for r in splits['test'][0]}):
        raise ValueError('tuning_and_heldout_questions_must_be_disjoint')
    profiles = {'qwen3.7-plus': deepcopy(old['profile'])}
    for model, filename in [
        ('deepseek-v4.1-flash-1017', 'deepseek_v41_flash_1017_token_plan_profile.json'),
        ('qwen3.8-flash', 'qwen38_flash_token_plan_profile.json'),
    ]:
        p = read(code/'configs'/filename)
        if p.get('model') != model or p.get('credential_slot') != 'token_plan':
            raise ValueError('explicit_public_model_profile_required')
        if any(k.lower() in {'api_key', 'token', 'password', 'secret', 'authorization'} for k in p):
            raise ValueError('credentials_forbidden_in_public_profile')
        profiles[model] = p
    for p in profiles.values():
        if (Decimal(str(p['input_cny_per_million'])), Decimal(str(p['output_cny_per_million']))) != (Decimal('4'), Decimal('12')):
            raise ValueError('inherited_4_12_bookkeeping_proxy_required')
    configurations = []
    previous = PRIOR_LEDGER
    for arm_id, model, mode, split, questions, cases, calls, extra in ARM_SPECS:
        cfg = {
            'experiment_id': EXPERIMENT_ID, 'plan_version': PLAN_VERSION,
            'status': 'awaiting_user_confirmation', 'root': str(root),
            'run_id': EXPERIMENT_ID+'_'+arm_id, 'mode': mode,
            'input': (REL/'inputs'/f'{split}.inputs.jsonl').as_posix(),
            'image_root': old['image_root'], 'question_count': questions, 'case_count': cases,
            'model': model, 'credential_slot': 'token_plan', 'profile': deepcopy(profiles[model]),
            'prompt_variant': 'answer', 'samples': 1, 'temperature': .2, 'top_p': .95,
            'max_output_tokens': 8192 if mode == 'case_batch' else 2048,
            'request_timeout_seconds': 120, 'max_attempts_per_sample': 2,
            'figure_labels': False, 'high_resolution': False, 'stream': False,
            'extra_body': {'enable_thinking': False},
            'max_requests': calls+extra, 'max_extra_requests': extra,
            'global_max_requests': HARD_REQUESTS, 'global_max_extra_requests': EXTRA_REQUESTS,
            'global_request_counter': (REL/'global_requests.json').as_posix(),
            'ledger': (REL/'private_ledgers'/f'{arm_id}.json').as_posix(),
            'inherit_ledger': previous, 'cap_cny': str(FIXED_CAP),
            'new_experiment_budget_cny': '200', 'additional_budget_granted_cny': '0',
            'budget_authorization': 'Original cumulative 200 CNY authorization is retained; new six-arm scope requires a separate explicit user approval file.',
            'shared_public_plan': relative(root, plan_path), 'split': split,
        }
        if mode == 'case_evidence':
            cfg['evidence_cache'] = (REL/'case_tool_evidence').as_posix()
            cfg['evidence_policy'] = 'Prebuilt completed cache required before paid execution; preparation never invokes GPU tools.'
        validate_cfg(cfg)
        path = config_dir/f'{arm_id}.json'
        configurations.append((path, cfg, {
            'id': arm_id, 'config': relative(root, path), 'out': (REL/'arms'/arm_id).as_posix(),
            'mode': mode, 'model': model, 'split': split, 'normal_requests': calls,
            'extra_requests': extra, 'question_count': questions, 'case_count': cases,
        }))
        previous = cfg['ledger']
    manifest = {
        'experiment_id': EXPERIMENT_ID, 'plan_version': PLAN_VERSION,
        'status': 'awaiting_user_confirmation', 'root': str(root), 'code': relative(root, code),
        'out': REL.as_posix(), 'arms': [entry for _, _, entry in configurations],
        'models': sorted(MODELS), 'normal_requests': NORMAL_REQUESTS,
        'extra_requests': EXTRA_REQUESTS, 'hard_requests': HARD_REQUESTS,
        'global_request_counter': (REL/'global_requests.json').as_posix(),
        'inherit_ledger': PRIOR_LEDGER, 'cap_cny': str(FIXED_CAP),
        'new_experiment_budget_cny': '200', 'additional_budget_granted_cny': '0',
        'remaining_authorized_budget_snapshot_cny': '173.265944',
        'budget_snapshot_note': 'Existing public summary snapshot only; no ledger opened or scanned and no budget reset.',
        'baseline_run': BASELINE_RUN, 'shared_public_plan': relative(root, plan_path),
        'previous_arm_config': relative(root, previous_path),
        'labels_read_by_configurator': False, 'new_inference': 0,
        'all_generation_before_scoring': True,
        'evidence_cache_generation': 'explicit separate pre-step; pipeline only checks the completed cache before E3',
    }
    # Validate everything above before publishing any new configuration.
    for split, (_, text) in splits.items():
        copy_frozen_input(root/REL/'inputs'/f'{split}.inputs.jsonl', text)
    for path, cfg, _ in configurations:
        dump_new(path, cfg)
    manifest_path = config_dir/'pipeline.json'
    dump_new(manifest_path, manifest)
    return {'status': 'awaiting_user_confirmation', 'manifest': relative(root, manifest_path),
            'normal_requests': NORMAL_REQUESTS, 'extra_requests': EXTRA_REQUESTS,
            'hard_requests': HARD_REQUESTS, 'new_paid_calls_started': 0,
            'approval_created': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configure', action='store_true', help='Optional explicit spelling; configuration is the only action.')
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--code', required=True, type=Path)
    parser.add_argument('--previous-arm-config', required=True, type=Path)
    parser.add_argument('--public-plan', type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(configure(args.root, args.code, args.previous_arm_config, args.public_plan)))


if __name__ == '__main__':
    main()
