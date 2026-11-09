## Round 2 review: one-case CUDA recovery amendment (post-fix)

**Delta verified.** I read the actual changed code and confirmed the fix is implemented, not just described:

- `local_assets/recover_cxr_online_skill_r49_cuda.py` (stage, lines 258–265) now computes `diagnostic_root`, asserts the existing diagnostic `status.json` is `completed_healthy` / `tool_invocations==1` / zero `main/meta/embedding_api_calls`, asserts the raw `exitcode` is `'0'`, then copies `status.json` and `exitcode` into `ROOT/recovery/cuda_1/diagnostic_evidence/` before writing `plan.json`.
- `local_assets/test_r49_cuda_production_recovery.py` adds `test_stage_archives_diagnostic_status_and_exit_without_production`, which asserts the archival occurs and that no `production_retry_started.json` or `services/tool_cache` is created.
- `reports/cxr_online_skill_r49_20261108/CUDA_PRODUCTION_RECOVERY_PLAN.md:31` documents the archival ("copies its existing `status.json` and `exitcode` … no diagnostic is rerun").

**Re-checked against the previously inspected integration paths:**

1. `publish_cxr_online_skill_r49.py::cuda_recovery` (lines 189–193) and `finalize_r49_report.py::cuda_recovery` (lines 439–443) read exactly `recovery/cuda_1/diagnostic_evidence/{status.json,exitcode}`. Stage now produces both, so the publication/verification path is satisfied for both the private and (via `export::recovery_records`) public trees — `recovery_records` copies `.json` and name-`exitcode` files.
2. `elapsed_s` consistency: stage reads `status.json` once and uses its `elapsed_s` in `plan['diagnostic']`; the same file is copied, so `diagnostic['elapsed_s'] == registration['diagnostic']['elapsed_s']` holds exactly. No rounding or second source.
3. The new `exitcode=='0'` assert matches the publisher's requirement and the actual diagnostic raw exit (0), and adds no digest/byte gate — it is an operational record check.
4. Archival is staged before `plan.json`, inside the guarded remote block; the new synthetic test confirms no production side effect and no cache creation. The plain `mkdir()` mirrors the existing `prior_jobs` pattern and is not a new failure mode (re-stage is already gated by `recovery_already_staged`).

**No new blocker found.** The change is narrowly scoped to the diagnostic-evidence archival; no frozen runtime/model/config, answer extraction, metric, postprocessor, memory/Skill rule, or target prediction is touched, and no byte/pixel/file/prefix digest check is added. The previously verified retry/commit/overlay/accounting bindings (`Tools.observe` == result.json, worker `original_image`, `Services`→`Tools(runtime,data,services)` for the overlay, shared `tool_failure_reason`, single-count physical accounting, raw-exit-1 vs exit-0 preservation) remain unchanged and coherent.

The one round-1 blocker is resolved exactly as specified; the supporting synthetic test and AST render are consistent with the on-disk code.

**Memory update.** Round-2: the sole blocker (unstaged `diagnostic_evidence/status.json`+`exitcode`) is fixed in `stage`, verified on disk, and closes the publish/finalize path with exact `elapsed_s` and raw-exit-0 consistency. The retry/commit/cache-overlay/accounting amendment is now scope-complete and internally coherent. Still unexecuted by design: the one fresh same-settings production tool retry and conditional original-stream resume, which remain gated on the actual new DeepSeek operational review + existing-authorization scope records and healthy GPU1/disk preconditions. This is operational readiness, not clinical validation or CUDA root-cause proof.

SCORE:9;VERDICT:ready;SCOPE_COMPLETE:true
