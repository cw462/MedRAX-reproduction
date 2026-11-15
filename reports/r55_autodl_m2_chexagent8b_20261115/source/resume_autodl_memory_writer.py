"""Restart the existing AutoDL memory lanes from their verified snapshots."""

import argparse
import fcntl
import json
from pathlib import Path
import stat
import sys
import time
from urllib.request import Request, urlopen

import prioritize_autodl_baselines as queue


KEYS = Path('/root/.config/medrax-autodl-r55/memory_resume.keys')
TOKEN_PLAN = 'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1'


def verify_memory_profile(root):
    for arm in queue.ARMS:
        for dataset in queue.DATASETS:
            manifest = queue.read(root/'manifests'/arm/(dataset+'.json'))
            config = manifest['config']
            profile = config['profile']
            if (profile['base_url'], profile['credential_slot'], manifest['protocol']['model']) != (
                    TOKEN_PLAN, 'token_plan', 'qwen3.7-plus'):
                raise ValueError(f'Unexpected main model route for {arm}/{dataset}')


def resume(root, *, token_plan_writer=False):
    sys.path.insert(0, str(root / 'bin'))
    import r55_memory_token_plan as writer

    jobs = root/'jobs'
    with (jobs/'baselines-priority.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        live = list(queue.controllers(root))
        if live:
            return {'state':'running','controller_count':len(live)}
        if any(queue.identify(int(path.read_text()), root/'bin/run_top4_priority.py', root)
               for path in jobs.glob('M*/*/runner.pid')):
            raise RuntimeError('An AutoDL memory dataset runner is active')
        if KEYS.is_symlink() or stat.S_IMODE(KEYS.stat().st_mode) != 0o600:
            raise ValueError('The existing credential file must be private')
        keys = KEYS.read_bytes().splitlines()
        if len(keys) != 2 or not all(keys) or keys[0].startswith(b'sk-ws-'):
            raise ValueError('The original Token Plan and DeepSeek credentials are required')
        verify_memory_profile(root)
        baseline = root.with_name('medrax_r55_top4_full848')/'chexagent8_11tools_open_budget'
        restore = queue.read(baseline/'jobs/qwen-token-plan-restored.json')
        if not restore or restore['transport'] != 'token_plan':
            raise ValueError('The original Token Plan cutover receipt is missing')
        import top4_parallel_datasets as lanes

        datasets = {f'{arm}/{ds}':lanes.dataset_info(root,arm,ds)
                    for arm in queue.ARMS for ds in queue.DATASETS}
        if all(value['correct'] is not None for value in datasets.values()):
            return {'state':'complete'}
        prior = queue.read(jobs/queue.RESUMED) or {}
        if prior.get('transport') != 'token_plan':
            raise ValueError('The existing memory queue was not on Token Plan')
        if token_plan_writer or writer.enabled(root):
            health = writer.probe(keys[0].decode('ascii'))
            if health['state'] != 'available':
                return health
            marker = jobs / writer.MARKER
            if not marker.is_file():
                queue.write(marker, {'writer': writer.ROUTE, 'epoch': time.time(),
                                     'saved': {k: v['saved'] for k, v in datasets.items()}})
        else:
            request = Request('https://api.deepseek.com/user/balance',
                              headers={'Authorization':'Bearer '+keys[1].decode('ascii')})
            with urlopen(request,timeout=8) as response:
                if json.load(response).get('is_available') is not True:
                    return {'state':'writer_unavailable','new_model_requests':0}
        receipt = queue.replace_memory_processes(root, {'datasets':datasets}, {}, KEYS,
                    transport='token_plan', reconcile_paused_expel=False)
        return {'state':'restarted', **receipt}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--token-plan-writer', action='store_true')
    args = parser.parse_args()
    print(json.dumps(resume(args.root, token_plan_writer=args.token_plan_writer)))
