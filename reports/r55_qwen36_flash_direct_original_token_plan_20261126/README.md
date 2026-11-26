# Qwen3.6-Flash Direct with the original project credential

The original and new Token Plan credentials were evaluated on the same 848 Direct questions with the same archived images, answer-only prompt, endpoint, model alias, temperature, output limit, and scorer. Each run disabled native thinking and used no retrieval or tools. The credential and run time differed.

| Benchmark | Original credential | New credential | Difference (pp) | New wrong, original right | New right, original wrong |
|---|---:|---:|---:|---:|---:|
| CheXBench OpenI | 254/380 (66.84%) | 256/380 (67.37%) | -0.53 | 9 | 11 |
| CheXBench Rad-ReStruct | 75/115 (65.22%) | 75/115 (65.22%) | +0.00 | 0 | 0 |
| CheXBench SLAKE | 114/123 (92.68%) | 115/123 (93.50%) | -0.81 | 0 | 1 |
| CheXBench pooled | 443/618 (71.68%) | 446/618 (72.17%) | -0.49 | 9 | 12 |
| Standalone SLAKE | 106/114 (92.98%) | 107/114 (93.86%) | -0.88 | 1 | 2 |
| VQA-RAD | 91/116 (78.45%) | 89/116 (76.72%) | +1.72 | 2 | 0 |
| Overall | 640/848 (75.47%) | 642/848 (75.71%) | -0.24 | 12 | 14 |

With the R55 explicit-answer scorer, the original credential scored 638/848 (75.24%) and the new credential scored 640/848 (75.47%). Exact answer text matched on 803/848 questions.

[Original-credential predictions and paired answers](predictions.jsonl) · [Protocol](protocol.json) · [Summary](summary.json) · [New-credential report and evaluation code](https://github.com/cw462/MedRAX-reproduction/blob/53f50cc100f4c2f9a0a7c3075c87f976125c369b/reports/r55_qwen36_flash_direct_20261126/README.md).
