# R4.3 chexbench：完整数据、冻结项目契约

完整分母618题：基线458（74.11%）→M43 466（75.40%）；纠正8、误改0、净增8，缺失10→0。这里的纠正是冻结评分下的错误转正确，含格式/答案域恢复，不等于全部医学错误修复。

| 子集 | 基线 | M43 |
|---|---:|---:|
| OpenI | 270/380 | 276/380 |
| Rad-Restruct | 73/115 | 73/115 |
| SLAKE | 115/123 | 117/123 |

宏平均76.0089%→77.0773%；微平均净增95%图像簇区间[0.4830917874396135, 2.2328548644338118]个百分点，宏平均区间[0.34098421977486654, 1.9918016641931406]。这是已暴露开发集上的条件结果，不是多种子或未见泛化。

新增10主模型、0工具，32615输入/415输出tokens，proxy0.135440CNY（非账单），API合计21.832秒。历史调用未重复计费；真实续答路径均不超过4主/2工具，整臂名义预算6/4。

[输入/原图](inputs.jsonl) · [参考](references.jsonl) · [固定最好整臂B](predictions_B.jsonl) · [M43预测](predictions_M43.jsonl) · [逐题评分](per_question.jsonl) · [评分摘要](summary.json) · [全量选择](selection.json) · [协议](protocol.json) · [完成/精确保留审计](completion_and_reuse_audit.json) · [新增资源](resource_accounting.json) · [历史完整图像/工具证据引用](reuse.json) · [退出凭证](job_receipt.json) · [本轮图像](image_assets.json) · [显式答案归因](explicit_answer_diagnostic.json)。

全部实际新请求/回复：
- [chexbench_openi_0032](calls/M43/chexbench_openi_0032.json)
- [chexbench_openi_0047](calls/M43/chexbench_openi_0047.json)
- [chexbench_openi_0075](calls/M43/chexbench_openi_0075.json)
- [chexbench_openi_0124](calls/M43/chexbench_openi_0124.json)
- [chexbench_openi_0137](calls/M43/chexbench_openi_0137.json)
- [chexbench_openi_0283](calls/M43/chexbench_openi_0283.json)
- [chexbench_openi_0308](calls/M43/chexbench_openi_0308.json)
- [chexbench_openi_0331](calls/M43/chexbench_openi_0331.json)
- [chexbench_slake_0047](calls/M43/chexbench_slake_0047.json)
- [chexbench_slake_0108](calls/M43/chexbench_slake_0108.json)

[总报告](../../README.md) · [官方评测要求核对](../../EVALUATION_CONTRACT.md)。
