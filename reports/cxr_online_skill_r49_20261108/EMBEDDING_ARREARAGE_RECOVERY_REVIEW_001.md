I've reviewed this production-embedding continuation against the actual sources (Read/Grep/Glob only; no execution/network/API/GPU; no target/reference/reward/Skill/candidate text, credentials, or full run payloads opened).

## Verdict

**Score: 9 / 10**
**VERDICT: ready**
**SCOPE_COMPLETE: true**

This is an **operational-only** continuation (one funded same-input embedding retry + historical-failure accounting), not clinical/result assurance, and execution remains gated on the still-missing explicit DashScope funding confirmation.

## What I verified at source level

**Reachability through frozen `assert_closed_sends` before embed**
- `RESUME_RUNNER` patches `cxr_online_primitives_r49.assert_closed_sends` and `Services.embed` before chaining into `mutation_fields_2/resume_runner.py --dataset ...`. The native runner is loaded via `runpy.run_path` *after* the patch, so `run_stream`'s `from ... import assert_closed_sends` binds the patched closure overlay. The synthetic test `test_actual_frozen_startup_reaches_retry…` loads the real `run_online_skill_r49.py` and confirms the flow reaches the retry, and the frozen primitive still raises `unknown_embedding_send_no_retry` before the patch.

**Closure overlay (only the one known 000063 HTTP400, everything else unchanged)**
- `closure_overlay` delegates to the frozen primitive unless `root/services` is exactly the CheXbench services root. It re-runs the frozen main/META checks verbatim and the embedding loop, exempting only `embeddings/000063` (whose `started.json` has no response); any other started-without-response embedding, or any unhealthy main/META receipt, still stops. `require_receipts=True` additionally requires the matching GEN/global registration, exact-input retry started/request, healthy receipt, and a validated 1024 vector. A historical exception alone cannot finalize the run.

**Once-guard / no reissue / error capture (retry_once)**
- Replay path verifies unchanged request + healthy receipt and re-validates the vector before returning; `started.json` without `response.json` → `retry_started_no_reissue_even_if_failure_known`. Fresh path writes `request`/`started` before the wire, sets `max_retries=0` and `follow_redirects=False`, and the request hook rejects a second request/wrong endpoint/wrong model/wrong input pre-transport. `APIStatusError` archives `http_status`/`body`/`request_id` (exit via stop), `APIConnectionError`/`APITimeoutError` classify transport-unknown, and a non-1024/finite/nonzero vector or wrong model is a hard stop with the raw `response.json` retained.

**Exact-input alias + SDK defaults**
- `embedding_overlay` aliases only `text == original request['input']` and `embed_model == request['model']` on the CheXbench services root, re-checks the immutable original failure bundle, then returns the validated vector; all other embeddings delegate to the frozen `Services.embed`. The retry uses `embeddings.create(**{'model','input'})` with no encoding/dimension override, so the installed SDK default is preserved and captured in `wire_request.json` (JSON body only, no headers; credential redacted).

**Accounting / disclosure / gates**
- `resources` counts the original failed receipt once in `embedding` totals, the healthy retry once in production totals, and reports the separate non-additive `isolated_embedding_diagnostic` with `usage_unknown`/`cost_unknown` (never free). `registered_embedding_http_failure` rejects any reconstructed original body, changed request, zero/non-1024 vector, missing response, or reissued attempt. Export/verify/publish/finalize all carry the `embedding_arrearage_1` chain (`known_repair` includes it; `ready()` chain is `embedding → fields → meta → cuda → dependency`), require `FUNDING_CONFIRMED.json` with `provider=aliyun_dashscope`, `funding_confirmed=True`, `confirmation_source=explicit_user_reply`, and preserve all prior raw-1 exits plus final controller/runner zeros.

## Critical blockers

None.

## Non-blocking observation
- The strict `len(vector)==1024` finite-float check is a declared scope constraint implemented faithfully in both `embedding_vector` (runtime) and the scorer. If the provider's default dimension differs or the SDK-default `encoding_format=base64` ever produces a non-float vector, the continuation conservatively stops (raw response retained, no registration) rather than emitting a wrong vector. That is a safe stop, not a silent failure; any future encoding/dimension change would require its own review and is explicitly out of scope here.

## Memory update
- `run_20261109_49eab001` reviewed: **ready / scope_complete=true / score 9**, operational-only production embedding continuation.
- Accepted: one `000063_arrearage_1` same-input/model/endpoint/default-SDK attempt; original `000063` BadRequestError closed-without-response preserved (body unknown, usage/cost unknown-not-free); closure overlay exempts only that registered 000063 and preserves all other main/META/embedding stop gates + final healthy-proof requirement; exact-input cache alias returns the validated 1024 vector, other embeddings delegate; SDK retries/redirects disabled, unknown/bad/invalid-vector stops without reissue; registration + wire/HTTP evidence + key redaction + no headers; prior fields2/meta/CUDA overlays retained via `mutation_fields_2/resume_runner.py`; serial CheX→SLAKE→VQA, cold libraries, prior raw-1 histories preserved, final raw 0.
- Execution remains gated: `EMBEDDING_FUNDING_CONFIRMED.json` (`provider=aliyun_dashscope`, `funding_confirmed=True`, `confirmation_source=explicit_user_reply`, non-empty reply/confirmed_at) + `EMBEDDING_ARREARAGE_RECOVERY_REVIEW_READY.json` (`verdict=ready`, `scope_complete=true`, `trace`) + completed DeepSeek metadata. No stage/launch until the actual user funding reply exists.
