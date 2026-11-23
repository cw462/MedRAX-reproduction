"""One new local attempt for a known user-terminated R54 tool, never an API retry."""
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from r54_off_resume_evidence import (original_interruption, recovery_folder, recovery_result,
                                     adoption_value, approved_recovery)


def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)


def gpu1_state():
    value = subprocess.run(['nvidia-smi', '--id=1', '--query-gpu=uuid,memory.free',
                            '--format=csv,noheader,nounits'], capture_output=True, text=True, check=True)
    uuid, free = [v.strip() for v in value.stdout.strip().split(',')]
    apps = subprocess.run(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid,used_memory',
                           '--format=csv,noheader,nounits'], capture_output=True, text=True, check=True)
    processes = []
    for line in apps.stdout.splitlines():
        fields = [v.strip() for v in line.split(',')]
        if fields[0] == uuid:
            processes.append({'pid': int(fields[1]), 'used_memory_mib': fields[2]})
    return {'gpu': '1', 'uuid': uuid, 'free_mib_observed': int(free), 'compute_processes': processes}


def await_gpu1(folder, *, probe=gpu1_state, sleep=time.sleep):
    folder = Path(folder); waiting = False; tick = time.monotonic()
    while True:
        state = probe()
        if state.get('gpu') != '1':
            raise ValueError('R54_resume_GPU1_identity')
        if state['free_mib_observed'] >= 18432 and state['compute_processes'] == []:
            save(folder / 'GPU_admission.json', dict(state, minimum_free_mib=18432,
                 waited=waiting, wait_elapsed_s=time.monotonic() - tick, not_a_reservation=True,
                 other_jobs_modified=False))
            return
        if not waiting:
            save(folder / 'GPU_wait.started.json', state); waiting = True
        sleep(10)


def execute_recovery_once(out, runtime, *, gate=await_gpu1, run=subprocess.run):
    cache, prior, old_started = original_interruption(out)
    spec = runtime['tools'][prior['tool']]
    if (runtime['backend_config'] != prior['runtime'] or str(spec.get('gpu')) != '1'
            or spec['backend'] != prior['backend']
            or spec['revision'] != old_started['identity']['revision']):
        raise ValueError('R54_recovery_runtime_or_original_tool_changed')
    folder = recovery_folder(out)
    folder.mkdir(parents=True, exist_ok=False)  # Any prior preparation/send consumes this attempt.
    save(folder / 'ORIGINAL_BINDING.json', {'original_cache': str(cache), 'request': prior,
         'started': old_started, 'original_generation_state': 'unknown_after_known_user_stop'})
    gate(folder)
    request = dict(prior, artifact_dir=str(folder / 'artifacts'))
    save(folder / 'request.json', request)
    save(folder / 'started.json', {'identity': old_started['identity'], 'gpu': '1',
         'new_attempt_number': 1, 'utc': datetime.now(timezone.utc).isoformat(), 'bound_spec': spec,
         'automatic_retry': False})
    command = [spec['python'], str(Path(__file__).with_name('tool_worker_r54.py'))]
    if spec.get('cpu_affinity') is not None:
        command = ['taskset', '-c', str(spec['cpu_affinity']), *command]
    env = dict(os.environ, MPLBACKEND='Agg', TOKENIZERS_PARALLELISM='false')
    env.update(spec.get('worker_env', {}))
    env.update(CUDA_VISIBLE_DEVICES='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    for flag in ('CUDA_LAUNCH_BLOCKING', 'TORCH_SHOW_CPP_STACKTRACES'):
        env.pop(flag, None)
    tick = time.monotonic()
    try:
        completed = run(command, input=json.dumps(request), capture_output=True, text=True,
                        env=env, timeout=spec.get('timeout', 600))
        for name in ('stdout', 'stderr'):
            with (folder / ('backend.' + name + '.log')).open('x', encoding='utf-8') as handle:
                handle.write(getattr(completed, name))
        save(folder / 'backend.exit.json', {'returncode': completed.returncode})
        with (folder / 'worker.exitcode').open('x', encoding='utf-8') as handle:
            handle.write(str(completed.returncode) + '\n')
        if completed.returncode:
            raise RuntimeError('backend_exit_' + str(completed.returncode))
        result = json.loads(completed.stdout.split('CXR_VQA_RESULT=')[-1])
    except Exception as error:
        if isinstance(error, subprocess.TimeoutExpired):
            for name in ('stdout', 'stderr'):
                value = getattr(error, name, None)
                if value is not None:
                    with (folder / ('backend.' + name + '.log')).open('xb') as handle:
                        handle.write(value if isinstance(value, bytes) else value.encode('utf-8'))
            save(folder / 'backend.timeout.json', {'timeout': error.timeout, 'automatic_retry': False})
        result = {'status': 'failed', 'observation': None, 'error_type': type(error).__name__,
                  'error': str(error)[:300]}
    result.update(identity=old_started['identity'], backend=spec['backend'],
                  elapsed_s=time.monotonic() - tick, utc=datetime.now(timezone.utc).isoformat())
    save(folder / 'result.json', result)
    return result


def adopt_completed_recovery(out):
    value = recovery_result(out)  # No adoption until actual native/result/GPU/input checks pass.
    save(value['directory'] / 'ADOPTION.json', adoption_value(value['directory']))
    return approved_recovery(out)
