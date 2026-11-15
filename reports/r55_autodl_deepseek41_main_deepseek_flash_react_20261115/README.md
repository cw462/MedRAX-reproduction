# MedRAX R55 · DeepSeek V4.1 Flash ReAct · 11 工具

AutoDL 完成冻结三集，最终生成及评分控制器退出码为 0。总分按 848 题汇总。

| 数据集 | 正式成绩 |
| --- | ---: |
| CheXBench | 422/618（68.28%） |
| SLAKE | 79/114（69.30%） |
| VQA-RAD | 90/116（77.59%） |
| **合计** | 591/848（69.69%） |

主答和 Verify 经官方 DeepSeek API 调用 DeepSeek V4.1 Flash（deepseek-flash）。各题独立作答，主模型和工具调用均无固定次数上限。11 个工具包括原版 Stanford AIMI CheXagent-8B。[原版 CheXagent-8B](https://huggingface.co/StanfordAIMI/CheXagent-8b/tree/4934e91451945c8218c267aae9c34929a7677829)

GPU 工具常驻路由的修复回执和运行尝试见运行摘要。原始工具观察记录了 CUDA 显存不足，涉及SLAKE 48/114 题、VQA-RAD 35/116 题。正式评分保留这些题的实际预测。

记录 2514 次主模型逻辑调用和 1449 次工具调用，其中 151 次工具失败。逐题记录附带同题 Verify 失败回执、观察和最终预测。逐题用时累计 17387.15 秒，已记录费率的 API 用量估算为 ¥20.4734。

逐题文件包含题面、选项、决策和工具观察。原图链接采用已公开的冻结病例。原始请求和派生图文件由私有归档保留。

[CheXBench](chexbench.jsonl) · [SLAKE](slake.jsonl) · [VQA-RAD](vqarad.jsonl) · [运行摘要](summary.json)

[实际运行入口](source/flash_react/code_official/run_qwen_baselines.py) · [CheXBench 来源](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [SLAKE 来源](https://www.med-vqa.com/slake/) · [VQA-RAD 来源](https://doi.org/10.17605/OSF.IO/89KPS)
