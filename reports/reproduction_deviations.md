# Reproduction deviations and unresolved checks

This project currently supports an adapted, restricted-tool development reproduction. It does not yet establish the paper's reported full-benchmark accuracy.

After the user's clarification, no further paid evaluation is planned before every required tool finishes download, integrity verification and real server inference. Recent small two/three-tool batches remain functional checks, not a formal baseline.

- Upstream source is pinned to `dae30e2f136ef0b2a40885a4c335386e9ffad052`. API requests use APIYi's compatible endpoint and request `gpt-4o-2024-11-20`; the provider's response name does not independently verify the underlying weights or reproduce the historical service.
- The historical baseline exposes only the classifier. The new five-case run exposes the classifier and report generator. Standalone segmentation success is separate evidence; unexecuted VQA/grounding loaders do not establish a complete six-tool Agent.
- Current paid diagnostic runs use fresh per-question conversations, two answer stages, fixed call/time limits and small preselected training samples. They do not establish the original paper's full context protocol, all-image coverage or 2,500-question result.
- Original classifier probability wording and report decoding were retained in the new two-tool batch. Classifier values are operating-point-normalized scores, not calibrated disease probabilities or localization/laterality outputs. Wording changes and report EOS/beam changes are separate factors, not hidden memory improvements.
- Source metadata has 2,500 questions and 609 case IDs; the paper describes 675 source cases. The difference is unresolved. Case IDs do not certify patient independence or absence of tool-pretraining overlap.
- All 1,346 referenced images are readable, but one question has no image; 95 questions have more than four images. The frozen validation30 includes up to four and does not validate those larger bundles.
- Two exact-image groups connect one train case to one heldout case. Original splits remain intact; new training pools exclude that train case, and an additional heldout denominator excludes the affected heldout case. One further cross-split perceptual-hash candidate is unreviewed. “Exact-overlap-excluded” does not mean proven leakage-free.
- Hash-only traces establish structured execution facts but cannot reconstruct the model reasoning or full report text. They cannot support invented clinical summaries or individual causal step credit. Task correctness, execution validity, clinical evidence and step credit remain separate.
- The first two-tool run has no complete GPU-peak measurement. Subsequent process profiling must report its scope; a device point sample is not a peak.
- The subsequent three-tool functional check measured process-local PyTorch peaks and exposed an execution failure when a response requested three tools under a two-tool limit. A third requested tool was blocked, and no final answer was produced. This must be addressed and frozen as a new protocol before formal comparisons, without rewriting the historical run.
- Inference/scoring file and process separation is implemented, but it is not operating-system-level denial of access to labels. No heldout labels or outputs have been used for selection in this V3 execution.

Every later configuration must keep its own fixed source, asset, tool-description, prompt, model, data, budget and memory hashes. Full-tool and memory comparisons require a common frozen protocol and the same resource limits across arms.
