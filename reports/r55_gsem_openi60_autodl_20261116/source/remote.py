"""AutoDL staging and detached worker control for the paired R55 M14 arms."""

import base64
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import time


BASE = Path('/root/autodl-tmp/medrax_r55_top4_full848')
QWEN_BATCH = BASE / 'r55_autodl_four_20261115_001'
RESIDENT_BATCH = BASE / 'r55_autodl_deepseek41_rerun_20261116_001'
RESIDENT = BASE.with_name('medrax_r55_top4_full848_chexagent8_20261114') / 'jobs'
DATA, REFS, RUNTIME = (BASE / x for x in ('data/chexbench', 'refs/chexbench', 'runtime'))
PYTHON = BASE / 'env/modern/bin/python'
MODELS = {'qwen36': 'qwen3.6-flash', 'deepseek41': 'deepseek-v4.1-flash-1017'}
ARM = 'R55-M14-GSEM'
CHEXAGENT_REVISION = '4934e91451945c8218c267aae9c34929a7677829'


def read(path):
    return json.loads(path.read_bytes())


def save(path, value):
    temp = path.with_suffix('.pending')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


@contextmanager
def control_lock(root):
    with root.with_suffix('.lock').open('a') as fp:
        fcntl.flock(fp, fcntl.LOCK_EX)
        yield


def hardware():
    line = subprocess.check_output(
        ['nvidia-smi', '--query-gpu=index,name,memory.free', '--format=csv,noheader,nounits'],
        text=True).strip().splitlines()[0]
    gpu, name, free = map(str.strip, line.split(','))
    if gpu != '0' or 'RTX 6000D' not in name:
        raise ValueError('AutoDL tool workers require the existing RTX 6000D on GPU 0')
    return {'gpu': gpu, 'name': name, 'free_mib': int(free), 'disk_free_mib': shutil.disk_usage(BASE).free // 2**20}


def env():
    return dict(os.environ, CUDA_VISIBLE_DEVICES='0', R55_MEMEVOLVE_GPU='0',
                GSEM_AUTODL_GPU_LOCK=str(RESIDENT / 'gpu-worker.0.lock'), R55_REQUIRE_CHEXAGENT8='1',
                OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', TOKENIZERS_PARALLELISM='false',
                PYTHONDONTWRITEBYTECODE='1', LANGCHAIN_TRACING_V2='false', LANGSMITH_TRACING='false')


def match_files(root, expected):
    for name, digest in expected.items():
        path = root / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'AutoDL input differs from the frozen lab artifact: {name}')


