# R54 no-Skill CheXBench results

All 618 CheXBench questions completed. The generation runner and the whole-cohort scorer exited successfully. Arm: `M43-IM-GT-T54-S0`. The other R54 datasets are outside this report's scope.

| CheXBench subset | Correct / questions | Accuracy |
| --- | ---: | ---: |
| Rad-Restruct | 79 / 115 | 68.70% |
| SLAKE | 117 / 123 | 95.12% |
| OpenI | 268 / 380 | 70.53% |
| **Total** | **464 / 618** | **75.08%** |

- [Per-question results in CSV](per_question.csv) and [JSON](per_question.json). Each row contains the question ID, question and options, extracted answer, mapped choice, reference, correctness, and main-model and tool call counts.
- [Saved score summary](summary.json).
- [Comparison and paired results for the 300 overlapping R56 questions](r54_vs_r56_overlap.json).

## Same-question comparison

All 300 CheXBench questions saved when R56 was paused matched the R54 questions on ID, question text, options and reference answer. R54 answered **241/300 (80.33%)** correctly and R56 **236/300 (78.67%)**. The R54 difference was **+1.67 percentage points**. R54 alone was correct on 23 questions, R56 alone on 18, both on 218, and neither on 41. All counts reuse the saved judgments from each run.

R54 used eight tools with Skill disabled and retained previously released same-image feedback. R54 and R56 use different tool sets and run conditions. The paired results describe performance on the shared questions.


## Per-question tool call evidence

The CSV and JSON now include `tool_call_details` for all 618 questions. The CSV encodes the list as JSON in that column. Each entry records the tool and backend, call order, executed arguments, source image reference, status, original saved return, and the observation delivered to the agent. Questions with no executed tool calls have an empty list.

The export covers **1,208 calls**. **1,199** calls have a saved raw artifact, including one failed call with a preserved partial artifact. Nine failed calls have no saved raw return and retain their error records. The failed calls remain failed. The separately recovered MedGemma call uses its actual recovery result.

Dataset image paths are relative. References prefixed `r54-artifact:` name files in the original run archive. Image binaries are outside this supplement. Tool answer text and saved correctness values are preserved.
