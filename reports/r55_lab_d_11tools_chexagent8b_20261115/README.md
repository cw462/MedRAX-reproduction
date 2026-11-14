# MedRAX R55 D · 11 工具 · CheXagent-8B

实验室双 RTX 3090 队列已完成 D 组的三个冻结子集。总分按 848 题合并计分。

| 数据集 | D 准确率 | Qwen CoT | D 改对 | D 改错 | 净变化 |
| --- | ---: | ---: | ---: | ---: | ---: |
| CheXBench | 432/618（69.90%） | 418/618 | 78 | 64 | +14 |
| SLAKE | 106/114（92.98%） | 106/114 | 6 | 6 | +0 |
| VQA-RAD | 92/116（79.31%） | 87/116 | 12 | 7 | +5 |
| **合计** | 630/848（74.29%） | 611/848 | 96 | 77 | +19 |

配对结果以冻结题目 ID 对齐，同一评分口径。差异反映本轮 D 与 CoT 的整体结果。其中工具、主模型决策和同图反馈均可能影响结果。[CoT 同题数据来源](https://github.com/cw462/MedRAX-reproduction/blob/0dcb00352c05c6833d2001201da2f5c564267e37/reports/r55_qwen_react_chexagent8b_11tools_open_budget_20261114/README.md)

D 使用 Qwen3.7-Plus、原版 Stanford AIMI CheXagent-8B 和 11 个工具。单题逻辑调用次数不限，Skill 关闭，沿用同图反馈。[CheXagent 模型版本](https://huggingface.co/StanfordAIMI/CheXagent-8b/tree/4934e91451945c8218c267aae9c34929a7677829)

共记录 2543 次主模型调用、1556 次工具调用，其中 33 次工具失败。可计费率的请求估算为 ¥43.7855，为归档用量估算。请求耗时、token 用量和未知价格请求见逐集摘要。CheXBench 的生成进程已保存全部预测，修复终止回执中的实验组简称兼容后，由原评分器生成正式分数。

逐题文件记录 5 项留有失败回执或观察的 Verify 调用，并保留对应题目的工具观察和最终预测。逐题源图链接沿用项目公开的冻结病例。ROI 坐标、转换参数、派生文件名和私有归档定位可在工具观察中追溯。新派生图字节保存在私有归档，公开报告采用已发布原图。

[CheXBench](chexbench.jsonl) · [SLAKE](slake.jsonl) · [VQA-RAD](vqarad.jsonl) · [运行配置与统计](summary.json)

[运行入口](source/run_r55_full848_dataset.py) · [评分器](source/score_r55_full848_dataset.py) · [双卡调度](source/queue_r55_lab_parallel.py) · [CheXBench 来源](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [SLAKE 来源](https://www.med-vqa.com/slake/) · [VQA-RAD 来源](https://doi.org/10.17605/OSF.IO/89KPS)
