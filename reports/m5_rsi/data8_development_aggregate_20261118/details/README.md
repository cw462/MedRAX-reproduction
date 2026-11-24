# Qwen3.7-Plus M5 eight-tool development experiment

Each arm used 300 frozen development training cases and the same 100 frozen development validation cases.
GEPA, Meta-Harness and their sequential combination used these 100 validation cases for candidate selection.
The comparison measures development validation performance. The separate 848-case held-out evaluation is planned for the local environment.

| Arm | Development train | Development validation | Corrections vs DATA | Harms vs DATA | Net |
| --- | ---: | ---: | ---: | ---: | ---: |
| M5 + new data | 182/300 | 68/100 | 0 | 0 | +0 |
| M5 + new data + GEPA | 184/300 | 69/100 | 2 | 1 | +1 |
| M5 + new data + Meta-Harness | 186/300 | 67/100 | 2 | 3 | -1 |
| M5 + new data + GEPA → Meta-Harness | 190/300 | 65/100 | 1 | 4 | -3 |

Corrections count wrong-to-right cases relative to DATA. Harms count right-to-wrong cases.
M5 + new data + GEPA had the highest development validation score, with a net change of +1 correct cases versus DATA.
All four scores describe this development set. Held-out performance and the cause of individual changes require separate evidence.

## Optimizer outcomes

| Arm | Stage | Slots completed | Duplicate GEPA updates | Admitted Meta-Harness slots | Invalid `rank` interface rejections |
| --- | --- | ---: | ---: | ---: | ---: |
| M5 + new data + GEPA | gepa | 12/12 | 12 | — | — |
| M5 + new data + Meta-Harness | meta | 12/12 | — | 0 | 12 |
| M5 + new data + GEPA → Meta-Harness | gepa | 6/6 | 6 | — | — |
| M5 + new data + GEPA → Meta-Harness | meta | 6/6 | — | 0 | 6 |

The slot receipts distinguish completed proposal calls from admitted candidates. Candidate hashes identify the exact snapshots used for the selected scores.
The four arms selected the same policy snapshot. Their score differences come from separate replays of that policy, so these development scores do not measure the effect of a modified policy.
An offline check of equivalent guard-return syntax passed for all 12 Meta-Harness proposals and all six proposals in the combined arm. The live runs retained their original admission decisions and produced no scores for those proposals.

## Evidence

- [Paired validation predictions](validation_comparison.csv) follow the sealed case order.
- [Per-arm results and archived provenance](summary.json) include configuration, tool names, runtime/source hashes, candidate component hashes, usage and timing.
- [Paired outcome counts and case IDs](paired_outcomes.json) distinguish gains and harms.
- Structured decisions, sanitized tool observations, proposal outcomes and technical-failure evidence are available by arm. [DATA](DATA.json), [GEPA](GEPA.json), [META](META.json), [GEPA → META](GEPA_META.json).
- [Case sources](SOURCES.md) record attribution and the scope of redistributable benchmark material. [Source snapshot](reproduce/README.md) documents the archived experiment implementation.
- API duration sums can overlap across requests and arms. A controller start can be the most recent resumed attempt.
- Usage-derived cost estimates are in their recorded currency. Archived responses and local estimates do not establish total provider fees.
- Provider request bodies, response envelopes and local storage paths remain in the private evidence archive.
- [RSI source at the archived commit](https://github.com/GaryTang32/RSI/tree/73564ae9b7f9ac3641fe276d5ceb9c549e8c17e8).

## Tools

`chest_xray_expert`, `llava_med_qa`, `medgemma`, `llava_rad`, `medvlm_r1`, `maira2_grounded_report`, `xray_phrase_grounding`, `roi_crop`.
