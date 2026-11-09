I've reviewed the three new files against the actual sources (Read/Grep/Glob only; no shell/network/GPU/API, no clinical/Skill/feedback/reward/reference/prediction payloads opened).

## Verdict

**Score: 9 / 10**
**VERDICT: ready**
**SCOPE_COMPLETE: true**

Scope is **diagnostic-only** — one isolated neutral embedding request to capture the HTTP 400 evidence. It is not a production recovery, not an R49 resume, and makes no claim about the 000063 cause or the base64-vs-float hypothesis.

## What I verified at source level

**Once-guard / no reissue (diagnose_r49_embedding_400_once.py:execute)**
- `assert not out.exists()` plus `out.mkdir(parents=True, exist_ok=False)` create `…/attempt_1` exclusively; `record()` uses `open('x')` so no file is overwritten. A partial attempt blocks re-execution rather than reissuing.

**Key source + redaction (lines 21-25, 70-88, execute)**
- Key arrives only via `sys.stdin` from `TRANSPORT_HOME/.secrets/qwen_api.key` — the same credential the R49 controller passes as `R49_EMBEDDING_API_KEY`. `sanitize()` recursively redacts the credential in every recorded JSON. The request hook records the JSON body only, never `Authorization` or other headers; only `x-request-id` is taken from the response. Tests confirm `Authorization` and the secret are absent from the archive and `[REDACTED]` is present.

**Request boundary / SDK defaults (wire_hooks + diagnostic_call)**
- The request hook enforces: first request only (`second_diagnostic_request_forbidden`), `POST`, URL `EMBED_BASE.rstrip('/')+'/embeddings'`, `model==text-embedding-v4`, `input==NEUTRAL_TEXT` — all pre-transport. It deliberately does NOT reject an injected `encoding_format`, so the installed SDK default (base64 per server 1.109.1) is preserved and captured in `wire_request.json`. The call itself passes only `model` + `input` (`embeddings.create(model=…, input=…)`), no encoding/dimension override.
- `max_retries=0`, `follow_redirects=False`, `timeout=120` on both the httpx client and the SDK; `http_client` is wired into `OpenAI(...)` so the hooks actually fire on the SDK's single request.

**Error capture / unknown-stop (diagnostic_call)**
- `APIStatusError` (covers `BadRequestError`) → `known_http_error`, full `status_code`/`body`/`request_id`, `usable_diagnostic_vector=False`, exit 1. `APIConnectionError`/`APITimeoutError` → `transport_unknown_stop_no_retry`, `response_received=False`, exit 2. Any other exception → `unexpected_stop_no_retry`, exit 3. A successful-but-base64/non-vector response is recorded in `response.json` but classified `unexpected_response` (not healthy), so no diagnostic vector can be mislabeled healthy. Usage is retained only if returned; no zero-cost claim.

**No implicit production action / isolation**
- `OUT` is a fresh run directory separate from `ROOT/runs/online_skill_r49_20261108`. The remote script imports only `openai`/`httpx`/`importlib.metadata` — no skill_services, no run_online_skill_r49, no tool/GPU, and it does not read or resend the failed Skill input, mutate the R49 run, retry 000063, or resume R49. `automatic_r49_resume`/`production_embedding_retry` are hard-coded False.

## Notes (non-blocking)
- `embedding_requests` (from the hook's counter) is recorded in `status.json` but not hard-asserted; a hook that never fired would surface there as `embedding_requests: 0`, which is self-describing rather than a correctness hazard.
- If Aliyun returns its request ID under a different header than `x-request-id`, the SDK `request_id` field and the full body in `http_response.json` still preserve it.
- The local OpenAI 0.28.1 vs server 1.109.1 mismatch is correctly scoped: the tests use `httpx.MockTransport` + stand-ins and do not claim server-SDK e2e parity.

## Memory update
- `run_20261109_49e0bd01` reviewed: **ready / scope_complete=true / score 9**, diagnostic-only. One neutral `text-embedding-v4` call at the production-compatible endpoint, SDK-default args (no encoding override), exclusive `…/attempt_1` no-reissue, JSON-body-only capture with credential redaction, pre-transport first-request/wrong-endpoint/non-neutral guards, SDK `max_retries=0` + `follow_redirects=False`, HTTP-error/transport-unknown/unexpected all stop without retry and never mark the result embedding-healthy. No production action, no R49 resume, no vector reuse.
- Next artifact step needs `EMBEDDING_DIAGNOSTIC_REVIEW_READY.json` = `{diagnostic_id:'r49_embedding_400_once_20261109', verdict:'ready', scope_complete:true, trace:…}` plus a completed DeepSeek review metadata record. Production recovery for 000063 remains out of scope and requires its own plan/review.
