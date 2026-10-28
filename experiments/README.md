# Official classifier smoke test

## Memory-agent runs with a non-OpenAI central model (2026-10-28)

`memory_agent_eval.py` is the entry point for the R0/R1-R3 memory experiment. It runs the
audited upstream Agent with the original classifier and report tools (segmentation
optional) against a frozen question subset, records every real tool execution in the format
`memory_pipeline.compile_run` accepts, and optionally injects retrieved training
trajectories into the first prompt. It does not read labels.

```bash
python experiments/memory_agent_eval.py \
  --repo /path/to/MedRAX \
  --input /path/to/frozen_subset.jsonl --images-root /path/to/images \
  --output /path/to/new-run --ledger /path/to/provider_ledger.json \
  --inherit-ledger /path/to/api_budget_100cny.json \
  --profile qwen3-vl-plus --arm r0 \
  --classifier-checkpoint /path/to/classifier.pt --report-cache /path/to/hf_cache \
  --max-cases 60 --max-tool-calls 3 --max-model-calls 4 --max-output-tokens 1024 \
  --api-key-stdin
```

Add `--pool runs/memory_pool_v1/pool.json --top-k 3` and `--arm r1`
for success-trajectory retrieval, `r2` for the deterministic rule summary, `r3` for
failure-aware retrieval. `--plan-only` prints the protocol hash and tool versions without
opening a journal or calling the API.

Companion entry points:

- `score_memory_runs.py` — the only label reader; writes the bound outcome sidecar
  (`correct`/`incorrect`/`invalid`/`error`), never predictions or answer text.
- `compare_memory_arms.py` — paired aggregate comparison (accuracy, transitions, exact
  McNemar, retrieval hit rate) for two arms over the same questions.
- `prepare_memory_subset.py` — declares and extracts a label-blind frozen subset with
  byte-verified images.
- `provider_profile.py` / `provider_ledger.py` — frozen provider profile and the shared-cap
  conservative ledger (see [the provider report](../reports/qwen-provider-2026-10-28.md)).

`test_provider_ledger.py` covers ledger accounting, inheritance, locking and the prompt-block
renderer. These are still execution facts, not clinical evidence; `step_credit` stays null.

V3 preparation also includes isolated [LLaVA-Med](llava_smoke.md) and [MAIRA-2](maira_smoke.md) checks, `chexagent_smoke.py`, a [private-process tool bridge](worker_bridge.md), and a [validation plan-only entry](VALIDATION_PROTOCOL.md). These modules' offline tests do not establish that their large models have loaded or inferred successfully. All required tools must complete real server checks before a formal paid comparison. The [two-tool](../reports/multi-tool-first5-2026-10-27.md) and [three-tool](../reports/three-tool-functional-check-2026-10-27.md) five-case runs are retained only as functional diagnostics.

Actual classifier, report and restricted-Agent execution is recorded in [the run report](../reports/real-smoke-2026-10-27.md). Unit tests remain separate from those real runs.

For the two-model report tool, run `python experiments/report_smoke.py --repo /path/to/MedRAX --image /path/to/image.png --output /path/to/new-run --cache-dir /path/to/fixed-hf-cache --device cuda:0`. Its two pinned snapshots must already exist locally; the runner forbids downloads, verifies weight digests, preserves upstream generation parameters, and records EOS/length-limit evidence. Report text remains in the ignored output directory. The classifier-only Agent command is documented in `SINGLE_TOOL_AGENT.md`.

This script runs **one real MedRAX classification tool call**, without an LLM or cross-case memory. It is not an Agent evaluation, paper accuracy result, or validated medical diagnosis. No model has been run as part of the offline tests included here.

Use an isolated Python >=3.10 environment. The classifier directly needs compatible `torch`/`torchvision`, `torchxrayvision`, `scikit-image`, `langchain-core`, and `pydantic`; keep `numpy<2` for the inspected MedRAX revision. Install the appropriate PyTorch build only after checking the machine's driver and CUDA support. The script records installed package versions; it does not choose or claim a validated dependency lock.

Initialize only an idle GPU with sufficient memory. The official `densenet121-res224-all` model may automatically download its approximately 27.1 MB checkpoint; dependency installation can require several GB. Cache location is controlled by the installed TorchXRayVision package, not MedRAX's `model_dir`. The upstream asset listing is https://github.com/mlmed/torchxrayvision/releases/expanded_assets/v1 . Review applicable model and image terms before use.

```bash
python experiments/classifier_smoke.py \
  --repo /path/to/official/MedRAX \
  --image /path/to/authorized/8bit-chest-xray.png \
  --output /path/to/new-smoke-output \
  --device cuda:0
```

`--output` must not exist. The script neither overwrites previous outputs nor modifies the upstream checkout. `--device cpu` is supported; a CUDA request fails if CUDA is unavailable and does not silently fall back. Input must be an 8-bit PNG/JPEG with valid dimensions. This only checks image format, not whether the image is a chest radiograph, its rights, view or clinical quality. The original code uses the first channel of color images and assumes an 8-bit range, so use appropriate source images without silently changing preprocessing.

The output `summary.json` records:

- Actual Git HEAD, checkout dirty status and classifier source SHA-256.
- Image byte SHA-256, byte count, dimensions and dtype, with no image contents or input path.
- Package versions, Python/OS architecture, CUDA build, GPU model and total memory.
- Every successfully observed checkpoint loaded through `torch.load`, with public filename, SHA-256 and bytes. The hook delegates to the original function without changing arguments or values. If no checkpoint load is observed, the script fails rather than inventing provenance.
- Initialization and inference wall time, synchronized CUDA measurement and peak allocated/reserved memory for this process. CPU runs have null GPU-memory values.
- Exactly 18 finite scores in [0,1], with output labels and order matched against the loaded model, and the tool's `analysis_status` checked. These values are model outputs, not verified clinical evidence or necessarily calibrated patient probabilities.

The official tool catches some exceptions and returns a failure payload. Such payloads cause a nonzero exit here. A failed run records stage and exception type, without exception text, paths or tracebacks. Exit 0 means the tool and format checks completed; exit 1 means the run failed; exit 2 covers CLI or output-directory errors. There is no automatic retry or timeout cancellation. `summary.json` retains model scores and a stable image hash; review it for disclosure before sharing. Hashing is not anonymization.

Generated output contains its own `.gitignore` with `*`; do not force-add it. The script imports `classification.py` by its file path to avoid importing `medrax.tools.__init__` and all unrelated tools. This is an isolated tool validation, not a substitute for testing the original full Agent.

Offline checks (fabricated records, no weights or inference):

```bash
python -m unittest discover -s experiments -p 'test_*.py' -v
```
