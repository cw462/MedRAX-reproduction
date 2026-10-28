# Official LLaVA-Med offline smoke

`llava_smoke.py` loads the local MedRAX tool. The historical upstream reference
is `dae30e2f136ef0b2a40885a4c335386e9ffad052`; actual commit, working-tree state and
source hashes are recorded. Edits or changed hashes do not block loading. The initial runtime candidate is
Transformers **4.45.2**, with Torch 2.2.x/CUDA, compatible Accelerate and
bitsandbytes, SentencePiece, protobuf, Pillow, Pydantic 2 and LangChain Core.
This is an implementation plus synthetic tests; actual GPU compatibility is
established only by a successful real smoke. Do not upgrade an existing known
working report environment in place.

The module imports no ML dependencies until its factory/CLI is used. The
factory is `create_llava_tool(repo, *, cache_dir, device="cuda:0")`, returning
the original BaseTool and path-free provenance. Initialize it serially before
starting API activity because temporary network/loader patches are global.

## Fixed local assets

The standard cache root must contain both directories:

```text
models--microsoft--llava-med-v1.5-mistral-7b/snapshots/91bb16c122001ddc9cf1fd36ce1dae09448943a2/
models--openai--clip-vit-large-patch14-336/snapshots/ce19dc912ca5cd21c8a653c79e251e808ccabcd1/
```

`MODEL_SPECS` provides the required file/size inventory and historical digest references: four LLaVA
shards plus tokenizer/config files, and the CLIP bin/config/preprocessor. Weight
bytes total **16,844,508,241**; 8-bit loading does not shrink the download.
Files not on the runtime allowlist, other than README/license notices, are
rejected. There is no download fallback. The original repo ID is retained for
MedRAX's `llava`/`mistral` branch; each loader is redirected to its local snapshot. This includes all three nested CLIP loaders that upstream
otherwise invokes without `cache_dir`.

Weight checksums are not verified, as requested by the user. Required weight
files must exist with their complete download sizes; config/tokenizer hashes are
recorded from actual bytes without equality requirements. The post-load stat
comparison returns an observation and does not abort on change. Hashes are
provenance records only; they do not impose an immutable-code or immutable-model rule.

## Run after assets and environment are ready

Example placeholders below are not private machine paths:

```bash
CUDA_VISIBLE_DEVICES=1 python -B experiments/llava_smoke.py \
  --repo /path/to/official/MedRAX \
  --cache-dir /path/to/fixed/hf-cache \
  --image /path/to/authorized/image.png \
  --question 'Describe the visible findings in this image.' \
  --output /path/to/private-runs/llava001 --device cuda:0
```

Exactly one CUDA device must be visible: upstream uses bare `.cuda()`. The
smoke requires an image because upstream's nominal image-optional path later
dereferences a missing image tensor. No CPU fallback or source patch is applied.
Original settings remain `load_in_8bit=True`, BF16 compute/vision, `vicuna_v1`,
`do_sample=False`, `temperature=0.2`, `max_new_tokens=500`, `use_cache=True`.

The output directory must be new. It receives `.gitignore`, a private
`answer.txt`, and `summary.json`. The summary contains hashes, versions, loader
events, timing, CUDA peaks, string-contract checks, sequence lengths and EOS
flags. It contains no original answer, question, image, identifying paths or
raw tokens. Failure returns nonzero. Neither a nonempty answer nor an EOS token
establishes clinical correctness or semantic completeness. A single-tool smoke
is not a six-tool Agent or a benchmark result.

Offline synthetic checks:

```bash
python -B -m unittest discover -s experiments -p 'test_llava_smoke.py' -v
```

Official sources: [LLaVA-Med model](https://huggingface.co/microsoft/llava-med-v1.5-mistral-7b),
[CLIP vision model](https://huggingface.co/openai/clip-vit-large-patch14-336),
[Microsoft source](https://github.com/microsoft/LLaVA-Med).
Keep the original license and research-use notices alongside downloaded assets.
