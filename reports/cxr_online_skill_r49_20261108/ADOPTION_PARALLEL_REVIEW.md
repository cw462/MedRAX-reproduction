I've reviewed this `adoption_1` implementation and its evidence/accounting/publication-gate design against the actual sources (Read only; no execution/network/API/GPU; no target/reward/reference data, clinical Skill/candidate/trajectory content, or credentials opened). Production is running independently; I am not pausing or modifying it.

## Verdict

**Score: 9 / 10**
**VERDICT: ready**
**SCOPE_COMPLETE: true**
**FINAL_RESULTS_AUDIT_COVERED: false**

This covers only the current source/protocol/gate design. A complete-results/claims audit is not possible yet and is not part of this parallel pass.

## What I verified at source level

**Bounded representative choice at assess only**
- `duplicate_entries` requires exactly 3 entries with `s_e1a0642fabefb0c7` appearing twice (`ADOPTED_POSITIVE`, `step_index∈{0,1}`, entries not identical) plus one unique entry; `effective_adoption` copies the model-selected duplicate and every other unique entry in original order via `copy.deepcopy` (verbatim status/step/evidence). `representative_choice` re-reads the original closed analysis request/reply, verifies `parse(raw)==analysis` and the source trajectory, appends `assistant(raw)` + `user(SELECTION_INSTRUCTION+duplicate_entries)` as a direct `service.call` into a fresh `analysis_<qid>_adoption_1` namespace, and requires `set(selected)=={'selected_duplicate_index'}` with index 0/1 — no operator unwrap/dedup/rewrite, no invented evidence.

**Write-phase preservation / native assess**
- `assessment_evolve_overlay` only intercepts `chexbench` + `wi==6`, verifies the batch equals `plan['window_question_ids']` (30 questions), deep-copies `analyses`, replaces only the two SOURCE_IDS' `skill_adoption`, and calls the captured native `module.assess` on the amended copy. The original `analyses` dict remains untouched, so cached MUTATE/review payloads still embed the old duplicate analysis (scorer re-checks `mutation_<qid>` payload analysis equals the original). Registration is written only after native assess succeeds, idempotently (`write_once`), and the test confirms a second evolve replay issues no extra physical repair call.

**Future ordinary ANALYZE boundary**
- `ensure_amendment` freezes `protected_original_events` from closed original-ANALYZE requests; `analysis_meta_overlay` replays original prompts for protected events, clarified prompts for already-clarified non-protected events, and appends `ANALYSIS_CLARIFICATION` only for new unarchived ordinary `analysis_<qid>` events (predicate `system==ANALYZE and event=='analysis_'+payload.trajectory.id`); any other saved prompt/missing protected/unknown send stops. Scorer `validate_analysis_unique_amendment` enforces 210/0/0 activation, `indices[qid] < 210` for original prompts, and rejects reclassification/extra namespaces.

**Wrapper reachability / authorization truthfulness**
- `RESUME_RUNNER` patches `Services.meta` and `evolving.evolve`, then delegates to `phrase_guard_1/resume_runner.py --dataset …`, so the native `run_online_skill_r49` imports the patched `evolve` after the patch; prior CUDA/META/fields/embedding/phrase overlays and cached paid calls are retained. `validate_authorization` requires the truthful deferred record (`verdict=audit_deferred_until_full_generation`, `review_completed=false`, `scope_complete=false`, exact user reply, `audit_before_publication=true`) — this concurrent review is not retrofitted into prelaunch-ready evidence, and the publisher/finalize gates reject rewriting it to ready.

**Accounting / public proof / publication gates**
- `resources` counts the two fresh choices once inside `R49_META` (`included_in_R49_META_totals=true`) and reports `repair_request_resources` as a non-additive subset; old analyses remain ordinary paid replies. Export/verify/publish add `adoption_1` to `known_repair`, disclose `registered_assessment_adoption_repair`/`analysis_unique_adoption_amendment`, `original_analysis_changed_for_mutation=false`, `automatic_future_adoption_repair=false`, `invalid_adoption_silently_ignored=false`. `adoption_recovery()` requires final controller+3-runner raw 0, preserves prior phrase/embedding raw-1 PIDs/logs, and — critically — requires a separate completed `RESULT_CLAIM_METADATA` with `scope_complete=true` and `audit_scope` covering `{adoption_protocol, request_resource_accounting, complete_results_and_claims}`. No new tool/embedding-failure exception is introduced; CUDA+phrase failed physical attempts and the HTTP400/embedding diagnostics remain independently accounted.

## Critical blockers

None.

## Non-blocking observations
- The repair choice is a direct multi-turn `service.call` (bypassing the meta overlay), which is intentional and documented; the scorer independently verifies the exact 4-message request (`text_semantics`), model-returned equality, and utc ordering.
- The `mutation_<qid>` write-phase check is conditional (`if mutation.is_file()`); if a SOURCE_ID was analyzed-but-not-retained it simply has no mutation to compare, which is consistent with the assess-only scope.
- The final audit requirement is correctly gated on a *future separate* completed result-claim review; this pass cannot and does not satisfy it.

## Memory update
- `run_20261109_49apr001` reviewed: **ready / scope_complete=true / score 9**, engineering-only, `FINAL_RESULTS_AUDIT_COVERED=false`.
- Accepted: two `analysis_<qid>_adoption_1` model-selected representative indices (0/1) over the two original conflicting duplicate entries; selected+unique entries copied verbatim in original order; only a deep-copied analysis changes at the assess boundary while cached MUTATE/review payloads keep the original analysis; native `assess` runs on the amended copy; registration only after successful assess; future ordinary ANALYZE gets a uniqueness clarification (210/0/0 activation) with protected-original/clarified replay and stop-on-unknown; wrapper chains through `phrase_guard_1` retaining all prior overlays; the initial user-directed audit-deferral record stays truthful and is not rewritten to ready; accounting keeps the two choices once in R49_META (non-additive subset); publication requires final raw-0 plus a separate completed result-claim audit covering protocol/resources/results.
- Not covered (still required before publication): the actual complete-denominator 618/114/116 result/claim audit. Production continues independently; no stage/launch/GPU/API action was taken by this review.
