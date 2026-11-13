RUN='[REDACTED]'
CACHE_ROOTS=['[REDACTED]', '[REDACTED]']
CONTROLLER='r55_full848_controller.py'
CONTROLLER_REPLACEMENT='r55_full848_controller.py.cache_path001.staging'
OLD_CONTROLLER_HASH='ae5d3273706645f0147c5ae19cbc410ea3e8d795cfd6ce0c075875742df009a9'
OLD_TOOLSET_HASH='6113db9bd97b1beb6a0faae27295a4c9cbfdf01c86ffb36ba85b0ea5487202c0'

import base64
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
    ARMS, JOBS, MIN_DISK_RESERVE, MIN_GPU_FREE_MIB, allocated, exit_code, free_cards,
    load, owned, paused_owned, record,
)

root = Path(RUN)
out = root/'generation/D/chexbench'
services = out/'services'
job = JOBS/'D'
ds_job = job/'chexbench'
code = root/'code/D'
sys.path.insert(0, str(code/'experiments'))
from cxr_online_primitives_r49 import assert_closed_sends

known_caches = tuple(Path(path).resolve() for path in CACHE_ROOTS)
toolset = code/'experiments/toolsets_r54.py'
receipt = job/'cache_path001.verified.json'


def frozen_boundary():
    assert owned(job/'controller.pid', root)['alive'] is False
    assert owned(ds_job/'runner.pid', out)['alive'] is False
    assert exit_code(job/'controller.exitcode') == exit_code(ds_job/'runner.exitcode') == 1
    assert exit_code(out/'generation.exitcode') == 1 and not (out/'complete.json').exists()
    assert 'ValueError: tool_image_outside_artifacts' in (ds_job/'runner.stderr.log').read_text()
    manifest = load(out/'manifest.json')
    assert manifest == load(root/'manifests/D/chexbench.json')
    ids = [row['question_id'] for row in manifest['inputs']]
    assert {path.stem for path in (out/'predictions'/ARMS['D']).glob('*.json')} == set(ids[:525])
    qid = ids[525]
    assert qid == 'chexbench_openi_0287'
    assert (out/'contexts'/(qid+'.json')).is_file()
    assert not any((out/folder/(qid+'.json')).exists() for folder in ('steps','prediction_events','feedback'))
    assert_closed_sends(out, require_receipts=True)
    call = services/'calls/R49-AGENT'/qid
    assert {path.name for path in call.iterdir()} == {'1'}
    assert all((call/'1'/(name+'.json')).is_file() for name in ('started','request','response','result'))
    selections = services/'tool_selections/R49-AGENT'/qid
    assert {path.name for path in selections.iterdir()} == {'1.json'}
    observed = load(selections/'1.json')
    assert observed['tool'] == 'maira2_grounded_report' and observed['cache_hit']
    return manifest, qid, observed


def install_toolset():
    old = toolset.read_bytes()
    assert sha256(old).hexdigest() == OLD_TOOLSET_HASH
    source = old.decode()
    anchor = "            if not path.is_relative_to((out/'tool_cache').resolve()):raise ValueError('tool_image_outside_artifacts')"
    assert source.count(anchor) == 1
    replacement = """            cache = (out/'tool_cache').resolve()
            if not path.is_relative_to(cache):
                source_caches = tuple(Path(name) for name in """+repr(CACHE_ROOTS)+""")
                for source_cache in source_caches:
                    if path.is_relative_to(source_cache):
                        relative = path.relative_to(source_cache)
                        rebound = (cache/relative).resolve()
                        if (relative.parts[:2] != (observation.get('cache_key'), 'artifacts')
                                or not rebound.is_relative_to(cache) or not rebound.is_file()):
                            raise ValueError('tool_image_copy_not_bound_to_observation')
                        path = rebound
                        break
                else:
                    raise ValueError('tool_image_outside_artifacts')"""
    patched = source.replace(anchor, replacement)
    compile(patched, str(toolset), 'exec')
    backup = toolset.with_name(toolset.name+'.before_cache_path001')
    with backup.open('xb') as handle:
        handle.write(old)
    staging = toolset.with_name(toolset.name+'.cache_path001.staging')
    with staging.open('x', encoding='utf-8') as handle:
        handle.write(patched)
    os.replace(staging, toolset)


