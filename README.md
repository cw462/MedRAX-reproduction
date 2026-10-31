# MedRAX reproduction and research extensions

**Latest completed experiment (2026-11-01, M1 feedback memory):** D0 / E / ES scored **42/35/38 out of 60**. E corrected 2 and harmed 9; ES corrected 3 and harmed 7. ES exceeded E by 3 but neither exceeded D0. The run used 60 independent training seeds plus sequential completed-case answer feedback, 332 model requests, no technical retries, CNY 3.433236 at existing accounting rates, and 38.9 minutes. This is a feedback-memory experiment with zero medical-tool calls, not a blind generalization or medical-tool gain test. See the [full report](reports/m1_evo_memory60/README.md), [concrete errors and implementation limits](reports/m1_evo_memory60/outcome_interpretation.md), and [all 60 cases with actual injected memories](reports/m1_evo_memory60/cases/README.md). No automatic retuning or rerun follows this negative result.

**Historical evidence completed (2026-10-31):** [历史实验总索引](reports/history/README.md) now connects the retained early runs, V4/V7, [V9](reports/v9/README.md), [V10](reports/v10/README.md) and [V11 full observable messages](reports/v11/traces/README.md). Start with [为什么连续几轮没有达到目标](reports/history/failure-synthesis.md) and the [same-60-question historical comparison](reports/history/cross-version-outcomes.md). This supplement publishes saved case inputs/images, actual model/tool messages where retained, frozen knowledge/experience assets and original plans. It also corrects V7 denominator mixing, distinguishes execution recovery from correction, and documents at least one prior input exposure in the fixed-60 selection. Missing early raw messages are explicitly marked rather than reconstructed. No new inference was run for publication. Older status paragraphs below are historical snapshots; the linked completion reports establish the actual completed scope.

