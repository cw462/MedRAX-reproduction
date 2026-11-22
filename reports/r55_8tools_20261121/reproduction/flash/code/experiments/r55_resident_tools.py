"""AutoDL resident workers using the tool backends' original model loaders."""

import argparse
from contextlib import redirect_stderr, redirect_stdout
import fcntl
import io
import json
import os
from pathlib import Path
import socket
import socketserver
import sys
import time
import traceback
from unittest.mock import patch


EXTENDED_MODELS = {
    'llava-rad': ('llava_rad', ('llavarad_source', 'llavarad_model', 'vicuna_model', 'biomedbert_config')),
    'medgemma': ('medgemma', ('medgemma_model',)),
    'medvlm-r1': ('medvlm_r1', ('medvlm_model',)),
}
FAMILIES = {
    'chest_xray_expert': 'chexagent',
    'maira2_grounded_report': 'maira',
    'xray_phrase_grounding': 'maira',
    'llava_med_qa': 'llava-med',
    **{tool: name for name, (tool, _) in EXTENDED_MODELS.items()},
}
BASELINE = 'chexagent8_11tools_open_budget'
MEMORY_ARMS = ('M2', 'M3', 'M7', 'M9')
DATASETS = ('slake', 'vqarad', 'chexbench')
INDIVIDUAL_MEMORY_ROUTES = ('llava-med', *EXTENDED_MODELS)


def memory_marker_name(family):
    return f'{family}.memory-enabled.json' if family in INDIVIDUAL_MEMORY_ROUTES else 'memory.enabled.json'


def socket_path(control, family):
    # AF_UNIX limits names to 108 bytes. Keep the sockets below a private directory.
    return control / 'sockets' / (family + '.sock')


def request_worker(path, payload):
    with socket.socket(socket.AF_UNIX) as conn:
        conn.settimeout(590)
        try:
            conn.connect(str(path))
        except (FileNotFoundError, ConnectionRefusedError):
            return None
        conn.sendall(json.dumps(payload).encode())
        conn.shutdown(socket.SHUT_WR)
        with conn.makefile('rb') as response:
            return json.load(response)


def request_maira(control, wire, request):
    workers = (('maira', wire), ('maira-replica', wire / 'replica'))
    deadline = time.monotonic() + 580
    while True:
        busy = False
        for name, address in workers:
            with (control / (name + '.route.lock')).open('a') as lease:
                if name == 'maira-replica' and not (control / (name + '.enabled.json')).is_file():
                    continue
                try:
                    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    busy = True
                    continue
                reply = request_worker(socket_path(address, 'maira'), {'request': request})
                if reply is not None:
                    return reply
        if not busy:
            return None
        if time.monotonic() >= deadline:
            raise TimeoutError('Timed out waiting for a resident MAIRA worker')
        time.sleep(0.03)


