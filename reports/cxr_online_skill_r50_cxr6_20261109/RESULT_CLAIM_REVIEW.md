I have completed a read-only review of the stopped R50 archive and publication code. I read the new stopped scorer, publisher, stop controller, both collectors, the report README/RESOURCE_SUMMARY/score/public-reproduction/provenance/copy-map, and the failure/retry/stop/approval controls and diagnoses. Findings below.

## Independent review — R50 user-stopped publication

### 1. `online_feedback_and_Skill_protocol` — honest, negative, internally consistent
- `reports/.../README.md:13` states the online-GT confounds (own prediction/event precede own GT; earlier same-image annotation feedback usable; per-dataset empty Skill state; not closed-test). No closed-test/Skill-causal/clinical/SOTA claim is made.
- Negative Skill findings in README (one-source card, 90 OpenI laterality injections, before 68/92 vs after 62/90, grounding 70/16/4-with-3-wrong, 55 positive attributions incl. 12 wrong/negative credit) all reconcile with `deployment_source/preparation/user_requested_interim_accuracy_20261110/skill_effect_analysis/ANALYSIS.md` and with `RESOURCE_SUMMARY.json` `Skill_state_at_stop` (1 card `s_39391f294d360026`, source `chexbench_openi_0073`, usage 90, `causal_gain_identified:false`). These are explicitly labeled ordered/different-case, not causal. No overclaim.

### 2. `request_resource_accounting` — unknown-not-zero, proxies-not-invoices
- `RESOURCE_SUMMARY.json:12699-12703`: `provider_Credits/provider_invoice_CNY/hardware_cost = null`, `unknown_not_zero: true`, with a clear cost model disclaimer.
- `call_groups` (R50-AGENT 1123 started/1123 terminal; R50-META 411/411) report `recorded_CNY_proxy` values with `provider_invoice:false`; `unsettled_or_missing_terminal:[]` while `interrupted_tool_started_without_result` records the single 436th-question tool cache with no result — the in-flight/unknown compute is surfaced, not zeroed.
- `prior_failure_and_retry_records` preserves the two tokenizer-load failures and their single unchanged retries. `elapsed_note`/`physical_tool_accounting_limit` correctly warn elapsed sums overlap and retry archives are linked, not summed.

### 3. `complete_results_and_claims` — 435 + interrupted 436 + full history, no 848 claim
- `results/user_stopped/summary.json`: 435/848, 336 correct = 77.24%, 413 unanswered, 436 interrupted. Subsets sum correctly (197+115+123=435; 142+78+116=336; skill 105+330=435; 74+262=336). `interrupted_input.json` = `chexbench_openi_0197` (ordinal 436), excluded from the denominator.
- `score.completed.json`/`reference_free_adaptation.json`: `n=435`, `references_read:false`, `all435_adapted_before_labels:true`, `original420_unchanged:true`, `full_cohort_score_receipts_consumed:false`. `score_r50_stopped_prefix.py` adapts all raw terminal answers before any reference/feedback read and asserts `event['saved_prediction'] == pred`.
- `public_reproduction/user_stopped/summary.json` adds `public_reproduction_passed:true`; `verify_public()` re-runs the same adapter/metrics with no model calls and asserts byte-level summary/per-question equality. No `complete.json`, no fabricated zero exit (raw exits -15/241/143, original/recovery exits 1 all retained in `stop.completed.json`/`USER_STOP.json`).

### Publication code integrity
- `publish_r50_user_stopped.py` `push()` protects base `3ab0a9275…`: asserts local HEAD == BASE, remote main == BASE, no pre-staged files; stages via literal-NUL pathspec, asserts `staged == allowlist`, commits, asserts `HEAD^ == BASE`, ordinary `git push` (no `--force`). `prepare()` allowlist = report + 18 `SOURCE_NAMES` + 9 `TEST_NAMES` + stopped scorer + 4 `INDEXES` (counts verified in `publish_cxr6_r50.py:22-31` and `finalize_r50_report.py:26`); `open_questions_for_later`, `.secrets`, `__pycache__`, `hf_modules` excluded.
- Credential handling is honest: `CREDENTIAL_REDACTION_RECEIPT.json` lists 8 outgoing files with one redacted quoted field each (originals preserved); `prepare()` asserts `text_has_secret` false on every staged file; the new `semantic_strings` guard (`outgoing_guard_new_checks.json`: 3 synthetic checks passed) fixes the `export002` false positive documented in `export002_diagnosis.json`/`outgoing_guard_pre_fix_snapshot.py`. The three snapshot files correctly represent distinct pre-fix states (verified by grep: only `source_assembly_pre_longpath_fix.py` contains `semantic_strings`/`StoppedEvidencePublisher`; the other two lack it and its `assemble()` is pre-longpath).

### Non-blocking limitations (not publication blockers)
- Source is a post-execution snapshot, not a byte/weight/model-identity attestation (explicitly disclosed in README/PROVENANCE).
- 435-case accuracy is a stopped ordered prefix; time/source/order confounds; no same-question Skill-off counterfactual (correctly labeled).
- Per-call CNY proxies are not invoices and elapsed sums overlap; hardware/in-flight/provider-credit cost remain unknown (not 0).
- I could not re-execute the scorer or re-count all 435/436 files directly (read-only; large tree), so the 336/435 figure rests on the internally consistent receipts and the `verify_public` equality assertions rather than an independent re-run.
- No post-push remote verification (user-waived); DeepSeek wrapper exit 143 is a deliberate stop, so no comparison result exists.

No integrity or publication blockers were found.

```json
{"scope_complete":true,"audit_scope":["online_feedback_and_Skill_protocol","request_resource_accounting","complete_results_and_claims"],"publication_blockers":[],"claim_supported":"yes","nonblocking_limitations":["Source is a post-execution snapshot, not a byte/weight/model-identity attestation (disclosed).","435-case accuracy is a stopped ordered prefix with time/source/order confounds and no same-question Skill-off counterfactual (disclosed).","Per-call CNY proxies are not provider invoices and elapsed sums overlap; hardware/in-flight/provider-credit costs remain unknown-not-zero (disclosed).","Reviewer did not re-execute the scorer or re-count 435/436 files directly; the score rests on internally consistent receipts and the verify_public equality assertions.","No post-push remote verification performed (user-waived); DeepSeek wrapper exit 143 is a deliberate stop, so no comparison result exists."]}
```
