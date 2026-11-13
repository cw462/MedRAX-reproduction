RUN='[REDACTED]'
REVISION='context_restore001'
CONTROLLER='r55_full848_controller.py'
FAILURES='failure_observation_r54.py'

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
    assert controller['pid'] == 1829720 and not controller['alive']
    assert runner['pid'] == 1829722 and not runner['alive']
    assert exit_code(job/'controller.exitcode') == exit_code(ds_job/'runner.exitcode') == exit_code(out/'generation.exitcode') == 1
    assert not (out/'complete.json').exists() and not (ds_job/'score.exitcode').exists()
    assert load(job/'controller.started.json')['recovery'] == 'context_read001'
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




def restore_context(manifest):
    case = 'chexbench_slake_0102'
    assert manifest['inputs'][217]['question_id'] == case
    target = out/'contexts'/(case+'.json')
    evidence = job/'history.context_read001'
    good = '1d9cc440f1f2dc88205a3a631040cb42f9c5f065b1591dec62b609afbd0c0104'
    bad = '5804d10f7cdb93a0a2f713ae1acf66b2a21e8e799b6876d830834930091f80d8'
    valid = (evidence/f'context.{case}.{good}.json').read_bytes()
    invalid = (evidence/f'context.{case}.{bad}.json').read_bytes()
    assert sha256(valid).hexdigest() == good and sha256(invalid).hexdigest() == bad
    assert len(valid) == len(invalid) and sum(a != b for a, b in zip(valid, invalid)) == 1
    assert (valid[3312287] ^ invalid[3312287]).bit_count() == 1
    context = json.loads(valid)
    assert (context['question_id'], context['ordinal'], context['window']) == (case, 218, 9)
    assert context['skill_snapshot'] == load(out/'windows/0009/read_snapshot.json')
    assert context['same_image_ids'] == load(out/'predictions'/ARMS['E']/(case+'.json'))['same_image_ids']
    original = evidence/f'context.{case}.original_inode.json'
    if not original.exists():
        assert sha256(target.read_bytes()).hexdigest() in (good, bad)
        pending = stage/'context.verified.pending.json'
        with pending.open('xb') as handle:
            handle.write(valid)
            handle.flush()
            os.fsync(handle.fileno())
        assert sha256(pending.read_bytes()).hexdigest() == good
        os.link(target, original)
        os.replace(pending, target)
    assert original.stat().st_ino != target.stat().st_ino
    assert sha256(target.read_bytes()).hexdigest() == good
    return {'question_id': case, 'ordinal': 218, 'window': 9,
            'original_inode': original.stat().st_ino, 'restored_inode': target.stat().st_ino,
            'restored_sha256': good, 'invalid_read_sha256': bad, 'differing_byte_offset': 3312287}


with (JOBS/'.launch.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if not history.is_dir():
        manifest, selection = boundary()
        assert 'JSONDecodeError' in (ds_job/'runner.stderr.log').read_text()
        assert (out/'failure_observations'/qid/'7.json').is_file()
        repair = restore_context(manifest)
        plan = load(root/'controller_plan.json')
        import run_r55_full848_production
        from online_memory_r49 import ReferenceVault

        def deny(*args, **kwargs):
            raise AssertionError('unexpected network or reference release')

        connect, connect_ex = socket.socket.connect, socket.socket.connect_ex
        socket.socket.connect = deny
        socket.socket.connect_ex = deny
        ReferenceVault.after_prediction = deny
        try:
            proof = run_r55_full848_production.run_dataset(
                code, out, Path(plan['data']['chexbench']), Path(plan['references']['chexbench']), 'E', 295)
        finally:
            socket.socket.connect, socket.socket.connect_ex = connect, connect_ex
        assert proof['first_new'] == qid and proof['model_requests'] == 0
        if not checked.exists():
            record(checked, dict(proof, context_repair=repair))

        def launch(plan):
            assert paused_owned(plan)
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

        value = launch(plan)
    else:
        assert load(job/'controller.started.json')['recovery'] == REVISION
        value = {'pid': int((job/'controller.pid').read_text()), **load(job/'controller.started.json')}
    print(json.dumps(value))