This repository contains independent evaluation adapters, data preparation utilities and an initial structured-memory module for [MedRAX](https://github.com/bowang-lab/MedRAX). The [V11 detailed review package](reports/v11/README.md) includes the selected public benchmark questions, options, relevant original and derived images, tool observations, model decisions and retrospective scoring, as explicitly requested for case-level error review. Credentials, model weights, unrelated private data and full raw execution logs are excluded. Published outcomes include answer information and are not suitable as a blind evaluation input.

**Detailed failure review (2026-10-31):** [为什么 V11 没有达到目标](reports/v11/failure-analysis-2026-10-31.md) connects the completed scores to the actual decisions and images. In addition to corrections being offset by harmful changes, a specific parser defect was found: malformed outer JSON could preserve the selected option while silently losing observations and `needs_followup=true`. Two S1 cases consequently missed S2 follow-up. The original predictions and scores are preserved; this retrospective finding is not a rerun or a measured gain from fixing the parser. Start with the [case and evidence index](reports/v11/README.md).

**Latest result (2026-10-31, V11 S3):** answer-blind reading of the original images, followed by anonymous matching to the same cached candidates, scored **40/60 (66.7%)**. This ties the old V10 gate, exceeds S1 by two questions and falls one below S2. S3 corrected four legal wrong answers, inherited two P0-failure recoveries and harmed five correct P0 answers: net +1 overall, but -1 excluding failure recovery. Its two roles used the same Qwen model in separate contexts. The run added 42 model calls, no tool calls, CNY 0.645396 at existing accounting rates and about 9 minutes 9 seconds. See the [completed S3 report](reports/v11-blindread60-2026-10-31.md). No further experiment has been started.

**Previous result (2026-10-30, V11 S1/S2):** cached-candidate selection and isolated scoring are complete. P0 / V10 gate (S0) / anonymous symmetric selection (S1) / one targeted follow-up (S2) scored **39/40/38/41 out of 60**. S2 corrected five legal wrong answers, recovered two missing P0 answers, and harmed five initially correct answers; the net gain excluding technical-failure recovery is zero. S2 did not reach the 42/60 minimum development target and tied the raw VKE candidate score. The two new stages used 78 additional model calls, nine crop attempts and CNY 1.000896 at existing accounting rates. See the [completed V11 report](reports/v11-selection60-2026-10-30.md) for the fixed protocol, all results and limits. No V10 inference was rerun.

**Previous result (2026-10-30, V10):** the fixed 60-question experiment and independent scoring are complete. P0/V/VK/VKE scored **39/40/39/40 out of 60**. VKE's total gain of one question includes two P0 technical-failure recoveries, one correction of a wrong legal answer, and two harmful changes. The minimum target of three additional correct answers was not met, and VKE did not outperform V. See the [completed V10 report](reports/v10-accuracy60-2026-10-30.md) for seven-category results, candidate and gate outcomes, the frozen protocol, interruptions, elapsed time, and the CNY 27.448612 ledger increment with its disclosed context-accounting difference.

**Previous result (2026-10-30, V9):** the fixed 20-question diagnostic is complete. P0/D/DK/DKB/DKC scored **14/13/14/14/13 out of 20**. No initially wrong answer was corrected, so the V9 expansion criterion was not met; the subsequent user-supplied V10 plan separately authorized the fixed sixty-question comparison. DK's one-question advantage over D comes from avoiding one harmful change, not improvement over P0. See the [completed report](reports/v9-diagnostic20-2026-10-30.md) and [detailed public results index](reports/v9/README.md) for configurations, per-question outcomes, retrieval records, evidence inventories, timing and failure counts.

**Earlier status (2026-10-29, seven-tool memory run):** the agent ran with **seven tools**
(classifier, report generator, segmentation, CheXagent VQA, LLaVA-Med, image visualizer, DICOM
processor) and `qwen3-vl-plus` as the central model. A 60-question training pool produced a
frozen pool of 60 trajectories; the same 29 validation questions were then run four times
(no memory, success retrieval, rule summary, success+failure retrieval):

| arm | answered | correct | accuracy (all 29) | accuracy (answered) |
|---|---:|---:|---:|---:|
| R0 no memory | 20/29 | 11 | 37.9% | 55.0% |
| R1 success retrieval | 27/29 | 14 | 48.3% | 51.8% |
| R2 rule summary | 26/29 | 12 | 41.4% | 46.2% |
| R3 success + failure retrieval | 28/29 | 16 | **55.2%** | 57.1% |

The raw gain comes mostly from **not exhausting the per-case call budget** (R0 failed 9 of 29
cases, R3 only 1); among answered cases the arms are nearly equal. R3 improved all 5 discordant
pairs (exact McNemar p = 0.0625) — suggestive, not conclusive. Missing tools: MAIRA-2 grounding
(runtime incompatibility) and the chest X-ray generator (no public weights).

See [the seven-tool report](reports/memory-agent-qwen-7tools-2026-10-29.md),
[the restricted two-tool run](reports/memory-agent-qwen-2026-10-28.md),
[provider facts](reports/qwen-provider-2026-10-28.md) and
[the execution checkpoint](reports/full_run_progress.md). Step credit, action selection, conflict
review and capacity updates (R4-R7) remain unimplemented; heldout and external evaluation were
not run. Research use only.

**Earlier status (2026-10-27):** the official classifier, report and segmentation tools have executed on RTX 3090 GPUs. A fixed 50-question development comparison found 24/50 correct for both direct answering and a classifier-only Agent, with six improvements and six regressions; this does not reproduce the complete paper protocol. See [diagnostic results](reports/diagnostic50-2026-10-27.md), [tool observations](reports/real-smoke-2026-10-27.md) and [report decoding ablation](reports/report-decoding-2x2-2026-10-27.md).

A completed ten-question [output-cap follow-up](reports/length-cap-followup-2026-10-27.md) observed no truncation at 1024 tokens; it is a selected development diagnosis, not a general accuracy improvement. [中文初步实验结论与实际耗时](reports/初步实验结论-2026-10-27.md).

**V3 checkpoint:** the complete image audit and a 30-case validation selection are frozen. Two/three-tool five-case batches have checked actual Agent wiring and exposed a tool-budget failure; they are **functional checks only, not the formal full-tool baseline**. See [current execution status](reports/full_run_progress.md), [data audit](reports/data-audit-v3-2026-10-27.md), [three-tool issue](reports/three-tool-functional-check-2026-10-27.md) and [shared budget](reports/budget_and_runtime.md). Full reproduction remains incomplete.

Large tool assets are still incomplete on the server, and the machine has shown in-place file
corruption ([data read integrity](reports/data-read-integrity-2026-10-28.md)); unverified weights
have not been used for inference.

## Provenance and reproducibility

The inspected upstream source was `bowang-lab/MedRAX` at commit `dae30e2f136ef0b2a40885a4c335386e9ffad052`; this commit is not established as the exact publication snapshot. Its license is Apache 2.0; a copy is preserved in `third_party/MedRAX-APACHE-2.0.txt`. Obtain the upstream source separately, inspect its requirements, and retain applicable upstream notices and model/data licensing terms. The V11 case review redistributes the selected benchmark inputs with [separate provenance and third-party data notices](reports/v11/data-provenance.md); the code license does not relicense those images or case materials.

The available ChestAgentBench metadata revision inspected was `921e60440927f9893228d843c0206b755744252a`. Acquisition, access conditions, image provenance, and any API use must be independently verified before execution. The available metadata has 2,500 records and 609 case IDs; the paper describes 675 source cases. This difference is unresolved. Case-level partitioning does not establish patient independence; image content duplicates and image availability must also be checked.

## Layout

- `runner/`: early-stage agent adapter and input sanitizer.
- `data_tools/`: deterministic case grouping and label isolation.
- `experiments/`: real tool/Agent runners, budgeted paired diagnostics, offline scoring and output-cap follow-up; failures and invocation limits are logged.
- `memory_core/`: frozen, structured-rule BM25 infrastructure with case exclusion and unknown evidence/credit.
- `memory_pipeline/`: audited structured execution-trace ingestion and frozen retrieval preparation; no real success pool or Agent memory comparison has run.
- `reports/`: completed results, per-question inputs/images, saved observable execution records, historical comparisons and protocol limitations.
- `third_party/`: upstream licensing notice.

The adapter invokes the real upstream `initialize_agent` and its event stream, but has only been exercised with simulated objects. It assigns a separate thread to each question and uses one prompt; the authors' `experiments/benchmark_medrax.ipynb` retains one thread across a case's questions and uses a second letter-only request. This protocol difference must be reported rather than described as an exact reproduction. Tool status is not a medical correctness label.

## Offline checks

From this repository directory, with a compatible Python interpreter:

```sh
python -m unittest discover -s runner -p 'test_*.py' -v
python -m unittest discover -s data_tools -p 'test_*.py' -v
python -m unittest discover -s experiments -p 'test_*.py' -v
python -m unittest memory_core.test_memory_core -v
python -m unittest memory_pipeline.test_pipeline -v
```

Unit tests use fabricated inputs and simulated objects. Real GPU and provider runs are reported separately and do not replace clinical validation or establish exact billing.

## Data handling

`data_tools/prepare_splits.py` requires local, authorized source metadata and an output directory that does not exist. It writes inference-only inputs, separately stored labels, and hashes. File separation alone is not process or operating-system access control; isolate the scorer from the inference and memory processes. Do not use test labels to build a memory pool, choose hyperparameters, or guide predictions. Avoid recording sensitive content in version control.

```sh
python data_tools/prepare_splits.py /path/to/metadata.jsonl /path/to/new-output-directory --seed example-seed
```

Only the explicitly authorized benchmark case/image and completed-experiment publication packages under `reports/` are committed. Credentials, model weights, unrelated private data and unrestricted raw run directories remain excluded. See [AGENTS.md](AGENTS.md) for the current publication scope and [historical completeness limits](reports/history/README.md).

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
