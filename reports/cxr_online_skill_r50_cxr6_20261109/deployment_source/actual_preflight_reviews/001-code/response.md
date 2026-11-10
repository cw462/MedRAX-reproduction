I've completed a full read-only review of the supplied R50 CXR6 sources/configs against the plan, and verified every inherited helper the new code imports. Here is the review.

---

# MedRAX R50 CXR6 — execution-code review (new-code, read-only)

**Verdict: READY for code deployment + mandatory health.** The code is structurally correct and correctly gated; I found no concrete launch/correctness blocker. Actual health has not run (ready flags `false`, `new3_health_pending`) — that gap is expected and correctly remains a pre-queue gate, not a fabricated check.

## What I verified (actual files, not plan assertions)

Inherited helper contracts all resolve and match the call sites:

| Import (from new R50 code) | Helper exists / matches |
|---|---|
| `cxr_author_alignment.extract/choice/m4cxr_normalize` | ✓ `extract().answer` return shape correct for `released_reward` |
| `cxr_image_memory_gt_r47.validate_protocol` | ✓ accepts `enable_thinking:false`, model settings match `protocol.json` |
| `cxr_image_memory_r44.tool_failure_reason` | ✓ |
| `run_cxr_action_r41.parse/answer` | ✓ `answer()` returns `None` on tool-plan, `{answer,reason,status:'completed'}` on final |
| `cxr_task_completion_r43.prompt/unscorable` | ✓ `unscorable` = `grade(row, pred, None)[1]` (legality flag), `grade` signature correct |
| `maira_smoke.create_maira_tool` + `REVISION` | ✓ pinned revision `795a2b1cd4…` matches guard assert; loads 8-bit |
| `llava_smoke` (`inspect_snapshot/offline_context/_device/…/UPSTREAM_COMMIT`) | ✓ all present |
| `chexagent_smoke.execute_tool` | ✓ 7-positional signature matches worker call |
| `run_sampled_vlm` (`profile_for/invoke/exclusive_lock/safe_error`) | ✓ `identity_ok` accepts `qwen3.7-plus[-YYYY-MM-DD]`; price_basis note present verbatim in `chexbench.json` |
| `run_direct_vlm.write`, `provider_ledger`, `v12_ledger`, `cxr_action_skill_r41`, `score_cxr_vqa_extension.grade` | ✓ all present |
| `deploy_v12` → `connect/ROOT` (from `remote`), `remote_python(source, timeout, input_bytes)` | ✓ `input_bytes=None` handled |
| `deploy_cxr_online_skill_r49` → `DATA/REFS/DATASETS/COUNTS/EMBED_*` | ✓ `DATASETS=('chexbench','slake','vqarad')`, `COUNTS={618,114,116}` — serial order correct |

## Method & leakage

- **Prescreen fix is correctly implemented.** `skill_lifecycle_r50.retrieve` uses `if candidates and prescreen:` with `pool=[… per-branch top5]`, `chosen` id-subset validation, and round-robin after; an empty `chosen` legitimately yields `[]`. The four supplied unittest methods are consistent with this implementation by inspection (n=1/5/6 all-reject → `[]` and 1 call; empty-pool → no prescreen; unknown id → `prescreen_unknown_id`; `ARM` identity).
- **GT-after-prediction ordering holds.** In `run_online_skill_r50.run_stream`, prediction is saved (`save_once(predpath)`) before `vault.after_prediction()` is ever called; `ReferenceVault.after_prediction` refuses if the prediction/`prediction_events` file is absent. Feedback events carry `released_at` + `timing:after_immutable_prediction`.
- **No future/current-label leak.** `main()` rejects any input row field outside `{question_id,question,images,image_id,source,options}`; reference files are only `is_file()`-checked in setup, never opened. `evolve` only receives the completed window batch whose labels were released post-prediction.
- **Empty-state and restart logging correct.** `screen()` writes `prescreen_events/<q>.json` only when a nonempty candidate pool is actually prescreened; window 0 (empty repo) correctly makes zero embedding/prescreen calls.

## Runtime GPU & health

- **GPU1 enforced everywhere, GPU0/CT untouched.** `r50_baseline_controls.validate_runtime` requires `runtime['tools'][*]['gpu']=='1'`, `arms['M']['tools']==list(TOOLS)`, `set(runtime['tools'])==set(TOOLS)`, and `configs/cxr_vqa_tool_worker_gpu.json == {'cuda_visible_devices':'1'}`. `Tools.observe` and the health controller both force `CUDA_VISIBLE_DEVICES='1'`. `maira_eos_guard_r50.validate_original_profile` expecting `cuda:0` is consistent (visible device index 0 under mask `1`).
- **Health gate is correct and mandatory.** `deploy_cxr6_r50.py HEALTH` probes exactly `NEW=('medgemma','llava_rad','medvlm_r1')` on `HEALTH_IMAGE`, records request/started/exitcode/stdout/stderr/`completed.json`, refuses to run if GPU1 mem ≥500 MiB or disk <3 GiB, and raises `SystemExit(1)` on any failure (preserved, no auto-resend). `queue`/`controller` assert `health/complete.json == three_new_tools_healthy` before any production Popen.
- **Exact six-tool menu preserved in runtime config.** `runtime.json` arms `M` and `R50-AGENT` both carry the six names in `TOOLS` order; `prepare()` strips the five removed interfaces and rewrites `worker_script` only for `xray_phrase_grounding`.

## Launch & archiving

