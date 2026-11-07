# VQA-RAD：AgentGain v3.2完整配对结果（2026-11-07）

M-AS、M-A均完成116/116，完成凭证齐全，进程退出0，随后才进行本数据集隔离评分。CheXbench仍按原冻结队列生成，没有按中途成绩改变范围或检索参数。历史M复用原已发布预测，未重新运行。

**M-AS为89/116，M-A为83/116，但不能把全部净增6题归为Skill贡献。** 只有4/116题实际注入卡片，其中1题形成正确性差异；其余112题两臂首请求完整载荷相同，仍出现净增5题的差异。未注入题的变化不能归因于未进入上下文的卡片，运行随机性或服务端差异等因素并未被控制。两新臂均低于历史M的99/116，当前整体方法没有超越历史M。

## 完整分母与配对结果

新两臂统一只去除一个包住完整合法JSON的围栏，原始回复和规范化记录均保留。沿用原答案字段NFKC、标点空白及true/false别名匹配，不猜自由文本、不从reason补答案、不用参考答案推断模型意图。历史M保留严格分数；同等去围栏机械敏感性恢复0条，历史分数不变。缺失保留在完整116题分母。

| 组 | 正确/116 | 准确率 | 评分缺失 |
|---|---:|---:|---:|
| M | 99 | 85.34% | 0 |
| M-AS | 89 | 76.72% | 2 |
| M-A | 83 | 71.55% | 3 |

| 比较 | 纠正 | 误改 | 净增 | 差值(pp) | 95%配对区间(pp) |
|---|---:|---:|---:|---:|---|
| M-AS vs M-A | 7 | 1 | +6 | +5.17 | [0.77, 10.74] |
| M-AS vs M | 3 | 13 | -10 | -8.62 | [-17.09, -1.55] |
| M-A vs M | 2 | 18 | -16 | -13.79 | [-24.07, -4.96] |

按可靠患者/检查/同图关系聚类，共58簇，10,000次配对percentile bootstrap，种子20261105，未作多重比较校正。M-AS vs M-A的完整队列区间虽低端高于0，仍不能越过低注入率及未注入题差异这一归因限制；它不是“6题均由Skill纠正”的证据。与历史M的区间也仅描述实际运行成绩差异，不隔离时段、提示、工具健康与调用策略。

[严格评分/全部配对变更](summary.json) · [严格逐题记录](per_question.jsonl) · [机械敏感性](mechanical_sensitivity_summary.json) · [敏感性逐题记录](mechanical_sensitivity_per_question.jsonl) · [历史M机械记录](historical_M_fence_recovery.json)。

## 实际Skill覆盖及全部配对差异

4道实际注入题均检索到Skill16844。以下完整列出，未按结果挑选。

| 注入题号 | M-AS | M-A | 参考答案 |
|---|---|---|---|
| vqarad_326 | No | No | No |
| vqarad_446 | No | Yes | No |
| vqarad_1141 | No | No | No |
| vqarad_1227 | No | No | No |

只有vqarad_446出现正确性变化，M-AS相对M-A多对1题；另3题相同。这4题太少，不能据此宣称普遍临床效益。对另外112题逐条核对公开的首请求载荷，模型、完整system/messages、原图、采样与输出上限均相同。[首请求可比性核对](request_comparability.json)。以下是全116题的全部8个正确性差异，其中7个发生在未注入题：

| 题号 | 是否注入 | M-AS相对M-A变化 |
|---|---|---|
| vqarad_298 | 否 | −1（M-AS格式缺失，M-A正确） |
| vqarad_446 | 是 | +1 |
| vqarad_651 | 否 | +1 |
| vqarad_1632 | 否 | +1 |
| vqarad_1717 | 否 | +1（M-A格式缺失） |
| vqarad_1874 | 否 | +1 |
| vqarad_1948 | 否 | +1 |
| vqarad_1997 | 否 | +1（M-A格式缺失） |

“纠正/误改”是最终评分正确性变化，包含结构缺失，不等于全部是临床推理纠错。也不把4题子集替代完整116题主结果。

## 实际调用、格式失败、时间与费用

两新臂同为qwen3.7-plus，temperature0.2/top_p0.95/thinking=false/max_output_tokens2048，最多6次主模型、4次医学工具。工具可选、可提前结束，不投票、不强制使用、不强行保留首答。先M-AS后M-A，使用同一工具菜单与GPU0，未复制历史失败缓存。

| 组 | 主模型发送 | 用工具题数/选择数 | 工具失败 | 缓存命中 | 6次触顶题 | 4工具触顶题 | 格式修复题/错误事件 | 首答改答题 | 墙钟分钟 | 已知用量费用(CNY) |
|---|---:|---|---:|---:|---:|---:|---|---:|---:|---:|
| M-AS | 129 | 3/3 | 0 | 0 | 2 | 0 | 2/12 | 0 | 7.66 | 1.216352 |
| M-A | 133 | 2/2 | 0 | 0 | 3 | 0 | 3/18 | 1 | 8.39 | 1.267768 |

