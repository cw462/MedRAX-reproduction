# R50 CXR6 — user-stopped incomplete results

The user explicitly requested stopping and publishing the existing results on2026-11-10. This archive contains **435/848 completed predictions**, an interrupted436th question, and **413 planned questions without a final prediction**. It is not a completed848-question experiment. The queued revised DeepSeek comparison was stopped before any formal request.

| Dataset | Completed / planned | Correct | Accuracy |
|---|---:|---:|---:|
| CheXBench | 435 / 618 | 336 | 77.24% |
| SLAKE CXR | 0 / 114 | — | Not started |
| VQA-RAD CXR | 0 / 116 | — | Not started |

Scores use the unchanged common raw-answer adapter and metrics: all435 raw answers were adapted before references were opened. The earlier user-requested420-case score is retained separately and its420 answers/grades agree exactly. There is no answer-quality filtering, regeneration, repaired grounding output, or fabricated zero exit. Raw amended runner/GEN exit is **-15**, controller **241**; every original/recovery001/recovery002 exit1 remains. The idle DeepSeek wrapper exit143 is a deliberate stop, not an executed comparison failure.

The main/META model is Qwen3.7-plus with thinking=false and the six-tool menu medgemma/llava_rad/chest_xray_expert/llava_med_qa/xray_phrase_grounding/medvlm_r1. Per-dataset empty Skill/same-image state, window30/buffer20, next-window Skill, top5/branch/top6 and all-reject prescreen are retained. Own prediction/event precede own GT; earlier same-image annotation feedback may be used. This online-GT system is not closed-test evaluation or a Skill-only causal comparison.

The original11producer modules were followed by3explicitly approved A.4 failure-observation modules from CheX317. The MAIRA300-token/unclosed-tag failure remains failed; it was never regenerated/repaired or turned into successful cache. Two earlier pre-generation loading failures each had one explicit unchanged retry, with poor text preserved. Helper transport/capture errors and all stage nonzero exits are retained in source/control/failure evidence. This is amendedR50 with protocol, order, source, budget, prompt, EOS and time confounds, not an exact unchanged-paper reproduction.

The frozen420-case Skill analysis found a real one-source card and90injections, all on OpenI laterality choices: before68/92=73.91%, after62/90=68.89%; this is a different-case ordered comparison, not a causal effect. Of90dual grounding attempts,70 returned both boxes,16 neither and4 only one;3of the4single-box decisions were wrong.55same-model positive attributions include12wrong answers, which actually received negative numeric reward credit. These negative observations are retained; no clinical, Skill-causal or official-SOTA claim is made. Corrected/harmed/net versus a same-question Skill-off run are unknown, not zero. A larger model/evidence anchoring alone does not validate the heuristic.

At the later435-question stop, Skill-injected cases are 74/105=70.48%. This later cutoff is separate from the preserved90-injection/420-case audit. Neither subgroup score is a counterfactual Skill gain; the actual stopped repository/card state is in RESOURCE_SUMMARY.json.

- [All435case pages](CASE_INDEX.md), with complete questions/options/original images/tools/feedback/Skill sources.
- [Interrupted question436](INTERRUPTED_CASE.md) and [full raw evidence](evidence/chexbench/).
- [Stopped-prefix score](results/user_stopped/summary.json) and [actual public reproduction](public_reproduction/user_stopped/summary.json).
- [Requests, failed attempts and unknown costs/time](RESOURCE_SUMMARY.json). Provider Credits/invoice, unknown in-flight compute and hardware cost are unknown, not0. Per-call CNY proxies are not a provider bill and elapsed sums may overlap.
- [Actual source/control/copy map](deployment_source/PROVENANCE.md), including original failures, retries, helper errors, user approvals and the earlier420-case analysis.
- [Earlier420-case Skill effectiveness analysis](deployment_source/preparation/user_requested_interim_accuracy_20261110/skill_effect_analysis/ANALYSIS.md), preserving its frozen denominator and negative observations.
- [New3 health evidence](evidence/health/) is separate from scored examples and was not rerun for publication.
- [Initial protocol](PROTOCOL.json), [preparation tests](TESTS.md), and [running README preserved](README.running_before_user_stop.md).
- [Previously published complete R49 archive](https://github.com/cw462/MedRAX-reproduction/blob/main/reports/cxr_online_skill_r49_20261108/README.md); its inference/private scoring/downloads were not repeated.

Reproduce the stopped score without any model/API request: `python experiments/score_r50_stopped_prefix.py --evidence reports/cxr_online_skill_r50_cxr6_20261109/evidence/chexbench --out /path/to/new_output`. Use an empty separate output directory. Original dataset/model attribution remains in question/source records; applicable original terms continue to apply. Source copies are post-execution snapshots, not independent byte/weight/clinical attestations. All uploaded credentials are excluded/redacted; private originals remain unchanged.

An actual fresh DeepSeek review completed for this stopped435-plus-interrupted436scope: native exit0, session`f027ed30-531c-4c73-b229-69b5e35f44fc`, scope_complete=true, publication_blockers=[]. Scientific claim_supported=yes. [Full review](RESULT_CLAIM_REVIEW.md) · [native metadata](RESULT_CLAIM_METADATA.json) · [raw CLI](RESULT_CLAIM_RAW_CLI.json) · [claim limits](CLAIMS_FROM_RESULTS.md). No independent model-weight attestation is claimed.

Publication staging adjustment: repository ignore rules omit some report logs. The same DeepSeek session reviewed the sole executable delta, `git add -f` restricted to the exact literal-NUL allowlist; ordinary push/base/parent/index protections remain. [Delta review](RESULT_PUBLISH_DELTA_REVIEW.md) · [actual delta metadata](RESULT_PUBLISH_DELTA_METADATA.json) · [latest publisher source](deployment_source/operational_delta/publish_r50_user_stopped.py). The prior full readiness snapshot is reused; only these added packaging records are checked separately.
