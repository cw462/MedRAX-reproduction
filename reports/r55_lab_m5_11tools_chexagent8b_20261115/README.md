# MedRAX R55 M5 · 11 工具 · CheXagent-8B

实验室双 RTX 3090 队列完成冻结的 CheXBench、SLAKE 和 VQA-RAD。合计按 848 题汇总。

| 数据集 | 正式成绩 | Qwen CoT | 11 工具 D | 较 D 改对 | 较 D 改错 | 净变化 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CheXBench | 454/618（73.46%） | 418/618 | 432/618 | 67 | 45 | +22 |
| SLAKE | 107/114（93.86%） | 106/114 | 106/114 | 2 | 1 | +1 |
| VQA-RAD | 93/116（80.17%） | 87/116 | 92/116 | 6 | 5 | +1 |
| **合计** | 654/848（77.12%） | 611/848 | 630/848 | 75 | 51 | +24 |

主回答使用 Qwen3.7-Plus Token Plan。工具包含原版 Stanford AIMI CheXagent-8B。[模型版本](https://huggingface.co/StanfordAIMI/CheXagent-8b/tree/4934e91451945c8218c267aae9c34929a7677829)

M5 每个数据集以七条 CerebraFusionMemory 模式起步，关闭 Skill 与动态生成工具。CheXBench 在保留前 383 题后从第 384 题续跑。此后及短集的记忆检索和写入使用百炼 Token Plan 的 DeepSeek V4.1 Flash。

配对结果使用同一冻结题目 ID 与参考答案。结果体现本轮的配置与运行条件。[11 工具 D 同题来源](https://github.com/cw462/MedRAX-reproduction/blob/dc6240fe683d0c83962eef53e3d0b9c5c0b3f769/reports/r55_lab_d_11tools_chexagent8b_20261115/README.md) · [CoT 同题来源](https://github.com/cw462/MedRAX-reproduction/blob/0dcb00352c05c6833d2001201da2f5c564267e37/reports/r55_qwen_react_chexagent8b_11tools_open_budget_20261114/README.md)

共记录 2816 次主模型调用和 1891 次工具调用，其中 31 次工具失败。已知费率的调用估算为 ¥53.5516。各角色的模型、用量、已知请求耗时和未知费用计数见运行摘要。

逐题记录有 9 次带失败回执或失败观察的 Verify 调用，并提供对应最终预测。

逐题文件包括问题、选项、最终预测、决策与工具观察。原图采用已公开的冻结病例链接。派生图名称和生成参数见观察记录，实际派生图字节与原始请求在私有归档中保留。

[CheXBench](chexbench.jsonl) · [SLAKE](slake.jsonl) · [VQA-RAD](vqarad.jsonl) · [运行配置与统计](summary.json)

[CheXBench 来源](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [SLAKE 来源](https://www.med-vqa.com/slake/) · [VQA-RAD 来源](https://doi.org/10.17605/OSF.IO/89KPS)