两臂实际所选工具均为chest_xray_expert。M-AS共3次、M-A共2次，全部成功，没有把失败观察传给后续付费推理；工具引用合法不代表解释医学正确。M-AS没有首答改变，M-A有1题首答改变，完整first_answer/decisions/evidence字段保留，不凭“调用工具”宣称发生了纠错。

M-AS的vqarad_298、vqarad_650及M-A的vqarad_23、vqarad_1717、vqarad_1997在各自6次结构修复尝试后仍失败，最后错误均为evidence_value。它们是输出结构/证据字段校验缺失，不应被描述为已完成合法临床错误；依原规则仍计入完整分母。没有第7次修复、预算外裁决或为评分重新生成。

历史M为240次主模型、122次逻辑工具选择；本次虽上限6+4高于原4+2，实际调用反而显著更少。上限不等于实际用量，也不代表两方法具有相同的行为策略。原M的时段和工具健康情况按原报告保留，不为追求公平事后全量重跑。

新两臂费用按返回token及输入/输出4/12 CNY每百万估算，合计2.484120 CNY；均无未知发送/未知用量。源学习和开发费用共享另计，不跨数据集重复计入，不是供应商结算账单。[逐组行为与用量](behavior_resources.json) · [原工具结果](raw_tool_results.jsonl) · [实际GPU设置](tool_worker_gpu.json)。

## 固定源库、范围与完整证据

同一11张源图驱动审阅库用于两数据集及后续CheXbench，期间不更新。原69份源回复全部保存；病例/题号归属规范化、43候选、26结构等拒绝、32内容排除，以及最终7张未改卡/4张有来源程序性修订均公开。此为操作方辅助审阅，不宣称完全自动或独立临床认证。源隔离范围是已披露的解码像素/可用明确ID，源此前参与开发，不排除所有近重复。

[共享源学习和审阅证据](../source_learning/README.md) · [冻结库](../source_learning/reviewed_bank.json) · [全部源内容审阅](../source_learning/source_content_review.json)。实际推理库SHA256为`9d4434eaad4059b57e4a4c525c68543c5b27e23e22787434f6dd79dd7567ff98`；公开脱敏和换行字节可能不同。固定检索max_cards2/min_overlap2/max_chars2200，不读目标答案、不按成绩调阈值、不对弱匹配强塞卡。M-AS116份检索记录中仅4份有卡（3.45%），M-A无卡。

[全部M-AS检索](retrieval_M-AS.jsonl) · [M-AS预测/首答/轨迹](predictions_M-AS.jsonl) · [M-A预测/首答/轨迹](predictions_M-A.jsonl) · [M-AS完整请求回复](calls/M-AS/) · [M-A完整请求回复](calls/M-A/) · [M-AS工具决策](tool_selections_M-AS.jsonl) · [M-A工具决策](tool_selections_M-A.jsonl) · [规范化M-AS](mechanical_format_M-AS.jsonl) · [规范化M-A](mechanical_format_M-A.jsonl) · [原图/派生图](image_assets.json) · [协议](protocol.json) · [冻结配置/输入和代码hash](frozen_run.json) · [发布白名单](publication_manifest.json)。

历史M复用路径与保存文件hash见[复用凭证](historical_reuse.json)：`reports/cxr_vqa_toolsets/results/vqarad/predictions_M.jsonl`，SHA256 `341a1f6b8910d7a5e2380006cbee07a8078e55bcce9df6590bfacb659eb47b2c`。没有重新发起历史M请求。源开发与八工具预检已在正式目标生成前完成，DICOM适配器参数错误也在目标前修复；本VQA-RAD目标没有技术故障恢复或覆盖旧预测。

## 复现与结论边界

在仓库根目录运行 `python reports/cxr_gain_v32_20261107/results/reproduce_scores.py`，从公开记录重现严格/机械敏感性完整分母成绩、纠正误改与聚类区间，无API调用、无语义解释。[隔离评分器](../../../../experiments/score_cxr_vqa_extension.py) · [机械敏感性及行为分析](../../../../experiments/analyze_cxr_gain_v32.py) · [新臂运行器](../../../../experiments/run_cxr_gain_v32.py) · [公开导出器](../../../../experiments/export_cxr_gain_v32.py)。原数据来源、图像关系和许可沿用[既有VQA-RAD报告](../../../cxr_vqa_extension/results/vqarad/README.md)及[历史M对照报告](../../../cxr_vqa_toolsets/results/README.md)。

完整队列上M-AS比同预算M-A多对6题，但仅1题变化与实际卡片出现重合，且这不是独立控制下的临床因果证明；其他净差发生在未注入且首请求相同的题目。两新臂均未超过历史M。当前结果不足以断言行动Skill普遍有效或有害，也不能把更多名义预算、工具调用本身或输出格式变化当作临床收益。
