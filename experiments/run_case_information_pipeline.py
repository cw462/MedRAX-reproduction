"""Prepare the frozen case-information plan, or execute after explicit approval.

Default preparation never reads credentials, labels, account ledgers or tool
weights. Execution is serial and scoring is a separate final subprocess only
after every raw generation arm is complete. E3 uses an explicitly prebuilt
tool-evidence cache; this pipeline never starts GPU evidence generation.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import sys

from configure_case_information import (ARM_SPECS, EXPERIMENT_ID, PLAN_VERSION, FIXED_CAP,
                                        NORMAL_REQUESTS, EXTRA_REQUESTS, HARD_REQUESTS,
                                        PRIOR_LEDGER, BASELINE_RUN, MODELS, inside, read)
from run_direct_vlm import now, write
from run_sampled_vlm import exclusive_lock, frozen_write, validate_cfg


def require_approval(path):
    if path is None:
        raise ValueError('explicit_user_approval_file_required_for_execute')
    # Keep the exact worker approval check authoritative at both entry points.
    from run_case_information import require_approval as worker_require_approval
    return worker_require_approval(path, EXPERIMENT_ID, PLAN_VERSION)


def load_manifest(manifest_path):
    manifest_path = Path(manifest_path).resolve()
    manifest = read(manifest_path)
    if (manifest.get('experiment_id') != EXPERIMENT_ID or manifest.get('plan_version') != PLAN_VERSION
            or manifest.get('status') != 'ready_for_approved_execution'
            or set(manifest.get('models', [])) != MODELS
            or manifest.get('normal_requests') != NORMAL_REQUESTS
            or manifest.get('extra_requests') != EXTRA_REQUESTS
            or manifest.get('hard_requests') != HARD_REQUESTS
            or Decimal(str(manifest.get('cap_cny'))) != FIXED_CAP
            or manifest.get('inherit_ledger') != PRIOR_LEDGER
            or manifest.get('baseline_run') != BASELINE_RUN):
        raise ValueError('frozen_case_information_manifest_required')
    root = Path(manifest['root']).resolve()
    inside(root, manifest_path)
    code = inside(root, manifest['code'])
    out = inside(root, manifest['out'])
    if out != root/'runs'/EXPERIMENT_ID:
        raise ValueError('new_isolated_experiment_output_required')
    arms = manifest.get('arms', [])
    if [a.get('id') for a in arms] != [s[0] for s in ARM_SPECS]:
        raise ValueError('fixed_eight_arm_order_required')
    configs = {}
    previous = PRIOR_LEDGER
    for arm, (arm_id, model, mode, split, questions, cases, calls, extra) in zip(arms, ARM_SPECS):
        cfg = read(inside(root, arm['config']))
        validate_cfg(cfg)
        if (cfg.get('experiment_id') != EXPERIMENT_ID or cfg.get('plan_version') != PLAN_VERSION
                or cfg.get('status') != 'ready_for_approved_execution'
                or Path(cfg['root']).resolve() != root
                or cfg.get('run_id') != EXPERIMENT_ID+'_'+arm_id
                or cfg.get('mode') != mode or cfg.get('model') != model
                or cfg.get('split') != split or cfg.get('question_count') != questions
                or cfg.get('case_count') != cases or cfg.get('samples') != 1
                or cfg.get('temperature') != .2 or cfg.get('top_p') != .95
                or cfg.get('max_output_tokens') != (8192 if mode == 'case_batch' else 2048)
                or cfg.get('extra_body') != {'enable_thinking': False}
                or cfg.get('figure_labels') is not False or cfg.get('high_resolution') is not False
                or cfg.get('max_requests') != calls+extra or cfg.get('max_extra_requests') != extra
                or cfg.get('global_max_requests') != HARD_REQUESTS
                or cfg.get('global_max_extra_requests') != EXTRA_REQUESTS
                or cfg.get('global_request_counter') != manifest['global_request_counter']
                or cfg.get('inherit_ledger') != previous
                or cfg.get('ledger') != f'runs/{EXPERIMENT_ID}/private_ledgers/{arm_id}.json'
                or Decimal(str(cfg.get('cap_cny'))) != FIXED_CAP):
            raise ValueError('frozen_arm_execution_contract_mismatch:'+arm_id)
        if inside(root, arm['out']) != out/'arms'/arm_id:
            raise ValueError('new_distinct_arm_output_required')
        for field in ('input', 'ledger', 'inherit_ledger', 'global_request_counter'):
            inside(root, cfg[field])  # Resolve paths only; do not read ledgers/counters.
        configs[arm_id] = cfg
        previous = cfg['ledger']
    return manifest_path, manifest, root, code, out, configs


def evidence_cache_ready(root, cfg):
    cache = inside(root, cfg['evidence_cache'])
    index_path = cache/'index.json'
    if not index_path.exists():
        raise RuntimeError('E3_requires_completed_prebuilt_evidence_cache_no_automatic_GPU_start')
    index = read(index_path)
    if (index.get('status') != 'complete' or index.get('schema_version') != 1
            or index.get('case_count') != cfg['case_count']
            or index.get('question_count') != cfg['question_count']):
        raise RuntimeError('E3_evidence_cache_not_complete')
    rows = [json.loads(line) for line in inside(root, cfg['input']).read_text(encoding='utf-8').splitlines() if line.strip()]
    expected = {str(r['question_id']): str(r['case_id']) for r in rows}
    if index.get('question_to_case') != expected:
        raise RuntimeError('E3_evidence_cache_question_binding_mismatch')
    cases = index.get('cases', [])
    if {str(c.get('case_id')) for c in cases} != set(expected.values()) or len(cases) != cfg['case_count']:
        raise RuntimeError('E3_evidence_cache_case_binding_mismatch')
    for case in cases:
        path = inside(cache, case['path'])
        if not path.is_file():
            raise RuntimeError('E3_evidence_cache_case_file_missing')


def execute(manifest_path, *, execute=False, approval=None, tune_labels=None, test_labels=None,
            report_out=None, key=None, run=subprocess.run, through_arm=None):
    manifest_path, manifest, root, code, out, configs = load_manifest(manifest_path)
    out.mkdir(parents=True, exist_ok=True)
    report = inside(root, report_out or root/'reports'/EXPERIMENT_ID)
    if report.name != EXPERIMENT_ID:
        raise ValueError('new_experiment_report_directory_required')
    state_path = out/'pipeline_status.json'
    arm_ids = [a['id'] for a in manifest['arms']]
    if through_arm is not None and through_arm not in arm_ids:
        raise ValueError('unknown_stage_boundary')
    with exclusive_lock(out/'.pipeline.lock'):
        frozen_write(out/'pipeline_protocol.json', {'manifest': manifest, 'arm_configurations': configs,
                     'default_prepare_only': True, 'approval_required': True,
                     'all_generation_before_scoring': True, 'automatic_GPU_evidence_generation': False})
        old_state = read(state_path) if state_path.exists() else {}
        if old_state.get('status') == 'completed':
            if (not (report/'metrics.json').exists() or read(report/'metrics.json').get('status') != 'completed'
                    or any(read(inside(root, a['out'])/'status.json').get('status') != 'generation_complete' for a in manifest['arms'])):
                raise RuntimeError('completed_pipeline_artifacts_missing_refusing_to_overwrite')
            return old_state
        if execute:
            approval = inside(root, approval) if approval is not None else None
            require_approval(approval)
            if tune_labels is None or test_labels is None:
                raise ValueError('isolated_tuning_and_heldout_labels_required_for_final_scoring_only')
            tune_labels, test_labels = inside(root, tune_labels), inside(root, test_labels)
            if key is None:
                key = sys.stdin.buffer.readline(65537).rstrip(b'\r\n')
            if (not isinstance(key, bytes) or not key or len(key) > 65536
                    or any(chr(c).isspace() or c < 32 or c >= 127 for c in key)):
                raise ValueError('invalid_stdin_credential')
            frozen_write(out/'execution_approval.json', read(approval))
        elif approval is not None or key is not None:
            raise ValueError('preparation_does_not_accept_approval_or_credentials')
        completed = []
        active = None
        try:
            for arm in manifest['arms']:
                if through_arm is not None and arm_ids.index(arm['id']) > arm_ids.index(through_arm):
                    result = {'status': 'stage_complete', 'completed_arms': completed,
                              'through_arm': through_arm, 'next_arm': arm['id'],
                              'scoring_started': False, 'updated_utc': now()}
                    write(state_path, result)
                    return result
                active = arm['id']
                arm_out = inside(root, arm['out'])
                child_state = arm_out/'status.json'
                state = read(child_state) if child_state.exists() else {}
                if state.get('status') == 'generation_complete':
                    completed.append(active)
                    continue
                if execute and state.get('status') == 'stopped':
                    raise RuntimeError('stopped_arm_requires_targeted_review_no_automatic_retry:'+active)
                if execute and arm['mode'] == 'case_evidence':
                    evidence_cache_ready(root, configs[active])
                command = [sys.executable, '-u', str(code/'experiments/run_case_information.py'),
                           '--config', str(inside(root, arm['config'])), '--out', str(arm_out)]
                command += ['--api-key-stdin', '--approval', str(approval)] if execute else ['--prepare-only']
                write(state_path, {'status': 'running' if execute else 'preparing', 'active_arm': active,
                                  'completed_arms': completed, 'updated_utc': now()})
                result = run(command, cwd=code, input=key+b'\n' if execute else b'', check=False)
                if result.returncode:
                    raise RuntimeError('worker_failed:'+active+':exit='+str(result.returncode))
                if not child_state.exists():
                    raise RuntimeError('worker_did_not_save_status:'+active)
                state = read(child_state)
                if execute:
                    if state.get('status') != 'generation_complete':
                        raise RuntimeError('generation_not_complete:'+active)
                    completed.append(active)
                elif state.get('status') not in ('prepared', 'generation_complete'):
                    raise RuntimeError('preparation_not_complete:'+active)
            if not execute:
                result = {'status': 'ready_for_approved_execution', 'completed_arms': completed,
                          'prepared_arms': [a['id'] for a in manifest['arms']],
                          'new_paid_calls_started': 0, 'updated_utc': now()}
                write(state_path, result)
                return result
            # No label is opened by this process or passed to an answer worker.
            if any(read(inside(root, a['out'])/'status.json').get('status') != 'generation_complete' for a in manifest['arms']):
                raise RuntimeError('all_eight_generation_arms_required_before_scoring')
            metrics = report/'metrics.json'
            if metrics.exists():
                if read(metrics).get('status') != 'completed':
                    raise RuntimeError('existing_scoring_incomplete_refusing_to_overwrite')
            else:
                write(state_path, {'status': 'running', 'step': 'isolated_scoring',
                                  'completed_arms': completed, 'updated_utc': now()})
                command = [sys.executable, '-u', str(code/'experiments/score_case_information.py'),
                           '--manifest', str(manifest_path), '--tune-labels', str(tune_labels),
                           '--test-labels', str(test_labels), '--out', str(report)]
                result = run(command, cwd=code, input=b'', check=False)
                if result.returncode or not metrics.exists() or read(metrics).get('status') != 'completed':
                    raise RuntimeError('isolated_scoring_not_complete')
            result = {'status': 'completed', 'completed_arms': completed, 'updated_utc': now(),
                      'report': report.relative_to(root).as_posix(), 'next': 'Publish the completed result; no further inference starts here.'}
            write(state_path, result)
            return result
        except Exception as exc:
            write(state_path, {'status': 'stopped', 'active_arm': active, 'completed_arms': completed,
                              'updated_utc': now(), 'error_type': type(exc).__name__, 'error': str(exc)})
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--prepare-only', action='store_true', help='Default; no API/GPU calls or credential reads.')
    modes.add_argument('--execute', action='store_true', help='Requires a later explicit user approval JSON.')
    parser.add_argument('--approval', type=Path)
    parser.add_argument('--tune-labels', type=Path)
    parser.add_argument('--test-labels', type=Path)
    parser.add_argument('--report-out', type=Path)
    parser.add_argument('--through-arm', help='Finish this arm then exit normally without scoring.')
    args = parser.parse_args(argv)
    result = execute(args.manifest, execute=args.execute, approval=args.approval,
                     tune_labels=args.tune_labels, test_labels=args.test_labels, report_out=args.report_out,
                     through_arm=args.through_arm)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
