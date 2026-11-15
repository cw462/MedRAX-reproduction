# MedRAX R55 · DeepSeek V4.1 Flash M2 · 11 工具

AutoDL 完成冻结三集，最终生成及评分控制器退出码为 0。总分按 848 题汇总。

| 数据集 | 正式成绩 | DeepSeek V4.1 Flash ReAct | 较 ReAct 改对 | 较 ReAct 改错 | 净变化 |
| --- | ---: | ---: | ---: | ---: | ---: |
| CheXBench | 428/618（69.26%） | 422/618 | 77 | 71 | +6 |
| SLAKE | 105/114（92.11%） | 79/114 | 28 | 2 | +26 |
| VQA-RAD | 98/116（84.48%） | 90/116 | 14 | 6 | +8 |
| **合计** | 631/848（74.41%） | 591/848 | 119 | 79 | +40 |

两组按题目 ID 和参考答案配对。[DeepSeek V4.1 Flash ReAct 同题记录](https://github.com/cw462/MedRAX-reproduction/blob/a459642b1e33386be62f41930d42143350ddf1c8/reports/r55_autodl_deepseek41_main_deepseek_flash_react_20261115/README.md)

主答和 Verify 经官方 DeepSeek API 调用 DeepSeek V4.1 Flash（deepseek-flash）。M2 使用 ExpeL。各数据集保持独立题序与记忆。记忆调用同一官方模型。11 个工具包括原版 Stanford AIMI CheXagent-8B。[原版 CheXagent-8B](https://huggingface.co/StanfordAIMI/CheXagent-8b/tree/4934e91451945c8218c267aae9c34929a7677829)

GPU 工具常驻路由的修复回执和运行尝试见运行摘要。原始工具观察记录了 CUDA 显存不足，涉及SLAKE 9/114 题。正式评分保留这些题的实际预测。运行摘要保留断点及续跑回执。

记录 1966 次主模型逻辑调用和 2512 次工具调用，其中 69 次工具失败。逐题记录附带同题 Verify 失败回执、观察和最终预测。已知模型请求耗时累计 9337.81 秒，已记录费率的 API 用量估算为 ¥28.6104。

逐题文件包含题面、选项、决策和工具观察。另附 ReAct 的同题预测和正确性。原图链接采用已公开的冻结病例。原始请求和派生图文件由私有归档保留。

[CheXBench](chexbench.jsonl) · [SLAKE](slake.jsonl) · [VQA-RAD](vqarad.jsonl) · [运行摘要](summary.json)

[实际运行入口](source/bin/run_top4_flash_expel_official.py) · [CheXBench 来源](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [SLAKE 来源](https://www.med-vqa.com/slake/) · [VQA-RAD 来源](https://doi.org/10.17605/OSF.IO/89KPS)
