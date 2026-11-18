# Qwen3.7-Plus M5 fixed META supplements

All three runs started at 16:05:44 Beijing time on November 18, 2026. Each strategy was fixed before validation. The source slots identify the archived Meta-Harness proposals that were rewritten into equivalent single expressions for the local policy interface.

| Strategy | Retention rule | Source slot | Development train | Development validation | Finished (Beijing) | Elapsed |
| --- | --- | --- | ---: | ---: | --- | ---: |
| Neighbor +0.2 | Keep all | META 001 | 188/300 | 68/100 | 18:18:48 | 2h 13m 04s |
| Neighbor +0.5 | Keep all | META 002 | 187/300 | 66/100 | 18:19:15 | 2h 13m 31s |
| Neighbor +0.5 with filter | Keep neighbors and non-neighbors with score > 0.7 | GEPA → META 005 | 187/300 | 68/100 | 18:11:49 | 2h 06m 05s |

## Experimental settings

- **Model and tools** — Qwen3.7-Plus with M5 and eight tools. The resident tool pool provides CheXagent-8B, LLaVA-Med, MedGemma, LLaVA-Rad, MedVLM-R1, MAIRA-2 grounded report, X-ray phrase grounding, and ROI crop. The runs shared the GPU tool execution slot. ROI ran on CPU.
- **Data** — one frozen 300-question development training split (220 Rad-ReStruct / OpenI and 80 SLAKE questions) and one frozen 100-question development validation split (70 and 30). Both splits match the original development report.
- **Memory and scoring** — each run built its own Memory from the training sequence and began validation from that run's saved trained Memory. Validation proceeded in order using the existing M5 post-prediction feedback and Memory update. The prediction was saved before the reference was opened. Accuracy is correct answers divided by the full split size. The original solver, memory-writing, and advice-synthesis prompt components were retained.
- **Retrieval** — every supplement set `top_k = 5`, `semantic_weight = 0.8`, lexical weight 0.2, and `max_neighbors = 3`. A neighbor is a graph-expanded node absent from the initial retrieval seeds. Ranking adds the specified bonus to a neighbor's score and uses the original score for other nodes. The filter applies to the original score. It keeps all neighbors and drops non-neighbors with score at or below 0.7.

## Interpretation

The +0.2 and +0.5/filter strategies both scored 68/100, matching the original DATA result. The +0.5-only strategy scored 66/100. The filter increased the observed score by two questions compared with the otherwise configuration-matched +0.5 run. The original META run scored 67/100 and its unmodified native policy used an effective `top_k = 3`, so the one-question difference against it cannot isolate the effect of neighbor weighting or filtering. Each entry here represents one run on the same 100 development validation questions.

[Original four-arm development report](README.md)
