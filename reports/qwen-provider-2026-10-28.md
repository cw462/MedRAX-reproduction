# Qwen central model: capability probe, provider facts and ledger

Date: 2026-10-28 (Asia/Shanghai). Status: **implementation and smoke verified; no full
validation comparison yet.** This note records what was measured, what was assumed and
what remains unverified.

## Why a different central model

The Codex execution budget was exhausted, and the user asked to continue the V3 plan with
Qwen or DeepSeek as the central model instead of `gpt-4o-2024-11-20`. MedRAX's Agent sends
images as data URLs, so the central model must be a vision-language model with function
calling. DeepSeek's public API is text-only; using it as the central model would remove the
image channel and turn the run into a text-only adaptation. Qwen VL is therefore the
faithful substitute.

## Live probe (2026-10-28, no clinical data sent)

Endpoint `https://dashscope.aliyuncs.com/compatible-mode/v1`, one synthetic text request and
one chest-radiograph request drawn from the frozen training split.

| model | result |
|---|---|
| `qwen3-vl-plus` | **200**: described the image as a chest X-ray; returned a well-formed `tool_calls` object when given a function schema |
| `qwen-vl-max` | 404 `model_not_found` |
| `qwen-vl-max-latest` | 403 `access_denied` |
| `qwen2.5-vl-72b-instruct` | 403 `access_denied` |
| `qwen2.5-vl-7b-instruct` | 403 `access_denied` |
| `deepseek-chat` on this endpoint | 404; the same key is rejected by `api.deepseek.com` (401) |

The account is a workspace-scoped key: `/models` lists 183 models, but only the three
`qwen*vl*` entries above are reachable. **The user's question about `qwen-vl-max` versus
`qwen2.5-vl-72b` cannot be answered by A/B on this key** — neither is accessible. The run
uses `qwen3-vl-plus`, a newer generation than both, and records that choice as a
deviation rather than a claimed equivalence.

Observed usage on a 1024-px CXR: 227 image tokens, ~250 prompt tokens in total for a
single-image turn; tool-call arguments arrive as a JSON string. `qwen3.8-max`, `qwen3.8-flash`,
`qwen3.7-*`, `deepseek-v4-*` and several third-party models are listed and were not used.

## Account arrears interrupted the first pool run (2026-10-28)

The first 60-question training run (`runs/train60_r0_v1`) started at 15:18 and completed four
questions; from the fifth question every request returned HTTP 400 with
`{"code": "Arrearage"}` (account in arrears). A three-call probe reproduced it for image and
text-only requests on the same key, so it was a billing state, not an image or prompt problem.
The run was stopped after 45 of 60 started questions, of which 4 were `completed` and 41 were
`model_error` with zero tool calls.

Two consequences are recorded rather than hidden:

- The conservative ledger charges an unclear outcome its full reservation, so the 41 rejected
  calls added about **1.27 CNY of internal accounting** although the provider billed nothing.
  The ledger is not the provider bill; the difference must be reconciled before quoting spend.
- The runner had no consecutive-failure stop. It now stops a resumable run after three
  consecutive model/tool failures with no tool execution, and stops immediately on
  401/402/403 (`api_auth_or_billing_error`). This is why the rerun uses a new protocol hash
  and a new run directory instead of resuming the interrupted one.

After the user topped up the account (15:37) a three-call probe returned 200 for
`image/jpeg`, `image/png` and text-only requests, and the pool run was restarted from
scratch as `runs/train60_r0_v2`.

## Pricing is an assumption, not a quote

The provider exposes no pricing endpoint, and the documentation host was unreachable from
this machine (`help.aliyun.com` resolved to a non-public address). The ledger therefore
uses a deliberately conservative assumption for `qwen3-vl-plus`:

- input: **4 CNY / million tokens**
- output: **12 CNY / million tokens**
- basis string in every manifest: `assumed_upper_bound_plus_tier_unverified_2026-10-28`

The ledger is an internal pre-call bound, **not the provider bill**. If the real list price
is lower (likely), the accounting overstates spend; if it is higher, the hard token ceiling
still bounds each call, but the total could exceed the internal number. Reconcile against
the provider console before publishing cost claims.

## Shared budget, not a new budget

- Cap: **100 CNY**, unchanged.
- Prior GPT-4o conservative spend inherited from `reports/api_budget_100cny.json`
  (`committed_cny = 21.02928` at the time of writing). The new ledger
  `reports/api_budget_qwen_100cny.json` reads that file, verifies its checksum and records
  `inherited_from` + `inherited_cny`; it refuses to start if the inherited ledger is missing
  or altered.
- The GPT-4o ledger itself is not modified, reset or re-initialised.

`provider_ledger.py` keeps the safety properties of `money_guard.py` (single locked file,
persistent identity anchor, checksummed atomic commits, reserve-before-call, unknown
outcomes charged in full, duplicate request ids refused) and changes one thing: the
reservation is sized from the actual prompt estimate plus the output bound, and a call that
uses more than its reservation is charged the actual amount instead of poisoning the
ledger. Exceeding the frozen per-call ceiling (32k input / 2048 output tokens) still blocks
the ledger permanently.

## Tool set actually used

`chest_xray_classifier` and `chest_xray_report_generator` (both already verified in earlier
real GPU runs), with `chest_xray_segmentation` available as an option. This is a **restricted
three-tool set**, not the six-tool paper Agent. CheXagent, LLaVA-Med and MAIRA-2 remain
unavailable because their weight downloads failed integrity checks; no claim is made about
them.

Per-call limits for the new runs: 3 tool calls, 4 model calls, 1024 output tokens, 240 s per
case, 120 s request timeout, zero retries.

## Protocol separation

`memory_pipeline` hashes the model and provider endpoint into `protocol_sha256`. Qwen runs
therefore form their own protocol family and can never retrieve GPT-4o memory records, and
vice versa. The frozen protocol for the current Qwen code state is

```
af04e2b8f868a655579db1d1186b36dae5c20f704863c1e2986223be70fe4574
```

Verified identical across two independent process invocations (2026-10-28). **Any edit to
`memory_agent_eval.py`, `tool_variants.py`, `provider_profile.py`, `provider_ledger.py`,
`memory_pipeline/injection.py`, the upstream tool sources, the prompts or the tool
provenance changes this hash and invalidates the pool.** Freeze the code before building the
pool.

## Known deviations to report

1. Central model is `qwen3-vl-plus` through DashScope, not GPT-4o through the paper's
   provider; every arm shares it, so model effects are not attributed to memory.
2. Prices are assumed and the ledger is not a bill.
3. Restricted tool set (classifier + report, optional segmentation).
4. The memory family is `multitool_original` with a new run-format name
   (`memory_agent_available_original_tools_v1`) added to the compiler; the older
   `first5_...` format is still accepted.
5. `_context` gained an optional `task_outcome` field used only by failure-aware retrieval;
   success-only retrieval output is unchanged.
6. Question count is 60 train / 40 validation, single-image only, chosen by a declared
   order-and-availability rule that never reads labels or outcomes.
