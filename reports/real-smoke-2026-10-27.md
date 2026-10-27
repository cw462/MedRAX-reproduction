# Real execution observations — 2026-10-27

This report records actual execution, not paper accuracy or a demonstrated research improvement. Raw images, reports, predictions and API traces remain outside Git.

## Observed runs

| Run | Observation | Scope |
|---|---|---|
| Official DenseNet classifier | 18 expected finite scores in [0,1]; initialization 0.374 s; inference 0.843 s; peak allocated CUDA memory 172,478,464 bytes | One public benchmark image, RTX 3090; output contract only |
| Restricted official Agent | 5/5 questions completed with a valid final option and one verified classifier return each; 15 model requests; 17,995 input + 2,369 output = 20,364 reported tokens | Five different memory-train cases, each with its complete one-image input; no answer scoring in this runner |
| Official report tool | Both findings and impression models loaded; both generate calls executed; two nonempty text sections; initialization 2.145 s; inference 1.076 s; peak allocated CUDA memory 560,945,152 bytes | One image; offline fixed assets; report structure is not semantic completeness or medical correctness |
| Official ChestX-Det segmentation tool | One real 14-channel forward; 12 nonempty structure metric sets and 2 empty model masks; initialization 0.684 s; full tool invocation 7.695 s; peak allocated CUDA memory 503,964,160 bytes | One image, second RTX 3090; invocation timing includes visualization and audit. The assumed 0.2 mm pixel spacing is not calibrated physical measurement |

The five Agent question times were 13.01, 21.60, 20.99, 21.47 and 22.25 seconds (sum 99.32 s, mean 19.86 s). Timing excludes prior downloads/installations and is not a throughput benchmark. Every Agent question had 3 model calls and 1 classifier call. Provider usage was present for all 15 calls; actual billed cost was not retrieved.

Sample selection was fixed input order, first five distinct memory-train cases with one image, before consulting any reference answer. This is not a representative or stratified accuracy sample. Each inference record had only question_id, question and images. No labels or explanations were sent to the model. File separation is not operating-system isolation.

## Provenance

- Upstream commit: `dae30e2f136ef0b2a40885a4c335386e9ffad052`; upstream working tree clean. This is not established as the publication snapshot.
- Dataset metadata revision: `921e60440927f9893228d843c0206b755744252a`.
- Requested model: `gpt-4o-2024-11-20`; OpenAI-compatible provider: `https://api.apiyi.com/v1`. A returned proxy model ID does not authenticate its underlying model.
- Classifier: TorchXRayVision 1.3.5, `densenet121-res224-all`, checkpoint SHA256 `56524913dd16a906422e8d8b66a7a5c46be1d82eb7ac012d8103776f1aa68899`.
- Report findings revision: `5bed2b551d7cadfe08f0757d29cc054dc1adb60d`; impression revision: `dd9e8a79659426980e8197657c81d2b9d443ddd0`. The runner pins and checks both Safetensors SHA256 values before loading.
- Python 3.10.18, PyTorch 2.2.1 / CUDA 12.1, torchvision 0.17.1; actual imported NumPy 1.26.4; LangChain Core 0.3.86, LangGraph 0.2.76, langchain-openai 0.2.14, OpenAI Python 1.109.1, Pydantic 2.14.1. Report runner used Transformers 4.45.2.

The project venv reused a pre-existing Python/CUDA environment through system-site-packages. It did not alter that environment. Unrelated inherited packages have dependency conflicts, and duplicate NumPy distribution metadata reports 1.26.0 although imported code reports 1.26.4. Initial smoke manifests recorded metadata versions; newer runners separately record imported versions. This is a verified limited execution environment, not a clean, fully isolated rebuild of all MedRAX dependencies.

## Problems already exposed

1. Official report arguments contain `beam_width=2`, but the actual GenerationConfig has `num_beams=1`. Therefore the run did **not** perform two-beam search. Upstream parameters were preserved for this test.
2. Both report generations reached `max_length=128`; GenerationConfig had no EOS token ID. Nonempty findings/impression text alone cannot establish natural termination or semantic completeness. This warrants a separately labeled parameter ablation, not a silent upstream change.
3. Unbounded modern dependency resolution selected an incompatible ormsgpack source candidate for Python 3.10. Pinning `ormsgpack==1.12.2` with wheel-only installation resolved that blocker.
4. An imported-module version can differ from distribution metadata in a reused environment. Reproducibility records must retain both, and the full protocol eventually needs a clean dependency environment.

## Protocol limits and next diagnosis

The Agent uses only the classifier, rather than the paper's full tool set. It dynamically imports official files to avoid loading every tool, preserves the official system prompt, adapts the notebook's first prompt, and runs the author's letter-only second phase. Each question gets a fresh thread; the author notebook shares a thread within a case. Images are embedded rather than loaded from remote URLs. Limits: 4 model calls, 2 tool calls, 512 output tokens per request, request timeout 60 s, call-boundary deadline 180 s, no provider retries. These differ from the paper protocol.

The report and segmentation tools are validated separately, not available to these five Agent runs. Three other paper tools remain unvalidated here; MAIRA-2 has model access requirements and larger VQA tools need separate compatibility work.

The subsequent fixed 50-case development comparison has completed: both matched two-stage direct vision answering and the restricted Agent answered 24/50 correctly, with six improvements and six regressions. [The diagnostic report](diagnostic50-2026-10-27.md) records invalid outputs, finish reasons, paired uncertainty and conservative budget accounting. Test-set labels were not involved. These development observations motivate a separately declared output-cap follow-up; a memory or tool-policy intervention still requires its own matched evaluation.

`memory_core` is currently a preset structured-rule library with BM25 filtering, verified split metadata, same-case exclusion and frozen snapshots. It has no learned summaries, real experience extraction, numerical step credit or Agent integration. Unknown medical evidence remains unknown and credit remains null.
