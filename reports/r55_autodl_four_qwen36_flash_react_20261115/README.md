# MedRAX R55 · Qwen3.6-Flash ReAct · 11 工具

AutoDL 完成冻结三集，最终生成及评分控制器退出码为 0。总分按 848 题汇总。

| 数据集 | 正式成绩 | Qwen3.7-Plus ReAct | 较旧组改对 | 较旧组改错 | 净变化 |
| --- | ---: | ---: | ---: | ---: | ---: |
| CheXBench | 429/618（69.42%） | 440/618 | 76 | 87 | -11 |
| SLAKE | 92/114（80.70%） | 100/114 | 3 | 11 | -8 |
| VQA-RAD | 87/116（75.00%） | 91/116 | 11 | 15 | -4 |
| **合计** | 608/848（71.70%） | 631/848 | 90 | 113 | -23 |

两组按题目 ID 和参考答案配对。差异反映这些运行配置下的实际结果。[Qwen3.7-Plus ReAct 同题记录](https://github.com/cw462/MedRAX-reproduction/blob/0dcb00352c05c6833d2001201da2f5c564267e37/reports/r55_qwen_react_chexagent8b_11tools_open_budget_20261114/README.md)

主答使用 Qwen3.6-Flash Token Plan，ReAct 配置三个题目工作进程。每题主模型及工具调用没有固定次数上限。11 个工具包括原版 Stanford AIMI CheXagent-8B。[原版 CheXagent-8B](https://huggingface.co/StanfordAIMI/CheXagent-8b/tree/4934e91451945c8218c267aae9c34929a7677829)

切换为三个共享 GPU 工具槽时沿用已保存的 434 道 CheXBench 预测。原控制器退出、保存断点和续跑控制器的回执见运行摘要。

记录 2774 次主模型逻辑调用和 1835 次工具调用，其中 57 次工具失败。逐题记录附带同题 Verify 失败回执、观察和最终预测。共累计 17943.20 秒逐题用时，已记录费率的 API 用量估算为 ¥17.5515。

逐题文件包含题面、选项、决策、工具观察及配对结果。原图链接采用已公开的冻结病例。原始请求和派生图文件由私有归档保留。

[CheXBench](chexbench.jsonl) · [SLAKE](slake.jsonl) · [VQA-RAD](vqarad.jsonl) · [运行摘要](summary.json)

[实际运行入口](source/flash_react/code/run_qwen_baselines.py) · [CheXBench 来源](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [SLAKE 来源](https://www.med-vqa.com/slake/) · [VQA-RAD 来源](https://doi.org/10.17605/OSF.IO/89KPS)
