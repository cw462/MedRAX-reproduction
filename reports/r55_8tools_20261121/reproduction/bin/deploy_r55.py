import json
import os
from pathlib import Path
import subprocess
import sys
import time

import baselines
import memory
import queue_r55 as queue
import r55_deepseek_rerun_runtime as runtime


ROOT = queue.ROOT
BASE = ROOT.parent
PRIOR = BASE / 'r55_autodl_qwen_8tools_20261116_001'
OFFICIAL = BASE / 'r55_autodl_deepseek41_rerun_20261116_001'
TRUSTED = BASE.parent / 'medrax_m5_rrsi_acc_ttl_v4_20261119/trusted'
TOOLS = runtime.read(PRIOR / 'plan.json')['tools']
DATASETS = {'slake': 114, 'vqarad': 116, 'chexbench': 618}
MODELS = {'flash': 'qwen3.6-flash', 'plus': 'qwen3.7-plus', 'deepseek': 'deepseek-flash'}
METHODS = {'flash': ('CRITIC', 'Reflexion', 'M2'), 'plus': ('CRITIC', 'Reflexion', 'M2'),
           'deepseek': ('ReAct', 'CRITIC', 'Reflexion', 'M2', 'M5')}
ORDER = [('deepseek', 'ReAct'), ('flash', 'CRITIC'), ('plus', 'CRITIC'),
         ('flash', 'M2'), ('plus', 'M2'), ('deepseek', 'M2'), ('deepseek', 'M5'),
         ('deepseek', 'CRITIC'), ('flash', 'Reflexion'), ('plus', 'Reflexion'), ('deepseek', 'Reflexion')]
COHORTS = [(model, arm, dataset) for dataset in DATASETS for model, arm in ORDER]

RESIDENT_ROUTE = '''

def route(request, root):
    if request['backend'] not in FAMILIES:
        return False
    from native_resident_pool import dispatch
    run_root = Path(os.environ['R55_8TOOLS_ROOT'])
    reply = dispatch({'run_root': str(run_root), 'resident_control': os.environ['R55_RESIDENT_ROOT']}, request)
    sys.stderr.write(reply['stderr'])
    print('CXR_VQA_RESULT=' + json.dumps(reply['result'], ensure_ascii=False))
    return True
'''


def stage():
    control = TRUSTED / 'residents'
    gateway = runtime.read(TRUSTED / 'gateway.json')
    snapshot = runtime.read(PRIOR / 'plan.json')['chexagent8_snapshot']
    if gateway['runtime']['backend_config']['chexagent8_snapshot'] != snapshot:
        raise ValueError('Active CheXagent checkpoint does not match the benchmark')
    resident = {}
    for family in ('chexagent', 'maira', 'llava-med', 'llava-rad', 'medgemma', 'medvlm-r1'):
        ready = runtime.read(control / f'{family}.ready.json')
        if not ready or not runtime.native(ready['pid']) or not Path(ready['socket']).is_socket():
            raise RuntimeError(f'No active resident tool service for {family}')
        resident[family] = ready['pid']
    plan = dict(models=MODELS, methods=METHODS, datasets=DATASETS, tools=TOOLS, cohorts=COHORTS,
                chexagent8_snapshot=snapshot, resident_root=str(control), resident_workers=resident,
                max_active_cohorts=2)
    runtime.save(queue.PLAN, plan)
    dispatcher = ROOT / 'bin/native_resident_pool.py'
    if not dispatcher.is_file():
        dispatcher.symlink_to(TRUSTED / 'native_resident_pool.py')
    memory.stage(ROOT, PRIOR, OFFICIAL, DATASETS)
    baselines.stage(ROOT, PRIOR, OFFICIAL, DATASETS)
    for model in MODELS:
        path = ROOT / model / 'code/experiments/r55_resident_tools.py'
        body = path.read_text()
        if 'def route(request, root):' in body and RESIDENT_ROUTE.strip() not in body:
            first, _, last = body.rpartition('def route(request, root):')
            rest = last.split('\n\ndef ', 1)
            body = first + RESIDENT_ROUTE + ('\n\ndef ' + rest[1] if len(rest) == 2 else '')
        if RESIDENT_ROUTE.strip() not in body:
            body += RESIDENT_ROUTE
        # The donor module may be linked. Replace our link without opening the donor for writing.
        temp = path.with_name(path.name + '.pending')
        temp.write_text(body)
        temp.replace(path)
    verified = []
    for model, method in ORDER:
        item = (model, method, 'slake')
        command = queue.command(item, 'verify')
        proc = subprocess.run(command, cwd=ROOT / model, env=queue.environment(item, plan),
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=100)
        if proc.returncode:
            raise RuntimeError(f'{model}/{method} verification failed\n{proc.stderr[-1800:]}\n{proc.stdout[-700:]}')
        verified.append([model, method])
    receipt = {'verified': verified, 'resident_workers': resident, 'cohorts': len(COHORTS),
               'datasets': DATASETS, 'gpu': runtime.gpu_sample()}
    runtime.save(queue.JOBS / 'staged.json', receipt)
    return receipt


def start():
    runtime.read(queue.JOBS / 'staged.json')['verified']
    queue.key_input(('flash', 'M2', 'slake'), 'run')
    with runtime.lease(queue.JOBS / 'launch.lock'):
        record = runtime.read(queue.JOBS / 'supervisor.started.json')
        if queue.live(record):
            return record
        for item in COHORTS:
            for phase in ('run', 'score'):
                if queue.live(runtime.read(queue.job_path(item) / f'{phase}.started.json')):
                    raise RuntimeError(f'Existing child still owns {item}')
        with (queue.JOBS / 'supervisor.log').open('ab') as log:
            proc = subprocess.Popen([queue.PYTHON, '-B', '-u', str(ROOT / 'bin/queue_r55.py')], cwd=ROOT,
                                    stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        state = dict(pid=proc.pid, start_ticks=runtime.native(proc.pid), epoch=time.time())
        runtime.save(queue.JOBS / 'supervisor.started.json', state)
        return state


if __name__ == '__main__':
    os.umask(0o077)
    actions = {'stage': stage, 'start': start, 'status': queue.status}
    print(json.dumps(actions[sys.argv[1]](), ensure_ascii=False))
