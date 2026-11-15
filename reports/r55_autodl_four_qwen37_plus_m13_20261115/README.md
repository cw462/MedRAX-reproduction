# MedRAX R55 · Qwen3.7-Plus M13 · 11 工具

AutoDL 完成冻结三集，最终生成及评分控制器退出码为 0。总分按 848 题汇总。

| 数据集 | 正式成绩 | Qwen3.7-Plus ReAct | 较 ReAct 改对 | 较 ReAct 改错 | 净变化 |
| --- | ---: | ---: | ---: | ---: | ---: |
| CheXBench | 441/618（71.36%） | 440/618 | 58 | 57 | +1 |
| SLAKE | 102/114（89.47%） | 100/114 | 6 | 4 | +2 |
| VQA-RAD | 91/116（78.45%） | 91/116 | 7 | 7 | +0 |
| **合计** | 634/848（74.76%） | 631/848 | 71 | 68 | +3 |

两组按题目 ID 和参考答案配对。差异反映这些运行配置下的实际结果。[Qwen3.7-Plus ReAct 同题记录](https://github.com/cw462/MedRAX-reproduction/blob/0dcb00352c05c6833d2001201da2f5c564267e37/reports/r55_qwen_react_chexagent8b_11tools_open_budget_20261114/README.md)

主答使用 Qwen3.7-Plus Token Plan。M13 使用 Lightweight Memory。各数据集保持独立题序与记忆。记忆模型为百炼 Token Plan 的 DeepSeek V4.1 Flash。11 个工具包括原版 Stanford AIMI CheXagent-8B。[原版 CheXagent-8B](https://huggingface.co/StanfordAIMI/CheXagent-8b/tree/4934e91451945c8218c267aae9c34929a7677829)

切换为三个共享 GPU 工具槽时沿用已保存的 CheXBench 预测与记忆。原控制器退出、保存断点和续跑控制器的回执见运行摘要。

记录 2663 次主模型逻辑调用和 1739 次工具调用，其中 17 次工具失败。逐题记录附带同题 Verify 失败回执、观察和最终预测。已知模型请求耗时累计 12364.80 秒，已记录费率的 API 用量估算为 ¥49.8358。

逐题文件包含题面、选项、决策、工具观察及配对结果。原图链接采用已公开的冻结病例。原始请求和派生图文件由私有归档保留。

[CheXBench](chexbench.jsonl) · [SLAKE](slake.jsonl) · [VQA-RAD](vqarad.jsonl) · [运行摘要](summary.json)

[实际运行入口](source/bin/run_top4_priority.py) · [CheXBench 来源](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [SLAKE 来源](https://www.med-vqa.com/slake/) · [VQA-RAD 来源](https://doi.org/10.17605/OSF.IO/89KPS)
