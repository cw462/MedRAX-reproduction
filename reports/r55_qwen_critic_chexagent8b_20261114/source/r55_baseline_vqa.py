"""Serve the pinned visual QA backends while evaluating their direct answers."""

import argparse
from contextlib import ExitStack, contextmanager, redirect_stdout
import importlib
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import select
import socket
import sys
import time
from unittest.mock import patch

from r55_baseline_common import DATASETS, VQA_TOOLS, bind, data_root, dataset_out, manifest_for, prediction_path, prompt_for


def socket_path(out, model):
    gpu = os.environ.get('CUDA_VISIBLE_DEVICES')
    suffix = f'-gpu{gpu}' if gpu in ('0', '1') else ''
    return Path('/tmp') / f'{out.name}-{model}{suffix}.sock'


def call_worker(out, model, image, question):
    payload = json.dumps({'image': str(image), 'question': question}).encode()
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(240)
        client.connect(str(socket_path(out, model)))
        client.sendall(payload)
        client.shutdown(socket.SHUT_WR)
        with client.makefile('rb') as response:
            return json.load(response)


def reuse_loader(stack, owner, name):
    original = getattr(owner, name)
    loaded = {}

    def reused(path, *args, **kwargs):
        key = str(path)
        if key not in loaded:
            loaded[key] = original(path, *args, **kwargs)
        return loaded[key]

    stack.enter_context(patch.object(owner, name, side_effect=reused))


@contextmanager
def accelerator_slot(root):
    from toolsets_r54 import exclusive_lock

    # The lab queue assigns one model process to one physical GPU.
    with exclusive_lock(root / 'jobs' / ('worker.gpu' + os.environ['CUDA_VISIBLE_DEVICES'] + '.lock')):
        yield


def load_short_answer_backend(path):
    spec = spec_from_file_location('_medvlm_short_answer_backend', path.resolve(strict=True))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Backend:
    def __init__(self, root, model, runtime, scratch, stack, short_answer_backend=None):
        import torch
        import transformers

        self.model, self.runtime, self.scratch = model, runtime, scratch
        self.root, self.stack = root, stack
        self.torch = torch
        self.model_root = Path(runtime['root'])
        self.repo = self.model_root / runtime['tool_repo']
        self.llava = None
        self.chexagent8 = None
        self.short_answer_backend = short_answer_backend
        if model in ('medgemma', 'medvlm_r1'):
            loader = (transformers.AutoModelForImageTextToText if model == 'medgemma'
                      else transformers.Qwen2VLForConditionalGeneration)
            reuse_loader(stack, loader, 'from_pretrained')
            reuse_loader(stack, transformers.AutoProcessor, 'from_pretrained')
        if model == 'llava_rad':
            sys.path.insert(0, runtime['llavarad_source'])
            builder = importlib.import_module('llava.model.builder')
            reuse_loader(stack, builder, 'load_pretrained_model')
        if model == 'chest_xray_expert' and runtime.get('chexagent8_snapshot'):
            from run_chexagent8_direct import CheXagent

            with accelerator_slot(root):
                self.chexagent8 = CheXagent(Path(runtime['chexagent8_snapshot']))
        elif model == 'chest_xray_expert':
            if os.environ.get('R55_REQUIRE_CHEXAGENT8') == '1':
                raise RuntimeError('CheXagent-8B snapshot path is required')
            import chexagent_smoke as smoke

            smoke.verify_tool_source(self.repo)
            spec = importlib.util.spec_from_file_location('_baseline_xray_vqa', self.repo / smoke.TOOL_RELATIVE)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            version = transformers.__version__
            try:
                with accelerator_slot(root), smoke.local_loaders(transformers, Path(runtime['chexagent_snapshot']),
                                                                Path(runtime['vision_snapshot']), []):
                    self.chexagent = module.XRayVQATool(model_name=smoke.MODEL_ID, device='cuda:0', dtype=torch.bfloat16)
            finally:
                transformers.__version__ = version
        if model == 'llava_med_qa':
            import llava_smoke as smoke
            from tool_worker_r54 import existing_snapshot

            with accelerator_slot(root), patch.object(smoke, 'inspect_snapshot', existing_snapshot):
                self.llava, _ = smoke.create_llava_tool(
                    self.repo, cache_dir=self.model_root / 'models/hf_full/hub', device='cuda:0')

    def answer(self, image, question):
        started = time.monotonic()
        with accelerator_slot(self.root), self.torch.inference_mode():
            if self.chexagent8 is not None:
                from run_chexagent8_direct import MODEL, REVISION

                answer, tokens = self.chexagent8.answer(image, question, max_new_tokens=512)
                observation = {'answer': answer, 'model': MODEL, 'revision': REVISION,
                               'backend_output_tokens': tokens}
            elif self.model == 'chest_xray_expert':
                answer, meta = self.chexagent.invoke({'image_paths': [str(image)], 'prompt': question,
                                                      'max_new_tokens': 512})
                self.check_meta(meta)
                observation = {'answer': answer['response'], 'model': 'StanfordAIMI/CheXagent-2-3b'}
            elif self.model == 'llava_med_qa':
                answer, meta = self.llava.invoke({'image_path': str(image), 'question': question})
                self.check_meta(meta)
                observation = {'answer': answer, 'model': 'microsoft/llava-med-v1.5-mistral-7b'}
            else:
                if self.short_answer_backend is None:
                    from cxr_vqa_extended_backends import execute_extended
                else:
                    execute_extended = self.short_answer_backend.execute_extended

                _, observation, _ = execute_extended({'runtime': self.runtime, 'backend': self.model,
                                                      'args': {'question': question}, 'image': str(image),
                                                      'artifact_dir': str(self.scratch)})
                if self.short_answer_backend is not None:
                    observation['answer_backend_source'] = self.short_answer_backend.__file__
        return {'status': 'completed', 'observation': observation, 'backend_compute_seconds': time.monotonic() - started,
                'clinical_correctness_verified': False}

    @staticmethod
    def check_meta(meta):
        if meta.get('analysis_status') != 'completed':
            raise RuntimeError(f'Tool returned a failure: {meta}')


