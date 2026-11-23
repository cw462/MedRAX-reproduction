"""Pause the owned R56 runner between active calls, preserving process state."""
import json
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path

from r54_after_r56_gate import R56_ARM, R56_RUN

SCOPE = 'R56_paused_for_R54_Off'


def paused_gate(receipt):
    if (receipt.get('schema') != 'r56_owned_runner_paused_for_r54_v1'
            or receipt.get('run') != R56_RUN or receipt.get('controller') != 'controller_recovery008'
            or receipt.get('active_child_processes') != 0 or receipt.get('open_calls') != 0):
        raise ValueError('R56_paused_admission_record_required')
    return {'predecessor_scope':SCOPE, 'predecessor_run':R56_RUN,
            'predecessor_active_controller':'controller_recovery008',
            'completed_predecessor_questions':0,
            'preserved_R56_predictions':receipt['saved_predictions'], 'R54_selected_questions':848}


def predecessor_admission(expected_controller, **kwargs):
    if expected_controller != 'controller_recovery008':
        raise ValueError('R56_paused_controller_mapping')
    receipt = json.loads((Path(R56_RUN)/'jobs/USER_PAUSE_FOR_R54_OFF.json').read_text())
    verify(receipt)
    return {'status':receipt,'active_controller':expected_controller,
            'actual_remote_native_files_checked':True,'gate':paused_gate(receipt),
            'utc':datetime.now(timezone.utc).isoformat(),'GPU_or_model_or_GT_calls':0}


def proc(pid):
    path = Path('/proc') / str(pid)
    fields = (path / 'stat').read_text().rsplit(') ', 1)[1].split()
    return fields[0], fields[19]


def verify(receipt, run=Path(R56_RUN)):
    run = Path(run)
    pid = receipt['runner_pid']
    if (receipt['schema'] != 'r56_owned_runner_paused_for_r54_v1'
            or receipt['controller'] != 'controller_recovery008'
            or receipt['run'] != str(run)
            or proc(pid) != ('T', receipt['start_ticks'])):
        raise ValueError('R56_owned_pause_required')
    return receipt


def pause(run=Path(R56_RUN), timeout=90):
    jobs = run / 'jobs'
    target = jobs / 'USER_PAUSE_FOR_R54_OFF.json'
    if target.exists():
        raise ValueError('R56_pause_already_recorded')
    queue = json.loads((jobs / 'queue_status.recovery008.json').read_text())
    if queue['active_job'] != 'chexbench.recovery008' or queue['state'] != 'running_dataset':
        raise ValueError('R56_owned_CheXBench_runner_required')
    pid = int((jobs / 'chexbench.recovery008.runner.pid').read_text())
    state, ticks = proc(pid)
    command = (Path('/proc') / str(pid) / 'cmdline').read_bytes().split(b'\0')
    out = run / 'generation/chexbench'
    if (pid != queue['runner_pid'] or state in ('T', 'Z')
            or str(out).encode() not in command
            or not any(x.endswith(b'/experiments/run_r56_writer_continue008.py') for x in command)):
        raise ValueError('R56_runner_ownership_mismatch')
    children = Path(f'/proc/{pid}/task/{pid}/children')
    services = out / 'services'
    patterns = ('calls/*/*/*/started.json', 'embeddings/*/started.json', 'tool_cache/*/started.json')
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        state, current_ticks = proc(pid)
        if current_ticks != ticks or state in ('T', 'Z'):
            raise ValueError('R56_runner_state_changed')
        if children.read_text().strip():
            time.sleep(.2)
            continue
        os.kill(pid, signal.SIGSTOP)
        keep_paused = False
        try:
            for _ in range(25):
                if proc(pid) == ('T', ticks):
                    break
                time.sleep(.01)
            else:
                continue
            if children.read_text().strip():
                continue
            if any(not (p.parent / 'result.json').is_file()
                   for pattern in patterns for p in services.glob(pattern)):
                continue
            receipt = {'schema':'r56_owned_runner_paused_for_r54_v1', 'run':str(run),
                       'controller':'controller_recovery008', 'runner_pid':pid, 'start_ticks':ticks,
                       'saved_predictions':len(list((out/'predictions'/R56_ARM).glob('*.json'))),
                       'active_child_processes':0, 'open_calls':0, 'utc':time.time(),
                       'user_request':'把在这个R54 无 Skill 组先跑一下'}
            with target.open('x', encoding='utf-8') as stream:
                json.dump(receipt, stream, indent=2, ensure_ascii=False)
            keep_paused = True
            return receipt
        finally:
            if not keep_paused and proc(pid)[1] == ticks:
                os.kill(pid, signal.SIGCONT)
                time.sleep(.12)
    raise TimeoutError('R56_no_quiescent_boundary_observed')
