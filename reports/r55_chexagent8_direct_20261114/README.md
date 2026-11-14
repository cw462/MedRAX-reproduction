# CheXagent-8B direct evaluation on the R55 cohorts

The AutoDL runner completed all 848 questions and exited 0 on November 14, 2026. Each prediction identifies the original Stanford CheXagent-8B checkpoint at revision `4934e91451945c8218c267aae9c34929a7677829`. The experiment used FP16 on an RTX 6000D, Transformers 4.40.0 and PyTorch 2.8.0+cu128. Decoding was greedy with up to 64 new tokens per question. The checkpoints and author code are available at the [original CheXagent-8B release](https://huggingface.co/StanfordAIMI/CheXagent-8b/tree/4934e91451945c8218c267aae9c34929a7677829).

| Cohort | Correct | Accuracy |
| --- | ---: | ---: |
| CheXBench | 373/618 | 60.36% |
| SLAKE | 84/114 | 73.68% |
| VQA-RAD | 81/116 | 69.83% |
| Overall | 538/848 | 63.44% |

CheXBench breaks down to Rad-ReStruct 67/115, SLAKE 101/123, and OpenI 205/380. The separate 114-question SLAKE uses short answers. Sixty-four image-question pairs recur across the CheXBench SLAKE and short-answer SLAKE cohorts, so the denominator counts question evaluations.

Each image and the original question were passed directly to the author processor and the CheXagent-8B User/Assistant template. CheXBench included the original answer choices and requested an option letter. The short-answer cohorts requested a bare Yes or No on polarity questions. [Protocol](protocol.json) · [Runner and scorer](source/) · [Process exit](runner.exitcode)

The primary scores use the project's common direct-answer scorer. The diagnostic files use a separate rule-based extraction on the same replies. The CheXBench diagnostic recovered one additional correct answer, giving 374/618. This run made 848 local model calls and zero external model requests. The dataset summaries record summed per-question latency. AutoDL rental charges are tracked separately.

The per-question files and raw replies are indexed by the original project question ID. The [SLAKE image links](slake/image_paths.json) refer to repository copies of the [SLAKE dataset](https://huggingface.co/datasets/BoKelvin/SLAKE) by Liu et al. (CC BY 4.0). The [VQA-RAD image links](vqarad/image_paths.json) refer to repository copies of the [VQA-RAD dataset](https://osf.io/89kps/) by Lau et al. (CC0 1.0).

CheXBench question IDs, raw model replies and correctness labels are included. The benchmark's question text, answer options, references and images are available to eligible researchers through the [CheXBench distribution](https://huggingface.co/datasets/StanfordAIMI/chexbench). [Rad-ReStruct](https://github.com/ChantalMP/Rad-ReStruct) and the [Indiana University Chest X-Ray Collection](https://openi.nlm.nih.gov/contactus) provide source attribution and image terms. The full frozen inputs and raw outputs are retained in the local experiment archive.

The lab queue uses the published score after confirming identical question manifests, references and scoring code. This report describes the direct 8B run. The agent baseline experiments use the 8B tool in their own trajectories.

