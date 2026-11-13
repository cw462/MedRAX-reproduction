RUN='[REDACTED PRIVATE PATH]'
REVISION='vqarad_tool_skip001'
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
out = root/'generation/D/vqarad'
job = JOBS/'D'
ds_job = job/'vqarad'
code = root/'code/D'
exp = code/'experiments'
sys.path.insert(0, str(exp))

qid = 'vqarad_1141'
stage = root/('stage.D.'+REVISION)
history = job/('history.'+REVISION)
checked = job/(REVISION+'.verified.json')
services = out/'services'
main_calls = services/'calls/R49-AGENT'/qid


def boundary():
    for path, owner, expected in ((job/'controller.pid', root, 1808078), (ds_job/'runner.pid', out, 1823281)):
        process = owned(path, owner)
        assert process['pid'] == expected and not process['alive']
    assert load(job/'controller.started.json')['recovery'] == 'cache_path001'
    assert exit_code(job/'controller.exitcode') == exit_code(ds_job/'runner.exitcode') == exit_code(out/'generation.exitcode') == 1
    assert not (out/'complete.json').exists() and not (ds_job/'score.exitcode').exists()
    assert 'unknown_model_generation_stop_no_retry' in (ds_job/'runner.stderr.log').read_text()
    manifest = load(out/'manifest.json')
    assert manifest == load(root/'manifests/D/vqarad.json')
    ids = [item['question_id'] for item in manifest['inputs']]
    assert len(ids) == 116 and ids[69] == qid
    assert {p.stem for p in (out/'predictions'/ARMS['D']).glob('*.json')} == set(ids[:69])
    assert not any((out/name/(qid+'.json')).exists() for name in ('steps', 'feedback', 'prediction_events'))
    assert {p.name for p in main_calls.iterdir()} == {'1','2'}
    for attempt in main_calls.iterdir():
        assert (attempt/'response.json').is_file() and not load(attempt/'result.json')['error']
    failed = load(services/'tool_selections/R49-AGENT'/qid/'2.json')
    cache = services/'tool_cache'/failed['cache_key']
    assert failed['tool'] == 'maira2_grounded_report' and failed['status'] == 'failed'
    assert load(cache/'backend.exit.json') == {'returncode': -11}
    event, = load(cache/'artifacts/backend_events.json')
    assert event['kind'] == 'generate' and event['status'] == 'started_unknown'
    assert not (cache/'artifacts/output.json').exists()
    for name, count in (('chexbench',618), ('slake',114)):
        earlier = job/name
        assert not owned(earlier/'runner.pid', root/'generation/D'/name)['alive']
        assert exit_code(earlier/'runner.exitcode') == exit_code(earlier/'score.exitcode') == 0
        assert exit_code(root/'generation/D'/name/'generation.exitcode') == 0
        assert load(root/'generation/D'/name/'analysis/summary.json')['questions'] == count
    return manifest, failed


def verify(plan, manifest, failed):
    source = exp/FAILURES
    desired = (stage/FAILURES).read_bytes()
    backup = source.with_name(source.name+'.before_'+REVISION)
    if not backup.exists():
        previous = source.read_bytes()
        assert sha256(previous).hexdigest() == ORIGINAL_HASH
        with backup.open('xb') as handle:
            handle.write(previous)
        pending = stage/(FAILURES+'.pending')
        with pending.open('xb') as handle:
            handle.write(desired)
        os.replace(pending, source)
    assert source.read_bytes() == desired and sha256(backup.read_bytes()).hexdigest() == ORIGINAL_HASH

    def deny(*args, **kwargs):
        raise AssertionError('unexpected network, subprocess or reference release')

    from online_memory_r49 import ReferenceVault
    from run_r55_full848_production import run_dataset
    from skill_services_r55 import Services

    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    subprocess.Popen = deny
    ReferenceVault.after_prediction = deny
    data = Path(plan['data']['vqarad'])
    prefix = run_dataset(code, out, data, Path(plan['references']['vqarad']), 'D', 69)
    assert prefix['first_new'] == qid and prefix['model_requests'] == 0

    context = load(out/'contexts'/(qid+'.json'))
    service = Services(manifest['config'], manifest['protocol'], manifest['runtime'], services,
                       'offline-verification', manifest['embedding_model'], manifest['embedding_base_url'])
    service.set_candidates(context['selected_skills'])
    original = service.call
    visited = []

    class BeforeSend(Exception):
        pass

    def check_call(row, arm, ordinal, messages):
        assert row['question_id'] == qid and arm == 'R49-AGENT'
        visited.append(ordinal)
        if ordinal == 3:
            raise BeforeSend
        assert (main_calls/str(ordinal)/'response.json').is_file()
        return original(row, arm, ordinal, messages)

    service.call = check_call
    try:
        service.execute(manifest['inputs'][69], 'r49_unbounded', data, context['same_image_context'] or None)
    except BeforeSend:
        assert visited == [1,2,3]
    else:
        raise AssertionError('expected boundary before request 3')
    evidence = load(out/'failure_observations'/qid/'2.json')
    assert evidence['raw_selection'] == failed and not evidence['backend_regenerated']
    boundary()
    result = dict(prefix, question_id=qid, tool='maira2_grounded_report', tool_ordinal=2,
                  backend_exit=-11, replayed_main_replies=2, next_main_ordinal=3)
    record(checked, result)
    return result


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
    dispatch, gpus = launch_cards(plan, ('D',))
    if 'D' not in dispatch:
        return {'waiting': 'gpu1', 'gpu_resources': gpus}
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
    admission = {'arm': 'D', 'gpu': '1', 'started_epoch': time.time(), 'recovery': REVISION,
                 'preserved_predictions': 69, 'next_question_id': qid, 'skipped_tool_ordinal': 2,
                 'gpu_at_admission': dispatch['D'], 'disk_free_bytes': available,
                 'estimated_required_bytes': needed}
    record(job/'controller.started.json', admission)
    command = shlex.join([sys.executable, '-B', '-u', str(controller), 'resume-vqarad', '--arm', 'D', '--resume-history', history.name])
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
        manifest, failed = boundary()
        plan = load(root/'controller_plan.json')
        value = (load(checked) if checked.exists() else verify(plan, manifest, failed)) if phase == 'verify' else launch(plan)
    print(json.dumps(value))
