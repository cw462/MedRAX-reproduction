"""Single-image smoke of the official CheXagent tool using audited local assets.

No downloads or model API calls. Local files must be present and complete;
source hashes are recorded without imposing an immutable-hash requirement. The official tool/generation behavior
is preserved; network loads are mapped to two fixed local snapshots. This checks
execution and output shape, never medical correctness or full MedRAX reproduction.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, ExitStack, redirect_stdout, redirect_stderr
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import socket
import subprocess
import sys
import time
from unittest.mock import patch

MODEL_ID = 'StanfordAIMI/CheXagent-2-3b'
MODEL_REVISION = '8f19b53a2eceda4c33b0acec6c81fbc293ad80d0'
VISION_ID = 'StanfordAIMI/XraySigLIP__vit-l-16-siglip-384__webli'
VISION_REVISION = 'f0edbf5d90dba44edb7f4f96d8663537cb0749bf'
APPROVED_MANIFEST_SHA256 = '3277106970e3ed1ac39f943fa0410624883166e4733c16484301c457c395a8b8'
# Independently checked with git show <commit>:medrax/tools/xray_vqa.py.
# Git stores LF; Windows checkouts may have CRLF. Only that conversion is allowed.
TOOL_REVIEWED_COMMIT = 'dae30e2f136ef0b2a40885a4c335386e9ffad052'
TOOL_LF_SHA256 = '41ebc005fb0b30d5dd6debba81d020df71e5d84c4195e6afae222964f9a8e254'
TOOL_RELATIVE = 'medrax/tools/xray_vqa.py'
PYTHON_FILES = {'configuration_chexagent.py', 'modeling_chexagent.py',
                'modeling_visual.py', 'tokenization_chexagent.py'}
MAIN_FILES = PYTHON_FILES | {'README.md', 'config.json', 'generation_config.json',
    'tokenizer_config.json', 'special_tokens_map.json', 'added_tokens.json', 'vocab.json',
    'merges.txt', 'model.safetensors.index.json',
    'model-00001-of-00003.safetensors', 'model-00002-of-00003.safetensors', 'model-00003-of-00003.safetensors'}
VISION_FILES = {'README.md', 'config.json', 'preprocessor_config.json', 'tokenizer_config.json',
                'special_tokens_map.json', 'spiece.model', 'model.safetensors'}
PACKAGES = {'torch': 'torch', 'torchvision': 'torchvision', 'transformers': 'transformers',
    'tokenizers': 'tokenizers', 'accelerate': 'accelerate', 'huggingface-hub': 'huggingface_hub',
    'numpy': 'numpy', 'Pillow': 'PIL', 'safetensors': 'safetensors', 'albumentations': 'albumentations',
    'opencv-python': 'cv2', 'pyarrow': 'pyarrow', 'einops': 'einops', 'matplotlib': 'matplotlib',
    'sentencepiece': 'sentencepiece', 'protobuf': 'google.protobuf',
    'langchain-core': 'langchain_core', 'pydantic': 'pydantic'}
DEFAULT_PROMPT = 'Describe the visible findings in this chest X-ray.'


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def verify_tool_source(repo):
    """Record source hashes; source edits do not block execution."""
    raw = (Path(repo) / TOOL_RELATIVE).read_bytes()
    normalized = raw.replace(b'\r\n', b'\n')
    canonical = hashlib.sha256(normalized).hexdigest()
    try:
        commit = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], stderr=subprocess.DEVNULL, text=True).strip()
        dirty = bool(subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain'], stderr=subprocess.DEVNULL, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    return {'filename': TOOL_RELATIVE, 'sha256': hashlib.sha256(raw).hexdigest(),
            'commit': commit, 'working_tree_dirty': dirty,
            'lf_sha256': canonical, 'reviewed_upstream_commit': TOOL_REVIEWED_COMMIT,
            'normalization': 'CRLF_to_LF_only', 'hash_policy': 'record_only',
            'review_is_historical_reference': True}


def write_json(path, value):
    with Path(path).open('w', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write('\n'); handle.flush(); os.fsync(handle.fileno())


def verify_assets(snapshot, vision_snapshot, manifest_path, repo):
    """Check required local files and sizes; checksums are observational only."""
    manifest_path, repo = Path(manifest_path), Path(repo)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 1 or not isinstance(manifest.get('models'), dict):
        raise ValueError('Unsupported asset inventory schema')
    verify_tool_source(repo)
    for key, path, model_id, revision, expected in (
        ('main', Path(snapshot), MODEL_ID, MODEL_REVISION, MAIN_FILES),
        ('vision', Path(vision_snapshot), VISION_ID, VISION_REVISION, VISION_FILES)):
        spec = manifest['models'][key]
        if spec['repo_id'] != model_id or spec['revision'] != revision or set(spec['files']) != expected:
            raise ValueError('Snapshot identity or reviewed file set mismatch')
        python_files = {str(x.relative_to(path)).replace('\\', '/') for x in path.rglob('*.py')}
        if python_files != (PYTHON_FILES if key == 'main' else set()):
            raise ValueError('Unexpected custom Python files in snapshot')
        if any(path.glob('*.bin')) or any(path.glob('*.pt')) or any(path.glob('*.pth')):
            raise ValueError('Unreviewed alternative checkpoint format present')
        for name, expected_file in spec['files'].items():
            file = path / name
            if not file.is_file():
                raise FileNotFoundError('Required local asset is missing')
            is_weight = name.endswith('.safetensors')
            if is_weight and file.stat().st_size != expected_file['bytes']:
                raise ValueError('Local weight download is incomplete')
            expected_file['sha256'] = None if is_weight else sha256_file(file)
    manifest['checksum_verification'] = 'skipped_by_user'
    manifest['hash_policy'] = 'record_only'
    return manifest


def validate_request(image, prompt, max_new_tokens):
    image = Path(image).resolve()
    if not image.is_file() or image.suffix.lower() not in ('.png', '.jpg', '.jpeg'):
        raise ValueError('One existing local PNG/JPEG is required')
    if (not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 512 or '<|' in prompt
            or any(x in str(image) for x in ('<|', '|>'))):
        raise ValueError('Smoke requires a short prompt without model control tags')
    if type(max_new_tokens) is not int or not 1 <= max_new_tokens <= 512:
        raise ValueError('Smoke generation cap must be within 1..512')
    return image


@contextmanager
def block_network():
    def blocked(*args, **kwargs):
        raise RuntimeError('Network use is prohibited during this local smoke')
    with ExitStack() as stack:
        stack.enter_context(patch.object(socket.socket, 'connect', blocked))
        stack.enter_context(patch.object(socket.socket, 'connect_ex', blocked))
        stack.enter_context(patch.object(socket, 'create_connection', blocked))
        import requests
        stack.enter_context(patch.object(requests.sessions.Session, 'request', blocked))
        yield


@contextmanager
def local_loaders(transformers, snapshot, vision_snapshot, calls):
    """Rewrite only reviewed model IDs; preserve official dtype/device choices."""
    snapshot, vision_snapshot = Path(snapshot).resolve(), Path(vision_snapshot).resolve()
    with ExitStack() as stack:
        for attribute, model_id, location, custom, weights in (
            ('AutoTokenizer', MODEL_ID, snapshot, True, False),
            ('AutoModelForCausalLM', MODEL_ID, snapshot, True, True),
            ('AutoModel', VISION_ID, vision_snapshot, False, True),
            ('AutoProcessor', VISION_ID, vision_snapshot, False, False)):
            cls = getattr(transformers, attribute)
            original = cls.from_pretrained
            def guarded(name, *args, _original=original, _attribute=attribute, _id=model_id,
                        _location=location, _custom=custom, _weights=weights, **kwargs):
                if str(name) not in (_id, str(_location)):
                    raise ValueError('Unreviewed model requested')
                for field in ('revision', 'code_revision', 'force_download'):
                    if kwargs.get(field):
                        raise ValueError('Unexpected remote revision/download request')
                    kwargs.pop(field, None)
                kwargs.update(local_files_only=True, trust_remote_code=_custom)
                if _weights:
                    kwargs['use_safetensors'] = True
                calls.append({'loader': _attribute, 'repo_id': _id, 'local_files_only': True})
                return _original(str(_location), *args, **kwargs)
            stack.enter_context(patch.object(cls, 'from_pretrained', guarded))
        yield


def generation_audit(input_length, generated_ids, eos_token_id, cap):
    if type(input_length) is not int or input_length <= 0:
        raise ValueError('Invalid generation input length')
    ids = [int(token) for token in generated_ids]
    eos_ids = eos_token_id if isinstance(eos_token_id, (list, tuple)) else [eos_token_id]
    last_eos = bool(ids) and ids[-1] in eos_ids
    return {'input_tokens': input_length, 'generated_tokens': len(ids),
        'last_token_is_eos': last_eos, 'output_at_cap': len(ids) >= cap,
        'official_decode_drops_last_token': True,
        'non_eos_last_token_dropped': bool(ids) and not last_eos,
        'termination': 'eos' if last_eos else 'length_or_other'}


def validate_result(result, audit):
    if not isinstance(result, (tuple, list)) or len(result) != 2:
        raise ValueError('Unexpected official tool result')
    output, metadata = result
    if (not isinstance(output, dict) or not isinstance(metadata, dict)
            or metadata.get('analysis_status') != 'completed'
            or not isinstance(output.get('response'), str) or not output['response'].strip()):
        raise ValueError('Tool returned a failure or empty response')
    if audit.get('generate_calls') != 1 or audit.get('visual_forward_calls', 0) < 1:
        raise ValueError('No verified generation and image-encoder execution')
    return {'response_characters': len(output['response']),
        'response_sha256': hashlib.sha256(output['response'].encode()).hexdigest(),
        'tool_execution_verified': True, 'clinical_correctness_verified': False}


def package_versions():
    result = {'python': platform.python_version()}
    for package, module_name in PACKAGES.items():
        try:
            distribution = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            distribution = None
        module = sys.modules.get(module_name)
        runtime = vars(module).get('__version__') if module is not None else None
        result[package] = {'distribution': distribution, 'imported': str(runtime) if runtime is not None else None}
    return result


def execute_tool(repo, snapshot, vision_snapshot, image, prompt, cap, device, audit):
    audit['source_tool'] = verify_tool_source(repo)
    import torch
    import transformers
    from PIL import Image
    if transformers.__version__ != '4.40.0' or importlib.metadata.version('transformers') != '4.40.0':
        raise ValueError('Actual and metadata Transformers versions must both be 4.40.0')
    if not re.fullmatch(r'cuda(?::\d+)?', device) or not torch.cuda.is_available():
        raise ValueError('This smoke requires an explicit available CUDA device')
    torch.cuda.set_device(device)
    if not torch.cuda.is_bf16_supported():
        raise ValueError('BF16 is unavailable; no silent dtype fallback')
    torch.cuda.reset_peak_memory_stats(device)
    audit['gpu'] = {'name': torch.cuda.get_device_name(device),
                    'total_memory_bytes': torch.cuda.get_device_properties(device).total_memory,
                    'cuda_runtime': torch.version.cuda, 'cuda_visible_devices': os.environ.get('CUDA_VISIBLE_DEVICES')}
    spec = importlib.util.spec_from_file_location('_audited_official_chexagent_tool', Path(repo) / TOOL_RELATIVE)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    original_version = transformers.__version__
    started = time.perf_counter()
    try:
        with local_loaders(transformers, snapshot, vision_snapshot, audit['loader_calls']):
            tool = module.XRayVQATool(model_name=MODEL_ID, device=device, dtype=torch.bfloat16)
    finally:
        transformers.__version__ = original_version
    torch.cuda.synchronize(device)
    audit['initialization_seconds'] = time.perf_counter() - started
    original_generate, original_open = tool.model.generate, Image.open
    def generate(input_ids, *args, **kwargs):
        input_length = int(input_ids.shape[-1])
        if input_length + cap > int(tool.model.config.max_position_embeddings):
            raise ValueError('Input plus generation exceeds reviewed model context')
        audit['generate_calls'] += 1
        try:
            output = original_generate(input_ids, *args, **kwargs)
        except BaseException as exc:
            audit['generation_error_type'] = type(exc).__name__
            raise
        audit['generation'] = generation_audit(input_length, output[0, input_length:].tolist(),
                                               tool.model.generation_config.eos_token_id, cap)
        return output
    def image_open(file, *args, **kwargs):
        if not isinstance(file, (str, os.PathLike)) or Path(file).resolve() != image:
            raise ValueError('Image access outside the one reviewed request')
        return original_open(file, *args, **kwargs)
    def visual_hook(module, inputs, output):
        audit['visual_forward_calls'] += 1
        audit['visual_output_shape'] = list(output.shape)
        audit['visual_output_finite'] = bool(torch.isfinite(output).all().item())
        if not audit['visual_output_finite']:
            raise ValueError('Nonfinite image encoder output')
    hook = tool.model.model.visual.register_forward_hook(visual_hook)
    started = time.perf_counter()
    try:
        with patch.object(type(tool.model), 'generate', lambda self, *a, **kw: generate(*a, **kw)), \
                patch.object(Image, 'open', image_open):
            result = tool.invoke({'image_paths': [str(image)], 'prompt': prompt, 'max_new_tokens': cap})
        torch.cuda.synchronize(device)
    finally:
        hook.remove()
        audit['inference_seconds'] = time.perf_counter() - started
        audit['peak_allocated_cuda_bytes'] = torch.cuda.max_memory_allocated(device)
        audit['peak_reserved_cuda_bytes'] = torch.cuda.max_memory_reserved(device)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'snapshot', 'vision-snapshot', 'approved-source-manifest', 'image', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--prompt', default=DEFAULT_PROMPT)
    parser.add_argument('--max-new-tokens', type=int, default=64)
    parser.add_argument('--device', default='cuda:0')
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / '.gitignore').write_text('*\n', encoding='utf-8')
    began = time.perf_counter()
    summary = {'status': 'initializing', 'generate_calls': 0, 'visual_forward_calls': 0, 'loader_calls': [],
        'clinical_correctness_verified': False, 'model_revision': MODEL_REVISION, 'vision_revision': VISION_REVISION,
        'runner_sha256': sha256_file(__file__), 'max_new_tokens': args.max_new_tokens,
        'protocol_deviations': ['One local image and short bounded generation; not a QA benchmark or full Agent.',
            'Selected local snapshots and no network; hashes are recorded without version gates.',
            'Official FP32 loading then BF16 casting and final-token slicing are preserved.',
            'Transformers must actually be 4.40.0; no version-spoof compatibility claim.']}
    write_json(args.output / 'summary.json', summary)
    try:
        image = validate_request(args.image, args.prompt, args.max_new_tokens)
        manifest = verify_assets(args.snapshot, args.vision_snapshot, args.approved_source_manifest, args.repo)
        summary.update(approved_manifest_sha256=sha256_file(args.approved_source_manifest),
            source_tool_sha256=verify_tool_source(args.repo)['sha256'],
            source_tool_lf_sha256=verify_tool_source(args.repo)['lf_sha256'], image_sha256=sha256_file(image),
            prompt_sha256=hashlib.sha256(args.prompt.encode()).hexdigest(), assets=manifest['models'])
        env = {'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'HF_HUB_DISABLE_TELEMETRY': '1',
               'HF_MODULES_CACHE': str((args.output / 'hf_modules').resolve()), 'MPLBACKEND': 'Agg'}
        with patch.dict(os.environ, env), block_network(), open(os.devnull, 'w') as sink, \
                redirect_stdout(sink), redirect_stderr(sink):
            result = execute_tool(args.repo, args.snapshot, args.vision_snapshot, image, args.prompt,
                                  args.max_new_tokens, args.device, summary)
        write_json(args.output / 'raw_result.json', result)
        summary.update(validate_result(result, summary), status='completed')
    except BaseException as exc:
        summary.update(status='failed', error_type=type(exc).__name__, tool_execution_verified=False)
    finally:
        summary.update(environment=package_versions(), total_seconds=time.perf_counter() - began)
        write_json(args.output / 'summary.json', summary)
    print(json.dumps({key: summary[key] for key in ('status', 'generate_calls', 'visual_forward_calls',
                                                  'tool_execution_verified')}), flush=True)
    return 0 if summary['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
