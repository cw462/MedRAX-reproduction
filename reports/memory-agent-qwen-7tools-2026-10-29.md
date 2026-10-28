# Seven-tool memory run with Qwen3-VL-Plus

Date: 2026-10-29 (Asia/Shanghai). Status: **full seven-tool registry, first paired memory
comparison on the frozen validation questions; development scale, not a paper reproduction and
not clinical validation.**

## Tool set actually wired

`chest_xray_classifier`, `chest_xray_expert`, `chest_xray_report_generator`, `chest_xray_segmentation`, `dicom_processor`, `image_visualizer`, `llava_med_qa`

Weights are local (CheXagent 12.6 GB + XraySigLIP 2.6 GB, LLaVA-Med 15.1 GB + CLIP 3.4 GB,
report generator 0.5 GB, classifier 28 MB, segmentation 261 MB). GPU placement: classifier,
report, segmentation and LLaVA-Med on `cuda:0`; CheXagent on `cuda:1`; utilities on CPU. Nothing
is downloaded at run time (`HF_HUB_OFFLINE=1`).

Not available: `xray_phrase_grounding` (MAIRA-2 needs transformers>=4.46; it loads in bf16 but
its grounding post-processing returns an empty object sequence on the pinned 4.45 runtime) and
`chest_xray_generator` (no public RoentGen weights were found). Both are documented blockers, not
silently replaced.

## What ran

| stage | run | questions | status counts | mean seconds |
|---|---|---|---|---|
| pool build (R0, seven tools) | `train60_full_r0` | 60 | {'completed': 45, 'case_budget_exceeded': 15} | 40.8 |
| validation R0 | `val29_full_r0` | 29 | {'completed': 20, 'case_budget_exceeded': 9} | 37.3 |
| validation R1 | `val29_full_r1` | 29 | {'completed': 27, 'case_budget_exceeded': 2} | 38.9 |
| validation R2 | `val29_full_r2` | 29 | {'completed': 26, 'case_budget_exceeded': 3} | 36.4 |
| validation R3 | `val29_full_r3` | 29 | {'completed': 28, 'case_budget_exceeded': 1} | 35.0 |

Pool: **60 trajectories**, 173
real tool steps, skipped {}, outcomes {'incorrect': 20, 'correct': 25, 'error': 15},
`success_retrieval_ready = True`.

Arms: R0 no memory; R1 success-trajectory retrieval; R2 deterministic rule summary; R3
success + failure retrieval. Same model, prompts, tool set and call limits in every arm; only the
injected block differs.

## Paired validation result (29 frozen questions)

| arm | graded | error/invalid | correct | accuracy (graded) | accuracy (all 29) | mean seconds | accounted CNY |
|---|---|---|---|---|---|---|---|
| R0 | 20 | 9 | 11 | 55.0% | 37.9% | 37.3 | 2.2882 |
| R1 | 27 | 2 | 14 | 51.8% | 48.3% | 38.9 | 2.1853 |
| R2 | 26 | 3 | 12 | 46.2% | 41.4% | 36.4 | 2.3019 |
| R3 | 28 | 1 | 16 | 57.1% | 55.2% | 35.0 | 2.0272 |

| comparison | shared | both correct | both wrong | R0 only | memory only | McNemar p |
|---|---|---|---|---|---|---|
| R0 vs R1 | 29 | 10 | 14 | 1 | 4 | 0.375 |
| R0 vs R2 | 29 | 9 | 15 | 2 | 3 | 1.0 |
| R0 vs R3 | 29 | 11 | 13 | 0 | 5 | 0.0625 |

**Reading the numbers.** R0 answered only 20 of 29 cases: nine exhausted the fixed per-case
budget (4 tool calls / 6 model calls) with no final answer, because without memory the agent
retries tools more often. The memory arms finished 26-28 of 29 cases. Most of the raw accuracy
difference therefore comes from *not failing*, not from better reasoning: among cases that
produced an answer, the accuracy is nearly identical (R0 55.0%, R3 57.1%). R3 (success + failure
memory) is the only arm whose paired comparison is close to conventional significance (5 of 5
discordant cases improved, exact McNemar p = 0.0625), but with 5 discordant pairs this is a weak
signal and the run is single-seed.

Retrieval behaviour:

| arm | questions with hits | hit rate | mean rendered | mean chars |
|---|---|---|---|---|
| R1 | 29/29 | 100.0% | 3.0 | 905.7 |
| R2 | 29/29 | 100.0% | 3.0 | 790.0 |
| R3 | 29/29 | 100.0% | 3.0 | 940.4 |

## Accounting

Ledger `api_budget_qwen_100cny_v8.json` (uncapped by user request on 2026-10-28):
committed **46.082632 CNY** across the whole Qwen stage, of which earlier
GPT-4o spend 21.02928 is carried by inheritance. Prices remain the conservative assumed
4 / 12 CNY per million tokens; the provider's public list price is lower, so the ledger
over-reserves. **It is not the provider bill.**

## What this establishes and what it does not

Establishes:

- the memory pipeline runs end to end with seven real tools, including a hosted VLM as the
  central model, with every tool call recorded as an execution fact;
- success trajectories from a 60-question training pool are frozen, retrieved under matching
  tool versions and injected into paired validation runs;
- the comparison is paired on identical questions with identical configuration, and every
  number is backed by hashed run artefacts plus an independent outcome sidecar.

Does not establish:

- clinical validity, a paper reproduction, or a general improvement;
- step credit, candidate action selection, conflict review or capacity-limited memory update
  (R4-R7 remain unimplemented);
- heldout or external evaluation;
- coverage of the full paper tool set: 7 of 9 tools are wired, MAIRA-2 grounding and the chest
  X-ray generator are missing for documented reasons.

## Reproduce

```bash
bash code/full_experiment.sh            # pool + R0/R1/R2/R3, writes runs/ and logs/
python code/make_report_v2.py           # this report
```
