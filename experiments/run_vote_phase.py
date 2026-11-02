"""Run a frozen list of independent sampling arms serially; never score in-process.

The answer workers receive input-only JSONL files and a credential through stdin.
Each arm inherits the previous arm's committed spend, including conservative
charges for interrupted requests. The phase stops on failure for explicit review.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_sampled_vlm import exclusive_lock, frozen_write, validate_cfg
from run_direct_vlm import now, read, write


def validate_manifest(manifest):
    arms = manifest['arms']
    if not arms or len({a['id'] for a in arms}) != len(arms):
        raise ValueError('nonempty_unique_arms_required')
    root = Path(manifest['root']).resolve()
    previous = manifest['inherit_ledger']
    seen_ledgers={(root/previous).resolve()}
    global_bounds=None
    normalized=[]
    for arm in arms:
        config_path=Path(arm['config'])
        if not config_path.is_absolute():config_path=root/config_path
        cfg = read(config_path)
        validate_cfg(cfg)
        if Path(cfg['root']).resolve()!=root:raise ValueError('one_runtime_root_required')
        if cfg['inherit_ledger'] != previous:
            raise ValueError('all_arms_must_inherit_the_preceding_spend')
        if Decimal(str(cfg['cap_cny'])) != Decimal(str(manifest['cap_cny'])):
            raise ValueError('one_budget_for_all_arms_required')
        if cfg['global_request_counter'] != manifest['global_request_counter']:
            raise ValueError('one_request_counter_for_all_arms_required')
        bounds=(cfg['global_max_requests'],cfg['global_max_extra_requests'])
        if global_bounds is not None and bounds!=global_bounds:raise ValueError('one_global_request_policy_required')
        global_bounds=bounds
        if cfg['budget_authorization'] != manifest['budget_authorization'] or Decimal(cfg['new_experiment_budget_cny'])!=Decimal(manifest['new_experiment_budget_cny']):
            raise ValueError('one_explicit_authorization_required')
        arm_out=Path(arm['out'])
        if not arm_out.is_absolute():arm_out=root/arm_out
        for path in (root/cfg['ledger'], root/cfg['global_request_counter'], arm_out):
            if not path.resolve().is_relative_to(root):
                raise ValueError('phase_path_outside_experiment_root')
        ledger_path=(root/cfg['ledger']).resolve()
        if ledger_path in seen_ledgers:raise ValueError('distinct_new_ledgers_required')
        seen_ledgers.add(ledger_path)
        previous = cfg['ledger']
        normalized.append(dict(arm,config=str(config_path.resolve()),out=str(arm_out.resolve())))
    return normalized


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--api-key-stdin', action='store_true')
    args = parser.parse_args()
    manifest = read(args.manifest)
    root=Path(manifest['root']).resolve();out = Path(manifest['out'])
    if not out.is_absolute():out=root/out
    out=out.resolve()
    if not out.is_relative_to(root):raise ValueError('phase_path_outside_experiment_root')
    out.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(out/'.phase.lock'):
        arms = validate_manifest(manifest)
        frozen_write(out/'phase_protocol.json', dict(manifest,
            arm_configurations={arm['id']:read(Path(arm['config'])) for arm in arms},
            implementation_commit=os.environ.get('MEDRAX_CODE_COMMIT', 'uncommitted')))
        key = sys.stdin.buffer.readline().strip() if args.api_key_stdin else b''
        if not args.prepare_only and (not key or not manifest.get('budget_authorization')):
            raise ValueError('authorized_budget_and_stdin_credential_required')
        completed = []
        for arm in arms:
            state_path = Path(arm['out'])/'status.json'
            state = read(state_path) if state_path.exists() else {}
            if state.get('status') == 'generation_complete':
                completed.append(arm['id']); continue
            write(out/'status.json', {'status':'preparing' if args.prepare_only else 'running',
                'updated_utc':now(), 'active_arm':arm['id'], 'completed_arms':completed,
                'planned_arms':[a['id'] for a in arms]})
            command = [sys.executable, str(Path(__file__).with_name('run_sampled_vlm.py')),
                '--config', arm['config'], '--out', arm['out']]
            command += ['--prepare-only'] if args.prepare_only else ['--api-key-stdin', '--resume']
            result = subprocess.run(command, input=None if args.prepare_only else key+b'\n', check=False)
            if result.returncode:
                write(out/'status.json', {'status':'stopped','updated_utc':now(),
                    'active_arm':arm['id'],'completed_arms':completed,'exitcode':result.returncode})
                return result.returncode
            if not args.prepare_only: completed.append(arm['id'])
        write(out/'status.json', {'status':'prepared' if args.prepare_only else 'generation_complete',
            'updated_utc':now(),'completed_arms':completed,'planned_arms':[a['id'] for a in arms]})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
