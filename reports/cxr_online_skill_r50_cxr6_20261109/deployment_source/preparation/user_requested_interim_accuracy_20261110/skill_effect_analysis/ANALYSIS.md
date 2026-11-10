# R50 frozen-prefix Skill analysis requested by the user

This is a descriptive secondary analysis of the previously scored 420-question prefix. No new prediction, grading, label-file read, ongoing-protocol change, old R49 private scoring, or final-score receipt was performed. A separate bounded read captured five historical card/context/window files once. The prefix and all negative results remain unchanged.

| Comparison | Correct / N | Accuracy |
|---|---:|---:|
| All uninjected cases | 262 / 330 | 79.39% |
| OpenI before first injection | 68 / 92 | 73.91% |
| OpenI with this one card | 62 / 90 | 68.89% |

All 90 injected cases are consecutive OpenI fine-grained questions, ordinals331–420. Their two options differ only in left/right. The crude gap is −10.51 percentage points; within OpenI it is −5.02 points (−6.80% relative accuracy). The comparison is between different ordered cases, not a same-question intervention. There is no concurrent uninjected control. Neither a causal benefit nor causal harm is identified. Post-injection windows score19/30,24/30,19/30; this does not show a consistent improving trajectory.

The actual card s_39391f294d360026, Phrase Grounding Verification for Conflicting Binary Choices, was created from one source, chexbench_openi_0073. Its condition specifies conflicting/negative/ambiguous initial VLM or expert results. Its decisive rule chooses the option with valid grounding boxes; with two boxes it prefers higher confidence or more precise localization. The first injected context contains this exact accepted card. Its source_count1 and active status are provenance/lifecycle facts, not efficacy validation.

The first two observed tool calls are grounding for all90 injected cases;75/90 use grounding alone. In the earlier92 OpenI cases,79 used grounding, only22 had exactly two grounding calls, and18 used grounding alone. Mean main/tool calls change from3.674/2.902 to2.311/2.300. These are descriptive behavior/call-count changes; they do not establish net cost or causal efficiency because tasks differ and new embedding/META overhead is not included.

| Two grounding results | Correct / N | Consequence |
|---|---:|---|
| Both options return boxes | 49 / 70 | Box presence does not discriminate the two options |
| Neither option returns boxes | 12 / 16 | Card requires an unspecified fallback |
| Only one option returns boxes | 1 / 4 | Three wrong answers follow the claimed decisive rule |

No numeric confidence field exists in these180 grounding observations. The card's confidence branch therefore has no returned confidence value to compare. Box geometry or a plausible rationale is not a recorded confidence score or independent clinical verification. For example, chexbench_openi_0166 returns no left-base box and a right-base box; the answer chooses right (B), while the saved reference is left (A). This shows failure against the benchmark, without a fresh clinical image review or a claim of medically adjudicated truth.

Completed historical windows cover adoption attribution only for ordinals331–390:55 ADOPTED_POSITIVE include43 correct and12 wrong;5 ADOPTED_NEGATIVE are wrong. The12 wrong positive attributions receive negative numeric credit in the actual reward-based updater. Thus the positive status is a same-model process judgment, not55 corrections or55 beneficial interventions, and the implementation does not blindly give all55 positive numeric credit. The final30 cases in this frozen-prefix analysis lack completed-window attribution in the captured historical documents.

Current evidence establishes a real card, injection and a matching execution pattern. It does not establish accuracy improvement; observed accuracy is lower and the learned decision rule has concrete counterexamples. The proposed improvement direction is stricter procedural applicability, explicit non-decisive handling of boxes/absence/confidence, source-supported limits, and decision-rationale consistency checks. These are recommendations for a separately authorized method revision, not changes to the running R50 protocol. The already-approved stronger-model formation protocol addresses candidate eligibility and evidence anchoring; those changes alone do not prove this heuristic reliable. No additional ablation or third arm has been launched.

Evidence: [summary](summary.json), [grounding patterns](grounding_patterns.json), [per-case patterns](grounding_per_case.json), [actual credit bindings](credit_case_bindings.json), [original scored prefix](../per_question.json), [archived capture inventory](archived_evidence.completed.json). Original card/context/window bytes are under archived_evidence/.
