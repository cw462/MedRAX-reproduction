"""Run open-budget Qwen baselines on the existing R55 AutoDL instance."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
from shutil import copy2
import subprocess
import sys
import time


RUNS = {6: ('chexagent8_open_budget', ('react', 'reflexion')),
        11: ('chexagent8_11tools_open_budget', ('react', 'critic', 'reflexion'))}
DATASETS = {'slake': 114, 'vqarad': 116, 'chexbench': 618}
REVISION = '4934e91451945c8218c267aae9c34929a7677829'


def read(path):
    return json.loads(path.read_bytes()) if path.is_file() else {}


def write(path, data):
    temporary = path.with_suffix(f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def active(path):
    data = read(path)
    if not data:
        return False
    try:
        fields = (Path('/proc') / str(data['pid']) / 'stat').read_text().rsplit(') ', 1)[1].split()
        return fields[0] not in ('Z', 'X') and int(fields[19]) == data['start_ticks']
    except FileNotFoundError:
        return False


def scores(out, method):
    return {
        dataset: {
            'saved': sum(1 for _ in (out / method / dataset / 'predictions').glob('*.json')),
            'questions': size,
            'summary': read(out / method / dataset / 'summary.json'),
        }
        for dataset, size in DATASETS.items()
    }


def status(out, methods):
    jobs = out / 'jobs'
    result = {'root': str(out), 'live': active(jobs / 'controller.started.json'),
              'state': read(jobs / 'state.json'), 'methods': {}}
    for method in methods:
        job = jobs / method
        attempts = sorted(job.glob('attempt-*'))
        latest = attempts[-1] if attempts else None
        exitfile = latest / 'exitcode' if latest else None
        started = read(latest / 'started.json') if latest else {}
        result['methods'][method] = {'datasets': scores(out, method), 'complete': read(job / 'complete.json'),
                                     'runner_pid': started.get('pid'),
                                     'runner_exit': int(exitfile.read_text()) if exitfile and exitfile.is_file() else None}
    return result


def stage(base, out, controller, runner, tool_runner):
    original = base / 'chexagent8'
    for folder in (out, out / 'code', out / 'jobs', out / 'logs'):
        folder.mkdir(mode=0o700, exist_ok=True)
    sources = {out / 'code' / 'run_qwen_baselines.py': runner, out / 'queue_qwen_open_budget.py': controller}
    if tool_runner:
        sources[out / 'code' / 'r55_baselines_11tools.py'] = tool_runner
    for target, source in sources.items():
        compile(source, str(target), 'exec')
        if target.is_file():
            if target.read_bytes() != source:
                raise ValueError(f'Run source changed after staging: {target.name}')
        else:
            temporary = target.with_suffix(f'.{os.getpid()}.tmp')
            temporary.write_bytes(source)
            temporary.replace(target)
    for module in ('r55_baseline_common.py', 'r55_baseline_vqa.py', 'run_chexagent8_direct.py',
                   'queue_chexagent8_lab.py', 'launch_llavarad.py'):
        dest = out / 'code' / module
        if not dest.is_file():
            copy2(original / 'code' / module, dest)
    cot = out / 'cot'
    if not cot.exists():
        cot.symlink_to((original / 'cot').resolve(strict=True), target_is_directory=True)


def launch(base, out, controller, key, runner, tool_runner, workers, tool_count):
    _, methods = RUNS[tool_count]
    if not controller or not key or not runner or workers < 1 or (tool_count == 11 and not tool_runner):
        raise ValueError('Incomplete launch input')
    out.mkdir(mode=0o700, exist_ok=True)
    with (out / 'launch.lock').open('a') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        jobs = out / 'jobs'
        marker = jobs / 'controller.started.json'
        if active(marker) or all((jobs / method / 'complete.json').is_file() for method in methods):
            return status(out, methods)
        stage(base, out, controller, runner, tool_runner)
        with (out / 'logs/controller.out').open('ab') as stdout, (out / 'logs/controller.err').open('ab') as stderr:
            child = subprocess.Popen(
                [sys.executable, '-B', '-u', str(out / 'queue_qwen_open_budget.py'), 'run',
                 str(base), str(workers), str(tool_count)],
                cwd=out, stdout=stdout, stderr=stderr, start_new_session=True, stdin=subprocess.PIPE,
            )
            child.stdin.write(key + b'\n')
            child.stdin.close()
        stat = (Path('/proc') / str(child.pid) / 'stat').read_text().rsplit(') ', 1)[1].split()
        write(marker, {'pid': child.pid, 'start_ticks': int(stat[19]), 'epoch': time.time(), 'workers': workers})
    return status(out, methods)


def identity(pid):
    try:
        proc = Path('/proc') / str(pid)
        f = (proc / 'stat').read_text().rsplit(') ', 1)[1].split()
        if f[0] not in ('Z', 'X'):
            return {'ticks': int(f[19]), 'state': f[0], 'ppid': int(f[1]),
                    'args': (proc / 'cmdline').read_bytes().split(b'\0')}
    except FileNotFoundError:
        pass
    return None


def process_stopped(pid):
    tasks = list((Path('/proc') / str(pid) / 'task').glob('*/stat'))
    try:
        return bool(tasks) and all(p.read_text().rsplit(') ', 1)[1][0] == 'T' for p in tasks)
    except FileNotFoundError:
        return False


def runner_requests_closed(out, method):
    roles = ('reflexion_evaluator', 'reflexion_retry') if method == 'reflexion' else (method,)
    for dataset in DATASETS:
        api = out / 'api' / dataset
        folders = []
        for role in roles:
            folders.extend(api.glob('calls/' + role + '*/' + '*/*/started.json'))
            service = api / 'tool_runs' / role / 'services'
            folders.extend(service.glob('calls/*/*/*/started.json'))
            folders.extend(service.glob('tool_cache/*/started.json'))
        if any(not (p.parent / 'result.json').is_file() for p in folders):
            return False
    return True


def pause_for_transport(out, correction=False):
    jobs = out / 'jobs'
    credentials = Path('/root/.config/medrax-autodl-r55')
    key_file = credentials / 'qwen37_workspace.key'
    staged = credentials / 'qwen37_workspace.staged'
    expected_key = key_file if correction else staged
    if not expected_key.is_file() or expected_key.stat().st_mode & 0o077:
        raise ValueError('Missing private workspace credential')
    receipt_name = 'qwen-workspace-correction.json' if correction else 'qwen-workspace-cutover.json'
    with (out / 'launch.lock').open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        marker = jobs / 'controller.started.json'
        supervisor = read(marker)
        if not active(marker) or supervisor.get('schedule') != 'parallel':
            raise RuntimeError('No live parallel supervisor to hand off')
        owner = identity(supervisor['pid'])
        if os.fsencode(out / 'queue_qwen_open_budget.py') not in owner['args']:
            raise RuntimeError('Unexpected Qwen supervisor identity')
        pids = {}
        before = {}
        stopped = set()
        draining = set()
        committed = False
        os.kill(supervisor['pid'], signal.SIGSTOP)
        try:
            for method in RUNS[11][1]:
                before[method] = {d: v['saved'] for d, v in scores(out, method).items()}
                if read(jobs / method / 'complete.json'):
                    continue
                attempt = sorted((jobs / method).glob('attempt-*'))[-1]
                pid = read(attempt / 'started.json')['pid']
                child = identity(pid)
                adopted = read(jobs / 'react.adopted.json')
                owned = child and (child['ppid'] == supervisor['pid'] or (
                    method == 'react' and (pid, child['ticks']) == (adopted.get('pid'), adopted.get('start_ticks'))))
                if not owned or not {os.fsencode(out / 'code/run_qwen_baselines.py'), method.encode(),
                                     os.fsencode(out)}.issubset(child['args']):
                    raise RuntimeError(f'Cannot identify the current {method} runner')
                pids[method] = pid
            if correction:
                # Python handles SIGINT on the coordinating thread. The runner
                # cancels queued cases and joins already active case workers.
                for method, pid in pids.items():
                    os.kill(pid, signal.SIGINT)
                    draining.add(method)
            deadline = time.monotonic() + (240 if correction else 150)
            exited = set()
            while set(pids) != stopped | exited:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Waiting for live baseline requests to finish')
                for method, pid in pids.items():
                    if method in stopped or method in exited:
                        continue
                    if not identity(pid):
                        if correction:
                            if not runner_requests_closed(out, method):
                                raise RuntimeError(f'{method} exited with unfinished request receipts')
                        elif not check_method(out, method):
                            raise RuntimeError(f'{method} exited incomplete during transport handoff')
                        exited.add(method)
                        continue
                    if correction:
                        continue
                    if not runner_requests_closed(out, method):
                        continue
                    os.kill(pid, signal.SIGSTOP)
                    try:
                        for _ in range(50):
                            if process_stopped(pid):
                                break
                            time.sleep(.02)
                        tasks = Path('/proc') / str(pid) / 'task'
                        children = any(p.read_text().strip() for p in tasks.glob('*/children'))
                        if process_stopped(pid) and not children and runner_requests_closed(out, method):
                            stopped.add(method)
                    finally:
                        if method not in stopped:
                            os.kill(pid, signal.SIGCONT)
                if set(pids) != stopped | exited:
                    time.sleep(.1)
            saved = {m: {d: v['saved'] for d, v in scores(out, m).items()} for m in before}
            if not correction:
                staged.replace(key_file)
            receipt = {'epoch': time.time(), 'endpoint': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                       'model': 'qwen3.7-plus', 'credential_slot': 'qwen37_workspace',
                       'old_runner_pids': {m: p for m, p in pids.items() if m not in exited or m in draining},
                       'saved': saved, 'deepseek_credential_rotated': False}
            write(jobs / receipt_name, receipt)
            adopted_path = jobs / 'react.adopted.json'
            if adopted_path.is_file():
                adopted_path.replace(jobs / 'react.adopted.before-workspace.json')
            committed = True
        finally:
            if committed:
                # Stop the dispatcher first so it cannot act on the intentionally ended children.
                os.kill(supervisor['pid'], signal.SIGTERM)
            os.kill(supervisor['pid'], signal.SIGCONT)
            for method in stopped:
                pid = pids[method]
                if committed:
                    os.kill(pid, signal.SIGTERM)
                os.kill(pid, signal.SIGCONT)
        previous = [supervisor['pid'], *pids.values()]
        for _ in range(160):
            if all(not identity(pid) for pid in previous):
                return receipt
            time.sleep(.05)
        raise RuntimeError('Waiting for the drained original runners to exit')


def stop_sequential(out):
    marker = read(out / 'jobs/controller.started.json')
    current = identity(marker['pid']) if marker else None
    if not current or current['ticks'] != marker['start_ticks']:
        return None
    if os.fsencode(out / 'queue_qwen_open_budget.py') not in current['args']:
        raise RuntimeError('The running baseline dispatcher identity changed')
    stages = sorted((out / 'jobs/react').glob('attempt-*'))
    if not stages:
        raise RuntimeError('The sequential dispatcher has not started ReAct')
    attempt = stages[-1]
    pid = read(attempt / 'started.json')['pid']
    react = identity(pid)
    if (not react or react['ppid'] != marker['pid'] or
            os.fsencode(out / 'code/run_qwen_baselines.py') not in react['args'] or b'react' not in react['args']):
        raise RuntimeError('Cannot adopt the existing ReAct process')
    os.kill(marker['pid'], signal.SIGSTOP)
    try:
        for _ in range(50):
            paused = identity(marker['pid'])
            if not paused or paused['state'] == 'T':
                break
            time.sleep(.02)
        else:
            raise RuntimeError('The sequential dispatcher did not pause')
        if not identity(pid):
            raise RuntimeError('ReAct exited during the dispatcher handoff')
        evidence = {'pid': pid, 'start_ticks': react['ticks'], 'attempt': str(attempt),
                    'previous_dispatcher': marker['pid']}
        write(out / 'jobs/react.adopted.json', evidence)
        os.kill(marker['pid'], signal.SIGTERM)
    finally:
        os.kill(marker['pid'], signal.SIGCONT)
    for _ in range(90):
        if not identity(marker['pid']):
            return evidence
        time.sleep(.05)
    raise RuntimeError('The sequential dispatcher did not exit')


def check_method(out, method):
    checked = {}
    for dataset, row in scores(out, method).items():
        summary = row['summary']
        if row['saved'] == row['questions'] and (summary.get('arm'), summary.get('dataset'),
                                                  summary.get('questions')) == (
                method, dataset, row['questions']):
            checked[dataset] = {k: summary[k] for k in ('correct', 'questions')}
    if set(checked) != set(DATASETS):
        return None
    receipt = dict(revision=REVISION, method=method, exit=0, tool_budget='open', tool_count=11,
                   datasets=checked)
    write(out / 'jobs' / method / 'complete.json', receipt)
    return receipt


def run_parallel(base, out, key, workers):
    sys.path.insert(0, str(out / 'code'))
    from queue_chexagent8_lab import environment, run_process

    root = base.with_name(base.name + '_chexagent8_20261114')
    plan = read(root / 'plan.json')
    if plan.get('revision') != REVISION:
        raise ValueError('Wrong CheXagent revision for this rerun')
    env = environment('0', Path(plan['checkpoint']))
    env['R55_BASELINE_SHARED_GPU_ROOT'] = str(root)
    jobs = out / 'jobs'
    with (jobs / 'run.lock').open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)

        def run_one(method):
            job = jobs / method
            job.mkdir(exist_ok=True)
            if read(job / 'complete.json'):
                return 'complete'
            adopted = read(jobs / 'react.adopted.json') if method == 'react' else None
            if adopted:
                while ((proc := identity(adopted['pid'])) and proc['ticks'] == adopted['start_ticks']):
                    time.sleep(2)
                attempt = Path(adopted['attempt'])
                if check_method(out, method):
                    # The adopted child wrote all three scores before exiting.
                    write(job / 'adopted.completed.json', adopted)
                    return 'complete'
                error = attempt / 'stderr.log'
                if error.is_file() and error.stat().st_size:
                    return f'Adopted ReAct exited incomplete. See {attempt}'
            attempt = job / f'attempt-{time.time_ns()}'
            command = [str(base / 'env/modern/bin/python'), '-B', '-u', str(out / 'code/run_qwen_baselines.py'),
                       str(root), str(out), method, '--workers', str(workers), '--r55-11-tools']
            if method == 'reflexion':
                command.append('--wait-for-react')
            code = run_process(command, env, attempt, key + b'\n')
            if code or not check_method(out, method):
                return f'Exit {code} or incomplete scores. See {attempt}'
            return 'complete'

        methods = RUNS[11][1]
        results = {}
        with ThreadPoolExecutor(max_workers=len(methods)) as pool:
            pending = {method: pool.submit(run_one, method) for method in methods}
            while pending:
                for method, future in list(pending.items()):
                    if not future.done():
                        continue
                    try:
                        results[method] = future.result()
                    except Exception as error:
                        results[method] = str(error)
                    del pending[method]
                write(jobs / 'state.json', {'phase': 'parallel', 'active_methods': list(pending),
                                            'results': results, 'epoch': time.time()})
                if pending:
                    time.sleep(3)
        if any(value != 'complete' for value in results.values()):
            write(jobs / 'state.json', {'phase': 'failed', 'results': results, 'epoch': time.time()})
            return 1
        write(jobs / 'state.json', {'phase': 'complete', 'results': results, 'epoch': time.time()})
        resumed = subprocess.run([sys.executable, '-B', str(root / 'prioritize_autodl_baselines.py'),
                                  'resume', str(root), str(out)], capture_output=True, text=True)
        write(jobs / 'memory-resume.json', {'exit': resumed.returncode,
                                            'stdout': resumed.stdout, 'stderr': resumed.stderr})
        return resumed.returncode


def launch_parallel(base, out, key, workers):
    if not key or workers < 1:
        raise ValueError('Missing existing main-model credential or workers')
    root = base.with_name(base.name + '_chexagent8_20261114')
    if not (root / 'jobs/baselines-priority.memory-paused.json').is_file():
        raise ValueError('The four memory groups have not yet been paused')
    jobs = out / 'jobs'
    with (out / 'launch.lock').open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        marker = jobs / 'controller.started.json'
        if (read(marker).get('schedule') == 'parallel' and active(marker)):
            state = read(jobs / 'state.json')
            failed = [m for m, v in state.get('results', {}).items() if v != 'complete']
            if not failed:
                return status(out, RUNS[11][1])
            if any(m in state.get('active_methods', ()) for m in failed):
                raise RuntimeError('A failed method still holds its worker')
            # A controller can be replaced while it is waiting on the adopted ReAct.
            # Baseline children publish to distinct method locks.
            for method in state.get('active_methods', ()):
                if method != 'react':
                    raise RuntimeError(f'Wait for the live {method} child before replacing the supervisor')
                adopted = read(jobs / 'react.adopted.json')
                adopted_proc = identity(adopted['pid']) if adopted else None
                if not adopted_proc or adopted_proc['ticks'] != adopted['start_ticks']:
                    raise RuntimeError('ReAct is no longer the adopted live worker')
            old = read(marker)
            proc = identity(old['pid'])
            if not proc or proc['ticks'] != old['start_ticks']:
                raise RuntimeError('Parallel dispatcher identity has changed')
            os.kill(old['pid'], signal.SIGTERM)
            for _ in range(90):
                proc = identity(old['pid'])
                if not proc or proc['ticks'] != old['start_ticks']:
                    break
                time.sleep(.05)
            else:
                raise RuntimeError('The previous parallel supervisor did not exit')
        if (read(marker).get('schedule') != 'parallel' and active(marker)):
            stop_sequential(out)
        with (out / 'logs/parallel-controller.out').open('ab') as stdout, \
                (out / 'logs/parallel-controller.err').open('ab') as stderr:
            command = [str(base / 'env/modern/bin/python'), '-B', '-u', str(out / 'queue_qwen_open_budget.py'),
                       'run-parallel', str(base), str(workers), '11']
            child = subprocess.Popen(command, cwd=out, stdin=subprocess.PIPE, stdout=stdout,
                                     stderr=stderr, start_new_session=True)
            child.stdin.write(key + b'\n')
            child.stdin.close()
        write(marker, {'pid': child.pid, 'start_ticks': identity(child.pid)['ticks'],
                       'workers': workers, 'schedule': 'parallel', 'epoch': time.time()})
        return status(out, RUNS[11][1])


def run(base, out, key, workers, tool_count):
    sys.path.insert(0, str(out / 'code'))
    from queue_chexagent8_lab import environment, release_worker, run_process

    if not key:
        raise ValueError('Existing main-model credential must be supplied on stdin')
    memory = base.with_name(base.name + '_chexagent8_20261114')
    plan = read(memory / 'plan.json')
    if plan['revision'] != REVISION:
        raise ValueError('Wrong CheXagent revision for this rerun')
    env = environment('0', Path(plan['checkpoint']))
    env['R55_BASELINE_SHARED_GPU_ROOT'] = str(memory)
    _, methods = RUNS[tool_count]
    frozen_root = memory if tool_count == 11 else base
    jobs = out / 'jobs'
    with (jobs / 'run.lock').open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for method in methods:
            job = jobs / method
            job.mkdir(exist_ok=True)
            if (job / 'complete.json').is_file():
                continue
            attempt = job / f'attempt-{time.time_ns()}'
            command = [sys.executable, '-B', '-u', str(out / 'code/run_qwen_baselines.py'),
                       str(frozen_root), str(out), method, '--workers', str(workers), '--open-tool-budget']
            if tool_count == 11:
                command.append('--r55-11-tools')
            write(jobs / 'state.json', {'phase': 'running', 'method': method, 'epoch': time.time()})
            try:
                code = run_process(command, env, attempt, key + b'\n')
            finally:
                release_worker(out, '0')
            checked = {}
            for dataset, row in scores(out, method).items():
                summary = row['summary']
                if row['saved'] == row['questions'] and (summary.get('arm'), summary.get('questions')) == (
                    method, row['questions']
                ):
                    checked[dataset] = {k: summary[k] for k in ('correct', 'questions')}
            if code != 0 or set(checked) != set(DATASETS):
                write(jobs / 'state.json', {'phase': 'failed', 'method': method, 'exit': code,
                                           'attempt': attempt.name, 'epoch': time.time()})
                return 1
            write(job / 'complete.json', {'revision': REVISION, 'method': method, 'exit': code,
                                          'tool_budget': 'open', 'tool_count': tool_count, 'datasets': checked})
        write(jobs / 'state.json', {'phase': 'complete', 'utc': datetime.now(timezone.utc).isoformat()})
        return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('launch', 'run', 'status', 'launch-parallel', 'run-parallel',
                                         'rotate-qwen', 'reload-qwen-workspace'))
    parser.add_argument('base', type=Path)
    parser.add_argument('workers', type=int)
    parser.add_argument('tool_count', type=int, choices=RUNS, nargs='?', default=6)
    args = parser.parse_args()
    name, methods = RUNS[args.tool_count]
    out = args.base / name
    if args.mode in ('rotate-qwen', 'reload-qwen-workspace'):
        if args.tool_count != 11:
            parser.error('rotate-qwen requires the parallel 11-tool run')
        key = sys.stdin.buffer.readline().strip()
        if not key:
            raise ValueError('Missing existing DeepSeek credential on stdin')
        receipt = pause_for_transport(out, correction=args.mode == 'reload-qwen-workspace')
        print(json.dumps(receipt), flush=True)
        print(json.dumps(launch_parallel(args.base, out, key, args.workers)), flush=True)
        return 0
    if args.mode == 'run-parallel':
        return run_parallel(args.base, out, sys.stdin.buffer.readline().strip(), args.workers)
    if args.mode == 'launch-parallel':
        print(json.dumps(launch_parallel(args.base, out, sys.stdin.buffer.readline().strip(), args.workers)))
        return 0
    if args.mode == 'run':
        return run(args.base, out, sys.stdin.buffer.readline().strip(), args.workers, args.tool_count)
    if args.mode == 'launch':
        controller, _, payload = sys.stdin.buffer.read().partition(b'\x00')
        key, _, source = payload.partition(b'\n')
        runner, _, tool_runner = source.partition(b'\x00')
        result = launch(args.base, out, controller, key.strip(), runner, tool_runner, args.workers, args.tool_count)
    else:
        result = status(out, methods)
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