def resident_route(request, root):
    family = FAMILIES.get(request['backend'])
    if not family:
        return False
    run_root = Path(root).resolve()
    root = Path('/root/autodl-tmp/medrax_r55_top4_full848_chexagent8_20261114')
    control = root / 'jobs/resident-tools'
    baseline = root.with_name('medrax_r55_top4_full848') / BASELINE
    artifacts = Path(request['artifact_dir']).resolve()
    in_baseline = artifacts.is_relative_to(baseline / 'api')
    in_memory = any(artifacts.is_relative_to((root / 'generation' / arm / dataset / 'services/tool_cache').resolve())
                    for arm in MEMORY_ARMS for dataset in DATASETS)
    in_memory = in_memory or artifacts.is_relative_to(Path('/dev/shm/r55_autodl_four_20261115_001'))
    in_memory = in_memory or any(artifacts.is_relative_to(Path(path)) for path in ('/root/autodl-tmp/medrax_r55_top4_full848/r55_autodl_deepseek41_main_20261115_001/persistent_generation/M2', '/dev/shm/r55_autodl_deepseek41_main_20261115_001/generation/M5', '/dev/shm/r55_autodl_deepseek41_main_20261115_001/flash_react/api'))
    in_memory = in_memory or artifacts.is_relative_to(run_root)
    memory_marker = control / memory_marker_name(family)
    allowed = (in_baseline and family not in EXTENDED_MODELS) or (in_memory and memory_marker.is_file())
    enabled = control / (family + '.enabled.json')
    if not allowed or not enabled.is_file():
        return False
    wire = Path(json.loads((control / 'socket-root.json').read_bytes())['root'])
    tick = time.monotonic()
    if family == 'maira':
        reply = request_maira(control, wire, request)
    elif family in INDIVIDUAL_MEMORY_ROUTES:
        with (control / (family + '.route.lock')).open('a') as lease:
            fcntl.flock(lease, fcntl.LOCK_EX)
            try:
                live_receipt = json.loads(enabled.read_bytes())
                if in_memory:
                    checked = json.loads(memory_marker.read_bytes())
                    if any(checked[k] != live_receipt[k] for k in ('pid', 'start_ticks')):
                        return False
            except FileNotFoundError:
                return False
            reply = request_worker(socket_path(wire, family), {'request': request})
    else:
        reply = request_worker(socket_path(wire, family), {'request': request})
    if reply is None or (family in INDIVIDUAL_MEMORY_ROUTES and reply['pid'] != live_receipt['pid']):
        return False
    result = reply['result']
    (artifacts.parent / 'backend_route.json').write_text(json.dumps({
        'family': family, 'worker_pid': reply['pid'], 'server_seconds': reply['seconds'],
        'client_seconds': time.monotonic() - tick,
    }) + '\n', encoding='utf-8')
    sys.stderr.write(reply['stderr'])
    print('CXR_VQA_RESULT=' + json.dumps(result, ensure_ascii=False))
    return True


