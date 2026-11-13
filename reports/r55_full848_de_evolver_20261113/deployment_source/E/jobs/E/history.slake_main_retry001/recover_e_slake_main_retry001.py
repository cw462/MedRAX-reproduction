RUN='[REDACTED PRIVATE PATH]'
REVISION='slake_main_retry001'
EXPERIMENTS=('cxr_online_primitives_r49.py', 'report_skill_r54.py', 'run_online_evolver_shared.py', 'skill_services_evolver_shared.py')
CONTROLLER='r55_full848_controller.py'
CONTROLLER_COPY='r55_full848_controller_e_slake_main_retry001.py'
SCORE='score_r55_full848_dataset.py'
SCORER='score_r55_full848_dataset_e_slake_main_retry001.py'
DRIVER_NAME='recover_e_slake_main_retry001.py'
MODULE='r55_full848_e_slake_main_recovery.py'
ORIGINAL_HASHES={'cxr_online_primitives_r49.py': '14b04e31c6ae54d01addec1885d12b7282abf64a21ee08cda96c42ce77d35ac3', 'report_skill_r54.py': 'f9ff9c97b07e45f3ca98e8ab7a20e7204e45601bbc24bd1eb61fc800c8ea0ac3', 'run_online_evolver_shared.py': '911be1e0d1688f5d5951b2af843bf5b8261da189ff6276f32baa58e7bd27ccc3', 'skill_services_evolver_shared.py': '70376ce2ac13ab5f809089e46ca77c09b7da23cd909cabbec61a73c340ce578c'}

import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import sys
import time

from r55_full848_controller import ARMS, JOBS, MIN_DISK_RESERVE, allocated, exit_code, launch_cards, load, owned, paused_owned, record

root = Path(RUN)
out = root/'generation/E/slake'
services = out/'services'
job = JOBS/'E'
ds_job = job/'slake'
code = root/'code/E'
exp = code/'experiments'
stage = root/('stage.E.'+REVISION)
history_job = job/('history.'+REVISION)
checked = job/(REVISION+'.verified.json')
sys.path.insert(0, str(stage))
sys.path.insert(1, str(exp))
from r55_full848_e_slake_main_recovery import ORIGINAL_SHA, QID, TARGET, history, validate_attempt, validate_payload


def boundary():
    for path, owner, pid in ((job/'controller.pid', root, 1831304), (ds_job/'runner.pid', out, 1899906)):
        state = owned(path, owner)
        assert state['pid'] == pid and not state['alive']
    assert exit_code(job/'controller.exitcode') == exit_code(ds_job/'runner.exitcode') == exit_code(out/'generation.exitcode') == 1
    assert not (out/'complete.json').exists() and not (ds_job/'score.exitcode').exists()
    assert not (root/'generation/E/vqarad').exists() and not (job/'vqarad').exists()
    assert not (history(services)/'1').exists()
    manifest = load(out/'manifest.json')
    assert manifest == load(root/'manifests/E/slake.json')
    ids = [row['question_id'] for row in manifest['inputs']]
    assert len(ids) == 114 and ids[69] == QID
    assert {p.stem for p in (out/'predictions'/ARMS['E']).glob('*.json')} == set(ids[:69])
    assert (out/'contexts'/(QID+'.json')).is_file()
    assert not any((out/name/(QID+'.json')).exists() for name in ('steps', 'feedback', 'prediction_events'))
    calls = (services/TARGET).parent
    assert {p.name for p in calls.iterdir()} == {'1', '2'}
    assert (calls/'1/response.json').is_file() and not load(calls/'1/result.json')['error']
    original, _ = validate_attempt(calls/'2', first=True)
    selection = load(services/'tool_selections/R49-AGENT'/QID/'1.json')
    assert selection['tool'] == 'maira2_grounded_report' and selection['status'] == 'completed'
    chex = root/'generation/E/chexbench'
    assert not owned(job/'chexbench/runner.pid', chex)['alive']
    assert all(exit_code(p) == 0 for p in (job/'chexbench/runner.exitcode', job/'chexbench/score.exitcode', chex/'generation.exitcode'))
    assert load(chex/'analysis/summary.json')['questions'] == 618
    return manifest, original


def verify(plan, manifest, original):
    def deny(*args, **kwargs):
        raise AssertionError('unexpected external request, subprocess or new feedback in replay')

    class BeforeSend(Exception):
        pass

    from online_memory_r49 import ReferenceVault
    from run_r55_full848_production import run_dataset
    from skill_services_evolver_shared import Services
    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    subprocess.Popen = deny
    ReferenceVault.after_prediction = deny
    os.environ['R55_SLAKE_RETRY_OFFLINE'] = '1'
    data = Path(plan['data']['slake'])
    proof = run_dataset(code, out, data, Path(plan['references']['slake']), 'E', 69)
    assert proof['first_new'] == QID and proof['model_requests'] == 0
    context = load(out/'contexts'/(QID+'.json'))
    service = Services(manifest['config'], manifest['protocol'], manifest['runtime'], services,
                       'offline-verification', manifest['embedding_model'], manifest['embedding_base_url'],
                       writer=manifest['writer'])
    service.experience_snapshot = context['skill_snapshot']
    prior = service.call
    visited = []

    def check_call(row, role, ordinal, messages):
        assert row['question_id'] == QID and role == 'R49-AGENT'
        visited.append(ordinal)
        if ordinal == 2:
            validate_payload(service, messages, original)
            raise BeforeSend
        assert (services/'calls'/role/QID/str(ordinal)/'response.json').is_file()
        return prior(row, role, ordinal, messages)

    service.call = check_call
    try:
        service.execute(manifest['inputs'][69], 'r49_unbounded', data, context['same_image_context'] or None)
    except BeforeSend:
        assert visited == [1, 2]
    else:
        raise AssertionError('retry boundary not reached')
    boundary()
    value = dict(proof, question_id=QID, ordinal=70, saved_tool_reused=True,
                 replayed_main_replies=1, retry_main_ordinal=2, request_sha256=ORIGINAL_SHA)
    record(checked, value)
    return value


