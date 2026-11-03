# Plus H1/S1/HS: completed tuning scoring

**[完整中文分析与结果边界](interpretation.md)** · [病例明细](per_case.json) · [资源与技能覆盖](publication_summary.json)

H1 improves overall, but its unflagged-history subset does not pass the frozen gate; S1 and HS also fail. The fixed fallback remains D. The pruned skill library has not been evaluated.

|Arm|Correct/402|Accuracy|Missing|
|---|---:|---:|---:|
|D|295/402|73.38%|0|
|H1|316/402|78.61%|0|
|S1|279/402|69.40%|0|
|HS|300/402|74.63%|0|

|Versus D|Corrections|Harms|Net|Paired case 95% CI pp|
|---|---:|---:|---:|---|
|H1|35|14|+21|+1.25 to +9.02|
|S1|14|30|-16|-7.71 to -0.50|
|HS|27|22|+5|-2.45 to +5.01|

[Metrics and unflagged history subset](metrics.json) · [402 question results](per_question.json) · [Official multilabel categories](categories.json) · [Skill utility](skill_utility.json).

Same 99 tuning cases; no heldout/Flash/control calls. CNY amounts are inherited proxies, not actual Token Plan Credits or an invoice. Missing outcomes remain missing; source-fold supervised reflection and crossfit evaluation are disclosed.
