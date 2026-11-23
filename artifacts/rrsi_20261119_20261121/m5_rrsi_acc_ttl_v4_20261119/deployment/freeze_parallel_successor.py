"""Continue the immutable serial prefix with parallel candidate replay."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--controller', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    package = root / 'source/m5_rrsi_acc_ttl_v4_parallel_20261120'
    sys.path.insert(0, str(package))
    from integration.native_gateway import read_key
    from m5rrsi.io import read_json, write_json, write_once, git
    from m5rrsi.validation import budget, freeze, verify_frozen
    old = root / 'run'
    run = root / 'run_parallel_20261120'
    config_path = root / 'configs/run_parallel_20261120.json'
    control = root / 'deployment'
    gateway = read_json(root / 'trusted/gateway.json')
    base = read_json(root / 'configs/run.json')
    environment = dict(os.environ)
    environment[base['search_llm']['api_key_env']] = read_key(gateway['key_files']['main'])
    environment[base['search_llm']['base_url_env']] = gateway['main_base_url']
    environment['PYTHONPATH'] = str(package)
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    os.environ.update(environment)
    marker = control / 'parallel_controller.started.json'
    status_path = control / 'parallel_controller.status.json'
    if args.controller:
        state = {'pid': os.getpid(), 'status': 'running', 'time': time.time(),
                 'config': str(config_path), 'run_dir': str(run)}
        write_json(status_path, state)
        try:
            with (control / 'parallel_controller.log').open('ab') as output:
                result = subprocess.run([sys.executable, '-B', '-m', 'm5rrsi.cli', 'run',
                         '--config', str(config_path), '--resume'], cwd=package,
                         env=environment, stdout=output, stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError('Parallel replay exited ' + str(result.returncode))
            progress = read_json(run / 'progress.json')
            complete = progress['completed'] == base['expected_questions']
            if not complete and not (run / 'STOP').exists():
                raise RuntimeError('Parallel replay returned before the full stream completed')
            if complete:
                from m5rrsi.report import report
                report(run)
            write_json(status_path, {**state, 'status': 'complete' if complete else 'checkpoint_stop',
                                     'completed': progress['completed'], 'finished_at': time.time()})
        except Exception as error:
            write_json(status_path, {**state, 'status': 'failed', 'error': str(error),
                                    'finished_at': time.time()})
            raise
        return
    if marker.is_file():
        prior = read_json(marker)
        proc = Path('/proc', str(prior['pid']), 'cmdline')
        if proc.is_file() and b'--controller' in proc.read_bytes().split(b'\0'):
            print(json.dumps({'status': 'already_running', **prior})); return
    if not (run / 'frozen.json').is_file():
        old_controller = read_json(control / 'formal_controller.started.json')
        if Path('/proc', str(old_controller['pid']), 'cmdline').exists():
            print(json.dumps({'status': 'waiting_for_serial_checkpoint', 'pid': old_controller['pid']})); return
        if not (old / 'STOP').is_file():
            raise RuntimeError('The serial stream has not requested a checkpoint handoff')
        for proc in Path('/proc').glob('[0-9]*/cmdline'):
            try:
                words = proc.read_bytes().split(b'\0')
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
            if str(root / 'configs/run.json').encode() in words and b'm5rrsi.cli' in words:
                raise RuntimeError('The serial coordinator is still active')
        completed = sorted((old / 'primary').glob('q*/completed.json'))
        n = len(completed)
        progress = read_json(old / 'progress.json')
        if progress['completed'] != n:
            raise RuntimeError('The current search checkpoint has not finished')
        checkpoint = read_json(old / 'search/checkpoints' / f'after_{n:06d}' / 'done.json')
        if git(base['upstream_repo'], 'rev-parse', 'evolve/med_m5') != checkpoint['commit']:
            raise RuntimeError('The official branch is not at the completed checkpoint')
        for directory, dirs, files in os.walk(old):
            rel = Path(directory).relative_to(old)
            dirs[:] = [name for name in dirs if name not in {'state', 'rootfs', 'wt', 'code', 'report'}]
            target = run / rel
            target.mkdir(parents=True, exist_ok=True)
            for name in files:
                if rel == Path('.') and name in {'frozen.json', 'run_identity.json', 'STOP', 'coordinator.lock'}:
                    continue
                shutil.copy2(Path(directory) / name, target / name)
        lineage = {'prior_run_dir': str(old), 'prior_frozen': str(old / 'frozen.json'),
                   'inherited_primary': n, 'inherited_rounds': n,
                   'effective_from_primary': n + 1, 'time': time.time(),
                   'authorized_change': 'Parallel drafts, candidate evaluations and independent repeats',
                   'state_policy': 'Existing locked state paths remain immutable in the prior run'}
        cfg = copy.deepcopy(base)
        cfg['run_dir'] = str(run)
        cfg['search'].update(eval_parallel=2, repeat_parallel=2, draft_parallel=2)
        cfg['execution_lineage'] = lineage
        unchanged = copy.deepcopy(cfg)
        unchanged.pop('execution_lineage')
        unchanged['run_dir'] = base['run_dir']
        for key in ('eval_parallel', 'repeat_parallel', 'draft_parallel'):
            if key in base['search']:
                unchanged['search'][key] = base['search'][key]
            else:
                unchanged['search'].pop(key)
        if unchanged != base or budget(cfg) != budget(base):
            raise RuntimeError('The handoff changed more than execution concurrency')
        write_json(config_path, cfg)
        identity = read_json(old / 'run_identity.json')
        identity['config'] = cfg
        write_once(run / 'run_identity.json', identity)
        write_once(run / 'lineage.json', lineage)
        frontier_path = run / 'search/official/med_m5/frontier.json'
        frontier = read_json(frontier_path)
        frontier['config']['eval_parallel'] = 2
        write_json(frontier_path, frontier)
        freeze(cfg)
        audit_before = len(list((run / 'runtime_audit').glob('*')))
        with (control / 'parallel_prefix_reuse.log').open('ab') as output:
            check = subprocess.run([sys.executable, '-B', '-m', 'm5rrsi.cli', 'run',
                    '--config', str(config_path), '--resume', '--stop-after', str(n)],
                    cwd=package, env=environment, stdout=output, stderr=subprocess.STDOUT)
        if check.returncode or len(list((run / 'runtime_audit').glob('*'))) != audit_before:
            raise RuntimeError('Inherited prefix did not reuse all locked operations; see parallel_prefix_reuse.log')
        write_json(root / 'evidence/parallel_handoff.json', lineage)
    cfg = read_json(config_path)
    verify_frozen(cfg)
    with (control / 'parallel_supervisor.log').open('ab') as output:
        process = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
                     '--root', str(root), '--controller'], cwd=package, env=environment,
                     stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                     start_new_session=True)
    receipt = {'pid': process.pid, 'config': str(config_path), 'run_dir': str(run),
               'time': time.time(), 'concurrency': cfg['search'], 'lineage': cfg['execution_lineage']}
    write_json(marker, receipt)
    print(json.dumps({'status': 'launched', **receipt}, indent=2))


if __name__ == '__main__':
    main()