- **Serial 618→114→116 with native exits.** `CONTROLLER` iterates `DATASETS` in order, writes `jobs/<ds>.pid/.exitcode` and `generation/<ds>/generation.exitcode`, stops the queue on nonzero rc, and verifies `complete.json` (`status/arm/questions`). `launch()` writes `.pid`/`.started.json`/`.exitcode` via a `bash -c` wrapper and forbids duplicate launch.
- **stdin credentials only.** Controller reads `main_key` + `embedding_key` from the launch pipe; `--api-key-stdin` required; `R50_EMBEDDING_API_KEY` set via env for the embedding client; `safe_error` redacts keys; secrets never printed.
- **Stop-on-failure / no automatic resend holds.** `assert_closed_sends` rejects `started.json` without `response.json` (`unknown_sent_no_reissue`) and (at end) any `result.json` with error/`response_received!=True`; `Services.embed` and `PaidCalls` raise on `started`-without-`response` rather than resending; tool cache `started_unknown` is treated as failure (`tool_failure_stop_no_automatic_retry`).
- **Complete archives / cost-time.** Every call folder persists `request.json`/`started.json`/`response.json`/`result.json` (with `elapsed_s`, `usage`, settlement); `complete.json` carries `windows` and full `final_repo`; embeddings/tool caches are content-keyed and idempotent on restart.
- **Dry-run is genuinely label-blind.** The stage dry-run runs `run_online_skill_r50.py` without `--execute`, blocks network (`socket.connect`) and reference-file opens (`Path.open` under `REFS[ds]`), but only `is_file()`-checks references — consistent with `reference_file_opens:0`.

## Blockers

None.

## Nonblocking limitations / observations

1. `cxr_vqa_tool_worker.py` and `cxr_vqa_extended_backends.py` are **not** in `SOURCE_PREPARATION.json runtime_sources`; the three new-tool backends (medgemma/llava_rad/medvlm_r1) are inherited from `OLD_CODE` (`code_cxr_online_skill_r49_20261108`) via the `stage()` `glob('*.py')` copy. This is the "reuse existing `cxr_vqa_extended_backends.py`" design; the new3 health gate is the first runtime proof. If that copy lacks the branches, health fails loudly (`unsupported_extended_backend`) and stops — correct behavior, not silent.
2. `maira_guard_worker_r50.py` (EOS guard) is bound only to `xray_phrase_grounding`, which is `historical_warm_environment_reused_no_new_probe` and therefore **outside the mandatory new3 health set**. Its pinned runtime assertions (dtype float16, device cuda:0, `max_new_tokens==300`, `use_cache is True`, tag-token mapping, `tool._run.__code__`) are first exercised in production. Accepted per "do not re-probe old3", but it is an un-probed new wrapper.
3. `EXECUTION_REVIEW_READY.json` is intentionally absent (it is this review's gate). Note `require_review()` in `deploy_cxr6_r50.py` additionally asserts `arm`, `session_id`, `modelUsage`, and `code_review_completed:true` — beyond this review's `scope_complete`/`verdict` — so those must be added when materializing the gate file.
4. `medgemma` uses the donor `.venv-maira` interpreter; `AutoModelForImageTextToText` (transformers ≥4.45) must be present there. Inherited donor config, verified by the new3 health.
5. `health(client)` polls `jobs/health.exitcode` with no timeout; a wrapper-level failure that never writes the file would poll indefinitely (operational edge, not a code-path bug).
6. `budget.existing_shared_ledger=false` disables money-cap enforcement for R50; cost is per-request accounting only, and `usage_unknown` is emitted when the provider omits usage — intended but worth knowing (no cap gate).
7. The chexbench `schedule()` historical-order path requires the order manifest to match `inputs.jsonl` order exactly and the 488-groups / 130-followup invariant; inherited from R49 and re-checked at dry-run.

---

```json
{
  "scope_complete": true,
  "verdict": "ready",
  "audit_scope": [
    "method_and_leakage",
    "runtime_GPU_and_health",
    "launch_and_archiving",
    "inherited_imports_and_helper_contracts",
    "prescreen_retrieval_and_restart"
  ],
  "blockers": [],
  "nonblocking_limitations": [
    "cxr_vqa_tool_worker.py and cxr_vqa_extended_backends.py are not in SOURCE_PREPARATION.json runtime_sources; the medgemma/llava_rad/medvlm_r1 backends are inherited from OLD_CODE during stage(), and the new3 health gate is their first runtime proof (fails loudly as unsupported_extended_backend if absent).",
    "The MAIRA EOS-guard worker (maira_guard_worker_r50.py) is bound only to xray_phrase_grounding, which is historical_warm_environment_reused_no_new_probe and not in the mandatory new3 health set; its pinned profile assertions are first exercised in production (accepted per no-reprobe-of-old3 scope).",
    "EXECUTION_REVIEW_READY.json is intentionally absent pre-review; require_review() additionally needs arm/session_id/modelUsage/code_review_completed beyond this review's scope_complete/verdict.",
    "medgemma runs under the donor .venv-maira interpreter; AutoModelForImageTextToText availability there is unverified until the new3 health check.",
    "health(client) polls jobs/health.exitcode without a timeout; a wrapper failure that never writes the file would poll indefinitely.",
    "budget.existing_shared_ledger=false disables monetary-cap enforcement for R50; costs are per-request accounting only with usage_unknown when usage is absent.",
    "chexbench schedule() historical-order path requires the order manifest to match inputs.jsonl exactly plus the 488-groups/130-followup invariant (inherited, re-checked at dry-run)."
  ]
}
```
