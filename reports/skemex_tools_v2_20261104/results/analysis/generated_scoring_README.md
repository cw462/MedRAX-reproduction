# Official SkeMex A1: completed crossfit evaluation

A0 is the user-confirmed direct D; no tool-agent baseline is claimed.

|View|Correct/402|Accuracy|Missing|
|---|---:|---:|---:|
|D_A0|295/402|73.38%|0|
|A1|279/402|69.40%|4|
|old_S1|279/402|69.40%|0|
|old_HS|300/402|74.63%|0|
|tools_v1_A1|276/402|68.66%|0|

|A1 versus|Corrections|Harms|Net|Case CI pp|
|---|---:|---:|---:|---|
|D_A0|15|31|-16|-7.62 to -0.76|
|old_S1|27|27|+0|-3.73 to +3.73|
|old_HS|23|44|-21|-9.38 to -1.20|
|tools_v1_A1|16|13|+3|-1.45 to +2.99|

[Metrics/usage](metrics.json) · [Per-question predictions](per_question.json) · [Official categories](categories.json). Tool-enabled A1 vs direct D combines tools, extra decision calls and memory. No matched tool-agent without-memory control was run; memory-only gain cannot be identified. Development-set evidence only. Source-fold supervised evolution and all meta calls count toward cost. Target utility is frozen. CNY is an inherited accounting proxy, not actual Token Plan Credits.
