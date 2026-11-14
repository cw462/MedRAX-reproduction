# Qwen CRITIC · 原版 CheXagent-8B

AutoDL 在冻结的 848 道题上完成了 Qwen CRITIC。工具调用记录确认 CheXagent 使用 Stanford AIMI 的原版 8B。三集均已正式评分，最终进程退出码为 0。[模型版本](https://huggingface.co/StanfordAIMI/CheXagent-8b/tree/4934e91451945c8218c267aae9c34929a7677829)

| 数据集 | 正确率 | CoT 同题分数 | CoT 错、本组对 | CoT 对、本组错 | 净变化 |
| --- | ---: | ---: | ---: | ---: | ---: |
| CheXBench | 425/618（68.77%） | 418/618 | 66 | 59 | +7 |
| SLAKE | 101/114（88.60%） | 106/114 | 2 | 7 | -5 |
| VQA-RAD | 91/116（78.45%） | 87/116 | 8 | 4 | +4 |
| **合计** | 617/848（72.76%） | 611/848 | 76 | 70 | +6 |

配对变化用冻结题目 ID 对齐，采用同一评分器。差异描述本次方法和工具配置的整体表现。

## 运行和工具记录

主答使用 qwen3.7-plus。可调用 CheXagent、LLaVA-Med、MedGemma、LLaVA-Rad、MedVLM-R1 和 ROI 裁剪。CheXBench 按选项计分，SLAKE 和 VQA-RAD 按归档的显式短答匹配规则计分。

CRITIC 读取同一冻结题目的 CoT 候选，再决定保留或修改答案。

评分账本记载 1591 次主模型逻辑调用，848 次工具调用及 105 次工具失败计数。逐请求用量按记录费率合计 9.9978 元，单题耗时累计 12256.45 秒。租赁实付和账单金额未知。[运行、计费、复现与失败明细](summary.json)

## 逐题证据

逐题文件提供题干、选项、参考答案、最终回复、主模型决策、工具观察及与 CoT 的配对判断。每题链接指向同一冻结原题及已审核可用的原图。裁剪记录包含坐标和派生图资产引用。未审核可公开的派生图保留在私有运行归档。

[CheXBench](chexbench.jsonl) · [SLAKE](slake.jsonl) · [VQA-RAD](vqarad.jsonl)

[实际运行入口](source/run_qwen_baselines.py) · [评分器](source/r55_baseline_common.py) · [CheXBench 来源](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [SLAKE 来源](https://www.med-vqa.com/slake/) · [VQA-RAD 来源](https://doi.org/10.17605/OSF.IO/89KPS)
