# Qwen ReAct · 原版 CheXagent-8B · 11 工具，调用次数不限

AutoDL 在冻结的 848 道题上完成了 Qwen ReAct。工具调用记录确认 CheXagent 使用 Stanford AIMI 的原版 8B。三集均已正式评分。最终进程退出码为 0。[模型版本](https://huggingface.co/StanfordAIMI/CheXagent-8b/tree/4934e91451945c8218c267aae9c34929a7677829)

| 数据集 | 正确率 | CoT 同题分数 | CoT 错、本组对 | CoT 对、本组错 | 净变化 |
| --- | ---: | ---: | ---: | ---: | ---: |
| CheXBench | 440/618（71.20%） | 418/618 | 96 | 74 | +22 |
| SLAKE | 100/114（87.72%） | 106/114 | 4 | 10 | -6 |
| VQA-RAD | 91/116（78.45%） | 87/116 | 9 | 5 | +4 |
| **合计** | 631/848（74.41%） | 611/848 | 109 | 89 | +20 |

配对变化用冻结题目 ID 对齐，采用同一评分器。差异描述本次方法和工具配置的整体表现。

## 运行和工具记录

主答使用 qwen3.7-plus。工具菜单包含 CheXagent、LLaVA-Med、MedGemma、LLaVA-Rad、MedVLM-R1、MAIRA-2 定位报告、胸片短语定位、ROI 裁剪、MedRet、Reflect 和 Verify。CheXBench 按选项计分，SLAKE 和 VQA-RAD 按归档的显式短答匹配规则计分。

每题主模型和工具调用次数无固定上限。相同工具动作反复出现或连续收到相同无效回复时，提示模型给出最终答案。各题独立作答，Skill 关闭。Verify 不可用时记录失败，主模型继续作答。

本轮于 2026-11-14T14:30:13+00:00 将 SLAKE 后续 Qwen3.7-Plus 请求切到百炼按量付费接口。
VQA-RAD 及早期 CheXBench 请求走了原接口，于 2026-11-14T15:44:38+00:00 修正。
已落盘的预测与调用回包继续沿用。按量付费请求的 token 用量见逐请求和数据集记录。

按量付费接口拒绝请求后，后续主模型调用于 2026-11-14T16:29:34+00:00 恢复到原 Token Plan。逐请求记录保留原拒绝与后续响应。

评分账本记载 2728 次主模型逻辑调用，1762 次工具调用及 17 次工具失败计数。有记录费率的请求用量估算为 32.2632 元，单题耗时累计 26662.22 秒。租赁实付和账单金额未知。[运行、计费、复现与失败明细](summary.json)

## 逐题证据

逐题文件提供题干、选项、参考答案、最终回复、主模型决策、工具观察及与 CoT 的配对判断。每题链接指向同一冻结原题及已审核可用的原图。裁剪记录包含坐标和派生图资产引用。未审核可公开的派生图保留在私有运行归档。

[CheXBench](chexbench.jsonl) · [SLAKE](slake.jsonl) · [VQA-RAD](vqarad.jsonl)

[实际运行入口](https://github.com/cw462/MedRAX-reproduction/blob/0dcb00352c05c6833d2001201da2f5c564267e37/reports/r55_qwen_react_chexagent8b_11tools_open_budget_20261114/source/run_qwen_baselines.py) · [评分器](https://github.com/cw462/MedRAX-reproduction/blob/0dcb00352c05c6833d2001201da2f5c564267e37/reports/r55_qwen_react_chexagent8b_11tools_open_budget_20261114/source/r55_baseline_common.py) · [CheXBench 来源](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [SLAKE 来源](https://www.med-vqa.com/slake/) · [VQA-RAD 来源](https://doi.org/10.17605/OSF.IO/89KPS)
