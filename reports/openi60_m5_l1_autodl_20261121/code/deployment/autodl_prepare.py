from pathlib import Path
import copy
import json
import shutil
import socket
import sys

root = Path(sys.argv[1]).resolve()
base = Path('/root/autodl-tmp/medrax_r55_top4_full848')
gateway_root = Path('/root/autodl-tmp/medrax_m5_rrsi_acc_ttl_v4_20261119/trusted')
native = root / 'native'
gateway = json.loads((gateway_root / 'gateway.json').read_text())
template_path = native / 'manifests/M5/chexbench.json'
template = json.loads(template_path.read_text())
original_data = '/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_vqa_extension/data/chexbench'
data = base / 'data/chexbench'
work = root / 'runs/openi60_s20261121'

assert not work.exists()
assert template['protocol']['model'] == 'qwen3.7-plus'
assert template['config']['profile']['base_url'] == gateway['main_base_url']
assert set(template['runtime']['tools']) == set(gateway['runtime']['tools'])
for name, spec in template['runtime']['tools'].items():
    deployed = gateway['runtime']['tools'][name]
    assert spec['revision'] == deployed['revision'], name
    assert spec['description'] == deployed['description'], name
    for field in ('python', 'gpu', 'worker_env'):
        if field in deployed:
            spec[field] = copy.deepcopy(deployed[field])
            if field == 'python':
                assert Path(spec[field]).is_file(), spec[field]

views = template['runtime']['backend_config']['r54_image_views_by_path']
backend = copy.deepcopy(gateway['runtime']['backend_config'])
backend['r54_image_views_by_path'] = {
    (str(data) + path[len(original_data):]
     if path == original_data or path.startswith(original_data + '/') else path): annotation
    for path, annotation in views.items()
}
assert len(backend['r54_image_views_by_path']) == len(views)
template['runtime']['backend_config'] = backend
template['config']['root'] = str(base)
template_path.write_text(json.dumps(template, ensure_ascii=False, indent=2) + '\n')

runtime = root / 'memory_runtime'
runtime.mkdir()
shutil.copytree(base / 'runtime/five/EvolveLab', runtime / 'EvolveLab',
                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
(runtime / 'models').symlink_to(base / 'runtime/five/models', target_is_directory=True)
(runtime / 'deps').symlink_to(base / 'runtime/deps', target_is_directory=True)
plan = json.loads((native / 'plan.json').read_text())
plan['data']['chexbench'] = str(data)
plan['references']['chexbench'] = str(base / 'refs/chexbench')
plan['memory_runtime'] = str(runtime)
(native / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')

sys.path.insert(0, str(root))
from openi60.setup import new_config, prepare

config = new_config(native, work)
config['autodl_residents'] = {
    'model_module': str(Path(gateway['source_dir']) / 'r55_resident_tools.py'),
    'dispatch_module': str(gateway_root / 'native_resident_pool.py'),
    'resident_control': gateway['resident_control'],
}
(root / 'config.local.json').write_text(json.dumps(config, indent=2) + '\n')
prepared = prepare(config)
cohort = json.loads((work / 'cohort.json').read_text())
expected = json.loads((root / 'deployment/selected_ids.json').read_text())
assert cohort['selected_ids'] == expected

live = {}
for family in ('chexagent', 'maira', 'llava-med', 'llava-rad', 'medgemma', 'medvlm-r1'):
    marker = Path(gateway['resident_control']) / (family + '.ready.json')
    ready = json.loads(marker.read_text())
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(5)
        connection.connect(ready['socket'])
        connection.sendall(b'{}')
        connection.shutdown(socket.SHUT_WR)
        reply = json.load(connection.makefile('rb'))
    assert reply['pid'] == ready['pid'] and reply['family'] == family
    live[family] = reply['pid']

record = {
    'prepared': prepared,
    'same_selected_ids_as_lab': True,
    'resident_processes': live,
    'environment': json.loads((base / 'environment.json').read_text()),
    'memory_model': json.loads((native / 'jobs/memory-writer-token-plan.json').read_text())['writer'],
    'new_health_inference_calls': 0,
}
(root / 'deployment/environment.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
