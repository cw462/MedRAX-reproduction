RUN='[REDACTED]'
REVISION='local_tool_skip001'
CONTROLLER='r55_full848_controller.py'
FAILURES='failure_observation_r54.py'
ORIGINAL_HASH='588a62cd940b1e42565e17324d2b94c7080e6e4ee6500aa2d7faf1dc0b85da13'

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

from r55_full848_controller import (
    ARMS, JOBS, MIN_DISK_RESERVE, allocated, exit_code, launch_cards, load, owned, paused_owned, record,
)

root = Path(RUN)
out = root/'generation/E/chexbench'
job = JOBS/'E'
ds_job = job/'chexbench'
code = root/'code/E'
exp = code/'experiments'
sys.path.insert(0, str(exp))

qid = 'chexbench_openi_0057'
services = out/'services'
history = job/('history.'+REVISION)
checked = job/(REVISION+'.verified.json')
stage = root/('stage.E.'+REVISION)


def boundary():
    controller = owned(job/'controller.pid', root)
    runner = owned(ds_job/'runner.pid', out)
    assert controller['pid'] == 1814176 and not controller['alive']
    assert runner['pid'] == 1814178 and not runner['alive']
    assert exit_code(job/'controller.exitcode') == exit_code(ds_job/'runner.exitcode') == exit_code(out/'generation.exitcode') == 1
    assert not (out/'complete.json').exists() and not (ds_job/'score.exitcode').exists()
    assert load(job/'controller.started.json')['recovery'] == 'verify_retry001'
    manifest = load(out/'manifest.json')
    assert manifest == load(root/'manifests/E/chexbench.json')
    ids = [row['question_id'] for row in manifest['inputs']]
    assert ids[295] == qid
    assert {p.stem for p in (out/'predictions'/ARMS['E']).glob('*.json')} == set(ids[:295])
    assert not any((out/folder/(qid+'.json')).exists() for folder in ('steps','feedback','prediction_events'))
    selection = load(services/'tool_selections/R49-AGENT'/qid/'7.json')
    assert selection['tool'] == 'llava_rad' and selection['status'] == 'failed'
    cache = services/'tool_cache'/selection['cache_key']
    assert load(cache/'backend.exit.json') == {'returncode': -11}
    event, = load(cache/'artifacts/backend_events.json')
    assert event['kind'] == 'generate' and event['status'] == 'started_unknown'
    assert not (cache/'artifacts/output.json').exists()
    main = services/'calls/R49-AGENT'/qid
    assert {p.name for p in main.iterdir()} == {str(n) for n in range(1, 8)}
    for attempt in main.iterdir():
        assert (attempt/'response.json').is_file() and not load(attempt/'result.json')['error']
    return manifest, selection


def verify(plan, manifest, selection):
    target = exp/FAILURES
    backup = target.with_name(target.name+'.before_'+REVISION)
    desired = (stage/FAILURES).read_bytes()
    assert sha256(target.read_bytes()).hexdigest() == ORIGINAL_HASH
    with backup.open('xb') as handle:
        handle.write(target.read_bytes())
    pending = target.with_name(target.name+'.'+REVISION+'.pending')
    with pending.open('xb') as handle:
        handle.write(desired)
    os.replace(pending, target)

    def deny(*args, **kwargs):
        raise AssertionError('unexpected network, worker, or reference release in offline replay')

    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    from online_memory_r49 import ReferenceVault
    ReferenceVault.after_prediction = deny
    from run_r55_full848_production import run_dataset
    from skill_services_evolver_shared import Services
    subprocess.Popen = deny

    data = Path(plan['data']['chexbench'])
    prefix = run_dataset(code, out, data, Path(plan['references']['chexbench']), 'E', 295)
    assert prefix['first_new'] == qid and prefix['model_requests'] == 0
    context = load(out/'contexts'/(qid+'.json'))
    service = Services(manifest['config'], manifest['protocol'], manifest['runtime'], services,
                       'offline-verification', manifest['embedding_model'], manifest['embedding_base_url'],
                       writer=manifest['writer'])
    service.experience_snapshot = context['skill_snapshot']
    original = service.call
    visited = []

    class BeforeSend(Exception):
        pass

    def inspect(row, arm, ordinal, messages):
        if arm == 'R49-AGENT':
            assert row['question_id'] == qid
            visited.append(ordinal)
            if ordinal == 8:
                raise BeforeSend
        assert (services/'calls'/arm/row['question_id']/str(ordinal)/'response.json').is_file()
        return original(row, arm, ordinal, messages)

    service.call = inspect
    try:
        service.execute(manifest['inputs'][295], 'r49_unbounded', data, context['same_image_context'] or None)
    except BeforeSend:
        pass
    else:
        raise AssertionError('next main model request boundary was not reached')
    assert visited == list(range(1, 9))
    evidence = load(out/'failure_observations'/qid/'7.json')
    assert evidence['raw_selection'] == selection and not evidence['backend_regenerated']
    boundary()
    value = {'question_id': qid, 'ordinal': 296, 'preserved_predictions': 295,
             'local_tool': 'llava_rad', 'tool_ordinal': 7, 'backend_exit': -11,
             'replayed_main_replies': 7, 'next_main_ordinal': 8, 'new_model_calls': 0}
    record(checked, value)
    return value


