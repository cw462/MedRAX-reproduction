# Official MAIRA-2 grounding offline smoke

This runner uses the local synchronous MedRAX grounding tool. Historical source
reference: `dae30e2f136ef0b2a40885a4c335386e9ffad052`. Its actual source/commit
metadata is recorded; changes no longer block loading. It requires an authorized, complete
local snapshot of `microsoft/maira-2` revision
`795a2b1cd4a310624b4e3d14b5a23e41fd273deb`. It never requests credentials,
accepts access conditions, downloads a file, or calls an external API.

`maira_smoke.py` and its tests establish an audited implementation. They do not
establish real model compatibility or medical validity; those require the real
smoke and independent evaluation respectively.

## Assets and runtime

Use a standard cache containing:

```text
models--microsoft--maira-2/snapshots/795a2b1cd4a310624b4e3d14b5a23e41fd273deb/
```

The required local inventory covers **22 files / 27,525,118,360 bytes**, including six safetensors
shards, all configuration/tokenizer files, chat template, license notices, and
the three reviewed custom Python modules. The complete checkpoint includes
the DINOv2 image backbone and Llama language model. No separate RAD-DINO or
Vicuna checkpoint is needed for the reviewed code path.

Use a separate environment with **Transformers 4.51.3**, its compatible
tokenizers/Hub versions, Torch 2.2.x and paired torchvision, compatible
Accelerate/bitsandbytes, NumPy, Pillow, SentencePiece, protobuf, matplotlib,
Pydantic and LangChain Core. Do not replace the report/LLaVA 4.45.2 environment.
The actual GPU peak and quantized compatibility remain to be measured.

The loader retains the original `load_in_8bit=True`, `load_in_4bit=False` and
does not add a dtype override. All model/processor loads are local-only;
pickle fallback is denied. The reviewed custom classes execute from a new
private HF dynamic-module cache, and their actual loaded source digests are recorded without equality requirements.
Initialize in a fresh worker with exactly one visible CUDA GPU. Loader/network
patches are process-wide, so initialization must precede unrelated API work.

The user requested removal of immutable-hash rules. Weight checksums are skipped;
file existence and complete weight download sizes still determine readiness.
Small-file and source hashes are recorded as provenance only. A changed code,
configuration or model digest does not itself stop the run.

## CLI and factory

Generic path placeholders:

```bash
CUDA_VISIBLE_DEVICES=1 python -B experiments/maira_smoke.py \
  --repo /path/to/official/MedRAX \
  --cache-dir /path/to/authorized/fixed-cache \
  --image /path/to/authorized/image.png \
  --phrase 'Pleural effusion' \
  --output /path/to/private-runs/maira001 --device cuda:0
```

The inference phrase must come from the visible task, never a reference label.
The output directory must be new. `tool_result.private.json` preserves the
unaltered original return, including failed returns; overlays and cached custom
code remain below the ignored private output. `summary.json` contains hashes,
counts, versions, geometry checks, actual feature/generation events, timings,
and CUDA memory peaks. It contains no original phrase/report, original boxes,
identifying paths, pixels, or token sequence. Failure returns nonzero.

Factory: `create_maira_tool(repo, *, cache_dir, temp_dir, device="cuda:0")`
returns `(original_tool, safe_provenance)` without inference. `temp_dir` must
be new; overlays are written to `temp_dir/overlays`. A worker must call
`validate_image(image_path)` before each invocation: the original processor
divides by zero on constant grayscale images. Use **synchronous** `tool.invoke`
with the original `max_new_tokens=300`; upstream `_arun` has a positional
argument bug that this runner does not patch. Call
`validate_observation(result, artifact_dir=overlays, image_size=[width,height])`
for the path-free execution/geometry summary. Forward the unchanged tool
result to the Agent, not this summary as a replacement prediction.

The smoke audits a real projected feature tensor of `[1,1369,4096]`, the image
token count, input-prefix preservation, generated-token count, EOS/cap flags,
and conversion output type. The config's older `image_seq_length=576` is
recorded without replacing the processor's actual 518/14 geometry. Plaintext
or malformed grounded text may make the original tool fail; the failure is
retained rather than recast as an empty successful prediction.

`completed_no_finding` means no box was returned. It is never a verified
negative clinical label. Coordinate checks and nonempty boxes likewise do not
establish clinical correctness. PNG checks in the safe observation helper
cover file location/signature/hash, not visual quality or lesion correctness.

```bash
python -B -m unittest discover -s experiments -p 'test_maira_smoke.py' -v
```

Sources: [official model and access terms](https://huggingface.co/microsoft/maira-2),
[Transformers 4.51.3 LLaVA](https://github.com/huggingface/transformers/blob/v4.51.3/src/transformers/models/llava/modeling_llava.py),
[DINOv2 implementation](https://github.com/huggingface/transformers/blob/v4.51.3/src/transformers/models/dinov2/modeling_dinov2.py).
