# MedRAX reproduction and research extensions

This repository contains independent evaluation adapters, data preparation utilities and an initial structured-memory module for [MedRAX](https://github.com/bowang-lab/MedRAX). It does not include images, benchmark labels, credentials, model weights or raw run logs. Reviewed aggregate run observations are documented separately.

**Status (2026-10-27):** the official classifier, report and segmentation tools have executed on RTX 3090 GPUs. A fixed 50-question development comparison found 24/50 correct for both direct answering and a classifier-only Agent, with six improvements and six regressions; this does not reproduce the complete paper protocol. See [diagnostic results](reports/diagnostic50-2026-10-27.md), [tool observations](reports/real-smoke-2026-10-27.md) and [report decoding ablation](reports/report-decoding-2x2-2026-10-27.md). The memory module has offline boundary tests and is not yet integrated into the Agent. Research use only.

A completed ten-question [output-cap follow-up](reports/length-cap-followup-2026-10-27.md) observed no truncation at 1024 tokens; it is a selected development diagnosis, not a general accuracy improvement. [中文初步实验结论与实际耗时](reports/初步实验结论-2026-10-27.md).

## Provenance and reproducibility

The inspected upstream source was `bowang-lab/MedRAX` at commit `dae30e2f136ef0b2a40885a4c335386e9ffad052`; this commit is not established as the exact publication snapshot. Its license is Apache 2.0; a copy is preserved in `third_party/MedRAX-APACHE-2.0.txt`. Obtain the upstream source separately, inspect its requirements, and retain applicable upstream notices and model/data licensing terms. This repository does not itself redistribute the upstream source or data.

The available ChestAgentBench metadata revision inspected was `921e60440927f9893228d843c0206b755744252a`. Acquisition, access conditions, image provenance, and any API use must be independently verified before execution. The available metadata has 2,500 records and 609 case IDs; the paper describes 675 source cases. This difference is unresolved. Case-level partitioning does not establish patient independence; image content duplicates and image availability must also be checked.

## Layout

- `runner/`: early-stage agent adapter and input sanitizer.
- `data_tools/`: deterministic case grouping and label isolation.
- `experiments/`: real tool/Agent runners, budgeted paired diagnostics, offline scoring and output-cap follow-up; failures and invocation limits are logged.
- `memory_core/`: frozen, structured-rule BM25 infrastructure with case exclusion and unknown evidence/credit.
- `reports/`: reviewed aggregate observations and protocol limitations.
- `third_party/`: upstream licensing notice.

The adapter invokes the real upstream `initialize_agent` and its event stream, but has only been exercised with simulated objects. It assigns a separate thread to each question and uses one prompt; the authors' `experiments/benchmark_medrax.ipynb` retains one thread across a case's questions and uses a second letter-only request. This protocol difference must be reported rather than described as an exact reproduction. Tool status is not a medical correctness label.

## Offline checks

From this repository directory, with a compatible Python interpreter:

```sh
python -m unittest discover -s runner -p 'test_*.py' -v
python -m unittest discover -s data_tools -p 'test_*.py' -v
python -m unittest discover -s experiments -p 'test_*.py' -v
python -m unittest memory_core.test_memory_core -v
```

Unit tests use fabricated inputs and simulated objects. Real GPU and provider runs are reported separately and do not replace clinical validation or establish exact billing.

## Data handling

`data_tools/prepare_splits.py` requires local, authorized source metadata and an output directory that does not exist. It writes inference-only inputs, separately stored labels, and hashes. File separation alone is not process or operating-system access control; isolate the scorer from the inference and memory processes. Do not use test labels to build a memory pool, choose hyperparameters, or guide predictions. Avoid recording sensitive content in version control.

```sh
python data_tools/prepare_splits.py /path/to/metadata.jsonl /path/to/new-output-directory --seed example-seed
```

No dataset, output directory, weights, generated logs or credentials should be committed. Validate output permissions and data policies before real use.

## Next steps

1. Reconstruct and document the author notebook protocol, data mapping, dependencies, model versions and image availability.
2. Validate a small number of real tool calls, capture costs and failure states, and compare a properly controlled baseline with the paper.
3. Only after a credible baseline, evaluate success and failure trajectory retrieval, step-level execution and evidence quality, action selection, conflict review, and bounded memory through matched ablations. Unknown evidence and unknown credit must remain unknown; final correctness alone does not validate each step.

All future results must separate simulations from actual model runs and report model, dataset, split, tools, costs and deviations.

## Limited R0 adapter

Prepare an inference-only input containing `question_id`, `question`, and relative `images` paths. After independently reviewing the input and obtaining all required permissions and dependencies, an example interface is:

```sh
python runner/r0.py --repo /path/to/MedRAX --input /path/to/inference.jsonl --images-root /path/to/images --output-dir /path/to/new-run --model-dir /path/to/weights --model APPROVED_MODEL --tools APPROVED_TOOL_CLASS --max-cases 1 --device cuda --max-tool-calls 3 --max-model-calls 4 --max-case-seconds 180 --request-timeout-seconds 60 --max-output-tokens 512
```

This example is not verified against a real model or tool. Per-question call gates and request timeouts do not enforce a monetary limit or stop an already running tool; tool initialization can download weights and a tool may make additional requests. Check provider cost and set appropriate limits before use. Scoring, resumption and author-protocol evaluation are not yet implemented.
