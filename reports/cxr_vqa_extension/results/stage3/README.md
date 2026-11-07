# 第三阶段：同图多题Q配对与病史H适用性（2026-11-07）

Q的六组生成全部完成，凭证齐全、退出码均为0，之后才进行隔离评分。CheXbench为74组204题，SLAKE为30组114题，VQA-RAD为36组94题，共140组412题，每组分别运行D-Q/M-Q。H在三个数据集均无完整独立病史字段，按冻结协议不适用，未补造病史或发起H请求。

**本次Q结果存在严重输出格式混杂，不能据此宣称工具提高临床正确率。** D-Q的140条组回复全部带Markdown围栏，原运行解析器不接受围栏，因此412道题全部进入严格格式缺失。M-Q的140条组回复均未使用工具，且大多符合原要求的裸JSON外层。两组严格分差主要包含这一格式接受差异；D-Q严格0分不代表它没有回答或影像能力为0。

## 实验问题、输入与实际运行

D-Q在一次组请求中直接回答同图相关问题；M-Q开放辅助工具接口，仍逐题绑定原图、题号与选项，禁止把其他问题的措辞或选项当作已知影像发现。主比较是M-Q vs D-Q，考察联合答题设置下开放工具接口后的整体行为。它本身不隔离“联合回答vs逐题回答”的效应，也不能仅凭结果推导使用了工具。

**实际两组每组都只发起一次主请求，D-Q、M-Q均为0次工具选择和0次后端调用。** 因而本次没有实际工具证据带来的收益可估计，观察到的是不同提示/接口条件下的输出与严格解析表现。M-Q名义上可选工具，不等于实际调用了工具。运行参数为qwen3.7-plus、temperature0.2、top_p0.95、thinking=false；实际逐请求token参数见完整请求记录，不能把按题数规划的上界当作实际用量。

同图组在读取目标答案前冻结。未入Q队列的CheXbench414题和VQA-RAD22题不进入Q分母；SLAKE114题全部进入。`data_manifest.json`保留原完整目标数据集元数据，导出的`inputs.jsonl/references.jsonl`只含Q冻结子集。不同阶段队列不同，不能直接用全量单题成绩作Q增益。

- [冻结队列](chexbench/joint_cohort.json)，原始文件SHA256：`7e5140a1a2f8a4d2a61531eead115ea85fe7c15966b077021bdd0a0346a44283`
- [联合运行器](../../../../experiments/run_cxr_vqa_joint.py)、[题图绑定与提示](../../../../experiments/cxr_vqa_joint.py)、[完整协议](chexbench/protocol.json)

## 严格结果：仅说明协议接受表现

沿用原答案字段评分器，不从reason或标准答案推断回答，不增加同义词、不剥离围栏或补写外层后重评。有争议的语义重评草稿仍未启用。所有缺失保留在各自完整Q分母。

| 数据集 | Q组数/题数 | D-Q严格正确 | D-Q缺失 | M-Q严格正确 | M-Q缺失 | M-Q微平均 | M-Q等权子集宏平均 |
|---|---:|---:|---:|---:|---:|---:|---:|
| chexbench | 74/204 | 0/204 | 204 | 162/204 | 2 | 79.41% | 72.70% |
| slake | 30/114 | 0/114 | 114 | 107/114 | 0 | 93.86% | 93.86% |
| vqarad | 36/94 | 0/94 | 94 | 72/94 | 0 | 76.60% | 76.60% |

CheXbench主指标为冻结Q子集的三子集等权宏平均（OpenI39题、Rad-Restruct44题、SLAKE121题），不是原全量618题。完整逐题记录与配对区间在各数据集summary/per_question中保留。以下区间针对严格协议结果，**不是临床工具收益区间**；“纠正”计数也包含从格式缺失转为可评分输出的变化。

| 数据集 | M-Q vs D-Q严格纠正/损害/净增 | 主指标差值(pp) | 95%聚类区间(pp) |
|---|---:|---:|---|
| chexbench | 162/0/+162 | +72.70 | [64.67, 81.00] |
| slake | 107/0/+107 | +93.86 | [86.67, 99.14] |
| vqarad | 72/0/+72 | +76.60 | [63.92, 88.37] |

按患者/检查/图像关系聚类后，本Q子集分别为74、30、36簇；10,000次配对percentile bootstrap，种子20261105，未作多重比较校正。原始数据关系保留，不将同一图上的多个问题当独立样本。

