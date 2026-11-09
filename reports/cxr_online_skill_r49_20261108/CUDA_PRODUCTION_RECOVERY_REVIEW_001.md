## Review: one-case CUDA production recovery amendment

**Scope.** Reviewed only the new recovery/cache/accounting amendment: `recover_cxr_online_skill_r49_cuda.py`, the targeted `score_online_skill_r49.py` functions (`registered_cuda_retry`, `tool_attempt_accounting`, `check_semantics`, `resources`), `export_online_skill_r49.py::recovery_records/export`, `verify_public_online_skill_r49.py`, and `publish_cxr_online_skill_r49.py::cuda_recovery/dependency_recovery/ready`. Readonly; no execution, no targets/references/Skill inspection.

**What checks out.** I traced the real integration points against frozen source rather than trusting the synthetic tests:

- `Tools.observe` (run_cxr_vqa_toolsets.py:395) writes `result.json` equal to its returned value, so `commit_healthy_retry`'s closed-cache and `registered_cuda_retry`'s `replacement==healthy` equality checks are coherent. `cxr_vqa_tool_worker.py` emits `original_image = str(image)` with the resolved path, so the `commit_healthy_retry`/scorer identity and image binding (`str((data_root/row['images'][i-1]).resolve()) == registration['original_image']`) are consistent.
- The wrapper target is correct: `Services` builds `Tools(self.runtime, data, self.out)` with `out = a.out/'services'` (skill_services_r49.py:89), matching the overlay's `services_root`; patching `base.Tools.call` reaches the R49 executor.
- `tool_failure_reason` is shared (cxr_image_memory_r44 → primitives → scorer/recovery), so the failed/healthy predicates agree.
- Accounting is single-counted correctly: `physical = active + [original_result]`; the healthy retry is in `active`, the failed old cache is added once, and the diagnostic is reported separately with `included_in_production_attempts=False`. No retry double-count, cache hits excluded from physical attempts.
- Export/publish correctly preserve raw-exit-1 history vs current-exit-0 (`prior_generation.exitcode`/`prior_jobs/*` vs `controller.*.exitcode`), and `recovery_records` copies `exitcode`-named files and `.exitcode` files.

**Genuine blocker (one).** The publication/verification gates require diagnostic evidence that nothing stages.

- `publish_cxr_online_skill_r49.py::cuda_recovery()` reads `recovery/'diagnostic_evidence/status.json'` and `.../exitcode` (lines 189–193).
- `finalize_r49_report.py::cuda_recovery()` reads the same under both `private` and `published` roots (lines 439–443).
- `recover_cxr_online_skill_r49_cuda.py::stage` only *reads* `ROOT/runs/online_skill_r49_cuda_diagnostic_20261108/attempt_1/status.json` to embed `elapsed_s` into `plan.json`; it never copies `status.json`/`exitcode` into `ROOT/recovery/cuda_1/diagnostic_evidence/`, and no other automated step does. `export::recovery_records` only copies what already exists under `ROOT/recovery`.

Consequence: after a successful retry and full three-dataset completion, `ready()`/publication fails on the missing `diagnostic_evidence` files. The evidence itself exists (`local_assets/r49_cuda_failure_20261108/isolated_diagnostic_attempt_1/{status.json,exitcode}`; `status.json` has separate zero `main/meta/embedding_api_calls` fields and `elapsed_s=10.615350947948173`, matching the scorer/publish predicates).

**Exact minimal fix.** In `stage`, copy the diagnostic records into the recovery archive:

```python
(a/'diagnostic_evidence').mkdir()
shutil.copyfile(Path(ROOT)/'runs/online_skill_r49_cuda_diagnostic_20261108/attempt_1/status.json',
                a/'diagnostic_evidence/status.json')
shutil.copyfile(Path(ROOT)/'runs/online_skill_r49_cuda_diagnostic_20261108/attempt_1/exitcode',
                a/'diagnostic_evidence/exitcode')
```

(gated by the same `recovery_already_staged` assertion). This keeps the amendment's no-new-byte/hash/prediction-gate property and closes the only concrete integration gap.

**Memory update.** R49 CUDA amendment is coherent for the retry/commit/overlay/accounting path; all cross-module identity, cache-key, and physical-attempt bindings verified against frozen source. One remaining gap: diagnostic `status.json`+`exitcode` must be staged into `recovery/cuda_1/diagnostic_evidence/` by the helper (currently only `elapsed_s` is propagated). Everything else is ready; retry remains unexecuted (40 stopped, q41 no answer/truth feedback), and the diagnostic output is correctly never reused as production evidence.

SCORE:7;VERDICT:not ready;SCOPE_COMPLETE:false
