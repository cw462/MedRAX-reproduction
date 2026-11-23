"""UID-separated chroot execution for hosts without Docker namespace privileges.

The filesystem and credentials are isolated. The network namespace is shared
with the host, unlike the internal Docker network used by DockerRuntime.
"""

import copy
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import uuid

from .io import ProtocolError, copy_tree, file_hash, read_json, tree_hash, tree_manifest, write_json
from .runtime import require_prediction


def readonly(path):
    for child in Path(path).rglob('*'):
        os.chown(child, 0, 0)
        os.chmod(child, 0o555 if child.is_dir() else 0o444)
    os.chown(path, 0, 0)
    os.chmod(path, 0o555)


def writable_state(path, uid):
    path = Path(path)
    for child in path.rglob('*'):
        if child == path / 'native_services' or path / 'native_services' in child.parents:
            continue
        os.chown(child, uid, uid)
        os.chmod(child, 0o700 if child.is_dir() else 0o600)
    os.chown(path, 0, 0)
    os.chmod(path, 0o1777)
    if (path / 'native_services').exists():
        readonly(path / 'native_services')


def launch(root, runtime_dir, spec, *, uid, timeout, memory_bytes, cpus, entrypoint='/runner/process_worker.py'):
    settings = {'uid': uid, 'memory_bytes': memory_bytes, 'cpu_seconds': max(1, int(timeout)),
                'cpus': cpus, 'pythonpath': spec['pythonpath'], 'entrypoint': entrypoint}
    process = subprocess.Popen([sys.executable, '-B', str(Path(runtime_dir) / 'process_launcher.py'),
                                str(root), json.dumps(settings)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        error = TimeoutError('restricted process exceeded its wall time')
        error.stdout, error.stderr = stdout, stderr
        raise error
    finally:
        # Also remove background children left after an otherwise successful worker.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return process.returncode, stdout, stderr


def retain_success(work, root, state, worker_result, receipt):
    """Keep the operation's evidence and independent state, release its rootfs."""
    work, root, state = Path(work), Path(root), Path(state)
    write_json(work / 'worker_result.json', worker_result)
    copy_tree(root / 'state', state)
    receipt.update(source_rootfs=str(root), retained_state=str(state))
    write_json(work / 'receipt.json', receipt)
    shutil.rmtree(root)


class ProcessRuntime:
    def __init__(self, config, audit_dir):
        self.cfg = config
        self.audit = Path(audit_dir).resolve()
        self.audit.mkdir(parents=True, exist_ok=True)
        self.runtime_dir = Path(config['runtime_dir']).resolve()
        self.template = Path(config['rootfs']).resolve()
        self.spec = read_json(self.template / 'process_runtime_spec.json')
        self.case_metadata = read_json(config['case_metadata'])
        self.uid = config.get('worker_uid', 62055)

    def preflight(self):
        if os.name != 'posix' or os.geteuid() != 0:
            raise ProtocolError('chroot process runtime requires the privileged Linux coordinator')
        for name in ('worker.py', 'process_worker.py', 'process_launcher.py', 'native_bridge.py'):
            if not (self.runtime_dir / name).is_file():
                raise ProtocolError('missing protected process runtime file: ' + name)
        if not (self.template / 'usr/local/bin/python').is_file():
            raise ProtocolError('candidate CPU rootfs is not built')
        if self.uid < 10000:
            raise ProtocolError('candidate requires a separate non-root UID')

    def call(self, harness, state, op, *, case=None, prediction=None, feedback=None, seed=0):
        if op not in {'initialize', 'predict', 'observe', 'migrate', 'check'}:
            raise ProtocolError('unknown native process operation')
        if op != 'observe' and feedback is not None:
            raise ProtocolError('feedback is only passed to observe')
        from integration.native_gateway import control_request
        harness, state = Path(harness).resolve(), Path(state).resolve()
        before_hash = tree_hash(harness)
        work = self.audit / uuid.uuid4().hex
        work.mkdir()
        root = work / 'rootfs'
        shutil.copytree(self.template, root, copy_function=os.link)
        shutil.copytree(harness, root / 'harness', dirs_exist_ok=True)
        readonly(root / 'harness')
        copy_tree(state, root / 'state')
        for name in ('worker.py', 'process_worker.py', 'native_bridge.py'):
            shutil.copy2(self.runtime_dir / name, root / 'runner' / name)
        readonly(root / 'runner')
        out = root / 'out'
        os.chown(out, self.uid, self.uid)
        os.chmod(out, 0o700)
        os.chmod(root / 'tmp', 0o1777)
        request = {'operation': op, 'seed': seed, 'harness_sha256': before_hash,
                   'model': self.cfg['model'], 'limits': self.cfg['limits']}
        registration = {'action': 'register', 'operation': op, 'seed': seed,
                        'limits': self.cfg['limits'], 'state_dir': str(root / 'state')}
        if case is not None:
            current = copy.deepcopy(case)
            for i, image in enumerate(current['images']):
                original = Path(image['path']).resolve()
                if file_hash(original) != image['sha256']:
                    raise ProtocolError('original image bytes changed')
                name = str(i) + original.suffix
                shutil.copy2(original, root / 'case_images' / name)
                image['path'] = '/case_images/' + name
            readonly(root / 'case_images')
            request['case'] = current
            meta = self.case_metadata[case['id']]
            registration.update(case=case, native_row=meta['native_row'], order_item=meta['order_item'],
                                ordinal=meta['ordinal'], image_annotations=meta['image_annotations'])
        if prediction is not None:
            request['prediction'] = prediction
        if feedback is not None:
            request['feedback'] = feedback
        session = control_request(self.cfg['control_socket'], registration)
        request['gateway_url'] = session['gateway_url']
        write_json(root / 'request.json', request)
        os.chmod(root / 'request.json', 0o444)
        writable_state(root / 'state', self.uid)
        started = time.monotonic()
        try:
            code, stdout, stderr = launch(root, self.runtime_dir, self.spec, uid=self.uid,
                timeout=self.cfg.get('timeout_seconds', 600), memory_bytes=self.cfg.get('memory_bytes', 8 * 2**30),
                cpus=self.cfg.get('cpus', 4))
            (work / 'stdout.log').write_bytes(stdout)
            (work / 'stderr.log').write_bytes(stderr)
            if code:
                raise ProtocolError('native process worker exited ' + str(code))
        except Exception as error:
            for key in ('stdout', 'stderr'):
                if hasattr(error, key):
                    (work / (key + '.log')).write_bytes(getattr(error, key))
            write_json(work / 'receipt.json', {'op': op, 'status': 'failed',
                       'error_type': type(error).__name__, 'seconds': time.monotonic() - started,
                       'isolation': 'chroot_uid_shared_network'})
            raise
        finally:
            usage = control_request(self.cfg['control_socket'], {'action': 'close', 'session': session['session']})
            write_json(work / 'gateway_receipt.json', usage)
        result = read_json(out / 'result.json')
        worker_result = copy.deepcopy(result)
        if usage.get('authoritative') is not True:
            raise ProtocolError('native gateway did not return authoritative usage')
        if result.get('harness_sha256') != before_hash or tree_hash(harness) != before_hash:
            raise ProtocolError('executed harness changed')
        if result.get('model') != self.cfg['model']:
            raise ProtocolError('native model changed')
        tree_manifest(root / 'state')
        result['usage'] = usage
        result['wall_seconds'] = time.monotonic() - started
        if op == 'predict':
            require_prediction(result)
        retain_success(work, root, state, worker_result,
                       {'op': op, 'seconds': result['wall_seconds'], 'usage': usage,
                        'harness_sha256': before_hash, 'isolation': 'chroot_uid_shared_network'})
        return result
