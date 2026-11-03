# Case information experiments: completed offline scoring

**[完整中文分析：准确率与病例区间、工具信用、用量与边界](interpretation.md)** · [补充统计](publication_summary.json) · [逐病例结果](per_case.json) · [阶段发布记录](publication_history.json)

All 3,513 planned model requests finished; the final scorer exited successfully. E2/E1 interim scoring was separately authorized earlier, and all later generation retained its frozen protocol. Final all-arm scoring ran only after E0 completed.

|Arm|Correct / planned|Accuracy|Missing|
|---|---:|---:|---:|
|D|295/402|73.38%|0|
|E2_Batch|354/402|88.06%|4|
|E2_Sequential|336/402|83.58%|0|
|E1_DeepSeek|306/402|76.12%|0|
|E1_QwenFlash|320/402|79.60%|1|
|E3_Classifier|293/402|72.89%|0|
|E3_Report|293/402|72.89%|0|
|E3_Evidence|289/402|71.89%|0|
|E1_Ensemble|317/402|78.86%|0|

|Versus D|Corrections|Harms|Net|Case-bootstrap 95% CI (pp)|
|---|---:|---:|---:|---|
|E2_Batch|69|10|59|9.92 to 19.55|
|E2_Sequential|51|10|41|6.20 to 14.32|
|E1_DeepSeek|39|28|11|-1.27 to 6.72|
|E1_QwenFlash|45|20|25|2.47 to 10.34|
|E3_Classifier|6|8|-2|-2.51 to 1.27|
|E3_Report|9|11|-2|-2.51 to 1.48|
|E3_Evidence|8|14|-6|-3.99 to 0.77|
|E1_Ensemble|30|8|22|2.71 to 8.35|

E0 fixed D: 793/1002 (79.14%).

[Full metrics, corrections/harms/missing and exact McNemar](metrics.json) · [402-question results](per_question.json) · [1,002-question E0](heldout_per_question.json).

All E1-E3 comparisons are exploratory on the same tuning cases. E0 evaluates only the fixed direct baseline. Tool evidence and technical recovery are separate from model/method improvement. CNY accounting proxies are not Token Plan invoices or a Credits conversion; actual Credits are unknown.
