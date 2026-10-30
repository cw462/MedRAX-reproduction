# V9 paired diagnostic metrics

Run status: **completed**. Planned N=20; failures remain in this denominator.

| Group/policy | Correct/N | Missing | Accuracy | Corrections | Harms | Net |
|---|---:|---:|---:|---:|---:|---:|
| P0 | 14/20 | 0 | 70.0% | — | — | — |
| D raw candidate | 4/20 | 15 | 20.0% | 0 | 10 | -10 |
| D always_retain | 14/20 | 0 | 70.0% | 0 | 0 | +0 |
| D always_accept | 13/20 | 0 | 65.0% | 0 | 1 | -1 |
| D evidence_gate | 13/20 | 0 | 65.0% | 0 | 1 | -1 |
| DK raw candidate | 3/20 | 16 | 15.0% | 0 | 11 | -11 |
| DK always_retain | 14/20 | 0 | 70.0% | 0 | 0 | +0 |
| DK always_accept | 13/20 | 0 | 65.0% | 0 | 1 | -1 |
| DK evidence_gate | 14/20 | 0 | 70.0% | 0 | 0 | +0 |
| DKB raw candidate | 2/20 | 18 | 10.0% | 0 | 12 | -12 |
| DKB always_retain | 14/20 | 0 | 70.0% | 0 | 0 | +0 |
| DKB always_accept | 14/20 | 0 | 70.0% | 0 | 0 | +0 |
| DKB evidence_gate | 14/20 | 0 | 70.0% | 0 | 0 | +0 |
| DKC raw candidate | 4/20 | 15 | 20.0% | 0 | 10 | -10 |
| DKC always_retain | 14/20 | 0 | 70.0% | 0 | 0 | +0 |
| DKC always_accept | 13/20 | 0 | 65.0% | 0 | 1 | -1 |
| DKC evidence_gate | 13/20 | 0 | 65.0% | 0 | 1 | -1 |

## Gate decisions on the same legal changed candidates

| Group | Corrections retained/available | Retention | Harms prevented/available | Prevention | False rejects | Wrong accepts | Error fallbacks |
|---|---:|---:|---:|---:|---:|---:|---:|
| D | 0/0 | N/A | 0/1 | 0.0% | 0 | 1 | 4 |
| DK | 0/0 | N/A | 1/1 | 100.0% | 0 | 0 | 5 |
| DKB | 0/0 | N/A | 0/0 | N/A | 0 | 0 | 5 |
| DKC | 0/0 | N/A | 0/1 | 0.0% | 0 | 1 | 4 |

Fallbacks are counted separately and never credited as successful harm prevention.

## Common completed samples (secondary)

| Group | Common N | P0 correct | Candidate correct | Final correct |
|---|---:|---:|---:|---:|
| D | 5 | 5 | 4 | 4 |
| DK | 4 | 4 | 3 | 4 |
| DKB | 2 | 2 | 2 | 2 |
| DKC | 5 | 5 | 4 | 4 |

All-four-group common completed N=2.

## Recorded time and resources

| Stage | Timed records | Elapsed total (s) | Median (s) | Model calls | Tool calls | Input tokens | Output tokens | Logical CNY | Incremental CNY |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| shared P0 | 20/20 | 1335.072 | 68.383 | 117.0 | 94.0 | 540073.0 | 43266.0 | 2.679484 | 2.679484 |
| D | 20/20 | 704.86 | 37.248 | 75.0 | 28.0 | 425888.0 | 22554.0 | 1.9742 | 1.9742 |
| DK | 20/20 | 722.577 | 38.287 | 75.0 | 24.0 | 437592.0 | 23411.0 | 2.0313 | 2.0313 |
| DKB | 20/20 | 653.148 | 35.355 | 71.0 | 24.0 | 423345.0 | 21293.0 | 1.948896 | 1.948896 |
| DKC | 20/20 | 754.272 | 40.386 | 75.0 | 32.0 | 456602.0 | 24425.0 | 2.119508 | 2.119508 |

Missing accounting fields remain N/A. Call counts do not substitute for measured duration. Shared P0 is charged once; branch totals exclude it. Cost is not independently verified provider billing.

## Injected context token estimates

| Group | Knowledge token estimate | Experience token estimate | Method |
|---|---:|---:|---|
| D | 0.0 | 0.0 | utf8_bytes_div4_estimate_not_provider_usage |
| DK | 3686.0 | 0.0 | utf8_bytes_div4_estimate_not_provider_usage |
| DKB | 3695.0 | 3709.0 | utf8_bytes_div4_estimate_not_provider_usage |
| DKC | 3872.0 | 6034.0 | utf8_bytes_div4_estimate_not_provider_usage |

Knowledge and experience values are injected-context estimates, separate from provider request usage.

## New observations

| Group | Collected | Explicit new usable | Explicit not new usable | Unadjudicated |
|---|---:|---:|---:|---:|
| D | 28 | 0 | 0 | 28 |
| DK | 24 | 0 | 0 | 24 |
| DKB | 24 | 0 | 0 | 24 |
| DKC | 32 | 0 | 0 | 32 |

## Limits

- Fixed development diagnostic; not an independent test or a stable effect estimate.
- Missing answers count as not correct in planned denominators.
- Exception fallback is not a successful gate rejection.
- Candidate harms include failures; gate opportunity denominators include only legal changed candidates.
- Clinical evidence quality is not inferred from tool calls, citations or model self-report.
- No inference-stage file has been modified by scoring.