## 格式诊断：不重评、不猜答案

诊断只检查整条最终回复的JSON结构、可选的一个完整围栏与冻结组题号，不读取参考答案，不抽取或重写答案、不据此生成新分数。`exact_question_id_map`表示顶层键恰好是本组全部原题号；仍因缺少规定的answers外层而不符合原运行解析器。围栏中有答案不保证答案正确。

| 数据集/组 | 最终组回复结构计数 |
|---|---|
| chexbench/D-Q | enclosing_fence_answers_wrapper: 39；enclosing_fence_exact_question_id_map: 33；enclosing_fence_unparseable_json: 2 |
| chexbench/M-Q | bare_answers_wrapper: 73；bare_unparseable_json: 1 |
| slake/D-Q | enclosing_fence_exact_question_id_map: 19；enclosing_fence_answers_wrapper: 11 |
| slake/M-Q | bare_answers_wrapper: 30 |
| vqarad/D-Q | enclosing_fence_exact_question_id_map: 8；enclosing_fence_answers_wrapper: 28 |
| vqarad/M-Q | bare_answers_wrapper: 36 |

这直接说明严格D-Q成绩不能解释为完全不会答题。即使日后进行机械格式敏感性处理，也必须先固定参考答案不可见的规则，对全部比较组统一应用，保留原始结果并与语义解释分开。本文没有发布新的回答内容重评分数，亦未重发任何问题。

## 时间、费用与恢复

| 数据集/组 | 请求/已保存回复 | 工具调用 | 生成历时(分钟) | 已知用量费用(CNY) |
|---|---:|---:|---:|---:|
| chexbench/D-Q | 74/74 | 0 | 5.90 | 0.503020 |
| chexbench/M-Q | 74/74 | 0 | 6.33 | 0.592212 |
| slake/D-Q | 30/30 | 0 | 2.65 | 0.260172 |
| slake/M-Q | 30/30 | 0 | 2.65 | 0.293024 |
| vqarad/D-Q | 36/36 | 0 | 2.25 | 0.254100 |
| vqarad/M-Q | 36/36 | 0 | 2.26 | 0.290552 |

Q共280次发送、280份保存回复，均有用量记录，按输入/输出4/12 CNY每百万token估算共2.193080 CNY；不是供应商结算账单。没有未知发送需重试；未读取共享账本。各组历时含本组运行时间，并行组不能相加作总墙钟历时。[时间、用量、请求结构与终态审计](resource_format_audit.json)。

队列切换SLAKE时，启动器引用了不存在的`slake_repaired_m/runtime.json`，在任何SLAKE新请求发送前退出。改为已存在的`runtime_m_repaired.json`；其D臂与原SLAKE D配置逐字段相等，随后安全接续。既有CheXbench预测、提示和请求未改变，也未重新生成。全部六组完成凭证在各数据集目录。

## H不适用及公开证据

三个数据集都缺少可独立提供给模型的完整年龄、性别、病史元组；题干线索不被转写为外部病史，答案或诊断不反推为病史。因此D-H/M-H不适用，未产生H评分或调用。[适用性凭证](h_applicability.json)。

完整Q证据按组保存：`joint_groups/D-Q或M-Q/组ID.json`为组终态，`calls/臂/组ID.json`为完整组请求与回复；`predictions_*.jsonl`保留逐题答案与group_id。题目、选项、原图、图像清单、运行配置、协议、逐题评分及工具零调用记录一并公开。未把组请求错挂到逐题目录，也没有遗漏Q子集外单题的说明。

[CheXbench白名单](chexbench/publication_manifest.json) · [SLAKE白名单](slake/publication_manifest.json) · [VQA-RAD白名单](vqarad/publication_manifest.json) · [评分复现](reproduce_scores.py) · [组感知导出器](../../../../experiments/export_cxr_vqa_extension.py)。

在仓库根目录运行 `python reports/cxr_vqa_extension/results/stage3/reproduce_scores.py`，从公开逐题原始预测重现严格分数、缺失和配对区间，不访问API、不对原回复做内容解释。

本阶段完成了预先冻结队列的生成与留证，但格式混杂与实际零工具调用使其不能支持临床工具增益结论。合法错误、格式缺失、未知发送与病史不适用是不同情况，报告保持区分。原数据来源、许可与图像关系沿用 [CheXbench](../chexbench/README.md)、[SLAKE](../slake/README.md)、[VQA-RAD](../vqarad/README.md) 的来源记录。
