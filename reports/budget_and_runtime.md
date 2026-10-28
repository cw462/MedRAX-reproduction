# Shared budget and runtime checkpoint

The user's ceiling remains **CNY 100 total**, not CNY 100 per experiment. Reuse the original authoritative server ledger, identity, lock and atomic reservations; do not reset it or introduce an independent spending ledger.

## Qwen stage (2026-10-28)

The GPT-4o ledger stayed at **21.02928** committed while a separate Qwen ledger inherited that
total under the same CNY 100 authorisation. The Qwen ledger uses a different price table, so it
is a separate file, not a second budget: each new file inherits the previous committed total and
is created only after the previous one is permanently blocked by an integrity rule.

| Qwen stage | Outcome |
|---|---|
| Capability probes and diagnoses | a few hundredths of a CNY |
| `train60_r0_v2` (60 questions, pool source) | completed; 60/60 |
| `val30_r0_v1` (30 questions, baseline) | completed; 29 valid + 1 provider timeout |
| `val30_r1_v1` (8 questions, first R1 attempt) | stopped at question 9: one completion of 4469 tokens exceeded the 2048 frozen ceiling; the ledger blocks permanently by design |
| `val30_r1b_v1` (8 questions, second attempt, ledger v2) | same question, same overrun, same block |
| `val29_r1c_v1` (29 questions, ledger v3) | completed; 29/29 |

Latest committed total (ledger `api_budget_qwen_100cny_v3.json`): **28.533768 CNY**, i.e. about
**7.50 CNY** of internal occupancy for the whole Qwen stage. Of that, roughly 1.27 CNY are
reservations for provider-rejected calls during the account-arrears window that were never
billed, and the two aborted R1 attempts add further over-counted reservations. **These are
conservative internal values, not the provider bill**; the assumed price table (4/12 CNY per
million tokens) was never verified against the provider console.

Raw runtime: about 48 minutes for the 60-question pool run (including a resume after an SSH
drop), 20 minutes for the 30-question baseline, 25 minutes for the final 29-question R1.

| Earlier stage | Elapsed wall time | Incremental conservative occupancy |
|---|---:|---:|
| Original 50 direct/Agent pairs | 34m50s | See original report; cumulative 11.96912 after this stage |
| Selected ten-pair 1024 follow-up | 9m28s | 1.88946 |
| Five-pair classifier + report smoke | 4m44s | 6.18548 |
| Five-pair classifier + report + segmentation check | 3m51s, plus initialization | 0.98522 |

After the three-tool functional check (before the Qwen stage), total conservative occupancy was
**21.02928**, remaining **78.97072**. The figures below explain the preceding batches and are
retained as accounting history.

After the five-pair two-tool smoke, cumulative occupancy is **20.04406**, remaining **79.95594**. Of the last batch, 0.98356 is attributed to reported usage and 5.20192 is the reservation retained for one request with unknown usage after timeout. Earlier unknown-use reservations are also retained. These are conservative budget values, not the provider bill. The shared ledger is authoritative if later batches have run.

Public APIYi pricing was rechecked at **2026-10-27 14:52:34 UTC** through its public `/api/pricing` and `/api/status` endpoints. The recorded model ratio 1.25, completion ratio 4, quota 500,000/USD and supported group ratio 1 remain compatible with the guard's USD 2.5/million input, USD 10/million output and conservative CNY 8/USD assumptions. Account-specific billing was unavailable. The 1024 cap reserves two original 512-output ledger blocks, totaling 5.20192 before a call; those blocks represent one API request, not two.

The earlier 50-pair known-token estimate was CNY 8.81874. Linear extrapolation to 2,500 pairs is approximately **CNY 441 and 29 hours**, excluding unknown charges, additional tool/model turns, memory construction, summaries, repetitions and external evaluation. It is a historical scenario, not a quote or proof that the full plan fits the remaining balance. A new multi-tool five-case sample is too small, and includes too little known failure behavior, for a reliable full-project forecast.

Model downloads and local GPU smoke checks do not consume this API ledger. They still require disk, bandwidth and GPU time. Download completion times are uncertain; partial assets support range resume and must pass size and hash checks before use.

Before each larger paid stage, freeze the full schedule, shared-ledger identity and stage ceiling; require a worst-case reservation to fit both limits. Report completed paired denominators and pending work if stopped. Never silently reduce the declared denominator, discard expensive errors or treat a conservative reservation release as a verified provider refund.
