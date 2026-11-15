# MedRAX R55 · Qwen3.6-Flash M5 · 11 工具

AutoDL 完成冻结三集，最终生成及评分控制器退出码为 0。总分按 848 题汇总。

| 数据集 | 正式成绩 | Qwen3.6-Flash ReAct | 较 ReAct 改对 | 较 ReAct 改错 | 净变化 |
| --- | ---: | ---: | ---: | ---: | ---: |
| CheXBench | 436/618（70.55%） | 429/618 | 69 | 62 | +7 |
| SLAKE | 106/114（92.98%） | 92/114 | 16 | 2 | +14 |
| VQA-RAD | 93/116（80.17%） | 87/116 | 15 | 9 | +6 |
| **合计** | 635/848（74.88%） | 608/848 | 100 | 73 | +27 |

两组按题目 ID 和参考答案配对。[Qwen3.6-Flash ReAct 同题记录](https://github.com/cw462/MedRAX-reproduction/blob/2ee1bfb54a95c0c67a96b34473d275403a526e72/reports/r55_autodl_four_qwen36_flash_react_20261115/README.md)

主答使用 Qwen3.6-Flash Token Plan。M5 使用 CerebraFusionMemory。各数据集保持独立题序与记忆。运行中从同济 AGI DeepSeek-V4.1-Flash 切换到官方 DeepSeek API 的 deepseek-flash，沿用切换时已保存的预测和记忆。每集从方法的 7 个初始记忆模式开始。11 个工具包括原版 Stanford AIMI CheXagent-8B。[原版 CheXagent-8B](https://huggingface.co/StanfordAIMI/CheXagent-8b/tree/4934e91451945c8218c267aae9c34929a7677829)

启动时使用三个共享 GPU 工具槽。同济连接中断后沿用已保存的预测，从中断的记忆写入继续。逐题记录和运行摘要保留原恢复回执。

记录 2505 次主模型逻辑调用和 1253 次工具调用，其中 9 次工具失败。逐题记录附带同题 Verify 失败回执、观察和最终预测。已知模型请求耗时累计 3861.56 秒，已记录费率的 API 用量估算为 ¥14.8901。

逐题文件包含题面、选项、决策和工具观察。另附 ReAct 的同题预测和正确性。原图链接采用已公开的冻结病例。原始请求和派生图文件由私有归档保留。

[CheXBench](chexbench.jsonl) · [SLAKE](slake.jsonl) · [VQA-RAD](vqarad.jsonl) · [运行摘要](summary.json)

[实际运行入口](source/bin/run_top4_flash_memory_official.py) · [CheXBench 来源](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [SLAKE 来源](https://www.med-vqa.com/slake/) · [VQA-RAD 来源](https://doi.org/10.17605/OSF.IO/89KPS)
