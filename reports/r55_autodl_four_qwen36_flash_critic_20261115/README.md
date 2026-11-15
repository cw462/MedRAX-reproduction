# MedRAX R55 · Qwen3.6-Flash CRITIC · 11 工具

AutoDL 完成冻结三集，最终生成及评分控制器退出码为 0。总分按 848 题汇总。

| 数据集 | 正式成绩 | Qwen3.6-Flash ReAct | 较 ReAct 改对 | 较 ReAct 改错 | 净变化 |
| --- | ---: | ---: | ---: | ---: | ---: |
| CheXBench | 444/618（71.84%） | 429/618 | 90 | 75 | +15 |
| SLAKE | 101/114（88.60%） | 92/114 | 13 | 4 | +9 |
| VQA-RAD | 95/116（81.90%） | 87/116 | 15 | 7 | +8 |
| **合计** | 640/848（75.47%） | 608/848 | 118 | 86 | +32 |

两组按题目 ID 和参考答案配对。差异反映这些运行配置下的实际结果。[Qwen3.6-Flash ReAct 同题记录](https://github.com/cw462/MedRAX-reproduction/blob/2ee1bfb54a95c0c67a96b34473d275403a526e72/reports/r55_autodl_four_qwen36_flash_react_20261115/README.md)

主答使用 Qwen3.6-Flash Token Plan。CRITIC 使用已完成的 Flash CoT 原始候选进行核查。Verify 在运行中从同济 AGI 切换到官方 DeepSeek API 的 deepseek-flash。11 个工具包括原版 Stanford AIMI CheXagent-8B。[原版 CheXagent-8B](https://huggingface.co/StanfordAIMI/CheXagent-8b/tree/4934e91451945c8218c267aae9c34929a7677829)

启动时使用三个共享 GPU 工具槽。

记录 1178 次主模型逻辑调用和 304 次工具调用，其中 29 次工具失败。逐题记录附带同题 Verify 失败回执、观察和最终预测。逐题用时累计 5261.91 秒，已记录费率的 API 用量估算为 ¥4.4793。

逐题文件包含题面、选项、决策、工具观察及配对结果。原图链接采用已公开的冻结病例。原始请求和派生图文件由私有归档保留。

[CheXBench](chexbench.jsonl) · [SLAKE](slake.jsonl) · [VQA-RAD](vqarad.jsonl) · [运行摘要](summary.json)

[实际运行入口](source/flash_react/code_official/run_qwen_baselines.py) · [CheXBench 来源](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [SLAKE 来源](https://www.med-vqa.com/slake/) · [VQA-RAD 来源](https://doi.org/10.17605/OSF.IO/89KPS)
