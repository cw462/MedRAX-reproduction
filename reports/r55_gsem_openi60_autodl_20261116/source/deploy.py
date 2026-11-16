"""Deploy the two M14 OpenI-60 arms through the established AutoDL connection."""

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import shlex
import sys
import tarfile


HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent
LAB = ASSETS / 'r55_gsem_openi60_20261116'
sys.path[:0] = [str(ASSETS / 'r55_evolver_after_de_20261111/autodl_top4'), str(LAB), str(ASSETS)]
from rented_host import connect
from deploy_r55_lab_baselines import PYTHON as LAB_PYTHON, TRANSPORT_HOME, lab
from deploy_r55_memevolve_openi60_once import values


RUN = 'r55_gsem_openi60_autodl_20261116_001'
LAB_RUN = '/home/imss/cw/MedRAX_reproduction_20261027/runs/r55_gsem_openi60_20261116_003'
MODELS = ('qwen36', 'deepseek41')

EXPORT = r'''
import base64, hashlib, io, json, sys, tarfile
from pathlib import Path
root, data, refs = map(Path, sys.argv[1:])
manifest = json.loads((root/'generation/manifest.json').read_bytes())
images = sorted({name for row in manifest['inputs'] for name in row['images']})
references = sorted({ref['file'] for ref in manifest['reference_files'].values()})
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
packet = io.BytesIO()
with tarfile.open(fileobj=packet, mode='w:gz') as out:
    paths = [root/name for name in ('gsem_memory.py', 'run_pilot.py', 'test_gsem.py',
                                   'accepted.private.json', 'initial_graph.json', 'generation/manifest.json')]
    paths.extend((root/'code/experiments').rglob('*.py'))
    for path in paths:
        if path.is_file():
            out.add(path, arcname=path.relative_to(root).as_posix(), recursive=False)
print(json.dumps({
    'code': base64.b64encode(packet.getvalue()).decode(),
    'images': {name: digest(data/name) for name in images},
    'references': {name: digest(refs/name) for name in references},
}))
'''


def execute(phase, payload=b'', *, timeout=45, model=None):
    args = ['/root/miniconda3/bin/python', '-B', '-c',
            (HERE / 'remote.py').read_text(encoding='utf-8'), RUN, phase]
    if model:
        args.append(model)
    with connect() as ssh:
        stdin, stdout, stderr = ssh.exec_command(shlex.join(args), timeout=timeout)
        if payload:
            stdin.write(payload)
            stdin.flush()
        stdin.channel.shutdown_write()
        output, errors = stdout.read(), stderr.read()
        code = stdout.channel.recv_exit_status()
    if code:
        raise RuntimeError(f'AutoDL {phase} exited {code}: {errors.decode(errors="replace")[-3000:]}')
    return json.loads(output)


def stage():
    locations = values()
    bundle = lab([LAB_PYTHON, '-B', '-c', EXPORT, LAB_RUN, locations['DATA'], locations['REFS']], timeout=45)
    raw = base64.b64decode(bundle['code'], validate=True)
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as tar:
        for name in ('gsem_memory.py', 'run_pilot.py', 'test_gsem.py'):
            if tar.extractfile(name).read().decode().splitlines() != (LAB / name).read_text(encoding='utf-8').splitlines():
                raise ValueError(f'Lab {name} differs from the recorded M14 source')
    bundle['sha256'] = hashlib.sha256(raw).hexdigest()
    bundle['service'] = (HERE / 'autodl_services.py').read_text(encoding='utf-8')
    bundle['deepseek_profile'] = json.loads(
        (ASSETS.parent / 'configs/deepseek_v41_flash_1017_token_plan_profile.json').read_bytes())
    bundle['lab_run'] = LAB_RUN
    return execute('stage', json.dumps(bundle).encode(), timeout=100)


def start(phase='start'):
    key = (TRANSPORT_HOME / '.secrets/token_plan_api.key').read_bytes().strip()
    if not key or b'\n' in key:
        raise ValueError('Missing existing Token Plan credential')
    return execute(phase, key + b'\n')


if __name__ == '__main__':
    argp = argparse.ArgumentParser(description=__doc__)
    argp.add_argument('phase', choices=('stage', 'start', 'retry-empty', 'status'))
    args = argp.parse_args()
    result = {'stage': stage, 'status': lambda: execute('status')}.get(args.phase, lambda: start(args.phase))()
    if args.phase != 'status':
        (HERE / f'{args.phase}.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
