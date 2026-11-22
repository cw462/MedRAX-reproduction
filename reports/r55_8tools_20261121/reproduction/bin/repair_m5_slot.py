"""Run the SLAKE M5 checkpoint repair in one reserved scheduler slot."""

import os
import shutil
import time

import queue_r55 as queue
import r55_deepseek_rerun_runtime as runtime


TARGET = ('deepseek', 'M5', 'slake')
WORKER = queue.ROOT / 'bin/resume_m5_worker.py'
JOB = queue.job_path(TARGET)
RECEIPT = queue.JOBS / 'repair-m5-slot.json'


def outstanding(plan):
    total = 0
    for item in plan['cohorts']:
        if tuple(item) == TARGET:
            continue
        job = queue.job_path(item)
        if ((job / 'run.started.json').is_file()
                and not (job / 'complete.json').is_file()
                and not (job / 'failed.json').is_file()):
            total += 1
    return total


def run_phase(phase, plan):
    original = queue.command
    if phase == 'run':
        def command(item, requested_phase):
            argv = original(item, requested_phase)
            if item == TARGET and requested_phase == 'run':
                argv[3] = str(WORKER)
            return argv

        queue.command = command
    try:
        return queue.launch(TARGET, phase, plan)
    finally:
        queue.command = original


def repair():
    plan = runtime.read(queue.PLAN)
    if plan['max_active_cohorts'] != 3 or not queue.live(runtime.read(queue.JOBS / 'supervisor.started.json')):
        raise RuntimeError('Expected a live three-cohort scheduler')
    if (JOB / 'complete.json').is_file() or any(queue.live(runtime.read(JOB / f'{phase}.started.json'))
                                               for phase in ('run', 'score')):
        raise RuntimeError('Native target is already active or complete')
    failed = runtime.read(JOB / 'failed.json')
    original_exit = runtime.read(JOB / 'run.exit.json')
    if failed.get('phase') != 'run' or original_exit.get('exit') in (None, 0):
        raise RuntimeError('Expected a failed generation receipt for SLAKE M5')
    compile(WORKER.read_bytes(), str(WORKER), 'exec')

    state = {'target': TARGET, 'controller_pid': os.getpid(), 'epoch': time.time()}

    def record(phase, **fields):
        state.update(phase=phase, updated_epoch=time.time(), **fields)
        runtime.save(RECEIPT, state)

    reserved = False
    archived = False
    phase = 'waiting_for_slot'
    try:
        runtime.save(queue.PLAN, dict(plan, max_active_cohorts=2))
        reserved = True
        cap_updated = time.time()
        record(phase, supervisor_cap=2)
        while True:
            if not queue.live(runtime.read(queue.JOBS / 'supervisor.started.json')):
                raise RuntimeError('Main scheduler exited while the repair waited for its slot')
            current = runtime.read(queue.PLAN)
            if current['max_active_cohorts'] != 2:
                raise RuntimeError('Repair slot reservation was replaced')
            heartbeat = runtime.read(queue.JOBS / 'gpu.json')
            if (heartbeat.get('epoch', 0) > cap_updated and outstanding(current) <= 2
                    and runtime.allowed(queue.ROOT, '/'.join(TARGET[:2]))
                    and shutil.disk_usage(queue.ROOT).free >= 2 * 1024**3):
                break
            time.sleep(4)

        archive = JOB / 'recovery' / f'retrieval-timeout-{time.time_ns()}'
        archive.mkdir(parents=True)
        for name in ('failed.json', 'run.exit.json', 'run.started.json', 'run.stdout.log', 'run.stderr.log'):
            original = JOB / name
            if original.is_file():
                original.replace(archive / name)
        archived = True
        phase = 'run'
        proc = run_phase(phase, current)
        record('running', run_pid=proc.pid, original_receipts=str(archive.relative_to(queue.ROOT)))
        code = proc.wait()
        result = {'exit': code, 'epoch': time.time()}
        runtime.save(JOB / 'run.exit.json', result)
        if code:
            raise RuntimeError(runtime.safe_error(JOB, phase))
        runtime.save(JOB / 'dataset.exit.json', result)

        phase = 'score'
        proc = run_phase(phase, current)
        record('scoring', score_pid=proc.pid)
        code = proc.wait()
        runtime.save(JOB / 'score.exit.json', {'exit': code, 'epoch': time.time()})
        if code:
            raise RuntimeError(runtime.safe_error(JOB, phase))
        queue.finish(TARGET, current)
        record('completed', score=runtime.read(JOB / 'complete.json'))
    except Exception as exc:
        if archived and not (JOB / 'complete.json').is_file():
            runtime.save(JOB / 'failed.json', {'phase': phase, 'error': str(exc), 'epoch': time.time()})
        record('failed', error=str(exc))
        raise
    finally:
        if reserved:
            current = runtime.read(queue.PLAN)
            if current['max_active_cohorts'] == 2:
                runtime.save(queue.PLAN, dict(current, max_active_cohorts=3))
                state['supervisor_cap'] = 3
                runtime.save(RECEIPT, state)


if __name__ == '__main__':
    os.umask(0o077)
    with runtime.lease(JOB / 'repair.lock'):
        repair()
