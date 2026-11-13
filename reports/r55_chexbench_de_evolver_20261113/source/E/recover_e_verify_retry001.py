RUN='[REDACTED]'
REVISION='verify_retry001'
MODULE='r55_full848_verify_recovery.py'
CONTROLLER='r55_full848_controller.py'
SERVICE='skill_services_r55.py'
PRIMITIVES='cxr_online_primitives_r49.py'
ORIGINAL_HASHES={'skill_services_r55.py': '2422421b81c1878178d945c0afb29d969407270ffec2846dd8054f3eff92d492', 'cxr_online_primitives_r49.py': 'bb6f3528babffcccc8531594d3a11290cf7fc397bdefb5f83849500b9f88c70c'}

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
qid = 'chexbench_openi_0012'
event = 'verify_'+qid+'_4'
services = out/'services'
verify_call = services/'calls/R55-VERIFY'/event
history = job/('history.'+REVISION)
checked = job/(REVISION+'.verified.json')
stage = root/('stage.E.'+REVISION)


def boundary():
    assert owned(job/'controller.pid', root) == {'pid': 1783539, 'alive': False} or (
        (job/'controller.pid').read_text().strip() == '1783539' and not owned(job/'controller.pid', root)['alive'])
    assert (ds_job/'runner.pid').read_text().strip() == '1783541'
    assert not owned(ds_job/'runner.pid', out)['alive']
    assert exit_code(job/'controller.exitcode') == exit_code(ds_job/'runner.exitcode') == 1
    assert exit_code(out/'generation.exitcode') == 1 and not (out/'complete.json').exists()
    assert not (ds_job/'score.exitcode').exists() and not history.exists()
    manifest = load(out/'manifest.json')
    assert manifest == load(root/'manifests/E/chexbench.json')
    ids = [row['question_id'] for row in manifest['inputs']]
    assert ids[250] == qid
    assert {path.stem for path in (out/'predictions'/ARMS['E']).glob('*.json')} == set(ids[:250])
    assert (out/'contexts'/(qid+'.json')).is_file()
    assert not any((out/folder/(qid+'.json')).exists() for folder in ('steps','prediction_events','feedback'))
    assert {path.name for path in verify_call.iterdir()} == {'1'}
    first = verify_call/'1'
    assert {path.name for path in first.iterdir()} == {'endpoint.json', 'request.json', 'started.json', 'result.json'}
    result = load(first/'result.json')
    assert (result['request_id'], result['error'], result['response_received']) == (
        'r55:R55-VERIFY:'+event+':1', 'HTTPError', False)
    return manifest


def install_experiment_sources():
    for name in (SERVICE, PRIMITIVES, MODULE):
        target = exp/name
        desired = (stage/name).read_bytes()
        compile(desired, str(target), 'exec')
        if target.is_file() and target.read_bytes() == desired:
            continue
        if name != MODULE:
            previous = target.read_bytes()
            assert sha256(previous).hexdigest() == ORIGINAL_HASHES[name]
            with (target.with_name(name+'.before_'+REVISION)).open('xb') as handle:
                handle.write(previous)
        pending = target.with_name(name+'.'+REVISION+'.pending')
        with pending.open('xb') as handle:
            handle.write(desired)
        os.replace(pending, target)


def verify(plan, manifest):
    install_experiment_sources()

    def deny(*args, **kwargs):
        raise AssertionError('unexpected send or reference release in offline replay')

    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    from online_memory_r49 import ReferenceVault
    ReferenceVault.after_prediction = deny
    from run_r55_full848_production import run_dataset
    from r55_full848_verify_recovery import RecoverableVerifier, ENDPOINT
    from skill_services_evolver_shared import Services

    data = Path(plan['data']['chexbench'])
    prefix = run_dataset(code, out, data, Path(plan['references']['chexbench']), 'E', 250)
    assert prefix['first_new'] == qid and prefix['model_requests'] == 0

    context = load(out/'contexts'/(qid+'.json'))
    service = Services(manifest['config'], manifest['protocol'], manifest['runtime'], services,
                       'offline-verification', manifest['embedding_model'], manifest['embedding_base_url'],
                       writer=manifest['writer'])
    service.experience_snapshot = context['skill_snapshot']
    original = RecoverableVerifier._attempt
    expected = load(verify_call/'1/request.json')

    class SendBoundary(Exception):
        pass

    def inspect(self, folder, payload):
        if folder.parent == verify_call:
            assert payload == expected and load(verify_call/'1/endpoint.json') == {'url': ENDPOINT}
            if folder.name == '2':
                assert not folder.exists()
                raise SendBoundary
        assert (folder/'response.json').is_file() or folder == verify_call/'1'
        return original(self, folder, payload)

    RecoverableVerifier._attempt = inspect
    try:
        service.execute(manifest['inputs'][250], 'r49_unbounded', data, context['same_image_context'] or None)
    except SendBoundary:
        pass
    else:
        raise AssertionError('retry boundary not reached')
    boundary()
    result = {'question_id': qid, 'ordinal': 251, 'preserved_predictions': 250,
              'verified_same_endpoint_and_payload': True, 'new_model_calls': 0,
              'retry_payload_sha256': sha256((verify_call/'1/request.json').read_bytes()).hexdigest()}
    record(checked, result)
    return result


def launch(plan):
    proof = load(checked)
    assert proof['question_id'] == qid and proof['new_model_calls'] == 0
    assert sha256((verify_call/'1/request.json').read_bytes()).hexdigest() == proof['retry_payload_sha256']
    assert paused_owned(plan)
    for name in (SERVICE, PRIMITIVES, MODULE):
        assert (exp/name).read_bytes() == (stage/name).read_bytes()
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
                 'preserved_predictions': 250, 'next_question_id': qid, 'retry_event': event,
                 'gpu_at_admission': dispatch['E'], 'disk_free_bytes': available,
                 'estimated_required_bytes': needed}
    record(job/'controller.started.json', admission)
    command = shlex.join([sys.executable, '-B', '-u', str(controller), 'resume-chexbench', '--arm', 'E'])
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
        print(json.dumps({'pid': int((job/'controller.pid').read_text()), **load(job/'controller.started.json')}))
    else:
        manifest = boundary()
        plan = load(root/'controller_plan.json')
        result = verify(plan, manifest) if phase == 'verify' else launch(plan)
        print(json.dumps(result))
