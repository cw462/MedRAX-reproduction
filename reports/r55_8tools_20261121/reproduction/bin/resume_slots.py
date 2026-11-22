"""Use available R55 slots for validated checkpoint continuations."""

import json
import os
from pathlib import Path
import shutil
import sys
import time

import queue_r55 as queue
import r55_deepseek_rerun_runtime as runtime


CONTINUATIONS = queue.JOBS / 'continuations'
STATUS = queue.JOBS / 'timeout-watch.json'


def request_path(item):
    model, method, dataset = item
    return CONTINUATIONS / model / method / f'{dataset}.json'


def submit(items):
    plan = runtime.read(queue.PLAN)
    with runtime.lease(queue.JOBS / 'continuations.submit.lock'):
        for item in items:
            if (list(item) not in plan['cohorts']
                    or (item[1] not in queue.MEMORY and item != ('flash', 'Reflexion', 'chexbench'))):
                raise ValueError('Expected a cohort with a validated continuation')
            path = request_path(item)
            existing = runtime.read(path)
            if existing.get('phase') in ('pending', 'running', 'scoring'):
                continue
            if not runtime.read(queue.job_path(item) / 'failed.json'):
                raise ValueError(f'{"/".join(item)} has no failing generation receipt')
            runtime.save(path, {'item': item, 'phase': 'pending', 'epoch': time.time()})


def set_native_cap(count):
    with runtime.lease(queue.JOBS / 'parallelism.lock'):
        plan = runtime.read(queue.PLAN)
        if plan['max_active_cohorts'] != count:
            runtime.save(queue.PLAN, dict(plan, max_active_cohorts=count))
            return time.time()
    return None


def native_outstanding(plan, continuations):
    count = 0
    for item in map(tuple, plan['cohorts']):
        if item in continuations:
            continue
        job = queue.job_path(item)
        if ((job / 'run.started.json').is_file() and not (job / 'complete.json').is_file()
                and not (job / 'failed.json').is_file()):
            count += 1
    return count


def launch(item, phase, plan):
    ordinary = queue.command
    if phase == 'run':
        worker = queue.ROOT / 'bin' / f'resume_{item[1].lower()}_worker.py'

        def command(identity, requested_phase):
            arguments = ordinary(identity, requested_phase)
            if identity == item and requested_phase == phase:
                arguments[3] = str(worker)
            return arguments

        queue.command = command
    try:
        return queue.launch(item, phase, plan)
    finally:
        queue.command = ordinary


def pending_requests():
    records = [runtime.read(path) for path in CONTINUATIONS.glob('*/*/*.json')]
    return sorted((record for record in records if record.get('phase') == 'pending'),
                  key=lambda record: (record['item'][2] != 'slake', record['epoch']))


def preserve_attempt(item):
    job = queue.job_path(item)
    if any(queue.live(runtime.read(job / f'{phase}.started.json')) for phase in ('run', 'score')):
        raise RuntimeError(f'{"/".join(item)} still has an active process')
    failed = runtime.read(job / 'failed.json')
    if failed.get('phase') != 'run':
        raise RuntimeError(f'{"/".join(item)} needs a failed generation receipt')
    keep = job / 'recovery' / f'prior-attempt-{time.time_ns()}'
    keep.mkdir(parents=True)
    for name in ('failed.json', 'run.exit.json', 'run.started.json', 'run.stdout.log', 'run.stderr.log'):
        path = job / name
        if path.is_file():
            path.replace(keep / name)
    return str(keep.relative_to(queue.ROOT))


def supervise():
    active = {}
    adopted_after = 0
    healthy = 0
    plan = runtime.read(queue.PLAN)
    with runtime.lease(queue.JOBS / 'continuations.supervisor.lock'):
        try:
            while True:
                for item, (phase, child, record) in list(active.items()):
                    exitcode = child.poll()
                    if exitcode is None:
                        continue
                    del active[item]
                    job = queue.job_path(item)
                    exit_record = {'exit': exitcode, 'epoch': time.time()}
                    runtime.save(job / f'{phase}.exit.json', exit_record)
                    try:
                        if exitcode:
                            raise RuntimeError(runtime.safe_error(job, phase))
                        if phase == 'run' and item[1] in queue.MEMORY:
                            runtime.save(job / 'dataset.exit.json', exit_record)
                            scorer = launch(item, 'score', plan)
                            record.update(phase='scoring', pid=scorer.pid)
                            active[item] = ('score', scorer, record)
                        else:
                            queue.finish(item, plan)
                            record.update(phase='completed', score=runtime.read(job / 'complete.json'))
                    except (OSError, RuntimeError, ValueError) as exc:
                        runtime.save(job / 'failed.json', {'phase': phase, 'error': str(exc), 'epoch': time.time()})
                        record.update(phase='failed', error=str(exc))
                    runtime.save(request_path(item), record)

                waiting = pending_requests()
                reserved = min(2, len(waiting) + len(active))
                changed = set_native_cap(3 - reserved)
                if changed is not None:
                    adopted_after = changed
                scheduler_live = queue.live(runtime.read(queue.JOBS / 'supervisor.started.json'))
                if not scheduler_live and reserved:
                    sample = runtime.gpu_sample()
                    healthy = healthy + 1 if sample['healthy'] else 0
                    runtime.save(queue.JOBS / 'gpu.json', dict(sample, healthy_samples=healthy))
                heartbeat = runtime.read(queue.JOBS / 'gpu.json')
                if waiting and len(active) < reserved and heartbeat.get('epoch', 0) > adopted_after:
                    native = native_outstanding(plan, active)
                    for record in waiting[:max(0, min(reserved - len(active), 3 - native - len(active)))]:
                        item = tuple(record['item'])
                        if not runtime.allowed(queue.ROOT, '/'.join(item[:2])) or shutil.disk_usage(queue.ROOT).free < 2 * 1024**3:
                            break
                        archived = None
                        try:
                            archived = preserve_attempt(item)
                            child = launch(item, 'run', plan)
                            record.update(phase='running', pid=child.pid, prior_attempt=archived)
                            active[item] = ('run', child, record)
                        except (OSError, RuntimeError, ValueError) as exc:
                            if archived:
                                runtime.save(queue.job_path(item) / 'failed.json', {'phase': 'run', 'error': str(exc),
                                                                                 'epoch': time.time()})
                            record.update(phase='failed', error=str(exc))
                        runtime.save(request_path(item), record)
                runtime.save(STATUS, {'phase': 'running' if active else 'waiting' if waiting else 'idle',
                                      'pid': os.getpid(), 'epoch': time.time(), 'native_cap': 3 - reserved,
                                      'active': [list(item) for item in active],
                                      'waiting': [record['item'] for record in pending_requests()]})
                if not reserved:
                    break
                time.sleep(4)
        finally:
            set_native_cap(3)


if __name__ == '__main__':
    os.umask(0o077)
    if len(sys.argv) > 1:
        requested = [tuple(value.split('/')) for value in sys.argv[1:]]
        submit(requested)
        print(json.dumps({'requested': requested}))
    else:
        supervise()
