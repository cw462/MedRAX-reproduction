# Fixed development comparison with conservative budget accounting

`diagnostic_eval.py` compares two-stage direct visual answering with the official classifier-only MedRAX Agent. The direct arm preserves the shared medical system first line and reasoning prompt, removing tool-specific instructions. Both arms use the same complete images, question, requested model, sampling settings, 512-token per-request limit and letter-only follow-up. This is a matched development diagnosis, not the exact author quickstart or six-tool paper protocol.

Prepare inference records with exactly question_id, question and images. Selection must be frozen before inspecting answers. The initial development sample contains 50 different memory-train cases with one complete image each, selected in file order. It is not representative stratified sampling. Each arm gets a fresh history; arm order alternates by question unless a fixed seed is provided.

```sh
python experiments/diagnostic_eval.py --repo /path/to/MedRAX \
  --input /path/to/diagnostic50/inference.jsonl \
  --images-root /path/to/diagnostic50/images --output /path/to/new-run \
  --ledger /path/to/shared-api-budget.json --base-url https://api.apiyi.com/v1 \
  --api-key-stdin --device cuda:0
```

Supply the key through an existing secure runtime environment or an authenticated process pipe, not a literal command argument, committed file or echoed terminal input. `--api-key-stdin` reads one line; otherwise the runner uses OPENAI_API_KEY. No automatic retries are enabled. Local tool execution cannot be cancelled by the call-boundary deadline.

`results.jsonl` writes and fsyncs a started record before each question/arm and a terminal record afterward. `summary.json` includes every planned question and arm, including missing images, errors, budget stops and unrun items. Resume with the same command and `--resume`; configuration, source, prompts, input/image hashes and ledger path must match. A previously started arm without a terminal result is marked interrupted and is never automatically reissued. Provider errors stop after three consecutive failed arms; authentication/permission errors and unexpected returned model IDs stop immediately.

The trace records invocation counts, returned model IDs, finish reasons, usage, repetition/failure tags and content hashes. It does not save raw chain-of-thought text or reference answers. A final valid option is not a correctness score. A `length` finish reason is retained even if the second phase later returns a valid letter.

## Budget assumptions

The user-authorized ceiling for this session is CNY 100. The shared ledger begins with CNY 0.54942, conservatively accounting for the earlier five-question smoke (17,995 input and 2,369 output tokens). Current verified APIYi public rates for the fixed model are USD 2.50/M input and USD 10/M output; both enabled groups have multiplier 1. The guard uses CNY 8/USD, exceeding the inspected provider recharge/display conversions (7 and 7.3), and does not subtract cache discounts.

Before every model call it reserves 128,000 input tokens plus 512 output tokens: CNY 2.60096. Complete valid usage releases excess reservation; errors, missing usage and interrupted pending calls retain the full reservation. An unexpected returned model or usage beyond the assumed bounds blocks further calls. The ledger uses Decimal amounts, atomic replacement, a persistent identity check and an exclusive process lock. Existing policy cannot be silently changed or reset.

This is an application pre-call ceiling under verified rates and token bounds, **not a provider-enforced account billing cap**. The provider's account-balance API requires separate account permissions not available to this run. Ledger values are conservative accounting, not observed actual charges. Recheck public pricing and model bounds before starting; stop if assumptions differ. Do not create a fresh ledger to bypass previously incurred costs, and do not run unrelated jobs with this key under an untracked budget.

## Independent scoring

After prediction, run the scorer separately with the frozen input, audit manifest and authorized development labels:

```sh
python experiments/score_diagnostics.py --results /path/to/run/results.jsonl \
  --labels /path/to/memory_train.labels.jsonl \
  --inference /path/to/diagnostic50/inference.jsonl \
  --audit-manifest /path/to/diagnostic50/audit_manifest.json \
  --output /path/to/new-score.json
```

The scorer ignores started records, rejects duplicate terminal results, retains the planned denominator, and reports direct/Agent accuracy, invalid/errors/unrun, paired gains/losses and a seeded case-cluster bootstrap interval. It writes aggregate counts and question-ID error indexes, not answer letters or reference explanations. Test labels must not enter inference, memory construction or hyperparameter selection. Only the predefined development partition is authorized for this diagnostic run.
