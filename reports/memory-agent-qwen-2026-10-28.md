# Memory-assisted multi-tool Agent with Qwen3-VL-Plus

Date: 2026-10-28 (Asia/Shanghai). Status: **first end-to-end run of the memory pipeline;
development-scale samples, not a paper reproduction and not clinical validation.**

This run replaces the retired Codex execution with the DeepSeek Harness and replaces the
GPT-4o central model with `qwen3-vl-plus` (DashScope compatible endpoint). The provider facts,
pricing assumption and the account-arrears interruption are documented in
[the provider report](qwen-provider-2026-10-28.md). A separate short note on the same
comparison, including a case-cluster bootstrap interval, is
[qwen-memory-initial-2026-10-28.md](qwen-memory-initial-2026-10-28.md); its counts and ledger
total agree with this report.

## What actually ran

| stage | run | questions | status counts | protocol |
|---|---|---|---|---|
| train pool build (R0, no memory) | `train60_r0_v2` | 60 | {'completed': 60} | `2c51bab7a891e9b2…` |
| validation baseline (R0) | `val30_r0_v1` | 30 | {'completed': 29, 'model_error': 1} | `2c51bab7a891e9b2…` |
| validation memory (R1) | `val29_r1c_v1` | 29 | {'completed': 29} | `2c51bab7a891e9b2…` |

Tools available in every arm: `chest_xray_classifier`, `chest_xray_report_generator` (original
implementations, provenance-hashed). Limits: 3 tool calls, 4 model calls, 1024 output
tokens, 240 s per case, zero retries. The same protocol hash is required for retrieval, so
all three runs share one agent configuration; only the memory arm differs.

Pool compilation (`runs/memory_pool_v1/compile_report.json`):

- compiled trajectories: **59**
- compiled real tool steps: 118
- skipped: {'image_read_integrity_failure': 1}
- task outcomes: {'incorrect': 25, 'correct': 34}
- independent outcome sidecar bound: yes
- `success_retrieval_ready`: True

## Paired validation result

Both arms answered the same 29 frozen validation questions in the same
order; the R1 arm additionally retrieved from the frozen training pool (top-k 3,
`min_score=0.0`, success-only, same-case excluded) and injected a bounded structural block
before the question.

| arm | graded | correct | accuracy (graded) | accuracy (all) | mean tool calls | mean seconds | accounted CNY |
|---|---|---|---|---|---|---|---|
| R0 baseline | 29 | 12 | 41.4% | 41.4% | 1.93 | 37.4 | 1.19606 |
| R1 success retrieval | 29 | 12 | 41.4% | 41.4% | 2.0 | 39.3 | 1.34813 |

Invalid/error counts over the shared questions: R0 `0` invalid + `0`
error; R1 `0` invalid + `0` error. The one question excluded from the
R1 input (`13238_8353800603808`) is the same question on which R0 timed out and both earlier R1
attempts hit the output ceiling, so it is outside the paired set. Under the full planned R0
denominator the baseline is 12/30 = 40.0%; the paired table uses the 29 shared questions.

Paired transitions over the 29 shared questions:

| both correct | both wrong | R0 only | R1 only |
|---|---|---|---|
| 9 | 14 | 3 | 3 |

Exact McNemar on the discordant pairs: p = **1.0**. With
6 discordant pairs this test
has very little power; the interval around a 41.4% accuracy is wide and
the comparison is **not** a demonstration of a general improvement.

Retrieval behaviour in R1: 29/29 questions
received at least one memory (100.0%), mean rendered memories
3.0, mean injected characters 932.1.

## Accounting

The Qwen ledger is the same ¥100 authorisation as the GPT-4o ledger and inherits its
committed total:

- inherited from the GPT-4o ledger: 21.02928 (carried through the chain) CNY
- committed after these runs (latest ledger `api_budget_qwen_100cny_v3.json`): **28.533768 CNY**
- of which reservations for provider-rejected calls during the arrears window are charged in
  full by policy although the provider billed nothing (see the provider report)
- prices are assumed (4 CNY/M input, 12 CNY/M output) and the ledger is **not** the bill. The
  provider's public pricing page lists CNY 1/M input and CNY 10/M output for Qwen3-VL-Plus up
  to 32K input, so the internal rates over-reserve; they are conservative, not exact.

## What this does and does not establish

Establishes:

- the memory pipeline runs end to end on real GPU tools and a real hosted VLM: successful
  trajectories are compiled from real executions, frozen into an immutable pool, retrieved
  with the agent's actual tool versions, rendered into a bounded prompt block, and evaluated
  on paired questions;
- every claim is backed by a hashed run artefact (`manifest.json`, `results.jsonl`,
  `trace.jsonl`, `summary.json`), an independent outcome sidecar and a frozen pool with a
  pinned SHA-256;
- the compiler refuses labels, answers, clinical verification and fabricated credit.

Does not establish:

- any improvement from memory: the paired sample is small, single-seed, and the retrieved
  context contains only structural execution facts (tool order, validity, output shapes) —
  no reasoning, no report prose, no medical content;
- a paper reproduction: the tool set is restricted (classifier + report, segmentation
  optional), the model is not GPT-4o, and the prompts/threading follow the earlier audited
  smoke rather than the author notebook;
- step credit, candidate action selection, conflict review or capacity-limited memory
  update: those modules (R4-R7 in the plan) are **not implemented** and are explicitly out
  of scope for this run; `clinical_evidence` stays `unknown` and `step_credit` stays `null`;
- heldout or external evaluation: `heldout_test` was not touched and external data is
  blocked on authorization.

## Reproduce

```bash
# 1. frozen subset (label-blind, byte-verified)
python experiments/prepare_memory_subset.py --splits data/prepared_v2 \
  --exclusions data/audit_v3/leakage_exclusion_manifest.json \
  --image-audit data/audit_v3/image_audit.jsonl --archive figures.zip \
  --out data/memory_v1 --train 60 --validation 40

# 2. pool build (R0 on training questions)
python experiments/memory_agent_eval.py ... --arm r0 --input data/memory_v1/inputs/memory_train_subset_v1.jsonl ...
python experiments/score_memory_runs.py --run runs/train60_r0_v2 --splits data/prepared_v2 \
  --labels data/prepared_v2/memory_train.labels.jsonl --outcomes runs/train60_r0_v2_scored/outcomes.json
python -m memory_pipeline --splits data/prepared_v2 --exclusions ... --run runs/train60_r0_v2 \
  --outcomes runs/train60_r0_v2_scored/outcomes.json --output runs/memory_pool_v1 --pool-version 1

# 3. paired validation
python experiments/memory_agent_eval.py ... --arm r0 --input data/memory_v1/inputs/validation_subset_v1.jsonl ...
python experiments/memory_agent_eval.py ... --arm r1 --pool runs/memory_pool_v1/pool.json --pool-sha256 <hex> ...
python experiments/compare_memory_arms.py --baseline runs/val30_r0_v1 --compare runs/val29_r1c_v1 \
  --labels data/prepared_v2/validation.labels.jsonl --report runs/val30_comparison.json
```
