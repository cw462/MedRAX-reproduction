"""Run the frozen R55 arms in order on the lab's shared pair of GPUs."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import os
from pathlib import Path
from shutil import disk_usage
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parent
JOBS = ROOT/'jobs'
ORDER = ('D', 'M5', 'E')
DATASETS = ('chexbench', 'slake', 'vqarad')


def read(path):
    return json.loads(path.read_bytes()) if path.is_file() else None


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix+'.tmp')
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    pending.replace(path)


def native(pid):
    try:
        data = (Path('/proc')/str(pid)/'stat').read_text().rsplit(') ',1)[1].split()
        return {'pid': pid, 'state': data[0], 'start_ticks': int(data[19])}
    except (FileNotFoundError, ProcessLookupError):
        return {'pid': pid, 'state': None, 'start_ticks': None}


def live(receipt):
    if not receipt:
        return None
    process = native(receipt['pid'])
    process['alive'] = (process['start_ticks'] == receipt['start_ticks']
                        and process['state'] not in (None, 'Z', 'X'))
    return dict(receipt, **process)


def gpu_status():
    def query(kind, fields):
        return subprocess.check_output(['nvidia-smi', f'--query-{kind}={fields}',
                                        '--format=csv,noheader,nounits'], text=True, timeout=10)

    gpus = {}
    for line in query('gpu', 'index,uuid,memory.used,memory.total').splitlines():
        idx, uuid, used, total = [v.strip() for v in line.split(',')]
        gpus[idx] = dict(uuid=uuid, used_mib=int(used), total_mib=int(total), pids=[])
    for line in query('compute-apps', 'gpu_uuid,pid').splitlines():
        if ',' not in line:
            continue
        uuid, pid = (v.strip() for v in line.split(',',1))
        for gpu in gpus.values():
            if gpu['uuid'] == uuid and pid.isdigit():
                gpu['pids'].append(int(pid))
    return gpus


def dataset_paths(arm, dataset):
    return ROOT/'generation'/arm/dataset, JOBS/arm/dataset, ROOT/'code'/arm


def official(plan, arm, dataset):
    out, job, _ = dataset_paths(arm, dataset)
    summary = read(out/'analysis/summary.json')
    result = read(job/'scorer.completed.json')
    generation = out/'generation.exitcode'
    if not (summary and result and result['returncode'] == 0 and generation.is_file()
            and generation.read_text().strip() == '0'):
        return None
    if (summary['arm'], summary['dataset'], summary['questions']) != (
            plan['arms'][arm], dataset, plan['counts'][dataset]):
        raise ValueError(f'Unexpected official score identity for {arm}/{dataset}')
    return {key:summary[key] for key in ('correct','questions','accuracy_pct',
                                         'tools_by_name','failed_tool_calls')}


def child(command, directory, phase, gpu, env, input_bytes=b''):
    with (directory/(phase+'.stdout.log')).open('xb') as out, \
            (directory/(phase+'.stderr.log')).open('xb') as err:
        process = subprocess.Popen(command, stdout=out, stderr=err, stdin=subprocess.PIPE,
                                   env=env, cwd=ROOT, start_new_session=True)
        save(directory/(phase+'.started.json'), dict(native(process.pid), gpu=gpu, epoch=time.time()))
        process.communicate(input_bytes)
    result = {'returncode': process.returncode, 'pid': process.pid, 'epoch': time.time()}
    save(directory/(phase+'.exit.json'), result)
    return result


def run_dataset(plan, arm, dataset, gpu, keys):
    out, job, code = dataset_paths(arm, dataset)
    job.mkdir(parents=True, exist_ok=True)
    with (job/'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if official(plan, arm, dataset):
            return 0
        attempts = sorted(job.glob('attempt-*'))
        for prev in attempts[-1:]:
            for phase in ('runner','scorer'):
                proc = live(read(prev/(phase+'.started.json')))
                if proc and proc['alive']:
                    raise RuntimeError(f'Existing {phase} is alive for {arm}/{dataset}')
        attempt = job/f'attempt-{len(attempts)+1:03d}'
        attempt.mkdir()
        out.mkdir(parents=True, exist_ok=True)
        manifest = read(ROOT/'manifests'/arm/(dataset+'.json'))
        saved = read(out/'manifest.json')
        if saved is None:
            save(out/'manifest.json', manifest)
        elif saved != manifest:
            raise ValueError('Frozen manifest changed')

        env = dict(os.environ, CUDA_VISIBLE_DEVICES=gpu, PYTHONDONTWRITEBYTECODE='1',
                   LANGCHAIN_TRACING_V2='false', LANGSMITH_TRACING='false')
        if arm == 'E':
            env['R49_EMBEDDING_API_KEY'] = keys[1].decode()
            env[manifest['writer']['api_key_env']] = keys[2].decode()
        command = [sys.executable,'-B','-u']
        common = ['--data',plan['data'][dataset],'--references',plan['references'][dataset]]
        input_bytes = keys[0]+b'\n'
        if arm == 'M5':
            env['R55_MEMEVOLVE_GPU'] = gpu
            command += [str(ROOT/'run_r55_11tools_m5.py'), '--code', str(code),
                        '--out',str(out),'--runtime',plan['memory_runtime']]
            input_bytes += keys[3]+b'\n'
        else:
            command += [str(ROOT/'run_r55_full848_dataset.py'),'--arm',arm,
                        '--code',str(code),'--out',str(out)]
        command += common
        exitcode = out/'generation.exitcode'
        if not (exitcode.is_file() and exitcode.read_text().strip() == '0'):
            result = child(command, attempt, 'runner', gpu, env, input_bytes)
            exitcode.write_text(str(result['returncode'])+'\n')
            if result['returncode']:
                return result['returncode']
        assert read(out/'complete.json')['questions'] == plan['counts'][dataset]
        if (out/'analysis/per_question.csv').is_file():
            # The stock scorer creates its CSV exclusively. Preserve a previous
            # unconfirmed analysis and generate a clean one from the immutable trace.
            (out/'analysis').rename(attempt/'previous_analysis')
        command = [sys.executable,'-B','-u',str(ROOT/'score_r55_full848_dataset.py'),
                   '--code',str(code),'--run',str(out)]
        result = child(command, attempt, 'scorer', gpu, dict(os.environ))
        if result['returncode'] == 0:
            save(job/'scorer.completed.json', result)
            assert official(plan, arm, dataset)
        return result['returncode']


def run_arm(plan, arm, keys):
    waiting = [d for d in DATASETS if not official(plan, arm, d)]
    active = {}
    failures = {}
    with ThreadPoolExecutor(max_workers=len(plan['gpus'])) as pool:
        while waiting or active:
            for gpu, (ds, task) in list(active.items()):
                if task.done():
                    try:
                        code = task.result()
                        if code != 0:
                            failures[ds] = code
                    except Exception as error:
                        failures[ds] = str(error)
                    del active[gpu]
            if waiting and len(active) < len(plan['gpus']):
                for gpu, info in gpu_status().items():
                    if (gpu in plan['gpus'] and gpu not in active and not info['pids']
                            and info['used_mib'] < 1024 and waiting):
                        ds = waiting.pop(0)
                        active[gpu] = (ds, pool.submit(run_dataset, plan, arm, ds, gpu, keys))
            save(JOBS/'queue.state.json', {'arm':arm, 'gpus':{g:a[0] for g,a in active.items()},
                                          'waiting':waiting,'failed':failures,'epoch':time.time()})
            if waiting or active:
                time.sleep(4)
    if failures:
        return failures
    scores = {ds:official(plan, arm, ds) for ds in DATASETS}
    correct = sum(s['correct'] for s in scores.values())
    questions = sum(s['questions'] for s in scores.values())
    save(JOBS/arm/'complete.json', {'arm':plan['arms'][arm], 'correct':correct, 'questions':questions,
                                   'accuracy_pct':100*correct/questions, 'datasets':scores})
    return {}


def run():
    keys = sys.stdin.buffer.read().splitlines()
    if len(keys) != 4 or not all(keys):
        raise RuntimeError('Expected existing main, embedding, writer and memory credentials')
    with (JOBS/'queue.run.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = read(ROOT/'plan.json')
        if (JOBS/'queue.finished.json').exists():
            (JOBS/'queue.finished.json').unlink()
        for arm in ORDER:
            failures = run_arm(plan, arm, keys)
            if failures:
                save(JOBS/'queue.finished.json', {'returncode': 1, 'arm':arm, 'failed':failures})
                return 1
        save(JOBS/'queue.finished.json', {'returncode': 0, 'completed': list(ORDER)})
    return 0


def launch():
    keys = sys.stdin.buffer.read()
    JOBS.mkdir(exist_ok=True)
    with (JOBS/'queue.launch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        existing = live(read(JOBS/'queue.started.json'))
        if existing and existing['alive']:
            return existing
        if (read(JOBS/'queue.finished.json') or {}).get('returncode') == 0:
            return {'complete': True}
        with (JOBS/'queue.stdout.log').open('ab') as out, (JOBS/'queue.stderr.log').open('ab') as err:
            process = subprocess.Popen([sys.executable,'-B','-u',str(Path(__file__).resolve()),'run'],
                                       stdin=subprocess.PIPE, stdout=out, stderr=err,
                                       start_new_session=True)
            process.stdin.write(keys)
            process.stdin.close()
        receipt = dict(native(process.pid), epoch=time.time())
        save(JOBS/'queue.started.json', receipt)
        return receipt


def tail(path):
    if not path.is_file():
        return ''
    with path.open('rb') as stream:
        stream.seek(max(0,path.stat().st_size-1400))
        return stream.read().decode(errors='replace')


def status():
    plan = read(ROOT/'plan.json')
    arms = {}
    for arm in ORDER:
        datasets = {}
        for ds in DATASETS:
            out, job, _ = dataset_paths(arm, ds)
            attempts = sorted(job.glob('attempt-*'))
            attempt = attempts[-1] if attempts else None
            predictions = out/'predictions'/plan['arms'][arm]
            item = {'saved':sum(1 for _ in predictions.glob('*.json')),
                    'questions':plan['counts'][ds], 'score':official(plan, arm, ds)}
            if attempt is not None:
                for phase in ('runner','scorer'):
                    item[phase] = live(read(attempt/(phase+'.started.json')))
                    exit = read(attempt/(phase+'.exit.json'))
                    if exit:
                        item[phase+'_exit'] = exit['returncode']
                        if exit['returncode'] != 0:
                            item[phase+'_error'] = tail(attempt/(phase+'.stderr.log'))
            datasets[ds] = item
        arms[arm] = {'datasets':datasets,'complete':read(JOBS/arm/'complete.json')}
    queue = live(read(JOBS/'queue.started.json'))
    return {'root':str(ROOT),'process':queue,'state':read(JOBS/'queue.state.json'),
            'finished':read(JOBS/'queue.finished.json'),'arms':arms,'gpus':gpu_status(),
            'free_bytes':disk_usage(ROOT).free,
            'queue_error':tail(JOBS/'queue.stderr.log') if queue and not queue['alive'] else ''}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('launch','run','status'))
    phase = parser.parse_args().phase
    if phase == 'run':
        raise SystemExit(run())
    print(json.dumps(globals()[phase](), ensure_ascii=True))
