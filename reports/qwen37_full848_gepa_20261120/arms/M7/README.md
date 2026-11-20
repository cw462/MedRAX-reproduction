# MedRAX R55 M7 · MobileE · CheXagent-8B

AutoDL 完成同一冻结题序下的 848 题。成绩来自原评分器，合计按题汇总。

| 数据集 | 正式成绩 | Qwen CoT | ReAct | 较 ReAct 改对 | 较 ReAct 改错 | 净变化 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CheXBench | 444/618（71.84%） | 418/618 | 440/618 | 58 | 54 | +4 |
| SLAKE | 103/114（90.35%） | 106/114 | 100/114 | 7 | 4 | +3 |
| VQA-RAD | 94/116（81.03%） | 87/116 | 91/116 | 7 | 4 | +3 |
| **合计** | 641/848（75.59%） | 611/848 | 631/848 | 72 | 62 | +10 |

主回答使用 Qwen3.7-Plus。11 个工具包含原版 Stanford AIMI CheXagent-8B。逐集配置记录检索时机、同图反馈、写入及调用设置。[CheXagent 版本](https://huggingface.co/StanfordAIMI/CheXagent-8b/tree/4934e91451945c8218c267aae9c34929a7677829)

表中按冻结题目 ID 和参考答案对齐。记忆与服务路由均参与本轮运行，API 路由和记忆写入切换的回执见运行摘要。[CoT 和 ReAct 同题数据](https://github.com/cw462/MedRAX-reproduction/blob/0dcb00352c05c6833d2001201da2f5c564267e37/reports/r55_qwen_react_chexagent8b_11tools_open_budget_20261114/README.md)

记录 3111 次主模型调用、2200 次工具调用，其中 15 次工具失败。已知费率下的请求估算 ¥62.8367。摘要保留各角色用量、已知请求耗时、未知费用计数及记忆用量。

逐题证据收录 11 次有工具失败回执或失败观察的 Verify 调用。这些题目的正式预测、失败观察和后续进度可按题号核对。

问答、选项及模型观察见逐题文件。原图通过已公开的冻结病例链接提供。派生图记录文件名和生成参数，实际图像和请求原件保存在私有归档。

[CheXBench](chexbench.jsonl) · [SLAKE](slake.jsonl) · [VQA-RAD](vqarad.jsonl) · [配置与统计](summary.json)

[运行入口](https://github.com/cw462/MedRAX-reproduction/blob/5c5e44b3a146f8a85786abf49939ba900b230062/reports/r55_autodl_m7_chexagent8b_20261115/source/bin/run_top4_priority.py) · [原评分器](https://github.com/cw462/MedRAX-reproduction/blob/5c5e44b3a146f8a85786abf49939ba900b230062/reports/r55_autodl_m7_chexagent8b_20261115/source/bin/score_r55_full848_dataset.py) · [CheXBench 来源](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [SLAKE 来源](https://www.med-vqa.com/slake/) · [VQA-RAD 来源](https://doi.org/10.17605/OSF.IO/89KPS)
