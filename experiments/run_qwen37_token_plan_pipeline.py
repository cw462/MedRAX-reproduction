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
import subprocess
import sys

from run_direct_vlm import now, read, write
from run_sampled_vlm import exclusive_lock, frozen_write

NAME = 'qwen37_token_plan_20261102'


def execute(root, code, regression_labels, tune_labels, key, *, run=subprocess.run,
            acknowledge_phase=None, acknowledge_arm=None, acknowledge_event=None):
    root = Path(root).resolve(); code = Path(code).resolve()
    if not code.is_relative_to(root):
        raise ValueError('code_must_be_inside_root')
    out = root/'runs'/NAME; out.mkdir(parents=True, exist_ok=True)
    cfg = code/'configs'/NAME; report = root/'reports'/NAME
    state_path = out/'pipeline_status.json'
    completed = []
    ack = (acknowledge_phase, acknowledge_arm, acknowledge_event)
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
        phase = 'phase0'
        try:
            for number in (0, 1, 2):
                phase = f'phase{number}'
                write(state_path, {'status': 'running', 'phase': phase,
                                  'step': 'configure', 'completed_phases': completed,
                                  'updated_utc': now()})
                if number:
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
                    if acknowledge_phase == phase:
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
    p.add_argument('--acknowledge-arm'); p.add_argument('--acknowledge-event')
    args = p.parse_args()
    key = sys.stdin.buffer.readline(65537).rstrip(b'\r\n')
    if not key or len(key) > 65536 or any(chr(c).isspace() or c < 32 or c >= 127 for c in key):
        raise ValueError('invalid_stdin_credential')
    execute(**vars(args), key=key)


if __name__ == '__main__':
    main()
