# MedRAX R55 · DeepSeek V4.1 Flash CRITIC · 11 工具

AutoDL 完成冻结三集，最终生成及评分控制器退出码为 0。总分按 848 题汇总。

| 数据集 | 正式成绩 | DeepSeek V4.1 Flash ReAct | 较 ReAct 改对 | 较 ReAct 改错 | 净变化 |
| --- | ---: | ---: | ---: | ---: | ---: |
| CheXBench | 412/618（66.67%） | 422/618 | 61 | 71 | -10 |
| SLAKE | 88/114（77.19%） | 79/114 | 14 | 5 | +9 |
| VQA-RAD | 93/116（80.17%） | 90/116 | 8 | 5 | +3 |
| **合计** | 593/848（69.93%） | 591/848 | 83 | 81 | +2 |

两组按题目 ID 和参考答案配对。[DeepSeek V4.1 Flash ReAct 同题记录](https://github.com/cw462/MedRAX-reproduction/blob/a459642b1e33386be62f41930d42143350ddf1c8/reports/r55_autodl_deepseek41_main_deepseek_flash_react_20261115/README.md)

主答和 Verify 经官方 DeepSeek API 调用 DeepSeek V4.1 Flash（deepseek-flash）。各题先保存同模型的 CoT 候选，再调用工具完成核查。11 个工具包括原版 Stanford AIMI CheXagent-8B。[原版 CheXagent-8B](https://huggingface.co/StanfordAIMI/CheXagent-8b/tree/4934e91451945c8218c267aae9c34929a7677829)

GPU 工具常驻路由的修复回执和运行尝试见运行摘要。原始工具观察记录了 CUDA 显存不足，涉及SLAKE 29/114 题。正式评分保留这些题的实际预测。

记录 2535 次主模型逻辑调用和 1677 次工具调用，其中 64 次工具失败。逐题记录附带同题 Verify 失败回执、观察和最终预测。逐题用时累计 24904.87 秒，已记录费率的 API 用量估算为 ¥30.6341。

逐题文件包含题面、选项、决策和工具观察。另附 ReAct 的同题预测和正确性。原图链接采用已公开的冻结病例。原始请求和派生图文件由私有归档保留。

[CheXBench](chexbench.jsonl) · [SLAKE](slake.jsonl) · [VQA-RAD](vqarad.jsonl) · [运行摘要](summary.json)

[实际运行入口](source/flash_react/code_deepseek_methods/run_qwen_baselines.py) · [CheXBench 来源](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [SLAKE 来源](https://www.med-vqa.com/slake/) · [VQA-RAD 来源](https://doi.org/10.17605/OSF.IO/89KPS)
