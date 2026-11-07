# 第二阶段：源学习技能与经验库的冻结迁移（2026-11-07）

三个数据集的 M-S、M-E 共六组均已生成完毕，完成凭证齐全、退出码均为0，之后才读取目标参考答案进行隔离评分。第三阶段独立接续运行，第一阶段报告及原始预测不变。

**当前严格口径下，六组的点估计均低于各自 M 基线。** 这说明本次冻结库及实际工具运行条件下没有观察到准确率增益；不能据此断言技能或经验本身普遍有害。工具失败、无效工具计划、单次随机生成和源库差异都限制归因。CheXbench M-E 的主指标配对区间低于0；其余比较的区间包含0或以0为端点。区间未作多重比较校正。

## 统一评分与分母

沿用已发布的严格答案字段规则，对 M、M-S、M-E 一视同仁：原解析器要求合法 answer/reason JSON；短答案沿用 NFKC、标点空白规范化与 true/false 别名；CheXbench 接受合法字母、唯一匹配的完整选项或字母与原全文一致的组合。只评分 answer，不根据 reason、标准答案或上下文猜测意图，不新增临床同义词。有争议的回答内容语义重评草稿未使用。本报告没有新增去围栏或自由文本敏感性分数。

缺失与技术失败均保留在完整分母。CheXbench 主指标是三个子集等权宏平均，微平均另列；SLAKE/VQA-RAD 为完整队列准确率。[冻结评分说明](source_learning/stage2_scoring_policy.json) · [评分代码](../../../../experiments/score_cxr_vqa_extension.py) · [公开记录复现](reproduce_scores.py)。

| 数据集 | 组 | 正确/完整分母 | 准确率/微平均 | 主指标 | 缺失 |
|---|---|---:|---:|---:|---:|
| chexbench | M | 452/618 | 73.14% | 74.36% | 10 |
| chexbench | M-S | 445/618 | 72.01% | 73.38% | 14 |
| chexbench | M-E | 421/618 | 68.12% | 71.28% | 11 |
| slake | M | 105/114 | 92.11% | 92.11% | 1 |
| slake | M-S | 99/114 | 86.84% | 86.84% | 6 |
| slake | M-E | 102/114 | 89.47% | 89.47% | 2 |
| vqarad | M | 99/116 | 85.34% | 85.34% | 0 |
| vqarad | M-S | 91/116 | 78.45% | 78.45% | 2 |
| vqarad | M-E | 92/116 | 79.31% | 79.31% | 3 |

M 基线全部复用已完成的冻结预测，未重新生成。[CheXbench M](../chexbench/predictions_M.jsonl) · [SLAKE M](../../../cxr_vqa_toolsets/results/slake/predictions_M.jsonl) · [VQA-RAD M](../../../cxr_vqa_toolsets/results/vqarad/predictions_M.jsonl)。本表不重评或覆盖第一阶段报告。

## 配对变化

按可靠患者、检查、同图关系聚类，10,000次配对 percentile bootstrap，种子20261105。CheXbench 488簇、SLAKE 30簇、VQA-RAD 58簇。纠正/损害是预测正确性变化，包含格式与技术缺失的影响，不能全部当作临床纠错。

| 数据集 | 比较 | 纠正 | 损害 | 净增正确 | 主指标差值(pp) | 95%区间(pp) | 微平均差值(pp) |
|---|---|---:|---:|---:|---:|---|---:|
| chexbench | M-S vs M | 36 | 43 | -7 | -0.98 | [-3.74, 1.67] | -1.13 |
| chexbench | M-E vs M | 33 | 64 | -31 | -3.09 | [-5.43, -0.77] | -5.02 |
| slake | M-S vs M | 4 | 10 | -6 | -5.26 | [-11.01, 0.00] | -5.26 |
| slake | M-E vs M | 5 | 8 | -3 | -2.63 | [-8.33, 2.80] | -2.63 |
| vqarad | M-S vs M | 4 | 12 | -8 | -6.90 | [-15.00, 0.85] | -6.90 |
| vqarad | M-E vs M | 2 | 9 | -7 | -6.03 | [-13.33, 0.00] | -6.03 |

逐题原始答案、参考答案、缺失与配对变更在各数据集 `per_question.jsonl`、`summary.json` 中；所有题目、选项、原图、派生图、请求、回复、工具选择和原始工具结果随各数据集白名单发布。[CheXbench证据](chexbench/publication_manifest.json) · [SLAKE证据](slake/publication_manifest.json) · [VQA-RAD证据](vqarad/publication_manifest.json)。

## 冻结源库与隔离边界

源来自 ChestAgentBench SkeMex tools-v2 的既有开发轨迹。本次最终源队列为69例、260条已释放反馈轨迹，源学习上限138次请求；旧设计页中的99例/402题是早期候选清单，不能作为本次最终样本数。M-S 学习可迁移的检查技能，M-E 总结具体源病例经验，两个库共享同一冻结源队列。学习后固定为69条技能与68条经验，目标评测期间不更新库、不读目标答案。

隔离检查覆盖三个目标数据集的解码RGB像素与可用明确患者/检查ID；这不证明不存在未标识的近重复或更早开发阶段接触。源数据此前已用于开发，本实验不是全新外部独立源集验证。CheXbench SLAKE子集与独立SLAKE亦存在已披露重叠，不能把三个结果当作完全独立重复。

