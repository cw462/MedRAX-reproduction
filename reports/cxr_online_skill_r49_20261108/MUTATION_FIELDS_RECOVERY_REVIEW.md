I've reviewed this second-recurrence amendment against the actual sources on disk (native Read/Grep/Glob only; no shell/network/GPU/API, and no clinical/reward/feedback/Skill payload opened). Prior case-1 findings are preserved only where the code is unchanged.

## Verdict

**Score: 9 / 10**
**VERDICT: ready**
**SCOPE_COMPLETE: true**

Scope is **operational only** — a mid-run learning-interface prompt-contract change plus one exact closed-event repair. It is not a clinical validation, isolated Skill-causal gain, official SOTA claim, or evidence that the CUDA root cause is fixed. Truthful scope record rides existing authorization (`uses_existing_r49_authorization=True`, `new_user_approval_claimed=False`, `operational_prompt_change_confound=True`, `original_static_protocol_claim=False` in finalize).

## What I verified at source level

**Case-2 repair boundary (recover_cxr_online_skill_r49_mutation_fields.py:97-162)**
- `current_repair` fires only for chexbench + `mutation_chexbench_slake_0013`, requires the event to already be in the frozen `protected_original_events`, forbids an image row, replays the original invalid reply through the real cached `Services.call`→`PaidCalls.call` path (no re-send), then enforces the failure signature (`PATCH`/`patch_section=='content'`/same target/target-in-snapshot).
- Exactly one fresh `mutation_chexbench_slake_0013_schema_2/1`; only same-target six-field `PATCH` or explicit `NONE` returns. `CREATE`/other target/other section/unknown → stop; no coercion/field-pick/unwrap/second-repair. Started-without-response is never reissued (`PaidCalls.call` `unknown_sent_no_reissue`). Closed-repair replay is idempotent (`write_once` + `recorded_at` reuse from stored registration).

**Ordinary MUTATE field clarification (lines 63-94, 102-121)**
- Ordinary = `system == MUTATE` and `event == 'mutation_'+payload['trajectory']['id']`. `ensure_amendment` freezes the protected old-ordinary-event list once and does not recompute on replay, so clarified cached requests can't be reclassified back to the old prompt.
- Cached replay: protected + original system → replays original; unprotected + clarified system → replays clarified; any other saved system → `unrecognized_cached_mutation_prompt_stop`. A missing protected request → stop. New uncached ordinary mutation → one normal call with `system+FIELDS_CLARIFICATION` (no extra event/ordinal). Redirect/analysis/review/old-repair names are excluded (tested).

**Wrapper chain and argv (RESUME_RUNNER, CONTROLLER)**
- All three children run the new runner. CheXbench chains only `meta_schema_1/resume_runner.py` (which itself chains `cuda_1/resume_runner.py` → native runner), so prior CUDA + schema-1 overlays are retained and neither consumed controller nor a tool retry is re-invoked. SLAKE/VQA run the native frozen runner under the field wrapper with cold memories. Layering order is correct: case-1 `exact_meta_overlay` wraps case-2 `mutation_fields_overlay`, which wraps the original `Services.meta`; the case-2 repair event passes through the case-1 guard and reaches its repair branch (verified against the actual meta_schema_1 resume runner).

**Scorer integration (score_online_skill_r49.py)**
- `_registered_meta_schema_case`/`registered_meta_schema_repairs` treat exactly two fixed cases (never a configurable mechanism); `registered_meta_schema_repairs` also rejects any unrecognized `meta_schema_*_registration.json` or `*_schema_*` namespace.
- `validate_mutation_fields_amendment` proves the declared old/clarified boundary from actual ordinary requests (system variant, protected membership, activation timestamps, payload==saved window source) and rejects undeclared/unprotected/reclassified prompts. `resources` counts both repairs once inside `R49_META` totals plus non-additive subsets, and reports the prompt-mode subset with `extra_ordinary_meta_calls: 0`.

**Export / verify / publish / finalize gates**
- `export` recognizes `mutation_fields_2` in `known_repair` and emits `registered_meta_schema_repair_2` + `ordinary_mutation_fields_amendment` flags; `verify` cross-checks them against the scorer's `meta_schema_repair_2.registered` and `mutation_fields_amendment.active`.
- `publish.ready()` chain (`fields → meta → cuda → dependency`) and `mutation_fields_recovery`/`meta_schema_recovery(continued_by_fields=…)`/`cuda_recovery(continued_by_meta=…)` exit-history logic are consistent with the actual staged tree: prior raw `1`s preserved, final `mutation_fields_2` controller + three runners `0`, `queue.state == 'all_three_datasets_exited_zero_after_mutation_fields_amendment'`.
- `finalize.load_completed` and `mutation_fields_recovery` (per-dataset `validate_mutation_fields_amendment`, shared/GEN amendment and registration equality, non-additive cost subset) all match the scorer output keys.

## Notes (non-blocking)
- No defect found that blocks readiness. The only cosmetic item remains the pre-existing shared recovery-tree `publication_manifest` scope label (not part of this amendment; no gate reads it). I did not rerun prior reviews/tests for ceremony and found no reason to request any additional test.

## Memory update
- `run_20261109_49fields02` reviewed: **ready / scope_complete=true / score 9**, operational-only prompt-contract change from the 150 boundary.
- Accepted: one exact case-2 repair `mutation_chexbench_slake_0013_schema_2/1` (original `PATCH(content)` preserved; same-target six-field PATCH or explicit NONE; CREATE/unknown/coercion/second-repair stop; unknown send not reissued), plus a schema-only `FIELDS_CLARIFICATION` system append for uncached ordinary MUTATE across all 3 datasets; old/clarified cached prompts replay their recorded variant; protected old-event list frozen once in `failure_events/mutation_fields_2_amendment.json`; no auto future repair, no extra ordinary request.
- Chain verified: CheXbench `mutation_fields_2 → meta_schema_1 → cuda_1 → native`; SLAKE/VQA `mutation_fields_2 → native`, cold memories; prior CUDA/schema-1 overlays and 150 records / 4 repos preserved; final controller+3 runners exit 0 with all prior exit-1 history retained.
- Next artifact step needs `MUTATION_FIELDS_RECOVERY_REVIEW_READY.json` = `{recovery_id:'mutation_fields_2', verdict:'ready', scope_complete:true, trace:…}` plus `MUTATION_FIELDS_RECOVERY_*` report/metadata with a completed DeepSeek operational-review session.