def install_sources():
    files = {**{name: exp/name for name in EXPERIMENTS}, MODULE: exp/MODULE,
             SCORER: root/SCORER, CONTROLLER_COPY: root/CONTROLLER_COPY}
    for name, target in files.items():
        raw = (stage/name).read_bytes()
        if target.exists() and target.read_bytes() == raw:
            continue
        if name in EXPERIMENTS:
            original = target.read_bytes()
            assert sha256(original).hexdigest() == ORIGINAL_HASHES[name]
            with target.with_name(name+'.before_'+REVISION).open('xb') as backup:
                backup.write(original)
            pending = target.with_name(name+'.'+REVISION+'.pending')
            with pending.open('xb') as handle:
                handle.write(raw)
            os.replace(pending, target)
        else:
            with target.open('xb') as handle:
                handle.write(raw)


def launch(plan):
    proof = load(checked)
    assert proof['request_sha256'] == ORIGINAL_SHA and proof['model_requests'] == 0 and paused_owned(plan)
    estimated = round(plan['observed_disk']['E_observed_raw_bytes']*848/60)
    required = MIN_DISK_RESERVE + max(0, estimated-allocated(root/'generation/E'))
    available = shutil.disk_usage(root).free
    if available < required:
        return {'waiting': 'disk', 'free_bytes': available, 'required_bytes': required}
    dispatch, resources = launch_cards(plan, ('E',))
    if 'E' not in dispatch:
        return {'waiting': 'gpu0', 'gpu_resources': resources}
    keys = sys.stdin.buffer.read().splitlines()
    assert len(keys) == 3 and all(keys)
    install_sources()
    history_job.mkdir()
    lineage = history(services)
    lineage.mkdir(parents=True, exist_ok=False)
    (services/TARGET).rename(lineage/'1')
    validate_attempt(lineage/'1', first=True)
    record(lineage/'plan.json', {'revision': REVISION, 'question_id': QID, 'logical_ordinal': 2,
           'first_attempt': str((lineage/'1').relative_to(services)),
           'authorized_second_attempt': str(TARGET), 'max_attempts': 2, 'request_sha256': ORIGINAL_SHA})
    for suffix in ('pid', 'exitcode', 'started.json', 'stderr.log', 'stdout.log'):
        item = job/('controller.'+suffix)
        item.rename(history_job/item.name)
    ds_job.rename(history_job/ds_job.name)
    (out/'generation.exitcode').rename(history_job/'generation.exitcode')
    for name in (CONTROLLER, CONTROLLER_COPY, SCORE, SCORER, DRIVER_NAME):
        shutil.copyfile(root/name, history_job/name)
    admission = {'arm': 'E', 'gpu': '0', 'started_epoch': time.time(), 'recovery': REVISION,
                 'preserved_predictions': 69, 'next_question_id': QID, 'main_retry_ordinal': 2,
                 'gpu_at_admission': dispatch['E'], 'disk_free_bytes': available,
                 'estimated_required_bytes': required}
    record(job/'controller.started.json', admission)
    command = shlex.join([sys.executable, '-B', '-u', str(root/DRIVER_NAME), 'run'])
    exit_path = shlex.quote(str(job/'controller.exitcode'))
    command += '; rc=$?; printf "%s\\n" "$rc" > '+exit_path+'; exit "$rc"'
    with (job/'controller.stdout.log').open('xb') as stdout, (job/'controller.stderr.log').open('xb') as stderr:
        proc = subprocess.Popen(['bash', '-c', command], cwd=root, start_new_session=True,
                                stdin=subprocess.PIPE, stdout=stdout, stderr=stderr)
        (job/'controller.pid').write_text(str(proc.pid))
        proc.stdin.write(b'\n'.join(keys)+b'\n')
        proc.stdin.close()
    return {'pid': proc.pid, **admission}


phase = sys.argv[1]
plan = load(root/'controller_plan.json')
if phase == 'run':
    from r55_full848_controller_e_slake_main_retry001 import run_arm
    raise SystemExit(run_arm(plan, 'E', resume_history=history_job.name, resume_dataset='slake'))

with (JOBS/'.launch.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if phase == 'launch' and history_job.is_dir():
        admission = load(job/'controller.started.json')
        assert admission['recovery'] == REVISION
        value = {'pid': int((job/'controller.pid').read_text()), **admission}
    else:
        manifest, original = boundary()
        value = (load(checked) if checked.is_file() else verify(plan, manifest, original)) if phase == 'verify' else launch(plan)
    print(json.dumps(value))
