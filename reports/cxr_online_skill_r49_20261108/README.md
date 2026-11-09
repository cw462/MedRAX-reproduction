# R49: completed results and public evidence

**Evidence-first publication at the user’s explicit request. Final DeepSeek result/claim review and final report are pending.**

All 848 question-level generations and three private scores completed. Scores below reuse the immutable saved results. This upload preserves negative findings, actual failures and recovery history. It does not assert that 848 questions are independent patients or cases.

| Dataset | R49 | Historical whole arm | Corrected / harmed / net |
|---|---:|---:|---:|
| chexbench | 465/618 | M43 466/618 | 49 / 50 / -1 |
| slake | 113/114 | M43 108/114 | 5 / 0 / +5 |
| vqarad | 97/116 | M42 100/116 | 4 / 7 / -3 |

VQA-RAD uses M42: the M43 phase retained M42’s 100/116 and did not run a separate VQA arm. CheX R47 online-GT 468/618 remains a secondary comparator in its saved results.

Final adoption_1 controller and all three original runners exited zero. Every initial/intermediate exit1 remains in the full recovery tree. No failed attempt is relabeled successful.

## Evidence and current reproduction status

- **chexbench** — running; no completed public reproduction asserted. [Saved scores](results/chexbench/summary.json), [all question-level results](results/chexbench/per_question.json), [questions/options/images/requests/replies/tools/feedback/Skills](evidence/chexbench/), [evidence manifest](evidence/chexbench/publication_manifest.json).
- **slake** — completed: saved public scores, extractions and resources match. [Saved scores](results/slake/summary.json), [all question-level results](results/slake/per_question.json), [questions/options/images/requests/replies/tools/feedback/Skills](evidence/slake/), [evidence manifest](evidence/slake/publication_manifest.json).
- **vqarad** — completed: saved public scores, extractions and resources match. [Saved scores](results/vqarad/summary.json), [all question-level results](results/vqarad/per_question.json), [questions/options/images/requests/replies/tools/feedback/Skills](evidence/vqarad/), [evidence manifest](evidence/vqarad/publication_manifest.json).

[Full failure and recovery evidence](evidence/recovery/) · [Executed code and helper provenance](deployment_source/PROVENANCE.md) · [Protocol](PROTOCOL.json) · [Method and limitations](METHOD_AND_LIMITS.md) · [Actual test history](TESTS.md) · [Publication sequence amendment](PUBLICATION_SEQUENCE_AMENDMENT.md).

## Interpretation and resource limits

This is an exposed online dataset-ground-truth feedback experiment with unrestricted request budgets, changed executor/sampling/time/prompts/EOS policy and mixed legacy caches. It has no simultaneous no-Skill control. Skill hits are 505/618, 0/114, 0/116; same-image memory hits are 130/618, 84/114, 58/116. SLAKE and CheX-SLAKE share 17 images / 64 matched questions; VQA paraphrases cluster by image. No Skill-only causality, equal-budget gain, closed-test SOTA or medical capability is claimed.

Each saved score summary contains complete per-category resources, known token/time/CNY usage proxies, failed production attempts and separately reported diagnostics. Missing provider usage/cost, hardware prices and full controller wall time stay unknown. CLI review USD estimates are separate from inference CNY proxies and are not provider invoices. Archived duplicate copies of a request are not additional charges.

The original execution/repair reviews cover their own historical scopes. A new final complete-results review has not yet been dispatched at preparation of this first upload. Final findings and a complete report will follow in a later commit; no favorable verdict is prewritten.
