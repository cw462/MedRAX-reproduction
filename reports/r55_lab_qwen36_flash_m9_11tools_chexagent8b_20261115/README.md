# MedRAX R55 · Qwen3.6-Flash M9 · 11 工具

实验室 RTX 3090 完成冻结三集，最终生成及评分控制器退出码为 0。总分按 848 题汇总。

| 数据集 | 正式成绩 | Qwen3.6-Flash ReAct | 较 ReAct 改对 | 较 ReAct 改错 | 净变化 |
| --- | ---: | ---: | ---: | ---: | ---: |
| CheXBench | 416/618（67.31%） | 429/618 | 67 | 80 | -13 |
| SLAKE | 100/114（87.72%） | 92/114 | 14 | 6 | +8 |
| VQA-RAD | 90/116（77.59%） | 87/116 | 11 | 8 | +3 |
| **合计** | 606/848（71.46%） | 608/848 | 92 | 94 | -2 |

两组按题目 ID 和参考答案配对。ReAct 对照来自 AutoDL。[Qwen3.6-Flash ReAct 同题记录](https://github.com/cw462/MedRAX-reproduction/blob/2ee1bfb54a95c0c67a96b34473d275403a526e72/reports/r55_autodl_four_qwen36_flash_react_20261115/README.md)

主答使用 Qwen3.6-Flash Token Plan。M9 使用 Generative。各数据集保持独立题序与记忆。各集从空记忆库起步，记忆和 Verify 从启动起使用官方 DeepSeek API 的 deepseek-flash。11 个工具包括原版 Stanford AIMI CheXagent-8B。[原版 CheXagent-8B](https://huggingface.co/StanfordAIMI/CheXagent-8b/tree/4934e91451945c8218c267aae9c34929a7677829)

该组在 GPU 0 运行。

记录 2074 次主模型逻辑调用和 1023 次工具调用，其中 13 次工具失败。逐题记录附带同题 Verify 失败回执、观察和最终预测。已知模型请求耗时累计 3234.51 秒，已记录费率的 API 用量估算为 ¥9.8873。

逐题文件包含题面、选项、决策和工具观察。另附 ReAct 的同题预测和正确性。原图链接采用已公开的冻结病例。原始请求和派生图文件由私有归档保留。

[CheXBench](chexbench.jsonl) · [SLAKE](slake.jsonl) · [VQA-RAD](vqarad.jsonl) · [运行摘要](summary.json)

[实际运行入口](source/r55_lab_flash_m12_m9_20261115_001/run_lab_flash.py) · [CheXBench 来源](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [SLAKE 来源](https://www.med-vqa.com/slake/) · [VQA-RAD 来源](https://doi.org/10.17605/OSF.IO/89KPS)
