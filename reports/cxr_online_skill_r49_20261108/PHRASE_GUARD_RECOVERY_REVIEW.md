I've reviewed this production EOS-policy amendment against the actual sources (Read only; no execution/network/API/GPU; no target/reward/reference data, clinical Skill/candidate text, credentials, or run payloads opened).

## Verdict

**Score: 9 / 10**
**VERDICT: ready**
**SCOPE_COMPLETE: true**

Scope is **engineering execution only** — a declared MAIRA generation-policy change plus one known-failure retry and its accounting/export/publication controls. It is not clinical/result correctness, causal-Skill effect, SOTA, or integrity certification.

## What I verified at source level

**EOS-only score change / prompt exclusion (`UnclosedTagEOSGuard`)**
- `__call__` validates tensor shapes, computes `open_depths` over only `input_ids[row, prompt_length:]` (prompt tags excluded), clones `scores` only when masking, sets only `scores[row, eos]==-inf`, never mutates the caller's tensor, and raises if masking leaves no finite non-EOS token. `open_depths` is an independent depth counter (explicitly not a full grammar validator). Tests confirm EOS-only change, prompt-tag exclusion, no token insertion/force-close, and the no-finite-token stop.

**Hook binding / composition (`install_eos_guard`)**
- `install_eos_guard` captures `original = tool.model.generate` *after* `capture_tool` has already bound `observed_generate`, so the chain is `guarded_generate → observed_generate → inference_events.generate → GenerationMixin.generate`; the `LogitsProcessorList([*prior, guard])` reaches the real `generate` while token/event capture still fire. `validate_original_profile` pins tag IDs, EOS id, non-special tags, greedy/no-beams/no-forced-EOS, 8-bit/f16/cuda:0. `finally` restores generate/trace/processor.

**Once-only / known-retry / fail-stop**
- Stage asserts `not a.exists()`; launch uses `.queue_launch.lock` + `controller.started.json` absence; `write_once` is idempotent-or-raise. `policy_observe` returns `started_unknown` (stop) on a started-without-result cache and refuses a second factory. The known q169 case verifies the original selection/identity unchanged, uses `OLD_KEY` (identity) with `_phrase_guard_1` suffix, requires full `generation_policy_evidence` (policy_id, capture_complete, EOS2 termination, policy_healthy, `final_generated_token_ids==[2]`, one call), and `commit_known_retry` atomically replaces the active selection only after a healthy guarded result; a failed/unknown retry stops and never registers.

**Exact alias / protected cache / all-future consistency**
- Legacy healthy caches/selections reuse the frozen `Tools.call` identity+key (image sha256 is the unchanged naming path, not a new integrity gate) and are labeled `legacy_healthy_cache`; new physical MAIRA calls use `key+'_phrase_guard_1'` with `guarded_new`/`guarded_cache` provenance. `ensure_amendment` freezes per-dataset `legacy_cache_keys_at_activation`/`protected_existing_selections` (168/0/0 boundary) and the scorer `validate_phrase_guard_amendment` rejects reclassification/recomputation, undeclared post-activation selections, and masked-step/token/factory tampering.

**Wrapper reachability**
- `RESUME_RUNNER` patches `base.Tools.call` with `guarded_tools_call` then delegates to `embedding_arrearage_1/resume_runner.py --dataset …`, so the CUDA `registered_call_overlay` sits *above* the phrase overlay and both compose; the prior embedding/fields/META/CUDA chains and cached paid calls are retained. The generated-stage test confirms the chain reaches the existing wrapper with correct argv.

**Accounting / public portable proof / gates**
- `tool_attempt_accounting` unions active healthy caches + CUDA-original + phrase-original failures exactly once; `resources` reports `registered_failed_historical_attempts=2` with distinct `registered_cuda_failed_attempts=1`/`registered_phrase_failed_attempts=1`, and the isolated 23.471671s failed diagnostic is separate non-additive (`included_in_production_attempts=False`, hardware cost unknown). Export/verify/publish/finalize add `phrase_guard_1` to `known_repair`, disclose `registered_phrase_guard_retry`/`declared_phrase_generation_policy_amendment`, require `same_generation_settings=false`/`same_MAIRA_generation_settings_claim=false`/`phrase_diagnostic_output_reused_in_R49=false`, and the finalize chain (`phrase → embedding(continued_by_phrase) → fields → meta → cuda → dependency`) preserves every prior raw-1 with the final `phrase_guard_1` controller/3-runner raw 0.

## Critical blockers

None.

## Non-blocking observations
- The guard is intentionally an independent tag-depth counter, not a complete grammar validator; malformed/unclosed-at-limit outputs still stop under the original parser (documented).
- The CPU-only candidate test stands in `transformers.LogitsProcessorList` with `list` (acknowledged; the delegation/ordering is what's exercised, not the server Transformers internals).
- `finalize.cuda_recovery` now asserts `registered_failed_historical_attempts == 2` (correct for the final CheXbench state, but makes that CUDA-specific writer gate depend on the later phrase failure too — a future-writer consistency note, not a runtime defect).

## Memory update
- `run_20261109_49pgr001` reviewed: **ready / scope_complete=true / score 9**, engineering-only MAIRA EOS-policy amendment.
- Accepted: one `phrase_guard_1` known-failure retry of q169/`xray_phrase_grounding` (original `nested_backend_error` cache/selection preserved, one guarded `OLD_KEY+'_phrase_guard_1'` attempt, atomic replace only on healthy+complete EOS2/policy evidence); `UnclosedTagEOSGuard` masks only EOS while generated obj/box spans are unclosed, preserves all other logits and original input/model/prompt/8-bit/f16/greedy/max300/decode/parser; all new physical MAIRA calls after 168 (SLAKE/VQA cold 0) use the guarded policy, legacy healthy caches/selections reused and labeled legacy; wrapper chains through `embedding_arrearage_1/resume_runner.py` retaining CUDA/META/fields/embedding overlays; accounting distinguishes 2 historical failures, isolated failed diagnostic stays separate/non-additive with unknown hardware cost; export/verify/publish/finalize gates enforce `generation_policy_changed=true`/`same_generation_settings=false` and preserve prior raw-1 + final raw 0.
- Execution requires `PHRASE_GUARD_RECOVERY_SCOPE.json` + `PHRASE_GUARD_RECOVERY_REVIEW_READY.json` (`verdict=ready`, `scope_complete=true`, `trace`) plus completed DeepSeek metadata; no stage/launch/GPU/API yet; a final result-claim review is still a separate future gate.
