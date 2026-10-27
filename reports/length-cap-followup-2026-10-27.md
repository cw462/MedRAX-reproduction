# Output-cap follow-up on ten selected development questions

The [predeclared selection rule](diagnostic-followup-plan.md) was applied to the completed [50-question diagnostic run](diagnostic50-2026-10-27.md). It selected the first ten questions in original input order with a truncation marker in either arm, from 29 eligible questions. Selection used neither reference labels nor correctness. Both arms were rerun with a 1024-token output cap instead of 512, with other declared settings and relative arm order unchanged. No protocol repair was enabled.

Actual execution ran from **21:15:24 to 21:24:52, Asia/Shanghai, on 2026-10-27: 9 minutes 28 seconds**. All 20 scheduled arm outcomes completed. Reference labels were accessed afterward by an offline scorer.

| Observation, same selected ten questions | Direct 512 | Direct 1024 | Agent 512 | Agent 1024 |
|---|---:|---:|---:|---:|
| Correct / fixed denominator | 3/10 | 5/10 | 4/10 | 6/10 |
| Questions with first-phase truncation | 5 | 0 | 10 | 0 |
| Completed valid final options | 10 | 10 | 9 | 10 |
| API error outcomes | 0 | 0 | 1 | 0 |
| Invalid tool-call schema markers | 0 | 0 | 1 | 0 |
| Model requests | 20 | 20 | 29 | 30 |
| Verified classifier returns | 0 | 0 | 9 | 10 |
| Observed input tokens | 15,425 | 15,872 | 33,319 | 36,157 |
| Observed output tokens | 4,507 | 4,954 | 5,531 | 5,657 |

The original Agent subset includes one request with unknown usage, so its token totals are incomplete. Each arm had two not-correct-to-correct changes and no correct-to-incorrect changes between the two caps. One of the Agent's two changes was the previously failed question, which completed and matched the reference in this retest. The within-arm accuracy difference was +20 percentage points, with an exploratory paired case-cluster percentile bootstrap 95% interval of [0, 50] percentage points for each arm (10,000 resamples, seed 20261027). These very small selected samples do not support a general accuracy claim. The 1024 Agent-versus-direct comparison had two improvements and one regression, not the two improvements and zero regressions of each arm's cap comparison.

No length stop or API error was observed in the 1024 run. This supports investigating output budget as an execution issue before evaluating memory. It does not establish the cause of the earlier HTTP error or prove that increasing the cap caused the accuracy changes: calls were repeated at temperature 0.2, there was no repeated-512 control, and provider conditions may vary. This is a targeted development follow-up, not a new held-out evaluation. It must not replace the full 50-question result with an apparently better denominator.

The 1024 run used 50 actual API requests and 62,640 reported tokens. Two reservation blocks were used before each request; those 100 ledger blocks are not 100 API calls. Its incremental conservative ledger charge was **CNY 1.88946**, taking the cumulative ledger from CNY 11.96912 to **CNY 13.85858**, with CNY 86.14142 remaining under the user's CNY 100 ceiling. These are conservative accounting values, not provider billing. The original unknown-charge reservation remains in the cumulative ledger; comparing subset ledger totals as if they were actual price savings would be misleading.

Median observed arm times were direct 19.30 to 21.56 seconds and Agent 27.04 to 35.49 seconds. Different service conditions and the original error limit timing comparisons; this was not a controlled throughput experiment.

## Reproduction and provenance

The follow-up verifies the completed baseline's manifest, journal and summary; checks input/image hashes, prompts, package versions, original source hashes and shared ledger identity; and writes a separate run directory. The original baseline remains intact. With the frozen baseline artifacts and matching runtime available:

```sh
python experiments/length_cap_followup.py \
  --baseline-run /path/to/completed-diagnostic50 \
  --input /path/to/diagnostic50/inference.jsonl \
  --output /path/to/new-followup-run \
  --ledger /path/to/the-existing-budget-ledger \
  --api-key-stdin
```

Use a secure runtime secret input; do not put credentials into a saved command. Repository and image locations are inferred from the baseline manifest, and the ledger must match its existing path. The existing `score_diagnostics.py` evaluates isolated labels after inference; comparing caps additionally requires restricting both results to the same frozen ten-question inference/audit subset. The full 50-question input is not an appropriate denominator for that subset comparison.

- Follow-up manifest SHA256: `974abc7748ccf89e30e711b51a37c28dc74b8aef8744f8cafa52871d69f447ba`.
- Follow-up result journal SHA256: `069e918a208f48bc29a17e2a671f561dd426fc01861c7127bc3301cc2ad2bcdf`.
- Follow-up summary SHA256: `dc0f546d825e5bb0c4d55e8dbdc095794ba4d115de7295b7fc70c0becc14d680`.
- Derived ten-question scoring input SHA256: `3a66eca99984b29e7be61e16b98cbb1407e2fe66b83659291a09c44825fc572b`.

No memory intervention or additional medical tool was evaluated. Clinical evidence remains unverified; valid tool execution and final answer matching are separate measurements.
