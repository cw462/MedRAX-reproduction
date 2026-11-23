"""Run a frozen list of independent sampling arms serially; never score in-process.

The answer workers receive input-only JSONL files and their own credential through
stdin. Mixed-provider phases select keys by their frozen credential slots.
Each arm inherits the previous arm's committed spend, including conservative
charges for interrupted requests. The phase stops on failure for explicit review.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import json
import os
from pathlib import Path
import re
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
        if cfg.get('credential_slot') not in {'dashscope', 'apiyi', 'token_plan'}:
            raise ValueError('valid_credential_slot_required')
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


def load_credentials(args, slots):
    """Read keys only for execution; never include supplied contents in errors."""
    if args.prepare_only:
        return {}
    if args.api_key_stdin:
        if len(slots) != 1:
            raise ValueError('mixed_credential_slots_require_json_stdin')
        raw = sys.stdin.buffer.readline(65537)
        try:
            values = {next(iter(slots)): raw.decode('utf-8').rstrip('\r\n')}
        except UnicodeError:
            raise ValueError('invalid_stdin_credentials') from None
    elif args.credentials_json_stdin:
        raw = sys.stdin.buffer.read(65537)
        try:
            values = json.loads(raw.decode('utf-8'))
        except (UnicodeError, ValueError):
            raise ValueError('invalid_stdin_credentials') from None
    else:
        raise ValueError('stdin_credentials_required')
    if len(raw) > 65536 or not isinstance(values, dict):
        raise ValueError('invalid_stdin_credentials')
    if not slots <= set(values) or set(values) - {'dashscope', 'apiyi', 'token_plan'}:
        raise ValueError('invalid_stdin_credentials')
    for value in values.values():
        if not isinstance(value, str) or not value or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError('invalid_stdin_credentials')
        try:
            value.encode('ascii')
        except UnicodeError:
            raise ValueError('invalid_stdin_credentials') from None
    return {slot: values[slot].encode('ascii') for slot in slots}


def acknowledgement_target(args, arms, out):
    """Route one explicit recovery acknowledgement to the stopped arm only."""
    event = args.acknowledge_stop
    target = args.acknowledge_stop_arm
    if not event and not target:
        return None
    if args.prepare_only or not event or not target:
        raise ValueError('stop_acknowledgement_requires_execution_arm_and_event')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,200}', event):
        raise ValueError('invalid_stop_event_id')
    phase_path = out/'status.json'
    state = read(phase_path) if phase_path.exists() else {}
    if state.get('status') != 'stopped' or state.get('active_arm') != target:
        raise ValueError('acknowledgement_must_target_active_stopped_arm')
    unfinished = []
    for arm in arms:
        path = Path(arm['out'])/'status.json'
        arm_state = read(path) if path.exists() else {}
        if arm_state.get('status') != 'generation_complete':
            unfinished.append((arm, arm_state))
    if not unfinished or unfinished[0][0]['id'] != target:
        raise ValueError('acknowledgement_must_target_first_unfinished_arm')
    arm, arm_state = unfinished[0]
    if arm_state.get('status') != 'stopped' or arm_state.get('stop_event_id') != event:
        raise ValueError('acknowledgement_must_match_pending_stop_event')
    if not (Path(arm['out'])/'stop_events'/f'{event}.json').is_file():
        raise ValueError('stop_event_record_missing')
    if (Path(arm['out'])/'stop_acknowledgements'/f'{event}.json').exists():
        raise ValueError('stop_event_already_acknowledged')
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--acknowledge-stop', metavar='EVENT_ID',
        help='Explicitly acknowledge one resolved stop event; never repeats its failed sample.')
    parser.add_argument('--acknowledge-stop-arm', metavar='ARM_ID',
        help='Exact currently stopped arm for --acknowledge-stop; no automatic reset.')
    credentials = parser.add_mutually_exclusive_group()
    credentials.add_argument('--api-key-stdin', action='store_true',
        help='One stdin key; allowed only when all arms use the same credential slot.')
    credentials.add_argument('--credentials-json-stdin', action='store_true',
        help='Read a JSON object of credential-slot keys from stdin; keys are never persisted.')
    args = parser.parse_args()
    manifest = read(args.manifest)
    root=Path(manifest['root']).resolve();out = Path(manifest['out'])
    if not out.is_absolute():out=root/out
    out=out.resolve()
    if not out.is_relative_to(root):raise ValueError('phase_path_outside_experiment_root')
    out.mkdir(parents=True, exist_ok=True)
    global_counter=(root/manifest['global_request_counter']).resolve()
    if not global_counter.is_relative_to(root):raise ValueError('global_counter_outside_root')
    # Serial ledger inheritance is safe only if different phases cannot execute
    # concurrently from the same preceding balance snapshot.
    with exclusive_lock(str(global_counter)+'.execution.lock'), exclusive_lock(out/'.phase.lock'):
        arms = validate_manifest(manifest)
        acknowledge_arm = acknowledgement_target(args, arms, out)
        configurations = {arm['id']: read(Path(arm['config'])) for arm in arms}
        frozen_write(out/'phase_protocol.json', dict(manifest,
            arm_configurations=configurations,
            implementation_commit=os.environ.get('MEDRAX_CODE_COMMIT', 'uncommitted')))
        if not args.prepare_only and not manifest.get('budget_authorization'):
            raise ValueError('authorized_budget_required')
        keys = load_credentials(args, {cfg['credential_slot'] for cfg in configurations.values()})
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
            if arm['id'] == acknowledge_arm:
                command += ['--acknowledge-stop', args.acknowledge_stop]
            key = None if args.prepare_only else keys[configurations[arm['id']]['credential_slot']] + b'\n'
            result = subprocess.run(command, input=key, check=False)
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
