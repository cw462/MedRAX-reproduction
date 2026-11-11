# R56 CheXBench · Interim results for the first 270 questions

2026-11-11 · Run arm `M43-IM-GT-S56-DS` · Recovery008

R56 answered **216 of the first 270 questions correctly (80.00%)** under the run's online feedback rule. The count uses binary correctness already stored in the per-question trajectories after each prediction was saved. This snapshot covers questions 1–270 in the run order. The formal CheXBench score follows completion of all 618 questions.

| Questions in run order | Correct | Accuracy |
| --- | ---: | ---: |
| 1–90 | 65 / 90 | 72.22% |
| 91–180 | 70 / 90 | 77.78% |
| 181–270 | 81 / 90 | 90.00% |
| **1–270** | **216 / 270** | **80.00%** |

The blocks contain different questions. Their accuracy can reflect question mix, accumulated same-image feedback and changes in the Skill repository over time.

## Skill use and adoption

| Recorded event | Questions |
| --- | ---: |
| At least one Skill retrieved as a candidate | 248 / 270 |
| At least one Skill activated during answering | 223 / 270 |
| Activated question with a saved adoption assessment | 193 / 223 |
| At least one positive adoption attribution | 148 / 193 |
| At least one negative adoption attribution | 39 / 193 |

The writer's saved assessments attributed adoption to at least one Skill on 187 of the 193 assessed questions. The remaining 30 activated questions were in the window whose assessment was still in progress. The latest committed repository contained six active cards and one merged card. One card accounted for 179 of the 223 questions with an activation. Adoption records reflect the writer model's interpretation of the answer trajectory. The experiment has yet to establish the effect of Skill activation on correctness.

## Historical results for the same questions

The comparisons match the first 270 R56 question IDs to [the previously published R49 per-question outcomes](../cxr_online_skill_r49_20261108/results/chexbench/per_question.json). A gain means R56 was correct where the historical arm was incorrect. A loss means the reverse.

| Historical arm | Correct | Historical accuracy | R56 gains | R56 losses | R56 difference |
| --- | ---: | ---: | ---: | ---: | ---: |
| R47 online same-image feedback (`R47_online_GT`) | 213 / 270 | 78.89% | 18 | 15 | +1.11 percentage points |
| R49 online Skill (`M43-IM-GT-S49`) | 218 / 270 | 80.74% | 12 | 14 | −0.74 percentage points |

Skill entered the answering process frequently. The paired historical differences amount to a net gain of three answers over R47 and a net loss of two against R49. The historical arms and the R56 protocol differ, so these results cannot isolate a Skill effect. The snapshot aggregates already-saved records without new inference or rescoring.


## Skill card text and per-question IDs

- [Skill cards](skill_cards.json) contains seven Skill IDs and eleven distinct saved text versions. Each card's nine content fields are reproduced as recorded. Version numbers in this export enumerate the distinct content for each ID in chronological snapshot order.
- [Question-to-Skill mapping](question_skill_mapping.json) contains all 270 question IDs in run order, with candidate IDs, activated IDs, the card version visible when each question was answered, and any saved adoption assessment. Empty ID lists mark questions with no candidate or no activation. An adoption value of `null` means no assessment was saved for that question. Assessment statuses are the writer model's attributions.

The mapping was captured after the last window in the original 270-question snapshot had committed. It contains 239 saved assessments across all 270 questions, including assessments with no Skill adoption entries. The accuracy and adoption counts above retain the earlier snapshot.
