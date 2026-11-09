I've reviewed the primary R49 files and traced the actual upstream interfaces they depend on. Here is my execution-readiness review.

## Verdict summary

**No genuine execution blocker found.** The R49 execution path is coherent, the interfaces match the actual upstream implementations, and the label-leakage / snapshot / tool-health / no-retry / receipt / scoring-separation guarantees are implemented in code, not just asserted in prose. A few minor, disclosed or non-blocking observations are listed at the end.

## Checklist (checked against actual source, not quoted claims)

**1. Current/future label leakage — safe.**
- `run_online_skill_r49.py` main: `allowed={'question_id','question','images','image_id','source','options'}` and `if any(set(x)-allowed for x in inputs): raise ValueError('inference_fields_include_labels')` rejects label-bearing input fields.
- `online_memory_r49.py` `ReferenceVault.after_prediction` requires the immutable prediction **and** prediction-event to exist and semantically bind (`reference_before_prediction_save`, `saved_prediction_event_binding_changed`) before reading the single per-question file. Existence check in main uses `is_file()` only, never `open`.
- `online_memory_r49.context` selects only `event['image_key']==current` AND `event['ordinal']<ordinal` AND `question_id in previous_ids`, and `incomplete_committed_same_image_prefix` guarantees strictly the processed prefix. Current/future truth and other-image episodes cannot enter.
- Scorer `score_online_skill_r49.score` adapts **all** arms (`adapt_current` → `adapt_historical` → optional `adapt_r47`) before `check_semantics`/`resources` open any R49 feedback/window/label; `completed_gate` deliberately does not open `complete.json` (`final_repo` is label-bearing).

**2. Window snapshot timing / evolution / restart / partial commits — safe.**
- `run_stream`: `snapshot=copy.deepcopy(repo)` frozen per window and saved to `read_snapshot.json`; retrieval only from that snapshot; `evolver` runs only at window end. Same-window skills are therefore invisible within the window (tests `test_real_window_evolution_is_visible_only_next_window`).
- `validate_prefix` allows only the sound crash-frontiers: predictions=strict prefix, feedback/events ∈ {n,n-1}, contexts/steps ∈ {n,n+1}. `save_once` (atomic link+fsync, immutable on conflict) and semantic request reuse (`skill_services_r49.Services.call` comparing `text_semantics` of saved messages plus model/temperature/top_p/max_tokens) make resume idempotent without new paid calls.
- `skill_evolve_r49.evolve` applies a second local PATCH to the current write-side record (not the stale snapshot), and `assess` rejects duplicate adoption IDs.

**3. Actual tool health / derived image binding — safe.**
- Reuses existing `tool_failure_reason` (`cxr_image_memory_r44.py:31`), which catches the R48 MAIRA shape (`analysis_status=failed` + empty `error`) and `outer_status_not_completed`/`started_unknown`, while `completed_no_finding` stays valid. `execute` raises before appending a failed observation or making another main call.
- `run_cxr_vqa_toolsets.append_observations` validates `derived_images` resolve inside `out/tool_cache`. `Tools` cache-keying by image bytes is the **pre-existing** tool cache, unchanged (authorized).

**4. Unknown send → no retry — safe.**
- `PaidCalls.call` (`run_cxr_vqa_toolsets.py:325`): `if not stored_response and (folder/'started.json').exists(): raise RuntimeError('unknown_sent_no_reissue:...')`. `assert_closed_sends` enforces started→response. `Services.embed` raises `unknown_embedding_send_no_retry`. `Tools.observe` returns `started_unknown` (→ `tool_failure_reason` → stop) rather than retrying.

**5. Private keys not archived — safe.**
- Keys arrive via stdin (`--api-key-stdin`) and env `R49_EMBEDDING_API_KEY`; `manifest.json`/`request.json`/`started.json`/`result.json` contain no key; `safe_error(exc, key)` redacts. `queue_controller.py` driver written to disk contains no secret.

