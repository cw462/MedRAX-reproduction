"""Run the actual pending R55 tool entry points as their dependencies arrive."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


GROUPS = {
    'chexagent': ('chest_xray_expert',),
    'llava_med': ('llava_med_qa',),
    'llava_rad': ('llava_rad',),
    'medvlm': ('medvlm_r1',),
    'maira': ('maira2_grounded_report', 'xray_phrase_grounding'),
}


def ready_to_run(root, group):
    hub = root / 'models/hf_full/hub'
    if group == 'chexagent':
        python = root / 'env/legacy/bin/python'
        return subprocess.run([python, '-B', '-c', 'import albumentations, pyarrow'],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if group == 'llava_med':
        clip = hub / 'models--openai--clip-vit-large-patch14-336/snapshots/ce19dc912ca5cd21c8a653c79e251e808ccabcd1'
        return all((clip / name).is_file() for name in ('config.json', 'preprocessor_config.json', 'pytorch_model.bin'))
    if group == 'llava_rad':
        return (root / 'jobs/priority-llavarad-compat.ready').is_file()
    if group == 'medvlm':
        return (root / 'jobs/priority-medvlm-source.ready').is_file()
    snapshot = hub / 'models--microsoft--maira-2/snapshots/795a2b1cd4a310624b4e3d14b5a23e41fd273deb'
    return all((snapshot / f'model-{n:05d}-of-00006.safetensors').is_file() for n in range(1, 7))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('group', choices=tuple(GROUPS))
    parser.add_argument('label')
    args = parser.parse_args()
    root = args.root
    while not ready_to_run(root, args.group):
        time.sleep(10)
    sys.path.insert(0, str(root / 'bin'))
    from run_top4_priority import shared_gpu_slot

    code = root / 'code/experiments'
    sys.path.insert(0, str(code))
    with shared_gpu_slot(root):
        subprocess.run([sys.executable, '-B', '-u', root / 'bin/tool_preflight.py', root, args.label,
                        *GROUPS[args.group]], check=False)
    receipt = root / 'tool-preflight' / args.label / 'result.json'
    tools = json.loads(receipt.read_text())['tools']
    for name, result in tools.items():
        if result['completed'] and result['worker_exit'] == 0:
            ready = root / 'jobs/priority-tool-ready' / (name + '.json')
            temp = ready.with_suffix(f'.{os.getpid()}.tmp')
            temp.write_text(json.dumps({'preflight': args.label, 'result': result}) + '\n')
            os.replace(temp, ready)
    return 0 if all(item['completed'] for item in tools.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
