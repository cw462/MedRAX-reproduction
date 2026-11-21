# OpenI60 共同协议 F 正式复跑

正式流沿用原 60 题与顺序。B0-F 答对 **48/60**，L1-F 答对 **39/60**。L1-F 相对 B0-F 纠正 **3** 题、误改 **12** 题，净变化 **-9** 题。

| 组别 | 正确 / 题数 | 准确率 | 主模型调用 | 工具调用 | 工具失败 |
|---|---:|---:|---:|---:|---:|
| B0 | 41/60 | 68.33% | 281 | 216 | 4 |
| L1 | 39/60 | 65.00% | 133 | 18 | 0 |
| B0-F | 48/60 | 80.00% | 259 | 199 | 13 |
| L1-F | 39/60 | 65.00% | 274 | 211 | 16 |

历史 B0/L1 配对为 G9/H11。F 正式配对准确率差为 **-15.00 个百分点**。两组各自初始化并沿题序在线更新记忆。前 8 题冒烟用于协议验收，表中数据来自独立正式流。

## 结果与轨迹

本次正式流有一处部署故障。两组全部 24 次 ROI 裁剪因原模块缺失而失败。模块补齐后按原请求补跑为 24/24 成功。表中成绩仍是裁剪故障发生时的完整在线流结果。 [失败回执、补跑证据与耗时](ROI_REPLAY.md)

- [原评分配对摘要](paired_analysis/summary.json) · [逐题配对 CSV](paired_analysis/paired_results.csv) · [固定队列](cohort.json)
- [B0-F 原评分](B0/analysis/summary.json) · [L1-F 原评分](L1/analysis/summary.json) · [公开运行配置](config.public.json)
- [纠正与误改轨迹索引](gain_harm_index.json) · [B0-F 全部步骤](B0/steps/) · [L1-F 全部步骤](L1/steps/)
- [协议事件、修复和计费汇总](protocol_cost_summary.json)
- [8 题冒烟验收记录](smoke_acceptance.json)

| 类型 | 题号 | B0-F | L1-F | 参考标注 |
|---|---|---|---|---|
| 纠正 | [chexbench_openi_0001](cases/chexbench_openi_0001.md) | A. surgical instruments in the right lung | B. surgical instruments in the left lung | B |
| 误改 | [chexbench_openi_0012](cases/chexbench_openi_0012.md) | B. small right pleural effusion | — | B |
| 误改 | [chexbench_openi_0038](cases/chexbench_openi_0038.md) | B. right indwelling catheter | A. left indwelling catheter | B |
| 误改 | [chexbench_openi_0067](cases/chexbench_openi_0067.md) | B. left base pulmonary atelectasis | A. right base pulmonary atelectasis | B |
| 误改 | [chexbench_openi_0089](cases/chexbench_openi_0089.md) | A. right rib deformity | B. left rib deformity | A |
| 纠正 | [chexbench_openi_0092](cases/chexbench_openi_0092.md) | B. left lung opacity | A. right lung opacity | A |
| 误改 | [chexbench_openi_0100](cases/chexbench_openi_0100.md) | B. right lower lobe pulmonary atelectasis | A. left lower lobe pulmonary atelectasis | B |
| 误改 | [chexbench_openi_0111](cases/chexbench_openi_0111.md) | A. left base pulmonary atelectasis | B. right base pulmonary atelectasis | A |
| 误改 | [chexbench_openi_0176](cases/chexbench_openi_0176.md) | B. right indwelling catheter | A. left indwelling catheter | B |
| 误改 | [chexbench_openi_0191](cases/chexbench_openi_0191.md) | A. right lower lobe pulmonary atelectasis | B. left lower lobe pulmonary atelectasis | A |
| 误改 | [chexbench_openi_0209](cases/chexbench_openi_0209.md) | B. surgical instruments in the left lung | A. surgical instruments in the right lung | B |
| 误改 | [chexbench_openi_0235](cases/chexbench_openi_0235.md) | A. small right pleural effusion | B. small left pleural effusion | A |
| 纠正 | [chexbench_openi_0236](cases/chexbench_openi_0236.md) | A. right base pulmonary atelectasis | B. left base pulmonary atelectasis | B |
| 误改 | [chexbench_openi_0240](cases/chexbench_openi_0240.md) | A. left pleural effusion | B. right pleural effusion | A |
| 误改 | [chexbench_openi_0265](cases/chexbench_openi_0265.md) | A. right thoracic vertebrae scoliosis | B. left thoracic vertebrae scoliosis | A |

## 评分口径与已知限制

B0-F 记录 `protocol_failure` **0** 题，其中原 aligned 评分正确 **0** 题。L1-F 对应为 **1** 题和 **0** 题。原评分器从终止原文独立提取显式答案，运行器状态与原 aligned 评分各自保留。准确率以 60 题为分母。

这是一组按题序执行的在线配对试验。后续题会受前序记忆写入影响，跨协议的差异包含整条运行轨迹的变化。

## 数据与代码

- [历史 B0/L1 的分数与轨迹](https://github.com/cw462/MedRAX-reproduction/tree/3d7fd6327db7088715ea686c57c198023409b1bb/reports/openi60_m5_l1_autodl_20261121)
- [F 协议审计、代码与离线回归](https://github.com/cw462/MedRAX-reproduction/tree/102be258cf5c51f7243125b08daf6caea18730b8/reports/openi60_protocol_audit_f_20261121)
- [CheXBench OpenI](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [输入与影像来源](data/inputs.jsonl)
