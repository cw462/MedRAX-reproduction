# Shared budget and runtime checkpoint

The user's ceiling remains **CNY 100 total**, not CNY 100 per experiment. Reuse the original authoritative server ledger, identity, lock and atomic reservations; do not reset it or introduce an independent spending ledger.

| Completed stage | Elapsed wall time | Incremental conservative occupancy |
|---|---:|---:|
| Original 50 direct/Agent pairs | 34m50s | See original report; cumulative 11.96912 after this stage |
| Selected ten-pair 1024 follow-up | 9m28s | 1.88946 |
| Five-pair classifier + report smoke | 4m44s | 6.18548 |
| Five-pair classifier + report + segmentation check | 3m51s, plus initialization | 0.98522 |

**Latest checkpoint:** after the three-tool functional check, total conservative occupancy is **21.02928**, remaining **78.97072**. New paid question answering is stopped until the complete tool set is ready, following the user's clarification. The figures below explain the preceding batch and are retained as accounting history.

After the five-pair two-tool smoke, cumulative occupancy is **20.04406**, remaining **79.95594**. Of the last batch, 0.98356 is attributed to reported usage and 5.20192 is the reservation retained for one request with unknown usage after timeout. Earlier unknown-use reservations are also retained. These are conservative budget values, not the provider bill. The shared ledger is authoritative if later batches have run.

Public APIYi pricing was rechecked at **2026-10-27 14:52:34 UTC** through its public `/api/pricing` and `/api/status` endpoints. The recorded model ratio 1.25, completion ratio 4, quota 500,000/USD and supported group ratio 1 remain compatible with the guard's USD 2.5/million input, USD 10/million output and conservative CNY 8/USD assumptions. Account-specific billing was unavailable. The 1024 cap reserves two original 512-output ledger blocks, totaling 5.20192 before a call; those blocks represent one API request, not two.

The earlier 50-pair known-token estimate was CNY 8.81874. Linear extrapolation to 2,500 pairs is approximately **CNY 441 and 29 hours**, excluding unknown charges, additional tool/model turns, memory construction, summaries, repetitions and external evaluation. It is a historical scenario, not a quote or proof that the full plan fits the remaining balance. A new multi-tool five-case sample is too small, and includes too little known failure behavior, for a reliable full-project forecast.

Model downloads and local GPU smoke checks do not consume this API ledger. They still require disk, bandwidth and GPU time. Download completion times are uncertain; partial assets support range resume and must pass size and hash checks before use.

Before each larger paid stage, freeze the full schedule, shared-ledger identity and stage ceiling; require a worst-case reservation to fit both limits. Report completed paired denominators and pending work if stopped. Never silently reduce the declared denominator, discard expensive errors or treat a conservative reservation release as a verified provider refund.