**6. Correct source interfaces / normal request storage, no byte comparison — safe.**
- R49 `schedule` (semantic IDs / order manifest) replaces R44's pixel `image_key`/`schedule`; R44 pixel functions are not imported. `request.json` stores the normal payload; semantic restart compares text only (image `url` stripped). No new file/pred/ref/prefix/code/pixel hash gate. Verified against `PaidCalls`, `Tools`, `validate_actions`, `agent_system`, `content`, `ACTION`, `parse`/`answer`, `prompt`/`unscorable`, `extract`/`choice`/`m4cxr_normalize`, `predictions`/`terminal`, `adapt`/`outcomes`, `bootstrap`/`cluster_keys`/`grade`, `r47 completed_gate`/`request_evidence`, `profile_for`/`invoke`/`exclusive_lock`/`safe_error` — all signatures match.

**7. Uncapped executor + normal stop behavior — safe.**
- `Services.__init__` sets `main_call_limits={}` and `tool_call_limits={}`; `execute` is a `while True` loop terminating only on legal final answer (`answer`+`unscorable`), three repeated invalid/identical actions, or technical exception. No hidden total-step cap.

**8. Empty initial state per dataset — safe.**
- `repo=initial(); memory={}` per `run_stream`; serial controller launches one process per dataset with separate `--out`; no cross-dataset state transfer.

**9. Counter/cost receipts — safe.**
- `PaidCalls` writes `result.json` with `settlement.charged_cny`/`usage`/`elapsed_s`/`model_returned`; scorer `resources()` reports agent/R49-META/embedding/tools separately with unknown-cost/elapsed counts, `provider_invoice:false`.

**10. Full completion / scoring separation — safe.**
- Scorer requires raw exit 0 (`generation.exitcode`), full fixed cohort, closed/healthy receipts, contiguous calls, steps↔response equality, tool-cache health, and `complete.json`/`final_repo.json` consistency; labels opened last; JSON conformance reported separately, no reason-based guess. Verified `adapt`/`outcomes` supply exactly the keys `summarize` reads.

**11. No new benchmark-dependent fixes — safe.**
- New logic is confined to the `*_r49.py` files; historical `validate_protocol`/`M43 466`/`M42 100`/`R47 468` are frozen comparisons, adapted uniformly, never selected by correctness.

**12. Disclosure limits — correctly framed, not blockers.** No contemporaneous no-Skill arm, no causal/SOTA/clinical claim; these are stated in PROTOCOL `limitations`/`METHOD_AND_LIMITS.md`.

## Minor non-blocking observations
- `online_memory_r49.context` enforces the 12000-char budget on the entries body only; the ~700-char fixed header is additional. Cosmetic budget deviation, no leakage/readiness impact.
- `token_context_guard_16384_implemented:false` — no context guard; oversized contexts surface as a technical error and stop (disclosed).
- `adapt_r47` reads R47's own frozen feedback archives (label-bearing historical artifacts) during the optional CheXbench historical comparator; adaptation itself stays reference-free and this is the authorized "frozen complete archive" read.
- Remote warm-environment completeness and R47/R48 `reference_vault` per-question layout are deployment assumptions covered by the offline dryrun's `is_file()` existence checks; I did not (and cannot) independently verify the remote.

## Test rerun statement
I did **not** and **cannot** independently rerun the reported raw-package 17, integrated 30, 3 scorer, or 6 execution tests, nor the three dryruns/probe. I read the test sources and confirmed they exercise the claims they state (e.g., `test_execution_r49` nested-failure stop + unknown-embedding-send; `test_online_r49` post-save label timing + window visibility + resume-after-prediction-before-feedback; `test_score_online_skill_r49` adaptation-before-labels + nonzero-exit gate; `test_skill_lifecycle_r49` two-local-PATCH preservation + duplicate-adoption rejection). Execution readiness rests on source inspection plus those claimed offline results, not on a rerun by me.

## Memory update
R49 execution review 001 (DeepSeek-native Claude Code route): inspected all R49 execution/scoring/deploy/tests + upstream interfaces; no execution blocker. Confirmed semantic-only grouping/restart (no byte/pixel gates), label-blind until own immutable prediction+event, frozen window skill snapshots, existing `tool_failure_reason` nested-failure guard, unknown-send no-retry, key-not-archived, unbounded executor with legal/3-repeat/technical stops, empty per-dataset state, separate cost receipts, reference-free adaptation before labels. R48 unchanged (stopped at slake_12376). Blockers: none. Tests not independently rerun. Ready to freeze source and run the single serial CheXbench618→SLAKE114→VQA116 queue.

SCORE:9, VERDICT:ready, SCOPE_COMPLETE:true
