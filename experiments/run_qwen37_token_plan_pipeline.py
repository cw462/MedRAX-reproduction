"""Run only the authorized Token Plan Qwen3.7 stages 0–2, with isolated offline scoring.

The answer subprocess receives one credential over stdin and no label argument.
Each complete phase is scored in a separate subprocess before the next frozen
configuration is materialized. A stopped worker never advances the pipeline.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from run_direct_vlm import now, read, write
from run_sampled_vlm import exclusive_lock, frozen_write

NAME = 'qwen37_token_plan_20261102'


def acknowledge_unsent_failure(root, out, cfg, report, phase, arm_id, target):
    """Confirm one located, unsent reservation failure without changing its evidence.

    This is not a terminal-sample acknowledgement. The existing worker must
    reopen its original ledger and pass all remaining protections before an API
    request can start. No counts, predictions or ledger records are changed here.
    """
    match = re.fullmatch(r'([A-Za-z0-9_-]+)__s([1-9][0-9]*)', target)
    if not match or phase not in ('phase0', 'phase1', 'phase2') or not re.fullmatch(r'[A-Za-z0-9_-]+', arm_id):
        raise ValueError('invalid_unsent_recovery_target')
    qid, sample = match[1], int(match[2])
    pipeline = read(out/'pipeline_status.json')
    state = read(out/phase/'status.json')
    if (pipeline.get('status') != 'stopped' or pipeline.get('phase') != phase
            or state.get('status') != 'stopped' or state.get('active_arm') != arm_id
            or pipeline.get('active_arm', arm_id) != arm_id):
        raise ValueError('unsent_recovery_requires_current_stopped_pipeline_phase_arm')
    for prior in range(int(phase[-1])):
        name = f'phase{prior}'
        if (read(out/name/'status.json').get('status') != 'generation_complete'
                or read(report/name/'metrics.json').get('status') != 'completed'):
            raise ValueError('unsent_recovery_must_target_next_unfinished_phase')
    manifest = read(cfg/f'{phase}.json')
    if Path(manifest['root']).resolve() != root or (root/manifest['out']).resolve() != out/phase:
        raise ValueError('unsent_recovery_manifest_location_mismatch')
    unfinished = []
    for arm in manifest['arms']:
        folder = (root/arm['out']).resolve()
        if not folder.is_relative_to(out/phase):
            raise ValueError('unsent_recovery_arm_outside_phase')
        arm_state = read(folder/'status.json') if (folder/'status.json').exists() else {}
        if arm_state.get('status') != 'generation_complete':
            unfinished.append((arm, folder, arm_state))
    if not unfinished or unfinished[0][0]['id'] != arm_id:
        raise ValueError('unsent_recovery_requires_first_unfinished_arm')
    _, folder, arm_state = unfinished[0]
    fatal = read(folder/'fatal_error.json')
    if (arm_state.get('status') != 'stopped' or fatal.get('question_id') != qid
            or fatal.get('sample') != sample
            or any('stop_event_id' in s for s in (pipeline, state, arm_state, fatal))):
        raise ValueError('unsent_recovery_fatal_target_or_stop_event_mismatch')
    checkpoint = folder/'checkpoints'/qid/f'sample_{sample}'
    reservation = read(checkpoint/'attempt_1/reserve_error.json')
    expected = 'LedgerIntegrityError:Ledger checksum mismatch'
    if (fatal.get('error') != expected or arm_state.get('error') != expected
            or reservation.get('error_type') != 'LedgerIntegrityError'
            or reservation.get('message') != 'Ledger checksum mismatch'
            or reservation.get('request_sent') is not False):
        raise ValueError('unsent_recovery_requires_exact_unsent_reservation_error')
    sent_names = ('started.json', 'result.json', 'response.json', 'terminal.json', 'stream_chunks.jsonl')
    if any((place/name).exists() for place in (checkpoint, *checkpoint.glob('attempt_*')) for name in sent_names):
        raise ValueError('unsent_recovery_rejects_sent_or_terminal_sample')
    confirmation = out/'unsent_recovery_acknowledgements'/f'{phase}__{arm_id}__{target}.json'
    if confirmation.exists():
        raise ValueError('unsent_failure_already_acknowledged')
    frozen_write(confirmation, {'utc': now(), 'phase': phase, 'arm': arm_id,
        'question_id': qid, 'sample': sample, 'fatal_error': fatal,
        'reserve_error': reservation, 'request_sent': False,
        'action': 'Resume the unfinished sample through the unchanged original ledger constructor.',
        'predictions_modified': False, 'ledger_modified': False, 'counters_reset': False,
        'stop_event_created': False})


def execute(root, code, regression_labels, tune_labels, key, *, run=subprocess.run,
            acknowledge_phase=None, acknowledge_arm=None, acknowledge_event=None,
            acknowledge_unsent_error=None):
    root = Path(root).resolve(); code = Path(code).resolve()
    if not code.is_relative_to(root):
        raise ValueError('code_must_be_inside_root')
    out = root/'runs'/NAME; out.mkdir(parents=True, exist_ok=True)
    cfg = code/'configs'/NAME; report = root/'reports'/NAME
    state_path = out/'pipeline_status.json'
    completed = []
    if acknowledge_event is not None and acknowledge_unsent_error is not None:
        raise ValueError('terminal_and_unsent_acknowledgements_are_mutually_exclusive')
    ack = (acknowledge_phase, acknowledge_arm, acknowledge_event or acknowledge_unsent_error)
    if any(x is not None for x in ack) and not all(x is not None for x in ack):
        raise ValueError('explicit_phase_arm_and_stop_event_required')

    def command(program, args, credential=False):
        result = run([sys.executable, '-u', str(code/'experiments'/program), *args],
                     cwd=code, input=key+b'\n' if credential else b'', check=False)
        if result.returncode:
            raise RuntimeError(f'subprocess_failed:{program}:exit={result.returncode}')

    with exclusive_lock(out/'.pipeline.lock'):
        frozen_write(out/'pipeline_protocol.json', {
            'experiment': NAME, 'stages': [0, 1, 2],
            'implementation_commit': os.environ.get('MEDRAX_CODE_COMMIT', 'uncommitted'),
            'normal_requests': 4484, 'technical_extra_limit': 230,
            'total_request_limit': 4714, 'original_authorized_budget_cny': '200',
            'cumulative_cap_cny': '394.252828', 'additional_budget_granted_cny': '0',
            'model': 'qwen3.7-plus', 'credential_slot': 'token_plan',
            'budget_policy': 'Inherit old phase1 D spend under unchanged cumulative cap; no reset or extra 200.',
            'phase0_gate': 'technical only; no 40-to-44 accuracy threshold',
            'separate_scoring_process': True, 'automatic_stage3': False})
        if acknowledge_unsent_error is not None:
            acknowledge_unsent_failure(root, out, cfg, report, acknowledge_phase,
                                      acknowledge_arm, acknowledge_unsent_error)
        phase = 'phase0'
        try:
            for number in (0, 1, 2):
                phase = f'phase{number}'
                write(state_path, {'status': 'running', 'phase': phase,
                                  'step': 'configure', 'completed_phases': completed,
                                  'updated_utc': now()})
                if number and (acknowledge_unsent_error is None or number > int(acknowledge_phase[-1])):
                    args = ['--phase', str(number), '--root', str(root), '--code', str(code),
                            '--phase0-manifest', str(cfg/'phase0.json'),
                            '--phase0-metrics', str(report/'phase0/metrics.json')]
                    if number == 2:
                        args += ['--phase1-metrics', str(report/'phase1/metrics.json')]
                    command('configure_qwen37_token_plan.py', args)
                manifest = cfg/f'{phase}.json'
                child_state = out/phase/'status.json'
                state = read(child_state) if child_state.exists() else {}
                if state.get('status') != 'generation_complete':
                    if state.get('status') == 'stopped' and acknowledge_phase != phase:
                        raise RuntimeError('stopped_phase_requires_explicit_acknowledgement:'+phase)
                    args = ['--manifest', str(manifest), '--api-key-stdin']
                    if acknowledge_phase == phase and acknowledge_event is not None:
                        args += ['--acknowledge-stop-arm', acknowledge_arm,
                                 '--acknowledge-stop', acknowledge_event]
                    write(state_path, {'status': 'running', 'phase': phase, 'step': 'generation',
                                      'completed_phases': completed, 'updated_utc': now()})
                    command('run_vote_phase.py', args, credential=True)
                if not child_state.exists() or read(child_state).get('status') != 'generation_complete':
                    raise RuntimeError('generation_not_complete:'+phase)
                metrics = report/phase/'metrics.json'
                if metrics.exists():
                    if read(metrics).get('status') != 'completed':
                        raise RuntimeError('existing_scoring_not_complete:'+phase)
                else:
                    write(state_path, {'status': 'running', 'phase': phase, 'step': 'offline_score',
                                      'completed_phases': completed, 'updated_utc': now()})
                    command('score_votes.py', ['--manifest', str(cfg/f'{phase}.score.json'),
                            '--labels', str(regression_labels if number == 0 else tune_labels),
                            '--out', str(report/phase)])
                    if not metrics.exists() or read(metrics).get('status') != 'completed':
                        raise RuntimeError('scoring_not_complete:'+phase)
                completed.append(phase)
            write(state_path, {'status': 'completed', 'phase': phase,
                              'completed_phases': completed, 'updated_utc': now(),
                              'next': 'Review stage2 results and publish; no further paid phase authorized here.'})
        except Exception as exc:
            # No provider responses or credential text are included in this wrapper.
            write(state_path, {'status': 'stopped', 'phase': phase,
                              'completed_phases': completed, 'updated_utc': now(),
                              'error': type(exc).__name__+': '+str(exc)})
            raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'code', 'regression-labels', 'tune-labels'):
        p.add_argument('--'+name, required=True, type=Path)
    p.add_argument('--acknowledge-phase', choices=('phase0', 'phase1', 'phase2'))
    p.add_argument('--acknowledge-arm')
    recovery = p.add_mutually_exclusive_group()
    recovery.add_argument('--acknowledge-event')
    recovery.add_argument('--acknowledge-unsent-error', metavar='QUESTION_ID__sN',
        help='One explicit acknowledgement of an exact unsent reservation failure; never resets money or request limits.')
    args = p.parse_args()
    key = sys.stdin.buffer.readline(65537).rstrip(b'\r\n')
    if not key or len(key) > 65536 or any(chr(c).isspace() or c < 32 or c >= 127 for c in key):
        raise ValueError('invalid_stdin_credential')
    execute(**vars(args), key=key)


if __name__ == '__main__':
    main()
