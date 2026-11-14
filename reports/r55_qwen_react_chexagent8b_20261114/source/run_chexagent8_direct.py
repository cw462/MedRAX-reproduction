"""Evaluate the original CheXagent-8b once its pinned snapshot is available."""

import argparse
import json
from importlib.metadata import version
from pathlib import Path
import sys
import time


MODEL = 'StanfordAIMI/CheXagent-8b'
REVISION = '4934e91451945c8218c267aae9c34929a7677829'
DATASETS = ('slake', 'vqarad', 'chexbench')


def snapshot_status(snapshot):
    expected = json.loads((snapshot/'snapshot.json').read_text())
    if (expected['repo'], expected['revision']) != (MODEL, REVISION):
        raise ValueError('Unexpected CheXagent checkpoint in this run')
    sizes = {}
    for name, size in expected['shards'].items():
        path = snapshot/name
        if path.is_file():
            if path.stat().st_size != size:
                raise ValueError(f'Unexpected downloaded shard size: {name}')
            sizes[name] = size
    return {'ready': sizes, 'expected': expected['shards']}


def require_snapshot(snapshot):
    status = snapshot_status(snapshot)
    if not status['expected'] or status['ready'] != status['expected']:
        raise RuntimeError('The CheXagent-8B snapshot download is incomplete')


def wait_for_snapshot(snapshot, out):
    while True:
        status = snapshot_status(snapshot)
        (out/'assets.json').write_text(json.dumps(status)+'\n')
        if status['ready'] == status['expected']:
            return
        time.sleep(15)


class CheXagent:
    def __init__(self, snapshot):
        import torch
        from transformers import AutoModelForCausalLM, AutoProcessor, GenerationConfig

        require_snapshot(snapshot)
        self.torch = torch
        self.dtype = torch.float16
        self.processor = AutoProcessor.from_pretrained(snapshot, trust_remote_code=True, local_files_only=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            snapshot, trust_remote_code=True, local_files_only=True, use_safetensors=True,
            torch_dtype=self.dtype, device_map={'':'cuda:0'}, low_cpu_mem_usage=True,
        ).eval()
        if self.model.config.model_type != 'chexagent':
            raise ValueError('Unexpected architecture for Stanford CheXagent-8B')
        self.config = GenerationConfig.from_pretrained(snapshot, local_files_only=True)
        self.config.do_sample = False
        self.config.num_beams = 1
        self.config.pad_token_id = self.config.eos_token_id

    def answer(self, image, prompt, max_new_tokens=64):
        from PIL import Image

        with Image.open(image) as source:
            pixels = source.convert('RGB')
        inputs = self.processor(images=[pixels], text=f' USER: <s>{prompt} ASSISTANT: <s>',
                                return_tensors='pt').to(device='cuda:0', dtype=self.dtype)
        with self.torch.inference_mode():
            tokens = self.model.generate(**inputs, generation_config=self.config, max_new_tokens=max_new_tokens)[0]
        return self.processor.tokenizer.decode(tokens, skip_special_tokens=True).strip(), int(tokens.numel())


def run(root, out, snapshot, baseline_code):
    sys.path.insert(0, str(baseline_code))
    from r55_baseline_common import bind, data_root, manifest_for, prediction_path, prompt_for, score_dataset
    from score_direct_answer_rerun import evaluate

    bind(root)
    from run_cxr_vqa_toolsets import exclusive_lock
    from online_memory_r49 import read, save_once

    arm = 'chexagent_8b'
    model_out = out/arm
    model_out.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(out/'run.lock'):
        wait_for_snapshot(snapshot, out)
        model = CheXagent(snapshot)
        save_once(model_out/'protocol.json', {
            'model': MODEL, 'revision': REVISION, 'model_type': model.model.config.model_type,
            'transformers': version('transformers'), 'torch': version('torch'), 'precision': 'float16',
            'gpu': model.torch.cuda.get_device_name(0), 'do_sample': False, 'num_beams': 1, 'max_new_tokens': 64,
            'input': 'original image and frozen question with choice text when present',
            'prompt': 'project short answer prompt, wrapped in the original CheXagent-8b User/Assistant template',
            'scoring': 'original exact match and deterministic explicit-answer extraction',
        })
        print('Original CheXagent-8b loaded on CUDA', flush=True)
        for ds in DATASETS:
            manifest = manifest_for(root, ds)
            images = data_root(root, ds)
            for index, row in enumerate(manifest['inputs'], 1):
                dest = prediction_path(model_out/ds, row)
                prompt = prompt_for(row)
                if dest.exists():
                    previous = read(dest)
                    if (previous['question_id'], previous['arm'], previous['prompt']) != (row['question_id'], arm, prompt):
                        raise ValueError(f'Saved prediction differs for {dest.name}')
                    continue
                image = (images/row['images'][0]).resolve(strict=True)
                if not image.is_relative_to(images):
                    raise ValueError('Image path outside cohort')
                start = time.monotonic()
                raw, tokens = model.answer(image, prompt)
                save_once(dest, {'question_id':row['question_id'], 'arm':arm, 'model':MODEL, 'revision':REVISION,
                                 'images':row['images'], 'raw':raw, 'prompt':prompt, 'output_tokens':tokens,
                                 'elapsed_s':time.monotonic()-start,'calls':{'tools':1,'failed_tools':0}})
                if index == 1 or index % 20 == 0 or index == len(manifest['inputs']):
                    print(f'{arm} {ds} {index}/{len(manifest["inputs"])}', flush=True)
            summary = evaluate(root, out, out/'extracted_scores', arm, ds)
            print(json.dumps(summary), flush=True)
        save_once(model_out/'complete.json', {
            'arm':arm, 'model':MODEL, 'revision':REVISION,
            'datasets':{ds:score_dataset(root, out, arm, ds) for ds in DATASETS},
            'diagnostic_datasets':{ds:read(out/'extracted_scores'/arm/ds/'summary.json') for ds in DATASETS},
        })


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root','out','snapshot','baseline_code'):
        parser.add_argument(name,type=Path)
    args = parser.parse_args()
    run(args.root,args.out,args.snapshot,args.baseline_code)
