import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import r55_deepseek_rerun_runtime as runtime


ROOT = runtime.ROOT
JOBS = ROOT / 'jobs'
PLAN = ROOT / 'plan.json'
PYTHON = '/root/autodl-tmp/medrax_r55_top4_full848/env/modern/bin/python'
CREDENTIALS = Path('/root/.config/medrax-autodl-r55/memory_resume.keys')
MEMORY = {'M2', 'M5'}


def job_path(item):
    model, method, dataset = item
    return JOBS / 'cohorts' / model / method / dataset


def output_path(item):
    model, method, dataset = item
    if method in MEMORY:
        return ROOT / model / 'generation' / method / dataset
    return ROOT / model / 'flash_react' / method.lower() / dataset


def command(item, phase):
    model, method, dataset = item
    work = ROOT / model
    command = [PYTHON, '-B', '-u']
    if method in MEMORY:
        return command + [str(work / 'bin/run_qwen8_memory.py'), phase, str(work), method,
                          '--dataset', dataset]
    baseline = work / 'flash_react'
    command += [str(baseline / 'code/run_qwen_baselines.py'), str(work), str(baseline), method.lower(),
                '--dataset', dataset, '--r55-8-tools', '--workers', '3']
    if method == 'Reflexion':
        command.append('--wait-for-react')
    if phase == 'verify':
        command.append('--prepare')
    return command


def environment(item, plan):
    model, method, _ = item
    return dict(os.environ, PYTHONPATH=str(ROOT / 'bin'), R55_8TOOLS_ROOT=str(ROOT),
                R55_RESIDENT_ROOT=plan['resident_root'], CUDA_VISIBLE_DEVICES='0', R55_MEMEVOLVE_GPU='0',
                R55_CHEXAGENT8_SNAPSHOT=plan['chexagent8_snapshot'], R55_REQUIRE_CHEXAGENT8='1',
                R55_QWEN8_ARM=f'{model}/{method}', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2',
                PYTHONDONTWRITEBYTECODE='1', LANGCHAIN_TRACING_V2='false', LANGSMITH_TRACING='false')


def key_input(item, phase):
    if phase != 'run':
        return None
    model, method, _ = item
    qwen, deepseek = CREDENTIALS.read_bytes().splitlines()
    main = deepseek if model == 'deepseek' else qwen
    return main + b'\n' + (deepseek + b'\n' if method in MEMORY else b'')


def launch(item, phase, plan):
    job = job_path(item)
    job.mkdir(parents=True, exist_ok=True)
    keys = key_input(item, phase)
    with (job / f'{phase}.stdout.log').open('ab') as out, (job / f'{phase}.stderr.log').open('ab') as err:
        proc = subprocess.Popen(command(item, phase), cwd=ROOT / item[0], env=environment(item, plan),
                                stdin=subprocess.PIPE if keys else subprocess.DEVNULL, stdout=out, stderr=err)
    runtime.save(job / f'{phase}.started.json', {
        'pid': proc.pid, 'start_ticks': runtime.native(proc.pid), 'epoch': time.time()})
    if keys:
        with proc.stdin as pipe:
            try:
                pipe.write(keys)
            except BrokenPipeError:
                pass
    return proc


def finish(item, plan):
    out = output_path(item)
    _, method, dataset = item
    memory = method in MEMORY
    score = runtime.read(out / ('analysis/summary.json' if memory else 'summary.json'))
    expected = plan['datasets'][dataset]
    label = f'R55-{method}' if memory else method.lower()
    if (score.get('arm'), score.get('dataset'), score.get('questions')) != (label, dataset, expected):
        raise ValueError('Native score does not match the planned cohort')
    saved = len(list((out / 'predictions').rglob('*.json')))
    if saved != expected:
        raise ValueError(f'Native score has {saved}/{expected} predictions')
    if memory and len(list((out / 'external_memory/episodes').glob('*/ingest.json'))) != expected:
        raise ValueError('Online memory writes are incomplete')
    runtime.save(job_path(item) / 'complete.json', {
        'questions': expected, 'correct': score['correct'], 'epoch': time.time()})


def live(record):
    return bool(record and record['start_ticks'] is not None
                and runtime.native(record['pid']) == record['start_ticks'])