def launch(plan):
    assert paused_owned(plan) and load(checked)['question_id'] == qid
    assert (exp/FAILURES).read_bytes() == (stage/FAILURES).read_bytes()
    estimates = plan['observed_disk']
    needed = MIN_DISK_RESERVE + max(0, round(estimates['E_observed_raw_bytes']*848/60)
                                    - allocated(root/'generation/E'))
    if exit_code(JOBS/'D/controller.exitcode') != 0:
        original = Path(plan['D']['source_run'])/plan['D']['source_generation']
        d_total = round(estimates['D_observed_raw_bytes']*550/298)+allocated(original)
        needed += max(0, d_total-allocated(root/'generation/D'))
    available = shutil.disk_usage(root).free
    if available < needed:
        return {'waiting': 'disk', 'free_bytes': available, 'required_bytes': needed}
    dispatch, gpus = launch_cards(plan, ('E',))
    if 'E' not in dispatch:
        return {'waiting': 'gpu0', 'gpu_resources': gpus}
    keys = sys.stdin.buffer.read().splitlines()
    assert len(keys) == 3 and all(keys)
    controller = root/CONTROLLER
    replacement = (stage/CONTROLLER).read_bytes()
    compile(replacement, str(controller), 'exec')
    history.mkdir()
    for suffix in ('pid', 'exitcode', 'started.json', 'stderr.log', 'stdout.log'):
        path = job/('controller.'+suffix)
        path.rename(history/path.name)
    ds_job.rename(history/ds_job.name)
    (out/'generation.exitcode').rename(history/'generation.exitcode')
    shutil.copyfile(controller, history/CONTROLLER)
    staged_controller = stage/(CONTROLLER+'.launch')
    with staged_controller.open('xb') as handle:
        handle.write(replacement)
    os.replace(staged_controller, controller)
    admission = {'arm': 'E', 'gpu': '0', 'started_epoch': time.time(), 'recovery': REVISION,
                 'preserved_predictions': 295, 'next_question_id': qid, 'skipped_tool_ordinal': 7,
                 'gpu_at_admission': dispatch['E'], 'disk_free_bytes': available,
                 'estimated_required_bytes': needed}
    record(job/'controller.started.json', admission)
    command = shlex.join([sys.executable, '-B', '-u', str(controller), 'resume-chexbench', '--arm', 'E', '--resume-history', history.name])
    codefile = shlex.quote(str(job/'controller.exitcode'))
    command += '; rc=$?; printf "%s\\n" "$rc" > '+codefile+'; exit "$rc"'
    with (job/'controller.stdout.log').open('xb') as stdout, (job/'controller.stderr.log').open('xb') as stderr:
        process = subprocess.Popen(['bash', '-c', command], cwd=root, start_new_session=True,
                                   stdin=subprocess.PIPE, stdout=stdout, stderr=stderr)
        (job/'controller.pid').write_text(str(process.pid))
        process.stdin.write(b'\n'.join(keys)+b'\n')
        process.stdin.close()
    return {'pid': process.pid, **admission}

with (JOBS/'.launch.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    phase = sys.argv[1]
    if phase == 'launch' and history.is_dir():
        assert load(job/'controller.started.json')['recovery'] == REVISION
        value = {'pid': int((job/'controller.pid').read_text()), **load(job/'controller.started.json')}
    else:
        manifest, selection = boundary()
        plan = load(root/'controller_plan.json')
        value = verify(plan, manifest, selection) if phase == 'verify' else launch(plan)
    print(json.dumps(value))
