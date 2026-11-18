# Qwen3.7-Plus M5 eight-tool development experiment

All four arms used Qwen3.7-Plus with the same M5 eight-tool configuration. The frozen training split contains 220 Rad-ReStruct and 80 SLAKE questions. The frozen validation split contains 70 Rad-ReStruct and 30 SLAKE questions. Each arm validated from its own trained memory snapshot. The three search arms used the development validation split for candidate selection. This report covers development validation, with a separate 848-question evaluation planned locally.

| Arm | Development train | Rad-ReStruct validation | SLAKE validation | Total development validation | Corrections vs DATA | Harms vs DATA | Net |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| M5 + new data | 182/300 | 51/70 | 17/30 | 68/100 | 0 | 0 | +0 |
| M5 + new data + GEPA | 184/300 | 51/70 | 18/30 | 69/100 | 2 | 1 | +1 |
| M5 + new data + Meta-Harness | 186/300 | 50/70 | 17/30 | 67/100 | 2 | 3 | -1 |
| M5 + new data + GEPA → Meta-Harness | 190/300 | 49/70 | 16/30 | 65/100 | 1 | 4 | -3 |

Corrections count questions changed from incorrect under DATA to correct. Harms count the reverse.

| Arm | Stage | Completed slots | Duplicate GEPA updates | Admitted Meta-Harness proposals | Invalid `rank` interface rejections |
| --- | --- | ---: | ---: | ---: | ---: |
| GEPA | GEPA | 12/12 | 12 | — | — |
| META | Meta-Harness | 12/12 | — | 0 | 12 |
| GEPA → META | GEPA | 6/6 | 6 | — | — |
| GEPA → META | Meta-Harness | 6/6 | — | 0 | 6 |

See the [12 GEPA candidate records](GEPA_CANDIDATES.md) for each proposal and its disposition. The 12 duplicate dispositions for standalone GEPA consist of ten over-length updates that fell back to the parent prompt and two request failures with no saved candidate text.

Each arm selected the same baseline policy snapshot, H0. The reported scores came from independent H0 replays. A later offline syntax check passed for all 18 rejected Meta-Harness proposals after the branch and return statements were rewritten as equivalent conditional expressions.

The eight tools were CheXagent-8B, LLaVA-Med, LLaVA-Rad, MedGemma, MedVLM-R1, MAIRA-2 grounded report, X-ray phrase grounding, and ROI crop. After the resident pool was enabled, the GPU tools shared a single execution slot and ROI ran on the CPU. MAIRA-2 report and phrase grounding shared one model process.

Code provenance is pinned to the archived [RSI source revision](https://github.com/GaryTang32/RSI/tree/73564ae9b7f9ac3641fe276d5ceb9c549e8c17e8) and [GEPA 0.1.4](https://pypi.org/project/gepa/0.1.4/).

Read the [fixed META supplement results and settings](META_SUPPLEMENTS.md).