def status():
    plan = runtime.read(PLAN)
    started = runtime.read(JOBS / 'supervisor.started.json')
    rows = []
    for item in plan.get('cohorts', []):
        job = job_path(item)
        done = runtime.read(job / 'complete.json')
        failed = runtime.read(job / 'failed.json')
        score = runtime.read(job / 'score.started.json')
        run = runtime.read(job / 'run.started.json')
        state = ('scored' if done else 'failed' if failed else 'scoring' if live(score)
                 else 'running' if live(run) else 'queued')
        preds = output_path(item) / 'predictions'
        rows.append(dict(model=item[0], method=item[1], dataset=item[2], state=state,
                         expected=plan['datasets'][item[2]], saved=len(list(preds.rglob('*.json'))),
                         correct=done.get('correct'), pid=(score if state == 'scoring' else run).get('pid'),
                         error=failed.get('error')))
    return dict(root=str(ROOT), supervisor=started, live=live(started),
                gpu=runtime.read(JOBS / 'gpu.json'), gpu_hold=runtime.read(JOBS / 'gpu-hold.json'),
                cohorts=rows)


def supervise():
    plan = runtime.read(PLAN)
    pending = [tuple(item) for item in plan['cohorts']]
    active = {}
    healthy_samples = 0
    with runtime.lease(JOBS / 'supervisor.lock'):
        while pending or active:
            gpu = runtime.gpu_sample()
            healthy_samples = healthy_samples + 1 if gpu['healthy'] else 0
            runtime.save(JOBS / 'gpu.json', dict(gpu, healthy_samples=healthy_samples))
            for item, (phase, proc) in list(active.items()):
                code = proc.poll()
                if code is None:
                    continue
                del active[item]
                job = job_path(item)
                runtime.save(job / f'{phase}.exit.json', {'exit': code, 'epoch': time.time()})
                if code:
                    runtime.save(job / 'failed.json', {'phase': phase, 'exit': code,
                                                      'error': runtime.safe_error(job, phase)})
                elif item[1] in MEMORY and phase == 'run':
                    runtime.save(job / 'dataset.exit.json', {'exit': 0, 'epoch': time.time()})
                    active[item] = ('score', launch(item, 'score', plan))
                else:
                    try:
                        finish(item, plan)
                    except ValueError as exc:
                        runtime.save(job / 'failed.json', {'phase': phase, 'error': str(exc)})
            scheduling = runtime.read(PLAN)
            target = tuple(scheduling.get('third_slot_first', ()))
            for _ in range(scheduling['max_active_cohorts'] - len(active)):
                choices = pending[:]
                if len(active) == 2 and target in choices:
                    choices.remove(target)
                    choices.insert(0, target)
                for item in choices:
                    job = job_path(item)
                    if (job / 'complete.json').is_file() or (job / 'failed.json').is_file():
                        pending.remove(item)
                        continue
                    if item[:2] == ('deepseek', 'Reflexion'):
                        dependency = job_path(('deepseek', 'ReAct', item[2]))
                        if (dependency / 'failed.json').is_file():
                            runtime.save(job / 'failed.json', {'error': 'Paired DeepSeek ReAct cohort failed'})
                            pending.remove(item)
                        if not (dependency / 'complete.json').is_file():
                            continue
                    requires_archive = ((item[1] == 'Reflexion' and item[0] != 'deepseek')
                                        or (item[:2] == ('deepseek', 'CRITIC') and item[2] != 'slake'))
                    if requires_archive and not (JOBS / 'replay' / item[0] / f'{item[2]}.json').is_file():
                        continue
                    if not runtime.allowed(ROOT, '/'.join(item[:2])) or shutil.disk_usage(ROOT).free < 2 * 1024**3:
                        break
                    active[item] = ('run', launch(item, 'run', plan))
                    pending.remove(item)
                    break
                else:
                    break
            if pending or active:
                time.sleep(4)
        failed = sum(row['state'] == 'failed' for row in status()['cohorts'])
        runtime.save(JOBS / 'finished.json', {'completed': len(plan['cohorts']) - failed, 'failed': failed,
                                              'epoch': time.time()})


if __name__ == '__main__':
    supervise()