def stage(root, bundle):
    with control_lock(root):
        if (root / 'stage.json').is_file():
            stage_receipt = read(root / 'stage.json')
            if bundle['sha256'] != stage_receipt['lab_bundle_sha256']:
                raise ValueError('An existing M14 deployment uses a different lab snapshot')
            return stage_receipt
        testing = root.with_name(root.name + '.staging')
        testing.mkdir()
        raw = base64.b64decode(bundle['code'], validate=True)
        if hashlib.sha256(raw).hexdigest() != bundle['sha256']:
            raise ValueError('AutoDL code transfer does not match the lab export')
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as tar:
            if any(not item.isfile() for item in tar):
                raise ValueError('Unexpected type in the source-only lab archive')
            tar.extractall(testing, filter='data')
        manifest_path = testing / 'generation/manifest.json'
        original = read(manifest_path)
        if original['arm'] != ARM or len(original['inputs']) != 60 or original['skill_enabled']:
            raise ValueError('The lab deployment does not contain the matched no-Skill OpenI-60 run')
        graph = read(testing / 'initial_graph.json')
        accepted = read(testing / 'accepted.private.json')
        if len(graph['cards']) != 18 or any(graph[k] != accepted[k] for k in ('cards', 'views')):
            raise ValueError('The exported initial graph differs from the accepted seed bank')
        match_files(DATA, bundle['images'])
        match_files(REFS, bundle['references'])

        qwen = read(QWEN_BATCH / 'manifests/M2/chexbench.json')
        runtime = deepcopy(qwen['runtime'])
        names = original['runtime']['arms']['M']['tools']
        if runtime['arms']['M']['tools'] != names or len(names) != 11:
            raise ValueError('AutoDL and lab tool menus differ')
        for name in names:
            spec = runtime['tools'][name]
            expected = original['runtime']['tools'][name]
            revision = CHEXAGENT_REVISION if name == 'chest_xray_expert' else expected['revision']
            if (spec['backend'], spec['revision']) != (expected['backend'], revision):
                raise ValueError(f'Unexpected AutoDL tool revision: {name}')
            if spec.get('python') and not Path(spec['python']).is_file():
                raise ValueError(f'AutoDL tool interpreter missing: {name}')
        if Path(runtime['backend_config']['chexagent8_snapshot']).name != 'chexagent8_4934e91':
            raise ValueError('AutoDL CheXagent-8B snapshot does not match the verified resident route')

        code = testing / 'code/experiments'
        for name in ('r55_resident_tools.py', 'tool_worker_r54.py'):
            shutil.copy2(RESIDENT_BATCH / 'code/experiments' / name, code / name)
        (code / 'autodl_services.py').write_text(bundle['service'], encoding='utf-8')
        runner = testing / 'run_pilot.py'
        source = runner.read_text(encoding='utf-8')
        source = source.replace('from skill_services_r55 import Services', 'from autodl_services import Services', 1)
        source = source.replace('missing established Qwen Token Plan credential', 'missing established Token Plan credential')
        runner.write_text(source, encoding='utf-8')
        save(testing / 'auxiliary.json', {k: original[k] for k in ('config', 'protocol')})
        manifest_path.rename(testing / 'lab-manifest.json')
        (testing / 'generation').rmdir()

        profiles = {'qwen36': qwen['config']['profile'], 'deepseek41': bundle['deepseek_profile']}
        for label, model in MODELS.items():
            arm = testing / label
            (arm / 'generation').mkdir(parents=True)
            for name in ('code', 'accepted.private.json', 'initial_graph.json', 'auxiliary.json'):
                (arm / name).symlink_to('../' + name)
            manifest = deepcopy(original)
            manifest['runtime'] = runtime
            exp = f'{root.name}-{label}'
            manifest['config'].update(model=model, experiment_id=exp, profile=profiles[label], root=str(root))
            manifest['protocol'].update(model=model, experiment_id=exp)
            manifest['deployment'] = {'host': 'AutoDL', 'lab_run': bundle['lab_run'],
                                      'chexagent_revision': CHEXAGENT_REVISION,
                                      'seed_graph': 'frozen lab initial graph', 'model_route': 'Token Plan'}
            save(arm / 'generation/manifest.json', manifest)

        scripts = ['-B', '-m', 'unittest', 'test_gsem']
        test = subprocess.run([str(PYTHON), *scripts], cwd=testing, env=env(), text=True,
                              capture_output=True, check=True, timeout=30)
        probe_code = '''
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'code/experiments'))
from autodl_services import Services
from run_pilot import load_encoder
from r55_resident_tools import FAMILIES, request_worker, socket_path
from run_sampled_vlm import profile_for
control = Path(sys.argv[2])
wire = Path(json.loads((control/'socket-root.json').read_bytes())['root'])
workers = {f: request_worker(socket_path(wire, f), {}) for f in sorted(set(FAMILIES.values()))}
if not all(reply and reply['family'] == family for family, reply in workers.items()):
    raise RuntimeError('Expected six resident AutoDL tool workers')
enc = load_encoder(Path(sys.argv[1]))
shape = [len(v) for v in enc(['frozen OpenI graph seed', 'same-image feedback'])]
if shape != [384, 384]:
    raise RuntimeError('Missing the warm MiniLM embedding runtime')
for label in ('qwen36', 'deepseek41'):
    m = json.loads((Path(label) / 'generation/manifest.json').read_bytes())
    profile = profile_for(m['config'])
    assert profile.model == m['protocol']['model'] and profile.identity_ok(profile.model)
    Services(m['config'], m['protocol'], m['runtime'], Path(label) / 'generation/services',
             'fixture-no-network', m['embedding_model'], m['embedding_base_url'])
print(json.dumps({'embedding_dims': shape, 'resident': {k: v['pid'] for k, v in workers.items()}}))
'''
        probe = subprocess.run([str(PYTHON), '-B', '-c', probe_code, str(RUNTIME), str(RESIDENT / 'resident-tools')],
                               cwd=testing, env=env(), text=True, capture_output=True, timeout=45)
        if probe.returncode:
            raise RuntimeError(probe.stderr[-3500:])
        stage_receipt = {'root': str(root), 'models': MODELS, 'questions_per_arm': 60,
                         'tools': names, 'chexagent': 'CheXagent-8B', 'chexagent_revision': CHEXAGENT_REVISION,
                         'image_files_matched': len(bundle['images']), 'reference_files_matched': len(bundle['references']),
                         'initial_cards': len(graph['cards']), 'initial_edges': len(graph['graph']['edges']),
                         'lab_bundle_sha256': bundle['sha256'], 'runtime_probe': json.loads(probe.stdout),
                         'test': test.stderr.strip(), 'hardware': hardware(), 'new_requests': 0}
        save(testing / 'stage.json', stage_receipt)
        testing.rename(root)
        return stage_receipt


def ticks(pid):
    try:
        stat = Path(f'/proc/{pid}/stat').read_text().rsplit(') ', 1)[1].split()
        return int(stat[19]) if stat[0] not in ('Z', 'X') else None
    except FileNotFoundError:
        return None