def serve_request(server, backend, root):
    client, _ = server.accept()
    with client:
        try:
            with client.makefile('rb') as source:
                request = json.load(source)
            image = Path(request['image']).resolve()
            if not any(image.is_relative_to(data_root(root, dataset)) for dataset in DATASETS):
                raise ValueError('Image outside the frozen benchmark data')
            result = backend.answer(image, request['question'])
        except Exception as error:
            if isinstance(error, RuntimeError) and 'out of memory' in str(error).lower():
                raise
            result = {'status': 'failed', 'observation': None, 'error_type': type(error).__name__, 'error': str(error)[:400]}
        try:
            client.sendall(json.dumps(result, ensure_ascii=False).encode())
        except BrokenPipeError:
            pass


def direct_answer(backend, image, prompt):
    try:
        with redirect_stdout(sys.stderr):
            return backend.answer(image, prompt)
    except OSError as error:
        # Only turn a confirmed image decode failure into a failed prediction.
        from PIL import Image

        try:
            with Image.open(image) as original:
                original.load()
        except OSError as decode:
            return {'status': 'failed', 'observation': None, 'error_type': type(decode).__name__,
                    'error': str(decode)[:300], 'backend_compute_seconds': 0.0}
        raise error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('out', type=Path)
    parser.add_argument('model', choices=VQA_TOOLS)
    parser.add_argument('--direct-only', action='store_true')
    parser.add_argument('--serve-only', action='store_true')
    parser.add_argument('--short-answer-backend', type=Path)
    parser.add_argument('--chexagent8-snapshot', type=Path)
    args = parser.parse_args()
    if args.short_answer_backend and (args.model != 'medvlm_r1' or not args.direct_only):
        parser.error('--short-answer-backend requires MedVLM-R1 direct evaluation')
    bind(args.root)
    from online_memory_r49 import save_once
    from r55_baseline_common import score_dataset
    from toolsets_r54 import exclusive_lock

    out = args.out / args.model
    out.mkdir(parents=True, exist_ok=True)
    scratch = out / 'scratch'
    scratch.mkdir(exist_ok=True)
    manifests = {dataset: manifest_for(args.root, dataset) for dataset in DATASETS}
    runtime = manifests['chexbench']['runtime']['backend_config']
    if args.chexagent8_snapshot:
        runtime = dict(runtime,chexagent8_snapshot=str(args.chexagent8_snapshot.resolve(strict=True)))
    if args.direct_only and args.serve_only:
        parser.error('--direct-only and --serve-only are mutually exclusive')
    path = socket_path(args.out, args.model)
    lock = (args.root / 'jobs' / f'{args.model}.{path.stem}.lock'
            if args.serve_only else out / 'worker.lock')
    short_answer = load_short_answer_backend(args.short_answer_backend) if args.short_answer_backend else None
    datasets = ('slake', 'vqarad') if short_answer else ('slake', 'vqarad', 'chexbench')
    with exclusive_lock(lock), ExitStack() as stack:
        path.unlink(missing_ok=True)
        backend = Backend(args.root, args.model, runtime, scratch, stack, short_answer)
        server = stack.enter_context(socket.socket(socket.AF_UNIX))
        server.bind(str(path))
        stack.callback(path.unlink, missing_ok=True)
        os.chmod(path, 0o600)
        server.listen(32)
        for dataset in (() if args.serve_only else datasets):
            folder = dataset_out(args.out, args.model, dataset)
            rows = manifests[dataset]['inputs']
            data = data_root(args.root, dataset)
            for index, row in enumerate(rows, 1):
                if select.select([server], [], [], 0)[0]:
                    serve_request(server, backend, args.root)
                output = prediction_path(folder, row)
                if output.is_file():
                    continue
                image = (data / row['images'][0]).resolve()
                if not image.is_relative_to(data):
                    raise ValueError('Image outside dataset')
                prompt = prompt_for(row)
                result = direct_answer(backend, image, prompt)
                observation = result['observation']
                save_once(output, {'question_id': row['question_id'], 'arm': args.model,
                                   'raw': observation['answer'] if observation else None,
                                   'backend': observation if observation else result, 'prompt': prompt,
                                   'elapsed_s': result['backend_compute_seconds'],
                                   'calls': {'tools': 1, 'failed_tools': int(result['status'] != 'completed')}})
                if index == 1 or index % 20 == 0:
                    print(f'{args.model} {dataset} {index}/{len(rows)}', flush=True)
            score_dataset(args.root, args.out, args.model, dataset)
        if args.direct_only:
            print(f'{args.model} direct evaluation complete', flush=True)
            return
        while not (args.out / 'release_gpu_workers').is_file():
            if select.select([server], [], [], 1)[0]:
                serve_request(server, backend, args.root)


if __name__ == '__main__':
    main()