一次源学习 M-E/9057 请求发送后因磁盘满未保存回复，未重发，排除该条经验。因此69/68条的库容量差异与一个源病例缺失也限制了两种记忆形式的纯因果比较。

- [最终源清单及筛查范围](source_learning/frozen_source_roster.json)
- [技能库](source_learning/bank_M-S.json)、[经验库](source_learning/bank_M-E.json)、[原始冻结摘要与校验值](source_learning/complete_banks.json)
- [源病例未知发送记录](source_learning/unknown_source_9057.json)、[目标恢复凭证](source_learning/target_transport_recovery.json)
- [源准备代码](../../../../experiments/prepare_cxr_vqa_extension_source.py)、[源学习代码](../../../../experiments/learn_cxr_vqa_extension_banks.py)、[目标运行代码](../../../../experiments/run_cxr_vqa_extension.py)

源输入SHA256：`a0e82f405964f62b466ed1d24096555981cc9ae1d516abd6f7b252ba7ff24de9`。冻结技能库SHA256：`26bd416f7adf85b2b3563d43389b64dcb04172aaeea24c647abe53473764f5ea`；经验库SHA256：`49950a367fd11134d56984d88a400f85a0351641968e620d618b753e6a541bbb`。公开脱敏文件的字节可能不同，校验值标识的是推理时实际使用的原始库。

## 工具、失败与时间费用

六组均用 qwen3.7-plus，temperature0.2、top_p0.95、thinking=false、max_output_tokens2048，最多4次主模型调用、2次可选工具调用；共享GPU工具逐次执行。提示、库绑定与运行配置见每组 `runtime_full_*.json`，调用细节见 `calls/`，工具决策见 `tool_selections_*.jsonl`。工具失败记录数包含复用缓存的失败结果，不能除以新后端尝试数解释为新调用失败率。

| 数据集/组 | 主请求发送 | 工具选择 | 失败工具记录 | 缓存命中 | 生成历时(分钟) | 已知用量费用(CNY) | 未知发送 |
|---|---:|---:|---:|---:|---:|---:|---:|
| chexbench/M-S | 1473 | 855 | 254 | 483 | 122.09 | 14.322916 | 1 |
| chexbench/M-E | 1492 | 874 | 344 | 410 | 122.28 | 14.838568 | 0 |
| slake/M-S | 261 | 147 | 88 | 52 | 15.05 | 2.969316 | 0 |
| slake/M-E | 262 | 148 | 80 | 81 | 11.25 | 2.987644 | 0 |
| vqarad/M-S | 228 | 112 | 54 | 55 | 9.94 | 2.457020 | 0 |
| vqarad/M-E | 248 | 132 | 71 | 86 | 9.46 | 2.624744 | 0 |

费用按返回的输入/输出token与4/12 CNY每百万token估算，目标新增已知费用共40.200208 CNY，源学习已知费用1.782156 CNY。另有两次未知用量请求（源M-E/9057、CheXbench M-S/openi_0242），费用未知，不按0计算；这不是供应商实际账单总额。基线费用复用旧记录，不重复计入新增费用。历时是本组首次发送至完成的墙钟时间（含中途恢复），并行组不能相加作为总历时。[逐组用量、请求编号、状态与时间](resource_audit.json)。

CheXbench M-S/openi_0242 ordinal1 发生SSL连接异常，发送标记存在、回复未保存，未重发。新建该题技术缺失终态并从下一题继续；此前预测与回复保留，分母仍618。各组终态分类见 `resource_audit.json`；其中“completed”也可能有不合选项规则的答案，不能与最终评分缺失简单等同。

发布检查还发现 SLAKE M-S/slake_11989 ordinal3 一份已归档PNG有IDAT CRC错误，归档base64哈希仍与请求引用一致。没有修图、修改预测或重发；该份2337855字节原始内容以 `.bin` 发布，SHA256为 `40909bf4d90d5c8193dffc55f6fba699c7f1818aec5ff9805fcdf80bfc7e2378`，见 [损坏原始字节](slake/invalid_request_image_bytes/40909bf4d90d5c8193dffc55f6fba699c7f1818aec5ff9805fcdf80bfc7e2378.bin) 与 [图像完整性清单](slake/image_assets.json)。该异常并不证明模型接收端如何解码，亦不单独证明根因；其质量风险作为本次实际运行条件保留。

## 复现与结论边界

在仓库根目录执行 `python reports/cxr_vqa_extension/results/stage2/reproduce_scores.py`，从公开预测重现严格正确数、缺失数、纠正/损害与两种聚类区间；不访问API、不重新生成。完整运行参数、请求、图像和原始工具结果可进一步审查。公开文件移除了凭据、私有路径和历史账本；不因脱敏改变预测内容或修正合法错误答案。[公开导出器](../../../../experiments/export_cxr_vqa_extension.py)。

目前证据支持“本次冻结技能/经验迁移没有改善严格完整分母成绩”。它尚不能区分检索选卡、库内容、工具故障、格式或随机波动各自造成多少变化。后续审查应先在不看参考答案的条件下固定任何机械格式处理规则，并对所有比较组统一应用；不能通过向参考答案解释回答来抬高单组结果。第一阶段有争议的语义方案及其数字不属于本报告正式结果。

原始数据来源、许可与第一阶段队列说明沿用 [CheXbench](../chexbench/README.md)、[SLAKE](../slake/README.md)、[VQA-RAD](../vqarad/README.md) 的来源记录。