def launch(root, label, key):
    arm = root / label
    started = arm / 'started.json'
    if started.is_file():
        return read(started)
    args = [str(PYTHON), '-B', '-u', str(root / 'run_pilot.py'), str(arm), str(DATA), str(REFS), str(RUNTIME)]
    exitfile = shlex.quote(str(arm / 'exitcode'))
    cmd = shlex.join(args) + (
        f'; rc=$?; printf "%s\\n" "$rc" > {exitfile}.tmp; mv {exitfile}.tmp {exitfile}; exit "$rc"')
    with (arm / 'stdout.log').open('xb') as out, (arm / 'stderr.log').open('xb') as err:
        worker = subprocess.Popen(['bash', '-c', cmd], cwd=arm, stdin=subprocess.PIPE, env=env(),
                                  stdout=out, stderr=err, start_new_session=True)
        pid, born = worker.pid, ticks(worker.pid)
        worker.stdin.write(key + b'\n')
        worker.stdin.close()
    receipt = {'pid': pid, 'ticks': born, 'epoch': time.time(), 'model': MODELS[label]}
    save(started, receipt)
    return receipt


def start(root, key):
    if not key or b'\n' in key:
        raise ValueError('Expected one existing Token Plan credential')
    with control_lock(root):
        if not (root / 'stage.json').is_file():
            raise ValueError('AutoDL M14 preflight has not completed')
        hw = hardware()
        if hw['free_mib'] < 15000 or hw['disk_free_mib'] < 1000:
            raise RuntimeError(f'Insufficient GPU or disk headroom for the two AutoDL runs: {hw}')
        return {'root': str(root), 'hardware': hw, 'workers': {label: launch(root, label, key) for label in MODELS}}


def retry_empty(root, key):
    if not key or b'\n' in key:
        raise ValueError('Expected one existing Token Plan credential')
    with control_lock(root):
        state = status(root)
        for label, current in state['arms'].items():
            arm = root / label
            if (current['alive'] or current['exit'] != 1 or current['saved'] or current['ingested']
                    or 'auxiliary.json' not in current.get('error', '')
                    or list((arm / 'generation').rglob('started.json'))):
                raise ValueError(f'{label} is not the empty auxiliary-config startup attempt')
        for label in MODELS:
            arm = root / label
            archive = arm / 'attempt-before-auxiliary-link'
            archive.mkdir()
            (arm / 'auxiliary.json').symlink_to('../auxiliary.json')
            for name in ('started.json', 'exitcode', 'stdout.log', 'stderr.log'):
                (arm / name).rename(archive / name)
            save(archive / 'repair.json', {'external_requests': 0, 'change': 'bind the frozen auxiliary config'})
        return {'root': str(root), 'hardware': hardware(),
                'workers': {label: launch(root, label, key) for label in MODELS}}


def status(root):
    arms = {}
    for label, model in MODELS.items():
        arm = root / label
        gen = arm / 'generation'
        receipt = read(arm / 'started.json') if (arm / 'started.json').is_file() else {}
        exit_code = int((arm / 'exitcode').read_text()) if (arm / 'exitcode').is_file() else None
        calls = list((gen / 'services/calls/R49-AGENT').glob('*/*/result.json'))
        returned = Counter(d['model_returned'] for p in calls if
                           (d := read(p)).get('response_received') and d.get('model_returned'))
        routes = Counter(read(p)['family'] for p in (gen / 'services/tool_cache').glob('*/backend_route.json'))
        items = sorted((gen / 'predictions' / ARM).glob('*.json'))
        result = {'model': model, 'pid': receipt.get('pid'), 'started_epoch': receipt.get('epoch'),
                  'alive': bool(receipt.get('ticks') and ticks(receipt['pid']) == receipt['ticks']),
                  'saved': len(items), 'latest_prediction_epoch': max((p.stat().st_mtime for p in items), default=None),
                  'ingested': len(list((gen / 'external_memory/episodes').glob('*/ingest.json'))),
                  'exit': exit_code, 'model_replies': dict(returned), 'resident_calls': dict(routes),
                  'score': read(arm / 'score.json') if exit_code == 0 else None}
        if exit_code:
            lines = (arm / 'stderr.log').read_text(errors='replace').splitlines()
            last = next((s for s in reversed(lines) if s.strip()), '')
            result['error'] = re.sub(r'(?i)\b(?:sk-|Bearer )[a-z0-9_.-]+', '[redacted]', last)[:500]
        arms[label] = result
    return {'root': str(root), 'epoch': time.time(), 'arms': arms}


if __name__ == '__main__':
    name, phase = sys.argv[1:3]
    if '/' in name or not name.startswith('r55_gsem_openi60_autodl_'):
        raise ValueError('Invalid M14 run directory')
    os.umask(0o077)
    root = BASE / name
    if phase == 'stage':
        result = stage(root, json.load(sys.stdin))
    elif phase == 'start':
        result = start(root, sys.stdin.buffer.read().strip())
    elif phase == 'retry-empty':
        result = retry_empty(root, sys.stdin.buffer.read().strip())
    elif phase == 'status':
        result = status(root)
    else:
        raise ValueError(phase)
    print(json.dumps(result, ensure_ascii=True))
