# R49: explicit MUTATE fields and one second confirmed-event repair

Status: **prepared, not executed**. This amendment requires an actual fresh narrow DeepSeek review and a truthful scope record under the existing confirmed-failure continuation authorization. It does not claim a new user approval. Frozen source/configuration files and completed question records are unchanged, but the new operational prompt behavior is explicitly different; no isolated Skill-causal or medical-capability improvement follows from it.

## Confirmed recurrence and immutable boundary

Production stopped after 150 committed predictions, contexts, prediction events and feedback events, with four completed window repositories and an unfinished `0004` window. All 372 Agent, 136 META and 62 embedding requests are closed; 212 logical tool selections are recorded. The new failed event is `mutation_chexbench_slake_0013`: PATCH, target present, `patch_section='content'`, normal model finish and 397 completion tokens. The previous distinct event used `c`. Both refer to the whole content container instead of one accepted content field. No medical payload, reward, target score or Skill content was consulted to diagnose this recurring schema ambiguity.

The original MUTATE prompt says “one content field” but does not enumerate the fixed six-field contract. The allowed fields remain exactly `name`, `description`, `applicable_conditions`, `required_tools`, `risk_level`, `core_action`. Scope fields, candidate validation and review are unchanged.

## Two bounded behaviors

**One current-case repair.** Preserve the original failed request/reply/result. For this exact event and target only, permit one fresh META request at `mutation_chexbench_slake_0013_schema_2/1`, with the same original past payload, model and parameters plus a schema-only clarification. The actual new model must return PATCH with the unchanged target and one of the six fields, or explicitly NONE. CREATE, another target/field, malformed output or an unknown send stops again. The operator never unwraps the container, chooses a clinical field, coerces a response or substitutes NONE. Original candidate validation/review still determines whether a patch is admissible and useful.

**Explicit fields on ordinary future mutations.** Across all three authorized datasets, a normal mutation is eligible only when its caller system equals original MUTATE and `event == 'mutation_' + payload['trajectory']['id']`. Its same normal event/ordinal receives one normal META call, with the same source payload. A fixed system append enumerates the six existing fields, excludes `c`/`content` container names and preserves CREATE/PATCH/NONE and scope rules. No additional call, clinical fact, image, label or case is added. Redirect, analysis, review, governance and old repair prompts are not generalized by this change. Another invalid future mutation still stops; there is no automatic repair loop.

## Stable cache replay and per-stream declaration

Each stream publishes one immutable `failure_events/mutation_fields_2_amendment.json`, schema `r49_mutation_fields_amendment_v1`. It records the exact original system, exact clarification, ordinary-event rule, six fields, activation boundary and sorted protected old ordinary events. CheXbench activates after 150 questions; SLAKE and VQA activate at their separate empty initial states. Copies are retained under `ROOT/recovery/mutation_fields_2/amendments/<dataset>.json`.

- A protected request whose system is original MUTATE replays that original prompt unchanged.
- A later cached request whose system is original MUTATE plus the fixed clarification replays exactly that clarified prompt.
- A new unarchived ordinary request uses the clarification, once, under its original event name.
- A missing protected request or any unrecognized saved system stops. A started request without a response is never reissued.

The initial protected-event list and timestamp are retained on restart, not recomputed after new calls. This avoids changing a clarified cached request back into an old prompt. Old request/reply archives remain untouched.

## Continuation and evidence

The private helper is `local_assets/recover_cxr_online_skill_r49_mutation_fields.py`. All three dataset children use its runner wrapper. CheXbench chains only the prior `meta_schema_1/resume_runner.py`, retaining the earlier exact-event correction and registered CUDA cache routing without re-invoking either consumed controller or another tool retry. SLAKE and VQA use the native frozen runner underneath this field-contract wrapper, with their original separate empty memories/libraries. No cross-dataset feedback or learned library is transferred.

The one second repair registers `failure_events/meta_schema_2_registration.json`, schema `r49_registered_meta_schema_repair_v2`, with original/new archive paths, actual control fields, target, window 4 and schema-only instruction. It is duplicated under `ROOT/recovery/mutation_fields_2/registration.json`. Old and fresh META charges remain naturally counted in their actual receipts; future ordinary clarifications do not add an extra request per event. Scoring/public reproduction must validate both prompt forms and fixed-case repair records without changing answer extraction or selecting on correctness.

The 150 completed question records and four repositories remain immutable; ordinal 151 does not begin until the unfinished fifth-window transition completes through the original strict pipeline. A new one-use serial controller resumes CheXbench then SLAKE then VQA, preserves every prior raw-exit-1/PID/log record and uses unique `jobs/<dataset>.mutation_fields_2.log` files. Current PIDs and exits describe actual new attempts only. GPU1/disk checks remain and other jobs/R48 are untouched. Any new failure stops the queue.

Launch requires `MUTATION_FIELDS_RECOVERY_SCOPE.json` and actual `MUTATION_FIELDS_RECOVERY_REVIEW_READY.json` in `local_assets/online_skill_r49_preparation`. No actual stage, launch, API, GPU invocation, scoring or review was performed while preparing this plan. Full scoring remains gated on complete three-dataset artifacts and actual current raw exits 0. No file/pixel/hash validation gate is introduced.
