"""Admit, run, and observe the two full-cohort R55 arms."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import time

from run_r55_full848_dataset import ARMS, COUNTS


ROOT = Path(__file__).resolve().parent
JOBS = ROOT/'jobs'
MIB = 1024**2
GPU = {'D': '1', 'E': '0'}
MIN_GPU_FREE_MIB = 18432
MIN_DISK_RESERVE = 512*MIB


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def record(path, value):
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle)
        handle.write('\n')


def exit_code(path):
    return int(path.read_text()) if path.is_file() else None


def owned(pidfile, expected):
    if not pidfile.is_file():
        return None
    pid = int(pidfile.read_text())
    proc = Path('/proc')/str(pid)
    try:
        stat = (proc/'stat').read_text().rsplit(') ', 1)[1].split()
        matches = str(expected).encode() in (proc/'cmdline').read_bytes()
        return {'pid': pid, 'alive': stat[0] != 'Z' and matches, 'state': stat[0],
                'start_ticks': int(stat[19])}
    except FileNotFoundError:
        return {'pid': pid, 'alive': False}


def predecessor_ready(plan):
    for item in plan['after_cohorts'].values():
        root = Path(item['run'])
        queue = owned(root/'queue.pid', root)
        if queue is None or queue['alive'] or exit_code(root/'queue.exitcode') != 0:
            return False
        if load(root/'queue.completed.json') != dict.fromkeys(item['arms'], 0):
            return False
        for arm in item['arms']:
            folder = root/arm
            process = owned(folder/'pid', root)
            if process is None or process['alive'] or exit_code(folder/'exitcode') != 0:
                return False
            if load(folder/'memory.completed.json')['questions'] != 60:
                return False
            if sum(1 for _ in (folder/'generation/predictions'/('R55-'+arm)).glob('*.json')) != 60:
                return False
    return True


def paused_owned(plan):
    paused = Path(plan['EvolveR']['policy_run'])
    pause = load(paused/'jobs/user_pause_before_full293_continue.json')
    process = owned(paused/'jobs/runner.pid', paused)
    return (process is not None and process['alive'] and process['state'] == 'T'
            and process['pid'] == pause['runner_pid'] and process['start_ticks'] == pause['runner_start_ticks'])


def gpu_resources(plan):
    cards = subprocess.check_output(
        ['nvidia-smi', '--query-gpu=index,uuid,memory.free', '--format=csv,noheader,nounits'],
        text=True, timeout=10)
    apps = subprocess.check_output(
        ['nvidia-smi', '--query-compute-apps=gpu_uuid,pid', '--format=csv,noheader,nounits'],
        text=True, timeout=10)
    pids_by_uuid = {}
    for line in apps.splitlines():
        uuid, pid = (part.strip() for part in line.split(',', 1))
        pids_by_uuid.setdefault(uuid, []).append(int(pid))
    resources = {}
    for line in cards.splitlines():
        index, uuid, mib = (part.strip() for part in line.split(','))
        if uuid == plan['gpu_uuids'].get(index):
            resources[index] = {'free_mib': int(mib), 'compute_pids': sorted(pids_by_uuid.get(uuid, []))}
    return resources


def free_cards(plan):
    return {index: gpu['free_mib'] if not gpu['compute_pids'] else 0
            for index, gpu in gpu_resources(plan).items()}


def launch_cards(plan, arms):
    resources = gpu_resources(plan)
    admissible = {}
    for arm in arms:
        index = GPU[arm]
        gpu = resources.get(index)
        if gpu is not None and (arm == 'E' or not gpu['compute_pids']):
            admissible[arm] = gpu
    return {arm: gpu for arm, gpu in admissible.items() if gpu['free_mib'] >= MIN_GPU_FREE_MIB}, resources


def allocated(path):
    if not path.exists():
        return 0
    result = subprocess.check_output(['du', '-s', '-B1', str(path)], text=True, timeout=30)
    return int(result.split()[0])


def launch(plan):
    JOBS.mkdir(exist_ok=True)
    with (JOBS/'.launch.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        arms = [arm for arm in GPU if not (JOBS/arm/'controller.started.json').exists()]
        if not arms:
            return {'waiting': None, 'launched': {}}
        if not predecessor_ready(plan):
            return {'waiting': 'predecessor_native_completion', 'launched': {}}
        assert paused_owned(plan), 'original_OpenI293_pause_ownership_changed'
        dispatch, resources = launch_cards(plan, arms)
        if not dispatch:
            return {'waiting': 'gpu', 'launched': {}, 'gpu_resources': resources,
                    'min_gpu_free_mib': MIN_GPU_FREE_MIB}
        source = Path(plan['D']['source_run'])/plan['D']['source_generation']
        clone_bytes = allocated(source)
        disk_plan = plan['observed_disk']
        bytes_for = {'D': round(disk_plan['D_observed_raw_bytes']*550/298)+clone_bytes,
                     'E': round(disk_plan['E_observed_raw_bytes']*848/60)}
        required = MIN_DISK_RESERVE + sum(
            max(0, bytes_for[arm]-allocated(ROOT/'generation'/arm)) for arm in GPU
            if exit_code(JOBS/arm/'controller.exitcode') != 0)
        disk_free = shutil.disk_usage(ROOT).free
        if disk_free < required:
            return {'waiting': 'disk', 'launched': {}, 'disk_free_bytes': disk_free, 'required_bytes': required}
        # Disk inventory can take time. Use a fresh GPU snapshot for dispatch.
        dispatch, resources = launch_cards(plan, arms)
        if not dispatch:
            return {'waiting': 'gpu', 'launched': {}, 'gpu_resources': resources,
                    'min_gpu_free_mib': MIN_GPU_FREE_MIB}
        keys = sys.stdin.buffer.read().splitlines()
        assert len(keys) == 3 and all(keys)
        result = {}
        for arm, gpu in dispatch.items():
            job = JOBS/arm
            job.mkdir(exist_ok=True)
            admission = {'arm': arm, 'gpu': GPU[arm], 'started_epoch': time.time(),
                         'disk_free_bytes': disk_free, 'estimated_required_bytes': required,
                         'allows_gpu_sharing': arm == 'E', 'gpu_at_admission': gpu}
            record(job/'controller.started.json', admission)
            command = shlex.join([sys.executable, '-B', '-u', str(Path(__file__).resolve()), 'run', '--arm', arm])
            codefile = shlex.quote(str(job/'controller.exitcode'))
            command += '; rc=$?; printf "%s\\n" "$rc" > '+codefile+'; exit "$rc"'
            with (job/'controller.stdout.log').open('xb') as stdout, (job/'controller.stderr.log').open('xb') as stderr:
                controller = subprocess.Popen(['bash', '-c', command], start_new_session=True,
                                              stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, cwd=ROOT)
                (job/'controller.pid').write_text(str(controller.pid))
                controller.stdin.write(b'\n'.join(keys)+b'\n')
                controller.stdin.close()
            result[arm] = {'pid': controller.pid, **admission}
        return {'waiting': 'gpu' if set(dispatch) != set(arms) else None, 'launched': result}


def prepare_dataset(arm, dataset, out, source):
    manifest_path = ROOT/'manifests'/arm/(dataset+'.json')
    if arm == 'D' and dataset == 'chexbench':
        excluded = {'.online.lock', 'manifest.json', 'analysis', 'complete.json', 'final_repo.json',
                    'generation.exitcode', 'generation.recovery001.exitcode'}
        shutil.copytree(source, out, ignore=lambda path, _: excluded if Path(path) == source else ())
        ids = [row['question_id'] for row in load(manifest_path)['inputs']]
        saved = {path.stem for path in (out/'predictions'/ARMS['D']).glob('*.json')}
        assert saved == set(ids[:298]) and not (out/'services').is_symlink()
    else:
        out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(manifest_path, out/'manifest.json')


def run_arm(plan, arm, *, resume_history=None, resume_dataset='chexbench'):
    job = JOBS/arm
    keys = sys.stdin.buffer.read().splitlines()
    assert len(keys) == 3 and all(keys)
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=GPU[arm], PYTHONDONTWRITEBYTECODE='1',
               LANGCHAIN_TRACING_V2='false', LANGSMITH_TRACING='false')
    if arm == 'E':
        writer = load(ROOT/'manifests/E/chexbench.json')['writer']
        env.update(R49_EMBEDDING_API_KEY=keys[1].decode())
        env[writer['api_key_env']] = keys[2].decode()
    source = Path(plan['D']['source_run'])/plan['D']['source_generation']
    code = ROOT/'code'/arm
    scores = {}
    reached_resume = resume_history is None
    for dataset, count in COUNTS.items():
        out = ROOT/'generation'/arm/dataset
        ds_job = job/dataset
        manifest_path = ROOT/'manifests'/arm/(dataset+'.json')
        resume = resume_history is not None and dataset == resume_dataset
        reached_resume = reached_resume or resume
        if not reached_resume:
            assert not owned(ds_job/'runner.pid', out)['alive']
            assert all(exit_code(path) == 0 for path in
                       (ds_job/'runner.exitcode', out/'generation.exitcode', ds_job/'score.exitcode'))
            assert load(out/'manifest.json') == load(manifest_path)
            assert load(out/'complete.json')['questions'] == count
            result = load(out/'analysis/summary.json')
            assert result['questions'] == count and result['arm'] == ARMS[arm]
            scores[dataset] = {k: result[k] for k in ('questions', 'correct', 'accuracy_pct')}
            continue
        if resume:
            assert load(out/'manifest.json') == load(manifest_path)
        else:
            prepare_dataset(arm, dataset, out, source)
        ds_job.mkdir()
        command = [sys.executable, '-B', '-u', str(ROOT/'run_r55_full848_production.py'),
                   '--arm', arm, '--code', str(code), '--out', str(out), '--data', plan['data'][dataset],
                   '--references', plan['references'][dataset]]
        start = time.time()
        with (ds_job/'runner.stdout.log').open('xb') as stdout, (ds_job/'runner.stderr.log').open('xb') as stderr:
            runner = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, env=env, cwd=code)
            (ds_job/'runner.pid').write_text(str(runner.pid))
            runner.communicate(keys[0]+b'\n')
        (ds_job/'runner.exitcode').write_text(str(runner.returncode))
        (out/'generation.exitcode').write_text(str(runner.returncode))
        duration = time.time()-start
        runtime = {'generation_wall_seconds': duration}
        if resume:
            prior = load(job/resume_history/dataset/'runtime.json')['generation_wall_seconds']
            runtime.update(generation_wall_seconds=prior+duration, original_generation_wall_seconds=prior,
                           resumed_generation_wall_seconds=duration)
        record(ds_job/'runtime.json', runtime)
        if runner.returncode:
            return runner.returncode
        done = load(out/'complete.json')
        assert done['arm'] == ARMS[arm] and done['questions'] == count
        score_file = 'score_r55_full848_dataset_e_slake_main_retry001.py' if arm == 'E' and dataset == 'slake' else 'score_r55_full848_dataset.py'
        score_command = [sys.executable, '-B', '-u', str(ROOT/score_file),
                         '--code', str(code), '--run', str(out)]
        with (ds_job/'score.stdout.log').open('xb') as stdout, (ds_job/'score.stderr.log').open('xb') as stderr:
            score = subprocess.run(score_command, stdout=stdout, stderr=stderr, cwd=code)
        (ds_job/'score.exitcode').write_text(str(score.returncode))
        if score.returncode:
            return score.returncode
        result = load(out/'analysis/summary.json')
        assert result['questions'] == count
        scores[dataset] = {k: result[k] for k in ('questions', 'correct', 'accuracy_pct')}
    correct = sum(result['correct'] for result in scores.values())
    record(job/'controller.completed.json', {'arm': arm, 'questions': 848, 'correct': correct,
                                             'accuracy_pct': 100*correct/848, 'datasets': scores})
    return 0


def status():
    result = {'arms': {}, 'disk_free_mib': shutil.disk_usage(ROOT).free//MIB}
    try:
        result['gpu0'] = gpu_resources(load(ROOT/'controller_plan.json')).get(GPU['E'])
    except (OSError, subprocess.SubprocessError, ValueError):
        result['gpu0'] = None
    for arm in GPU:
        job = JOBS/arm
        if not (job/'controller.started.json').is_file():
            result['arms'][arm] = {'state': 'waiting', 'gpu': GPU[arm]}
            continue
        controller = owned(job/'controller.pid', ROOT)
        terminal = exit_code(job/'controller.exitcode')
        value = {'gpu': GPU[arm], 'controller': controller, 'exit_code': terminal, 'datasets': {}}
        for dataset, count in COUNTS.items():
            ds_job = job/dataset
            out = ROOT/'generation'/arm/dataset
            item = {'expected': count, 'saved': sum(1 for _ in (out/'predictions'/ARMS[arm]).glob('*.json')),
                    'runner': owned(ds_job/'runner.pid', out), 'runner_exit': exit_code(ds_job/'runner.exitcode'),
                    'generation_exit': exit_code(out/'generation.exitcode'),
                    'score_exit': exit_code(ds_job/'score.exitcode')}
            if item['score_exit'] == 0:
                summary = load(out/'analysis/summary.json')
                item['score'] = {k: summary[k] for k in ('questions', 'correct', 'accuracy_pct')}
            value['datasets'][dataset] = item
        if terminal == 0:
            value['summary'] = load(job/'controller.completed.json')
        elif terminal is not None:
            tails = [job/'controller.stderr.log']
            for dataset, item in value['datasets'].items():
                if item['runner_exit'] not in (0, None):
                    tails.append(job/dataset/'runner.stderr.log')
                if item['score_exit'] not in (0, None):
                    tails.append(job/dataset/'score.stderr.log')
            value['failure_tails'] = {str(path.relative_to(job)): path.read_text(errors='replace')[-2600:]
                                      for path in tails if path.is_file()}
        result['arms'][arm] = value
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('check', 'launch', 'run', 'resume-chexbench', 'resume-vqarad', 'status'))
    parser.add_argument('--arm', choices=tuple(GPU))
    parser.add_argument('--resume-history', choices=('history.cache_path001', 'history.verify_retry001',
                                                      'history.local_tool_skip001', 'history.context_read001',
                                                      'history.context_restore001', 'history.vqarad_tool_skip001'))
    args = parser.parse_args()
    plan = load(ROOT/'controller_plan.json')
    if args.phase == 'run':
        raise SystemExit(run_arm(plan, args.arm))
    if args.phase == 'resume-chexbench':
        history = args.resume_history or {'D': 'history.cache_path001', 'E': 'history.verify_retry001'}[args.arm]
        assert (JOBS/args.arm/history).is_dir()
        raise SystemExit(run_arm(plan, args.arm, resume_history=history))
    if args.phase == 'resume-vqarad':
        assert args.arm == 'D' and args.resume_history == 'history.vqarad_tool_skip001'
        assert (JOBS/args.arm/args.resume_history/'vqarad').is_dir()
        raise SystemExit(run_arm(plan, args.arm, resume_history=args.resume_history, resume_dataset='vqarad'))
    if args.phase == 'check':
        print(json.dumps({'predecessors_complete': predecessor_ready(plan), 'paused_original_owned': paused_owned(plan),
                          'status': status()}))
    elif args.phase == 'launch':
        print(json.dumps(launch(plan)))
    else:
        print(json.dumps(status()))
