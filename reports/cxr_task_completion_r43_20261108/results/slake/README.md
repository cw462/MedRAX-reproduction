# R4.3 slake：完整数据、冻结项目契约

完整分母114题：基线107（93.86%）→M43 108（94.74%）；纠正1、误改0、净增1，缺失1→0。这里的纠正是冻结评分下的错误转正确，含格式/答案域恢复，不等于全部医学错误修复。

| 子集 | 基线 | M43 |
|---|---:|---:|
| all | 107/114 | 108/114 |

宏平均93.8596%→94.7368%；微平均净增95%图像簇区间[0.0, 2.7522935779816518]个百分点，宏平均区间[0.0, 2.7522935779816518]。这是已暴露开发集上的条件结果，不是多种子或未见泛化。

新增1主模型、0工具，1733输入/31输出tokens，proxy0.007304CNY（非账单），API合计1.658秒。历史调用未重复计费；真实续答路径均不超过4主/2工具，整臂名义预算6/4。

[输入/原图](inputs.jsonl) · [参考](references.jsonl) · [固定最好整臂B](predictions_B.jsonl) · [M43预测](predictions_M43.jsonl) · [逐题评分](per_question.jsonl) · [评分摘要](summary.json) · [全量选择](selection.json) · [协议](protocol.json) · [完成/精确保留审计](completion_and_reuse_audit.json) · [新增资源](resource_accounting.json) · [历史完整图像/工具证据引用](reuse.json) · [退出凭证](job_receipt.json) · [本轮图像](image_assets.json) · [显式答案归因](explicit_answer_diagnostic.json)。

全部实际新请求/回复：
- [slake_12416](calls/M43/slake_12416.json)

[总报告](../../README.md) · [官方评测要求核对](../../EVALUATION_CONTRACT.md)。
