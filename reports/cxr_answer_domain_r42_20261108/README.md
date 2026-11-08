# ARIS R4.2：实际增分结果与继续优化

后续更新：[R4.3项目严格口径记录](../cxr_task_completion_r43_20261108/README.md)和[论文/作者评测要求溯源](../cxr_task_completion_r43_20261108/EVALUATION_CONTRACT.md)。本页分数保留原工程契约，不冒称官方评测。

**VQA-RAD完整116题：原M99/116（85.34%），M42为100/116（86.21%），纠正1、误改0、净增1题。** 新增1次主模型调用、0次工具，115题原M答案/理由/状态精确保留。原评分、参考与旧记录不变；没有从reason补答案或放宽JSON接受规则。

这是已暴露开发benchmark上的归档前缀续答，不能声称全116题新独立生成、稳定泛化或医学能力提高。95%配对簇区间为[0，2.70]个百分点，包含0。CheXbench和SLAKE本轮无干预，仍需超过458/618、107/114；VQA下一门槛更新为100/116。

## 总体比较和目标

[完整数据集与全部主要方案对照](OVERVIEW.md)汇总数据规模、完整分母准确率、记忆/技能及其他方案。目标随当前最强记录滚动更新，不固定崇尚M或Skill。只有真实结果超过对应最好记录才算该项进展，审稿ready只是执行门槛。

## 本轮方法与ARIS过程

第一轮独立审稿4/10、not ready，否决了仅做12例MCQ源格式pilot作为增分主实验的充分性。改为保留原M4主/2工具：仅对题面确定为二元、没有显式or备选、已有合法显式答案不在二元域、且有预算和健康工具前缀的轨迹，追加一次无工具重述。全116题统一扫描，106题已合规、8题范围外、1题预算耗尽、1题可续答；不在代码写qid白名单、不读参考筛选。

第二轮审稿发现新解析器曾放宽原M契约，随后修正为整条JSON恰好answer/reason两个字符串、answer不超过300字符；不去围栏、不补字段、不抽片段。四项针对性测试通过后，第二轮8/10、ready，才发出唯一一次请求。评审为原生Codex同家族provisional，不是跨模型家族独立接受。[协议与完整选择](results/vqarad/protocol.json) · [全部门槛](results/vqarad/selection.json) · [预先方案](PLAN.md)。

程序恢复原M末轮实际请求、原图和原始assistant回复，再附加固定提示；模型返回显式Yes。没有在客户端把small改成Yes。该题历史2主/1工具加本轮1主后为3主/1工具，未超过原4/2预算。已用满4主的另一项没有续答；含or的Right side正确答案也没有被粗暴改写。

## 完整证据和资源

[完整116题输入/原图引用](results/vqarad/inputs.jsonl) · [独立参考](results/vqarad/references.jsonl) · [M42全量预测](results/vqarad/predictions_M42.jsonl) · [原M全量预测](results/vqarad/predictions_M.jsonl) · [全部逐题评分](results/vqarad/per_question.jsonl) · [唯一新请求与回复](results/vqarad/calls/M42/vqarad_113.json) · [全量/复用/退出门槛](results/vqarad/completion_and_reuse_audit.json) · [任务退出凭证](results/vqarad/job_receipt.json)。

原图、历史全部工具观察、派生图及原M请求已在[原完整数据集证据](../cxr_vqa_toolsets/results/README.md)公开，本报告保留完整引用，不重新生成或重复收费。[历史图像清单](../cxr_vqa_toolsets/results/vqarad/image_assets.json) · [本次实际请求图像](results/vqarad/image_assets.json) · [继承引用说明](results/vqarad/reuse.json)。公开版本只作路径重定位、图像外置及隐私脱敏，不改变答案或临床观察内容；精确原始档案保留于独立run。

新增输入2794tokens、输出18tokens，已知tokenproxy **0.011392 CNY**，不是供应商账单。历史M240次主调用、122次逻辑工具选择不计为新发送；归档路径总计241主/122工具。通用评分摘要中的`M42.resources.selected=122`、`episode_seconds`继承原前缀口径，**不是122次新工具或本轮运行耗时**。以[独立资源核算](results/vqarad/resource_accounting.json)中的新增1主/0工具及实际API秒数为准。

仅在116份预测和完成凭证保存、1发送/1回复、任务退出0后隔离评分。严格公开复现：

```text
python experiments/reproduce_cxr_answer_domain_r42.py
```

## 后续方向

先完成本次发布核验，再继续ARIS审查更高收益的独立方案：以当前最好臂为固定起点，研究能恢复更多无效输出或纠正合法错误的机制；记忆、Skill、可靠工具、联合上下文均可保留为候选，但需用相同完整分母和明确的信息/预算条件比较。现有失败卡库不直接扩张，也不把已暴露benchmark当新测试。不会在生成途中看分改法，不为挑阳性重复这次请求。
