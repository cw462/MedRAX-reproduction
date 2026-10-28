# Initial Qwen success-memory comparison

The completed exploratory comparison shows **no net accuracy increase**: both the no-memory Agent and the success-retrieval Agent answered **12/29 questions correctly (41.38%)**. Three questions changed from wrong to correct, and three changed from correct to wrong.

| Same 29 validation questions | No memory R0 | Success retrieval R1 |
|---|---:|---:|
| Correct / paired denominator | 12/29 | 12/29 |
| Valid completed answers | 29/29 | 29/29 |
| Model requests | 86 | 89 |
| Actual tool calls | 56 | 58 |
| Observed input tokens | 184,657 | 216,520 |
| Observed output tokens | 38,119 | 40,171 |
| Mean time per question | 37.4 s | 39.3 s |
| Conservative usage accounting for these paired outcomes | CNY 1.19606 | CNY 1.34813 |

The paired cases comprise nine both-correct, fourteen both-not-correct, three improved and three worsened outcomes. The exploratory paired case-cluster bootstrap 95% interval for the accuracy difference is **[-17.24, +17.24] percentage points** (29 distinct cases, 10,000 resamples, seed 20261028). Exact McNemar p=1.0. These observations neither establish a benefit nor rule out smaller effects on a larger independent evaluation.

## What actually ran

Both groups requested `qwen3-vl-plus` through the DashScope compatible endpoint, with identical recorded tools, tool versions, model configuration, prompts, source hashes and protocol hash. The available tools were the original classifier and report generator. This is a two-tool development experiment; the six-tool paper reproduction remains incomplete.

The training run completed 60 questions, with 35 reference-matching answers and 25 wrong answers under the recorded relaxed parser. A frozen training trajectory pool supplied structured execution facts. R1 queried and injected memory on all 29 evaluated questions, using three cards each and approximately 932 characters per question on average. Injected records exclude answer letters, option text and raw report prose. Clinical evidence remains unknown and step credit remains null. This is success-trajectory retrieval, not the full success/failure, credit, conflict or capacity method.

## Denominator and recovery limitations

The original Qwen validation run planned **30 single-image questions** and scored 12 correct, 17 incorrect and one API error: **12/30 (40%)** under the full planned denominator. This is a separate single-image development subset, not the earlier mixed-image validation30 selection.

Two earlier memory attempts stopped after eight terminal outcomes when reported completion usage exceeded the accounting profile ceiling despite a 1024-token request parameter. Their records and charges are retained. A subsequent recovery run omitted the affected question and completed the remaining 29. The table compares R0 and that single recovery R1 run on exactly the same 29 questions. It does **not** combine the best answers from different attempts, treat the omitted question as correct or present 29 as a completed 30-question evaluation. The exclusion occurred during recovery, so this is not a pristine preregistered comparison.

The runs were sequential, with stochastic model sampling and no repeated no-memory, random-memory or equal-token fixed-instruction controls yet. There is no heldout result. R2/R3 summaries and the later credit/action/conflict/update ablations have no result in this table.

## Budget and evidence

The cumulative conservative ledger after R1 recovery is **CNY 28.533768**, leaving **71.466232** under the original CNY 100 total ceiling. This inherits all earlier GPT-4o and Qwen accounting, including interrupted/repeated runs; it is not the provider bill. No new API round was started while waiting for this run to finish.

The internal Qwen rates remain CNY 4/million input and CNY 12/million output at the recorded profile ceiling. The [official Model Studio pricing page](https://help.aliyun.com/zh/model-studio/model-pricing) currently lists mainland Qwen3-VL-Plus rates of CNY 1/million input and CNY 10/million output for input up to 32K; the internal figures therefore remain conservative for that tier. Requests exceeding the profile limit require an explicit protocol/accounting repair, not repeated ledger restarts or selective removal of difficult cases.

| Artifact | R0 SHA256 | R1 recovery SHA256 |
|---|---|---|
| Manifest | `bf67b7be3026fa815b246adc076ec073393f05246b4dc4aa7bd1c20e541b5f3e` | `08a4ff03cbb31104f5f5dc7285b138a111ab5f1376ff48b113591893975ea3bd` |
| Result journal | `7d65d6016ed686d496ecc4d45f37fa4fc9c4d86de872fda7dbb64a3c20a0cf89` | `7d4c32db40f7ee67f579b57c0953ab6894752918323a7344e9ebb7df9e467504` |
| Final summary | `7a2fa5d8400479359a6eb08509116f7467f731d9957ea9036f39bf9abb56d879` | `a40f0fb6480b66f691b59c5730a798cd42487edcdb07317915b4ab101bcd8a73` |

Private journals, references and detailed recovery analysis remain outside Git. The aggregate comparison was computed in a separate read-only scoring process after completion; no reference answers were passed to an inference or memory query.
