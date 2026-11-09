# Executed-source and reporting provenance

This directory is an explicit publication copy assembled after all three R49 datasets completed. It preserves recorded deployed sources and reporting controls; it is not a byte, pixel, file, prediction, reference or prefix-hash attestation. No source hash was calculated for this copy. The existing runtime cache naming mechanism is separate from this provenance statement.

## Recorded source locations

- Remote project: `/home/imss/cw/MedRAX_reproduction_20261027`.
- Actual CODE: `/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_online_skill_r49_20261108`.
- Actual RUN: `/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r49_20261108`.
- Local evidence mirror: `D:/MedRAX_Experiment_Artifacts/online_skill_r49_20261108`.

[Actual deployed sources](actual_code/) contain 249 payload files from the completed one-time source capture: regular immediate `experiments/*.py` files and `configs/cxr_vqa_tool_worker_gpu.json`. Source-capture started/completed receipts are preserved beside them. This includes the original R49 modules, existing runtime dependencies and the actually deployed `cxr_author_alignment.py` dependency. A source snapshot after execution does not establish the timing of every historical source file; the run protocol, original failures and operational recovery records provide the declared execution history.

The root RUN controller is preserved as [queue_controller.py](queue_controller.py), its executed protocol as [PROTOCOL.executed.json](PROTOCOL.executed.json), and its original execution-review marker as [EXECUTION_REVIEW_READY.json](EXECUTION_REVIEW_READY.json). This marker covers its original execution scope, not the later complete-results audit. Original deployed recovery controllers/wrappers and raw exit-1 history are supplied separately by the single shared recovery export. They must not be replaced with the final successful attempt alone.

Fifteen explicitly named local helper sources are copied flat in this directory. They cover the original deployment, individual dependency/tool/META/embedding/adoption continuations, isolated diagnostics, EOS policy implementation, completed-dataset pulls, once-only offline scoring and supplemental source preservation. These are sources that control transport/recovery/reporting; they are not all frozen Agent-method modules, and operational amendments remain disclosed in their individual plans and evidence.

## Completed-dataset reporting and canonical-input path failure

[reporting_provenance](reporting_provenance/) preserves the user-authorized reporting schedule, three dataset pull receipts, final-controls receipt, native scoring started/completed receipts and supplemental capture receipts. The first CheX scoring command stopped at the strict manifest/input semantic check before answer adaptation or reference scoring because the published data file used `assets/...` image aliases while the executed manifest used canonical `images/...` paths. The original started receipt, recorded pre-adaptation failure and explicitly authorized resume-start receipt are retained under [score_receipts](reporting_provenance/score_receipts/).

The actual canonical source `inputs.jsonl` was separately copied once from the recorded remote CheX data directory to the evidence mirror; both [that input file](reporting_provenance/dataset_completion/chexbench/source_data/inputs.jsonl) and its [source receipt](reporting_provenance/dataset_completion/chexbench/SOURCE_INPUT_PULL_RECEIPT.json) are preserved. This was an offline source-path correction; it did not alter R49 predictions, runtime or native public scoring rules. The completed CheX metric is reused from the successful native attempt. The historical accounting remains two native CLI attempts, one pre-adaptation failure and one completed metric calculation. SLAKE and VQA-RAD each retain their own independent once-only scoring records. No metric was recomputed by this source-copy step.

The canonical input JSONL records image paths; this provenance copy does not claim that its containing directory is a complete original-image export. The separate public evidence exporter must provide original/derived image assets and portable mappings.

## Supplemental failure evidence

The completed final-controls transfer preserved the full RUN recovery tree after all three actual child runners and the final controller exited zero. A separate local missing-only supplement then preserved the already captured CUDA 17-file diagnostic inventory, adoption 25-file failure-boundary inventory and technical metadata, and the phrase-token format mapping. Their original captures were not rerun. Existing status/exit files were left in place; missing original evidence was added without overwriting or content comparison. The [supplemental receipts](reporting_provenance/supplemental_receipts/) record the actual copy scope.

## Publication limits

[COPY_MAP.json](COPY_MAP.json) is the explicit source-to-public-destination map for this directory. The outgoing text set was checked for literal API/Hugging Face token and PEM private-key patterns; no findings were detected. Keys, model weights and unrelated local directories were not selected. This is a necessary outgoing content check, not an assurance that the clinical outputs or learned Skills are correct.

This preparation performed no new inference, embedding, diagnostic invocation, scoring, export, writer/publisher invocation or Git operation. It does not claim GitHub publication or a completed final audit. The actual final selected DeepSeek review must cover the complete results, adoption protocol, request/resource accounting, these reporting helpers and the canonical-source failure/resume proof. Earlier engineering reviews do not substitute for that final result-and-claim review.

## Final local tooling and canonical-image alias supplement

Three stable local finalization/publication sources are additionally preserved: [finalize_r49_report.py](finalize_r49_report.py), [test_r49_reporting_provenance.py](test_r49_reporting_provenance.py), and [publish_cxr_online_skill_r49.py](publish_cxr_online_skill_r49.py). They are local report, provenance-test and publication tools, not remote inference code. Copying their source did not execute them.

The actual [CANONICAL_IMAGE_ALIAS_PLAN.json](reporting_provenance/dataset_completion/chexbench/CANONICAL_IMAGE_ALIAS_PLAN.json) and [CANONICAL_IMAGE_ALIAS_RECEIPT.json](reporting_provenance/dataset_completion/chexbench/CANONICAL_IMAGE_ALIAS_RECEIPT.json) are preserved at their explicit reporting-provenance paths. They record the separate local construction of canonical image filename aliases from existing published image assets. The source input JSONL and predictions remain unchanged; no new image, pixel or file-content hash validation is asserted. These controls complement the earlier source-path repair and do not themselves replace the eventual public image export or reproduction result.

This extension adds five explicit copies, bringing the copy map to 293 source/control files, plus this provenance document and the copy map. The same necessary outgoing credential-literal check found no matches in the five added files. No export, reproduction, writer, publisher, inference or Git operation was executed by this extension.
