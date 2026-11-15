# MedRAX R55 · Qwen3.6-Flash M2 · 11 工具

AutoDL 完成冻结三集，最终生成及评分控制器退出码为 0。总分按 848 题汇总。

| 数据集 | 正式成绩 | Qwen3.6-Flash ReAct | 较 ReAct 改对 | 较 ReAct 改错 | 净变化 |
| --- | ---: | ---: | ---: | ---: | ---: |
| CheXBench | 433/618（70.06%） | 429/618 | 78 | 74 | +4 |
| SLAKE | 105/114（92.11%） | 92/114 | 16 | 3 | +13 |
| VQA-RAD | 94/116（81.03%） | 87/116 | 15 | 8 | +7 |
| **合计** | 632/848（74.53%） | 608/848 | 109 | 85 | +24 |

两组按题目 ID 和参考答案配对。差异反映这些运行配置下的实际结果。[Qwen3.6-Flash ReAct 同题记录](https://github.com/cw462/MedRAX-reproduction/blob/2ee1bfb54a95c0c67a96b34473d275403a526e72/reports/r55_autodl_four_qwen36_flash_react_20261115/README.md)

主答使用 Qwen3.6-Flash Token Plan。M2 使用 ExpeL。各数据集保持独立题序与记忆，记忆模型为百炼 Token Plan 的 DeepSeek V4.1 Flash。11 个工具包括原版 Stanford AIMI CheXagent-8B。[原版 CheXagent-8B](https://huggingface.co/StanfordAIMI/CheXagent-8b/tree/4934e91451945c8218c267aae9c34929a7677829)

切换为三个共享 GPU 工具槽时沿用已保存的 CheXBench 预测与记忆。原控制器退出、保存断点和续跑控制器的回执见运行摘要。M2 的 VQA-RAD 在第 86 题前保留断点。该题在原字符预算内裁减同图工具观察后继续。逐题记录和运行摘要保留原恢复回执。

记录 2404 次主模型逻辑调用和 1137 次工具调用，其中 5 次工具失败。逐题记录附带同题 Verify 失败回执、观察和最终预测。已知模型请求耗时累计 3539.19 秒，已记录费率的 API 用量估算为 ¥15.6068。

逐题文件包含题面、选项、决策、工具观察及配对结果。原图链接采用已公开的冻结病例。原始请求和派生图文件由私有归档保留。

[CheXBench](chexbench.jsonl) · [SLAKE](slake.jsonl) · [VQA-RAD](vqarad.jsonl) · [运行摘要](summary.json)

[实际运行入口](source/bin/run_top4_priority.py) · [CheXBench 来源](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [SLAKE 来源](https://www.med-vqa.com/slake/) · [VQA-RAD 来源](https://doi.org/10.17605/OSF.IO/89KPS)