def verify():
    manifest, qid, observed = frozen_boundary()
    cache = services/'tool_cache'
    copied = {}
    for result in cache.glob('*/result.json'):
        for name in load(result).get('derived_images', []):
            source = Path(name).resolve()
            if source.is_relative_to(cache):
                continue
            source_cache, = [p for p in known_caches if source.is_relative_to(p)]
            rel = source.relative_to(source_cache)
            dest = (cache/rel).resolve()
            assert rel.parts[:2] == (result.parent.name, 'artifacts') and dest.is_relative_to(cache)
            digest = sha256(source.read_bytes()).hexdigest()
            assert sha256(dest.read_bytes()).hexdigest() == digest
            copied[str(source)] = digest
    assert set(observed['derived_images']) <= copied.keys()
    install_toolset()

    def no_external(*args, **kwargs):
        raise AssertionError('external request forbidden during recovery replay')

    socket.socket.connect = no_external
    socket.socket.connect_ex = no_external
    from online_memory_r49 import ReferenceVault
    ReferenceVault.after_prediction = no_external
    from run_r55_full848_production import run_dataset
    plan = load(root/'controller_plan.json')
    checked = run_dataset(code, out, Path(plan['data']['chexbench']), Path(plan['references']['chexbench']), 'D', 525)
    assert checked['first_new'] == qid and checked['model_requests'] == 0

    # Reuse the real first main reply and tool selection. Intercept the next send.
    from skill_services_r55 import Services, Tools
    context = load(out/'contexts'/(qid+'.json'))
    agent = Services(manifest['config'], manifest['protocol'], manifest['runtime'], services,
                     'offline-verification', manifest['embedding_model'], manifest['embedding_base_url'])
    agent.set_candidates(context['selected_skills'])
    raw_call = agent.call
    tool_call = Tools.call
    visited = []

    class SendBoundary(Exception):
        pass

    def cached_tool(self, row, action, arm, ordinal):
        assert row['question_id'] == qid and arm == 'R49-AGENT' and ordinal == 1
        assert action['tool'] == observed['tool']
        value = tool_call(self, row, action, arm, ordinal)
        assert value == observed
        return value

    def check_main(row, arm, ordinal, messages):
        assert row['question_id'] == qid and arm == 'R49-AGENT'
        visited.append(ordinal)
        if ordinal == 1:
            return raw_call(row, arm, ordinal, messages)
        assert ordinal == 2
        assert not (services/'calls'/arm/qid/'2').exists()
        parts = messages[-2]['content']
        images = [part['image_url']['url'] for part in parts if part['type'] == 'image_url']
        assert len(images) == len(observed['derived_images'])
        for url, name in zip(images, observed['derived_images']):
            assert sha256(base64.b64decode(url.split(',', 1)[1])).hexdigest() == copied[name]
        raise SendBoundary

    Tools.call = cached_tool
    agent.call = check_main
    try:
        agent.execute(manifest['inputs'][525], 'r49_unbounded', Path(plan['data']['chexbench']),
                      context['same_image_context'] or None)
    except SendBoundary:
        assert visited == [1, 2]
    else:
        raise AssertionError('expected the actual next model request boundary')
    assert not (services/'calls/R49-AGENT'/qid/'2').exists()
    result = {'prior_predictions': 525, 'next_question_id': qid, 'replayed_main_reply': 1,
              'next_main_ordinal': 2, 'verified_copied_images': len(copied), 'new_model_calls': 0}
    record(receipt, result)
    print(json.dumps(result))


def launch():
    plan = load(root/'controller_plan.json')
    with (JOBS/'.launch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest, qid, observed = frozen_boundary()
        assert load(receipt)['next_question_id'] == qid
        assert paused_owned(plan)
        if free_cards(plan).get('1', 0) < MIN_GPU_FREE_MIB:
            print(json.dumps({'waiting': 'gpu1'}))
            return
        estimates = plan['observed_disk']
        original = Path(plan['D']['source_run'])/plan['D']['source_generation']
        d_total = round(estimates['D_observed_raw_bytes']*550/298)+allocated(original)
        e_total = round(estimates['E_observed_raw_bytes']*848/60)
        needed = MIN_DISK_RESERVE + max(0, d_total-allocated(root/'generation/D'))
        if exit_code(JOBS/'E/controller.exitcode') != 0:
            needed += max(0, e_total-allocated(root/'generation/E'))
        available = shutil.disk_usage(root).free
        if available < needed:
            print(json.dumps({'waiting': 'disk', 'free_bytes': available, 'required_bytes': needed}))
            return
        keys = sys.stdin.buffer.read().splitlines()
        assert len(keys) == 3 and all(keys)
        controller = root/CONTROLLER
        assert sha256(controller.read_bytes()).hexdigest() == OLD_CONTROLLER_HASH
        replacement = root/CONTROLLER_REPLACEMENT
        compile(replacement.read_bytes(), str(replacement), 'exec')
        history = job/'history.cache_path001'
        history.mkdir()
        # Preserve each failed job receipt and log before switching to the resumed job.
        for path in [job/(f'controller.{suffix}') for suffix in
                     ('pid','exitcode','started.json','stderr.log','stdout.log')]:
            path.rename(history/path.name)
        ds_job.rename(history/ds_job.name)
        (out/'generation.exitcode').rename(history/'generation.exitcode')
        shutil.copyfile(controller, history/CONTROLLER)
        os.replace(replacement, controller)
        admission = {'arm': 'D', 'gpu': '1', 'started_epoch': time.time(), 'recovery': 'cache_path001',
                     'preserved_predictions': 525, 'next_question_id': qid,
                     'disk_free_bytes': available, 'estimated_required_bytes': needed}
        record(job/'controller.started.json', admission)
        command = shlex.join([sys.executable, '-B', '-u', str(controller), 'resume-chexbench', '--arm', 'D'])
        command += '; rc=$?; printf "%s\\n" "$rc" > '+shlex.quote(str(job/'controller.exitcode'))+'; exit "$rc"'
        with (job/'controller.stdout.log').open('xb') as stdout, (job/'controller.stderr.log').open('xb') as stderr:
            process = subprocess.Popen(['bash','-c',command], cwd=root, start_new_session=True,
                                       stdin=subprocess.PIPE, stdout=stdout, stderr=stderr)
            (job/'controller.pid').write_text(str(process.pid))
            process.stdin.write(b'\n'.join(keys)+b'\n')
            process.stdin.close()
        print(json.dumps({'pid': process.pid, **admission}))


if sys.argv[1] == 'verify':
    verify()
else:
    assert sys.argv[1] == 'launch'
    launch()