class Resident:
    def __init__(self, family, cfg, control):
        self.family = family
        self.cfg = cfg
        if family == 'chexagent':
            from run_chexagent8_direct import CheXagent

            self.snapshot = Path(cfg['chexagent8_snapshot'])
            self.model = CheXagent(self.snapshot)
        elif family == 'llava-med':
            import llava_smoke
            from tool_worker_r54 import existing_snapshot

            root = Path(cfg['root'])
            with patch.object(llava_smoke, 'inspect_snapshot', existing_snapshot):
                self.llava = llava_smoke.create_llava_tool(root / cfg['tool_repo'],
                                                          cache_dir=root / 'models/hf_full/hub', device='cuda:0')
        elif family in EXTENDED_MODELS:
            import cxr_vqa_extended_backends as extended

            tool, keys = EXTENDED_MODELS[family]
            self.loader_name = 'load_' + tool
            self.loader_bindings = {key: cfg[key] for key in keys}
            self.assets = getattr(extended, self.loader_name)(cfg)
        else:
            import maira_smoke
            from cxr_vqa_tool_worker import existing_snapshot

            root = Path(cfg['root'])
            with patch.object(maira_smoke.audit, 'inspect_snapshot', existing_snapshot):
                self.tool, self.provenance = maira_smoke.create_maira_tool(
                    root / cfg['tool_repo'], cache_dir=root / 'models/hf_full/hub',
                    temp_dir=control / ('maira-runtime-' + str(os.getpid())), device='cuda:0',
                )

    def backend(self, request):
        from tool_worker_r54 import execute

        if self.family == 'chexagent':
            import run_chexagent8_direct

            if Path(request['runtime']['chexagent8_snapshot']) != self.snapshot:
                raise ValueError('CheXagent checkpoint changed')
            with patch.object(run_chexagent8_direct, 'CheXagent', return_value=self.model):
                return execute(request)

        cfg = request['runtime']
        if (cfg['root'], cfg['tool_repo']) != (self.cfg['root'], self.cfg['tool_repo']):
            raise ValueError('Tool loader source changed')
        if self.family == 'llava-med':
            import llava_smoke

            with patch.object(llava_smoke, 'create_llava_tool', return_value=self.llava):
                return execute(request)
        if self.family in EXTENDED_MODELS:
            import cxr_vqa_extended_backends as extended

            if any(cfg.get(key) != value for key, value in self.loader_bindings.items()):
                raise ValueError('Tool checkpoint or loader source changed')
            with patch.object(extended, self.loader_name, return_value=self.assets):
                return execute(request)

        import maira_smoke

        original_dir = self.tool.temp_dir

        def reuse(repo, *, cache_dir, temp_dir, device):
            root = Path(self.cfg['root'])
            if (repo, cache_dir, device) != (root / self.cfg['tool_repo'], root / 'models/hf_full/hub', 'cuda:0'):
                raise ValueError('MAIRA loader parameters changed')
            # Its official adapter records the overlay path in the observation.
            self.tool.temp_dir = temp_dir / 'overlays'
            self.tool.temp_dir.mkdir(parents=True, exist_ok=False)
            return self.tool, self.provenance

        try:
            with patch.object(maira_smoke, 'create_maira_tool', side_effect=reuse):
                return execute(request)
        finally:
            self.tool.temp_dir = original_dir

    def run(self, request):
        import torch
        from tool_worker_r54 import inference_events

        if FAMILIES.get(request['backend']) != self.family:
            raise ValueError('Tool does not belong to this worker')
        events = []
        log = io.StringIO()
        tick = time.monotonic()
        torch.cuda.reset_peak_memory_stats()
        with redirect_stdout(log), redirect_stderr(log):
            try:
                with inference_events(request, events):
                    result = self.backend(request)
            except Exception as exc:
                traceback.print_exc()
                result = {'status': 'failed', 'observation': None,
                          'error_type': type(exc).__name__, 'error': str(exc)[:300]}
        result.update(actual_model_events=events, cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'),
                      adapter_revision='cxr-vqa-existing-snapshot-binding-3')
        if self.family in EXTENDED_MODELS:
            torch.cuda.empty_cache()
        return {'result': result, 'pid': os.getpid(), 'seconds': time.monotonic() - tick, 'stderr': log.getvalue()}


def serve(root, control, wire, family):
    from run_top4_priority import shared_gpu_slot

    manifest = json.loads((root / 'manifests/M2/slake.json').read_bytes())
    cfg = manifest['runtime']['backend_config']
    with shared_gpu_slot(root):
        started = time.monotonic()
        resident = Resident(family, cfg, control)
        ready = {'ready': family, 'pid': os.getpid(), 'loader_seconds': time.monotonic() - started}
        if family in EXTENDED_MODELS:
            import torch

            torch.cuda.empty_cache()
            ready['model_mib'] = round(torch.cuda.memory_allocated() / (1024 ** 2))

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            call = json.load(self.rfile)
            if 'request' in call:
                response = resident.run(call['request'])
            else:
                response = {'pid': os.getpid(), 'family': family}
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode())

    path = socket_path(wire, family)
    with socketserver.UnixStreamServer(str(path), Handler) as server:
        path.chmod(0o600)
        print(json.dumps(ready), flush=True)
        server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('control', type=Path)
    parser.add_argument('wire', type=Path)
    parser.add_argument('family', choices=sorted(set(FAMILIES.values())))
    args = parser.parse_args()
    sys.path.extend((str(args.root / 'code/experiments'), str(args.root / 'bin')))
    serve(args.root, args.control, args.wire, args.family)




def route(request, root):
    if request['backend'] not in FAMILIES:
        return False
    from native_resident_pool import dispatch
    run_root = Path(os.environ['R55_8TOOLS_ROOT'])
    reply = dispatch({'run_root': str(run_root), 'resident_control': os.environ['R55_RESIDENT_ROOT']}, request)
    sys.stderr.write(reply['stderr'])
    print('CXR_VQA_RESULT=' + json.dumps(reply['result'], ensure_ascii=False))
    return True
