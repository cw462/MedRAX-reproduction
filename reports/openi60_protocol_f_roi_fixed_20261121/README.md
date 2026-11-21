# OpenI60 共同协议 F 正式复跑（ROI 模块补齐）

正式流沿用原 60 题与顺序。B0-F 答对 **47/60**，L1-F 答对 **40/60**。L1-F 相对 B0-F 纠正 **4** 题、误改 **11** 题，净变化 **-7** 题。

| 组别 | 正确 / 题数 | 准确率 | 主模型调用 | 工具调用 | 工具失败 |
|---|---:|---:|---:|---:|---:|
| B0 | 41/60 | 68.33% | 281 | 216 | 4 |
| L1 | 39/60 | 65.00% | 133 | 18 | 0 |
| B0-F | 47/60 | 78.33% | 246 | 184 | 2 |
| L1-F | 40/60 | 66.67% | 267 | 203 | 4 |

历史 B0/L1 配对为 G9/H11。F 正式配对准确率差为 **-11.67 个百分点**。两组各自初始化并沿题序在线更新记忆。前 8 题冒烟用于协议验收，表中数据来自独立正式流。

## 结果与轨迹

- [原评分配对摘要](paired_analysis/summary.json) · [逐题配对 CSV](paired_analysis/paired_results.csv) · [固定队列](cohort.json)
- [B0-F 原评分](B0/analysis/summary.json) · [L1-F 原评分](L1/analysis/summary.json) · [公开运行配置](config.public.json)
- [纠正与误改轨迹索引](gain_harm_index.json) · [B0-F 全部步骤](B0/steps/) · [L1-F 全部步骤](L1/steps/)
- [协议事件、修复和计费汇总](protocol_cost_summary.json)
- [8 题冒烟验收记录](smoke_acceptance.json)

| 类型 | 题号 | B0-F | L1-F | 参考标注 |
|---|---|---|---|---|
| 误改 | [chexbench_openi_0001](cases/chexbench_openi_0001.md) | B. surgical instruments in the left lung | A. surgical instruments in the right lung | B |
| 误改 | [chexbench_openi_0038](cases/chexbench_openi_0038.md) | B. right indwelling catheter | A. left indwelling catheter | B |
| 纠正 | [chexbench_openi_0084](cases/chexbench_openi_0084.md) | A. left rib deformity | B. right rib deformity | B |
| 纠正 | [chexbench_openi_0092](cases/chexbench_openi_0092.md) | B. left lung opacity | A. right lung opacity | A |
| 误改 | [chexbench_openi_0100](cases/chexbench_openi_0100.md) | B. right lower lobe pulmonary atelectasis | A. left lower lobe pulmonary atelectasis | B |
| 纠正 | [chexbench_openi_0107](cases/chexbench_openi_0107.md) | B. left thoracic vertebrae scoliosis | A. right thoracic vertebrae scoliosis | A |
| 误改 | [chexbench_openi_0135](cases/chexbench_openi_0135.md) | A. right lower lobe pulmonary atelectasis | B. left lower lobe pulmonary atelectasis | A |
| 误改 | [chexbench_openi_0175](cases/chexbench_openi_0175.md) | A. surgical instruments in the right abdomen | No surgical instruments or foreign bodies are visible. | A |
| 误改 | [chexbench_openi_0185](cases/chexbench_openi_0185.md) | B. surgical instruments in the left breast | A. surgical instruments in the right breast | B |
| 误改 | [chexbench_openi_0196](cases/chexbench_openi_0196.md) | B. elevated right diaphragm | A. elevated left diaphragm | B |
| 误改 | [chexbench_openi_0235](cases/chexbench_openi_0235.md) | A. small right pleural effusion | B. small left pleural effusion | A |
| 误改 | [chexbench_openi_0236](cases/chexbench_openi_0236.md) | B. left base pulmonary atelectasis | A. right base pulmonary atelectasis | B |
| 误改 | [chexbench_openi_0239](cases/chexbench_openi_0239.md) | A. elevated left diaphragm | B. elevated right diaphragm | A |
| 纠正 | [chexbench_openi_0240](cases/chexbench_openi_0240.md) | B. right pleural effusion | A. left pleural effusion | A |
| 误改 | [chexbench_openi_0265](cases/chexbench_openi_0265.md) | A. right thoracic vertebrae scoliosis | B. left thoracic vertebrae scoliosis | A |

## 运行与工具验证

AutoDL RTX 6000D 上两组并行。北京时间 15:51:06 开始，17:08:19 完成最后一组生成，总用时 77.2 分钟。

| 组别 | ROI 成功 / 派发 | 生成中断及恢复次数 |
|---|---:|---:|
| B0-F | 12/12 | 5 |
| L1-F | 12/12 | 4 |

两组每次续跑均保留已锁定的预测、先前记忆图和反馈。恢复中使用已归档的检索响应，对无响应的请求单独保存回执。无响应请求的服务端执行与计费状态未知。 [时间、裁剪回执统计与恢复记录](execution.json) · [恢复代码](deployment/resume_f_disconnect.py)

另一个独立存档记录了旧部署中的裁剪故障和 24 次 CPU 重放。 [上一轮 F 结果](https://github.com/cw462/MedRAX-reproduction/tree/88357648257efe49da59359a1750f927ae2f95de/reports/openi60_protocol_f_autodl_20261121)

## 评分口径与已知限制

B0-F 记录 `protocol_failure` **1** 题，其中原 aligned 评分正确 **0** 题。L1-F 对应为 **1** 题和 **0** 题。原评分器从终止原文独立提取显式答案，运行器状态与原 aligned 评分各自保留。准确率以 60 题为分母。

这是一组按题序执行的在线配对试验。后续题会受前序记忆写入影响，跨协议的差异包含整条运行轨迹的变化。

## 数据与代码

- [历史 B0/L1 的分数与轨迹](https://github.com/cw462/MedRAX-reproduction/tree/3d7fd6327db7088715ea686c57c198023409b1bb/reports/openi60_m5_l1_autodl_20261121)
- [F 协议审计、代码与离线回归](https://github.com/cw462/MedRAX-reproduction/tree/102be258cf5c51f7243125b08daf6caea18730b8/reports/openi60_protocol_audit_f_20261121)
- [CheXBench OpenI](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [输入与影像来源](data/inputs.jsonl)
