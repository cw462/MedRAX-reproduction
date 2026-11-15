# MedRAX R55 · Qwen3.6-Flash M12 · 11 工具

实验室 RTX 3090 完成冻结三集，最终生成及评分控制器退出码为 0。总分按 848 题汇总。

| 数据集 | 正式成绩 | Qwen3.6-Flash ReAct | 较 ReAct 改对 | 较 ReAct 改错 | 净变化 |
| --- | ---: | ---: | ---: | ---: | ---: |
| CheXBench | 435/618（70.39%） | 429/618 | 75 | 69 | +6 |
| SLAKE | 106/114（92.98%） | 92/114 | 17 | 3 | +14 |
| VQA-RAD | 91/116（78.45%） | 87/116 | 14 | 10 | +4 |
| **合计** | 632/848（74.53%） | 608/848 | 106 | 82 | +24 |

两组按题目 ID 和参考答案配对。ReAct 对照来自 AutoDL。[Qwen3.6-Flash ReAct 同题记录](https://github.com/cw462/MedRAX-reproduction/blob/2ee1bfb54a95c0c67a96b34473d275403a526e72/reports/r55_autodl_four_qwen36_flash_react_20261115/README.md)

主答使用 Qwen3.6-Flash Token Plan。M12 使用 MemEvolve EvolveR。各数据集保持独立题序与记忆。各集从空记忆库起步，记忆和 Verify 从启动起使用官方 DeepSeek API 的 deepseek-flash。11 个工具包括原版 Stanford AIMI CheXagent-8B。[原版 CheXagent-8B](https://huggingface.co/StanfordAIMI/CheXagent-8b/tree/4934e91451945c8218c267aae9c34929a7677829)

SLAKE 第 100 题写入记忆后切换到 GPU 1，从第 101 题续跑。

记录 2533 次主模型逻辑调用和 1252 次工具调用，其中 21 次工具失败。逐题记录附带同题 Verify 失败回执、观察和最终预测。已知模型请求耗时累计 4285.97 秒，已记录费率的 API 用量估算为 ¥15.1498。

逐题文件包含题面、选项、决策和工具观察。另附 ReAct 的同题预测和正确性。原图链接采用已公开的冻结病例。原始请求和派生图文件由私有归档保留。

[CheXBench](chexbench.jsonl) · [SLAKE](slake.jsonl) · [VQA-RAD](vqarad.jsonl) · [运行摘要](summary.json)

[实际运行入口](source/r55_lab_flash_m12_m9_20261115_001/run_lab_flash.py) · [CheXBench 来源](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [SLAKE 来源](https://www.med-vqa.com/slake/) · [VQA-RAD 来源](https://doi.org/10.17605/OSF.IO/89KPS)
