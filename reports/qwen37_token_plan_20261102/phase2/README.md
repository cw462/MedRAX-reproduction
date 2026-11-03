# 阶段2：固定K9独立采样投票

D输入配置，每题9次独立采样，T=0.7。预设主结果K9为296/402（73.63%），较原D/选中单答D多对1题；相同温度的缓存K1为297/402，K9少对1题。全部比较的病例bootstrap区间跨0，没有明确的投票收益证据。完整K1–9曲线仅作诊断，不替换固定K9。

[指标/三对照/置信区间](metrics.json) · [逐题评分](per_question.json) · [投票诊断](vote_diagnostics.json) · [402题与所有采样证据](evidence/README.md) · [结果分析](../results_analysis.md)

3618个样本中3610 completed、3 request_failed、5 unparsed；8题各少1个合法票，均单列技术不完整，所有一致度分母固定9。402题最终均有投票答案。原D仅在并列领先选项中作平票锚，原缺答没有重发或回填。

原D锚直接[引用阶段1](../phase1/evidence/arms/D/)，没有再进行402次D调用。[阶段成本摘要](cost_summary.json)中D是已有锚的固定取得成本；[全轮执行合计](../execution_summary.md)只计算一次，避免双计。
