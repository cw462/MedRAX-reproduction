"""Stage, start and inspect the seven affected DeepSeek R55 cohorts on AutoDL."""

import json
import sys
from pathlib import Path

from r55_launch_autodl_flash_memory import execute


REMOTE = r'''
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

BASE = Path('/root/autodl-tmp/medrax_r55_top4_full848')
SOURCE = BASE / 'r55_autodl_deepseek41_main_20261115_001'
ROOT = BASE / 'r55_autodl_deepseek41_rerun_20261116_001'
JOBS = ROOT / 'jobs'
BIN = ROOT / 'bin'
RUNTIME = BIN / 'r55_deepseek_rerun_runtime.py'
BASELINE_SOURCE = SOURCE / 'flash_react/code_deepseek_methods'
BASELINES = ROOT / 'flash_react/code_official'
COUNTS = {'slake': 114, 'vqarad': 116, 'chexbench': 618}
PROVIDERS = {'M2': 'expel', 'M5': 'cerebra_fusion_memory'}
QUEUE = [
    ('ReAct', 'slake', []),
    ('M5', 'slake', []),
    ('ReAct', 'vqarad', [('ReAct', 'slake')]),
    ('M2', 'slake', []),
    ('CRITIC', 'slake', []),
    ('Reflexion', 'slake', [('ReAct', 'slake')]),
    ('Reflexion', 'vqarad', [('Reflexion', 'slake'), ('ReAct', 'vqarad')]),
]


def read(path):
    return json.loads(path.read_bytes())


def code(path, source):
    compile(source, str(path), 'exec')
    tmp = path.with_suffix('.pending')
    tmp.write_text(source, encoding='utf-8')
    tmp.replace(path)


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Unexpected source boundary: ' + old[:80])
    return source.replace(old, new)


def load_source(path):
    return path.read_text(encoding='utf-8')


def link(dst, src):
    assert src.exists()
    if not dst.exists():
        dst.symlink_to(src, target_is_directory=src.is_dir())
    assert dst.resolve() == src.resolve()


def route_source(source):
    source = once(source, 'def route(request, root):\n', 'def resident_route(request, root):\n')
    source = once(source, "    root = Path('/root/autodl-tmp/medrax_r55_top4_full848_chexagent8_20261114')",
        "    run_root = Path(root).resolve()\n"
        "    root = Path('/root/autodl-tmp/medrax_r55_top4_full848_chexagent8_20261114')")
    source = once(source, "    memory_marker = control / memory_marker_name(family)",
        "    in_memory = in_memory or artifacts.is_relative_to(run_root)\n"
        "    memory_marker = control / memory_marker_name(family)")
    return source + """

def route(request, root):
    if request['backend'] not in FAMILIES:
        return False
    if not Path(request['artifact_dir']).resolve().is_relative_to(Path(root).resolve()):
        raise RuntimeError('R55 rerun GPU artifact escaped its run root')
    if not resident_route(request, root):
        raise RuntimeError('R55 rerun requires a live resident GPU tool')
    return True
"""


def stage_code(runtime):
    for name in ('env', 'data', 'refs', 'runtime'):
        link(ROOT / name, SOURCE / name)
    link(JOBS / 'priority-tool-ready', SOURCE / 'jobs/priority-tool-ready')
    BIN.mkdir(exist_ok=True)
    code(RUNTIME, runtime)
    for path in (SOURCE / 'bin').glob('*.py'):
        if path.name != 'run_top4_flash_memory_official.py':
            link(BIN / path.name, path)
    code_root = ROOT / 'code/experiments'
    code_root.mkdir(parents=True, exist_ok=True)
    donor_code = SOURCE / 'code/experiments'
    for path in donor_code.iterdir():
        if path.name not in ('tool_worker_r54.py', 'r55_resident_tools.py', '__pycache__'):
            link(code_root / path.name, path)
    code(code_root / 'tool_worker_r54.py', load_source(donor_code / 'tool_worker_r54.py'))
    code(code_root / 'r55_resident_tools.py', route_source(load_source(donor_code / 'r55_resident_tools.py')))

    memory = load_source(SOURCE / 'bin/run_top4_flash_memory_official.py')
    first = memory.index('PROVIDERS = ')
    memory = memory[:first] + f'PROVIDERS = {PROVIDERS!r}\n' + memory[memory.index('ARM_LABELS = ', first):]
    memory = once(memory, "('five' if arm in ('M3', 'M5') else 'expansion')", "'five'")
    memory = once(memory, "        service_class = Services\n", """        class ManagedServices(Services):
            def call(self, row, role, ordinal, messages):
                from r55_deepseek_rerun_runtime import call_main
                return call_main(root, self, super().call, row, role, ordinal, messages)

        service_class = ManagedServices
""")
    start = memory.index('    class GuardedTools(Tools):\n')
    end = memory.index('    class DiskGuardedMemory(RecoveryMemory):\n', start)
    memory = memory[:start] + """    class GuardedTools(Tools):
        def observe(self, name, spec, args, image, identity, folder, saved):
            backend = super().observe
            if name in ('roi_crop', 'medret', 'reflect', 'verify'):
                return backend(name, spec, args, image, identity, folder, saved)
            from r55_deepseek_rerun_runtime import guarded_tool
            return guarded_tool(root, arm, name, folder, saved,
                                lambda: backend(name, spec, args, image, identity, folder, saved))

""" + memory[end:]
    memory = once(memory, '        def retrieve(self, row):\n', """        def retrieve(self, row):
            if not verify:
                from r55_deepseek_rerun_runtime import wait_for_arm
                wait_for_arm(root, arm)
""")
    memory = once(memory, "    summary = score_dataset(root/'code', out)\n", """    generation = out/'generation.exitcode'
    if not generation.is_file():
        native_exit = read(root/'jobs/cohorts'/arm/dataset/'dataset.exit.json')
        assert native_exit['exit'] == 0
        marker = generation.with_suffix('.pending')
        marker.write_text('0\\n')
        marker.replace(generation)
    summary = score_dataset(root/'code', out)
""")
    code(BIN / 'run_top4_flash_memory_official.py', memory)

    BASELINES.mkdir(parents=True, exist_ok=True)
    for name in ('r55_baseline_common.py', 'r55_baseline_vqa.py', 'run_chexagent8_direct.py'):
        link(BASELINES / name, BASELINE_SOURCE / name)
    entry = load_source(BASELINE_SOURCE / 'run_qwen_baselines.py')
    entry = once(entry,"    parser.add_argument('--prepare', action='store_true')",
        "    parser.add_argument('--prepare', action='store_true')\n"
        "    parser.add_argument('--dataset', choices=tuple(DATASETS), required=True)")
    entry = once(entry,'        for dataset in DATASETS:\n','        for dataset in (args.dataset,):\n')
    entry = once(entry,"        for dataset in ('slake', 'vqarad', 'chexbench'):\n",
        "        for dataset in (args.dataset,):\n")
    entry = once(entry, "    with exclusive_lock(args.out / f'{args.method}.lock'):\n",
        "    scheduled = json.loads((args.root/'plan.json').read_bytes())['baseline_cohorts'][args.method]\n"
        "    assert args.dataset in scheduled\n"
        "    with exclusive_lock(args.out / f'{args.method}.lock'):\n")
    entry = once(entry, "'cohorts': DATASETS,", "'cohorts': {ds: DATASETS[ds] for ds in scheduled},")
    entry = once(entry,"        start = time.monotonic()\n        if method == 'react':",
        "        from r55_deepseek_rerun_runtime import wait_for_arm\n"
        "        wait_for_arm(self.root, os.environ['R55_RERUN_ARM'])\n"
        "        start = time.monotonic()\n        if method == 'react':")
    entry = once(entry, "'critic_initial_answer': 'archive an official DeepSeek Flash CoT candidate per case',",
        "'critic_initial_answer': 'replay the frozen same-model CoT candidate',")
    code(BASELINES / 'run_qwen_baselines.py', entry)
    baseline = load_source(BASELINE_SOURCE / 'r55_baselines_11tools.py')
    baseline = once(baseline, 'from contextlib import nullcontext\nimport fcntl\n', 'import os\n')
    baseline = once(baseline, '        from run_top4_flash_memory_official import shared_gpu_slot\n',
                    '        from r55_deepseek_rerun_runtime import guarded_tool\n')
    start = baseline.index('        class SharedTools(Tools):\n')
    end = baseline.index('        self.tool_workers = {}\n', start)
    baseline = baseline[:start] + """        arm = os.environ['R55_RERUN_ARM']

        class SharedTools(Tools):
            def observe(self, name, spec, args, image, identity, folder, saved):
                backend = super().observe
                if name not in GPU_TOOLS:
                    return backend(name, spec, args, image, identity, folder, saved)
                return guarded_tool(root, arm, name, folder, saved,
                                    lambda: backend(name, spec, args, image, identity, folder, saved))

""" + baseline[end:]
    code(BASELINES / 'r55_baselines_11tools.py', baseline)


def import_runtime():
    sys.path.insert(0, str(BIN))
    import r55_deepseek_rerun_runtime as rt
    assert rt.ROOT == ROOT
    return rt


def stage(runtime):
    if (JOBS / 'staged.json').is_file():
        return read(JOBS / 'staged.json')
    assert shutil.disk_usage(ROOT).free >= 1400 * 1024**2
    stage_code(runtime)
    rt = import_runtime()
    prior = read(SOURCE / 'plan.json')
    hw = rt.gpu_sample()
    assert hw['healthy']
    control = rt.RESIDENT_ROOT / 'jobs/resident-tools'
    wire = Path(read(control / 'socket-root.json')['root'])
    families = ('chexagent', 'maira', 'llava-med', 'llava-rad', 'medgemma', 'medvlm-r1')
    workers = {}
    for family in families:
        resident = read(control / f'{family}.enabled.json')
        assert rt.native(resident['pid']) == resident['start_ticks']
        assert (wire / 'sockets' / f'{family}.sock').is_socket()
        workers[family] = resident['pid']
    assert (SOURCE / 'jobs/runtime-fixes/resident-routes-20261116/enabled.json').is_file()

    reruns = {(a, d) for a, d, _ in QUEUE}
    arm_names = ('ReAct', 'M2', 'M5', 'CRITIC', 'Reflexion')
    kept = {}
    for arm in arm_names:
        kept[arm] = {}
        for ds, n in COUNTS.items():
            if (arm, ds) in reruns:
                continue
            before = (SOURCE / 'generation' / arm / ds / 'analysis/summary.json'
                      if arm in PROVIDERS else SOURCE / 'flash_react' / arm.lower() / ds / 'summary.json')
            summary = read(before)
            assert summary['questions'] == n
            kept[arm][ds] = {'questions': n, 'correct': summary['correct'], 'source': str(before.relative_to(SOURCE))}
    for arm, ds in {(a if a in PROVIDERS else 'ReAct', d) for a, d in reruns}:
        manifest = read(SOURCE / 'manifests' / arm / f'{ds}.json')
        assert len(manifest['inputs']) == COUNTS[ds] and len(manifest['runtime']['tools']) == 11
        assert manifest['skill_enabled'] is False and manifest['config']['model'] == 'deepseek-flash'
        assert manifest['runtime']['backend_config']['chexagent8_snapshot'] == prior['chexagent8_snapshot']
        if arm in PROVIDERS:
            assert manifest['memory_provider'] == PROVIDERS[arm]
        ident = f'{ROOT.name}-{arm}-{ds}'
        manifest['protocol']['experiment_id'] = ident
        manifest['config']['experiment_id'] = ident
        rt.save(ROOT / 'manifests' / arm / f'{ds}.json', manifest)

    source_cot = SOURCE / 'flash_react/cot/slake/predictions'
    frozen = ROOT / 'flash_react/cot/slake/predictions'
    frozen.mkdir(parents=True, exist_ok=True)
    ids = {r['question_id'] for r in read(ROOT / 'manifests/ReAct/slake.json')['inputs']}
    assert len(ids) == 114 and {p.stem for p in source_cot.glob('*.json')} == ids
    for q in sorted(ids):
        name = q + '.json'
        candidate = read(source_cot / name)
        call = read(SOURCE / 'flash_react/api/slake/calls/cot' / q / '1/result.json')
        archived = read(SOURCE / 'flash_react/api/slake/calls/cot' / q / '1/response.json')
        assert (candidate['arm'], candidate['question_id']) == ('cot', q)
        assert call['response_received'] is True and call['model_returned'] == 'deepseek-flash'
        assert candidate['raw'] == (archived['choices'][0]['message']['content'] or '')
        rt.save(frozen / name, candidate)
    (ROOT / 'flash_react/api').mkdir(exist_ok=True)

    plan = {
        'source_run': str(SOURCE), 'model': 'deepseek-flash', 'endpoint': 'https://api.deepseek.com/chat/completions',
        'queue': [{'arm': a, 'dataset': d, 'questions': COUNTS[d], 'depends_on': deps} for a, d, deps in QUEUE],
        'retained': kept, 'baseline_cohorts': {'react': ['slake', 'vqarad'], 'critic': ['slake'],
                                             'reflexion': ['slake', 'vqarad']},
        'memory_initial': {'M2': 'empty', 'M5': 'seven_default_patterns'},
        'deepseek_by_arm': prior['deepseek_by_arm'], 'datasets': COUNTS,
        'chexagent8_snapshot': prior['chexagent8_snapshot'],
        'critic_candidate_source': str(source_cot),
        'max_active_cohorts': 2, 'gpu_tool_slots': 1, 'min_free_mib': rt.MIN_FREE_MIB,
        'gpu_monitor_sample_seconds': rt.SAMPLE_SECONDS, 'resident_only': True, 'resident_workers': workers,
    }
    rt.save(ROOT / 'plan.json', plan)
    logs = JOBS / 'validation'
    logs.mkdir(exist_ok=True)
    for arm, ds, _ in QUEUE:
        args = rt.command_for(arm, ds, 'verify')
        if arm in PROVIDERS:
            verify = ROOT / 'verification' / arm / ds
            if (verify / 'verified.json').is_file():
                continue
            if verify.exists():
                verify.rename(verify.with_name(f'{ds}-partial-{time.time_ns()}'))
        else:
            args += ['--prepare']
        stdout, stderr = logs / f'{arm}-{ds}.stdout.log', logs / f'{arm}-{ds}.stderr.log'
        with stdout.open('wb') as out, stderr.open('wb') as err:
            proc = subprocess.run([str(rt.PYTHON), '-B', *args], cwd=ROOT, env=rt.job_env(plan, arm),
                                  stdin=subprocess.DEVNULL, stdout=out, stderr=err, timeout=70)
        if proc.returncode:
            raise RuntimeError(f'{arm}/{ds} offline preflight failed: ' + stderr.read_text()[-1000:])
    for arm, provider in PROVIDERS.items():
        checked = read(ROOT / 'verification' / arm / 'slake/verified.json')
        assert (checked['provider'], checked['bound_questions'], checked['new_external_model_requests']) == (provider, 114, 0)
    seeds = read(ROOT / 'verification/M5/slake/storage/cerebra_fusion_memory/cf_database.json')
    assert len(seeds['nodes']) == 7
    receipt = {'epoch': time.time(), 'root': str(ROOT), 'cohorts': len(QUEUE),
               'new_predictions': sum(COUNTS[d] for _, d, _ in QUEUE), 'offline_verified': True,
               'official_model': 'deepseek-flash', 'gpu': hw, 'workers': workers,
               'frozen_cot_candidates': len(ids)}
    rt.save(JOBS / 'staged.json', receipt)
    return receipt


def start(key):
    assert key and len(key.splitlines()) == 1 and read(JOBS / 'staged.json')['offline_verified']
    rt = import_runtime()
    stamp = JOBS / 'supervisor.started.json'
    if stamp.is_file():
        prior = read(stamp)
        if rt.native(prior['pid']) == prior['start_ticks'] or (JOBS / 'complete.json').is_file():
            return prior
        for f in (JOBS / 'cohorts').glob('*/*/*.started.json'):
            child = read(f)
            if rt.native(child['pid']) == child['start_ticks']:
                raise RuntimeError('A prior native cohort still owns this queue')
    with (JOBS / 'supervisor.log').open('ab') as log:
        child = subprocess.Popen([str(rt.PYTHON), '-B', '-u', str(RUNTIME), 'supervise'],
                                 cwd=ROOT, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        rec = {'pid': child.pid, 'start_ticks': rt.native(child.pid), 'epoch': time.time()}
        rt.save(stamp, rec)
        with child.stdin:
            child.stdin.write(key + b'\n')
    return rec


os.umask(0o077)
ROOT.mkdir(mode=0o700, exist_ok=True)
JOBS.mkdir(exist_ok=True)
mode = sys.argv[1]
if mode == 'status':
    result = import_runtime().status()
else:
    with (JOBS / 'deploy.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if mode == 'stage':
            result = stage(json.load(sys.stdin)['runtime'])
        else:
            result = start(sys.stdin.buffer.read().strip())
print(json.dumps(result, ensure_ascii=False))
'''


def deploy(phase, payload=b""):
    return execute(phase, payload, 150 if phase == "stage" else 45, source=REMOTE)


def main():
    phase = sys.argv[1]
    if phase not in ("stage", "start", "status"):
        raise SystemExit("Expected stage, start or status")
    if phase == "stage":
        runtime = Path(__file__).with_name("r55_deepseek_rerun_runtime.py").read_text(encoding="utf-8")
        data = json.dumps({"runtime": runtime}).encode()
    else:
        data = sys.stdin.buffer.read() if phase == "start" else b""
    print(json.dumps(deploy(phase, data), ensure_ascii=False))


if __name__ == "__main__":
    main()
