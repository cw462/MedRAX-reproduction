# Qwen3.6-Flash Direct baseline

Qwen3.6-Flash answered the 848 frozen R55 chest X-ray questions using one original image, the question, and the supplied options when present. The prompt requested a short answer or an option letter. Native thinking was disabled. Sampling used temperature 0 and a 60-token output limit, with no tool calls or retrieval.

| Benchmark | Direct accuracy |
|---|---:|
| CheXBench OpenI | 256/380 (67.37%) |
| CheXBench Rad-ReStruct | 75/115 (65.22%) |
| CheXBench SLAKE | 115/123 (93.50%) |
| CheXBench pooled | 446/618 (72.17%) |
| Standalone SLAKE | 107/114 (93.86%) |
| VQA-RAD | 89/116 (76.72%) |
| Overall | 642/848 (75.71%) |

The main scores use the same Direct answer scorer as the DeepSeek V4.1 Flash RAG experiment. Qwen scored 630/835 (75.45%) on the 835 questions scored by DeepSeek Direct. The 13 other CheXBench items have original images in the Qwen first-call archive.

## Comparison with prompted CoT

The comparison below uses the R55 explicit-answer scorer for both the new Direct replies and the [archived CoT run](https://github.com/cw462/MedRAX-reproduction/blob/70fe042bc5a49a88db8507520477bb062d87d638/reports/r55_qwen36_flash_cot_20261115/README.md). It compares the two recorded configurations, which also differ in sampling settings and output budget.

| Benchmark | Direct | Prompted CoT | Wrong to right | Right to wrong |
|---|---:|---:|---:|---:|
| CheXBench pooled | 444/618 (71.84%) | 313/618 (50.65%) | 178 | 47 |
| Standalone SLAKE | 107/114 (93.86%) | 86/114 (75.44%) | 23 | 2 |
| VQA-RAD | 89/116 (76.72%) | 71/116 (61.21%) | 28 | 10 |
| Overall | 640/848 (75.47%) | 470/848 (55.42%) | 229 | 59 |

## Records

The [per-question records](predictions.jsonl) include the prompt inputs, answers, scores, response metadata, and links to the existing benchmark case evidence. [Protocol](protocol.json), [summary and token usage](summary.json), [runner](source/run_direct.py), and [Direct scorer](source/score_direct.py) provide the evaluation configuration and implementation.

The input images were taken from the first Qwen3.6-Flash ReAct call for each frozen case. The [R55 eight-tool run](https://github.com/cw462/MedRAX-reproduction/tree/reports/r55-autodl-8tools-20261121) documents the archive. Benchmark assets retain their source terms.
