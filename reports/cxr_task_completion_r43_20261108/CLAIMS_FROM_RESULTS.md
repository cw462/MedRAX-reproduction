# R42/R43 Result-to-Claim 判定

- date: 2026-11-08
- claim_supported: partial
- confidence: high（针对下列限定判定；不代表泛化或临床效益证据充分）
- reviewer_route: native Codex / requested gpt-6-astra / ultra / host-default；路由由主执行者提供
- actual_returned_model_identity: unknown
- review_independence: same-family
- acceptance_status: provisional
- integrity_status: unavailable（未发现 EXPERIMENT_AUDIT.json；已有完成、复用及资源审计不替代该专项审计）
- evidence_precheck: 3/3 verified；仅证明 466、108、100 存在于所引摘要，不证明语义主张
- review_scope: 已完成结果的窄范围判断；未调用服务器、API或评分复现程序，未修改预测、代码或参考

总体 partial 针对“超过最好实验且改善真实答案能力”的较宽目标；下列项目成绩记录本身得到支持，不应把 partial 误读为这些计数尚未成立。

| 候选主张 | claim_supported | 判定 |
|---|---|---|
| (a) 冻结项目契约、完整分母下，CheXbench 458→466/618、SLAKE 107→108/114；此前 VQA-RAD 原 M 99→M42 100/116 | yes | 支持这些已完成的项目开发记录；R43没有新增VQA调用。 |
| (b) 全部增分都是新的医学推理或临床准确性提升 | no | 至少四个R43增分项的旧回复已有明确正确JSON answer；其余也混有矛盾消解、答案域适配和实质答案变化，不能统一归为医学能力提升。 |
| (c) 整条回复必须恰好answer/reason两键、answer≤300字符是论文/数据集官方要求 | no | 这是本项目parse_final的附加工程约定；所核对论文与作者评分代码不支持该官方归因。 |
| (d) 记忆/Skill普遍提升准确率，或当前成绩已超过论文官方SOTA | no | 没有相应机制隔离与一致官方口径证据；R43没有新增Skill学习，SLAKE只保留既有最强Skill整臂。 |

what_results_support:
- 已读取CheXbench和SLAKE全部per_question记录，分别包含618和114个配对题号；现有逐题评分合计与摘要一致。CheXbench净增8、SLAKE净增1，均0误改；608/113题评分字段不变，完成审计另确认answer/reason/status精确保留。
- 固定整臂基线为CheXbench M-C41、SLAKE M-S41。参考无关门槛筛出10/1个项目不可评分输出，新增11次主请求均收到回复，0新工具、0未知发送、0无效回退。它们提高了本项目端到端任务完成与严格契约下的正确数。
- CheXbench微平均74.1100%→75.4045%，三子集宏平均76.0089%→77.0773%；独立SLAKE93.8596%→94.7368%。VQA-RAD既有M42为86.2069%。
- 已记录的图像簇区间只描述当前开发样本：CheX微平均增益95%区间[0.4831,2.2329]个百分点；SLAKE和VQA的增益区间包含0。区间不消除反复开发、基线选择及单次随机性限制。
- 新增资源为34348输入/446输出tokens，11主/0工具，已知proxy 0.142744 CNY；这不是供应商账单，也不是整套历史轨迹的总成本。

what_results_dont_support:
- 不支持“R43纠正了9个原先错误的医学判断”。直接读旧/新回复可确认：chexbench_openi_0283、chexbench_slake_0047、chexbench_slake_0108及slake_12416原来就有正确显式answer。至少四项是输出契约恢复；未将离线枚举当新评分器。其他项也不能仅凭分数变化判定新增医学知识或有效视觉推理。
- 不支持将0误改解释为一般纠错机制安全：R43选择规则保留所有已合法答案，本来就未测试修改合法错误答案时的纠正/误改权衡。
- 不支持全部题目重新独立推理、未见测试泛化、临床应用效益或模型整体能力改善。不能把CheXbench-SLAKE与独立SLAKE的重叠样本作为独立合并证据。
- 不支持把已变化私有SLAKE目录的简短No当作新增结果。当前主张依赖已披露的冻结公开档重建，保留原长回复与公开元数据变换，不声称私有原请求逐字节一致。
- 不支持一个统一的“官方宽容解析器”。作者实现有模型/任务差异；去掉自设JSON门槛后也不能按参考挑选答案、把理由任意补成答案，或把随机回退信用解释为模型能力。

missing_evidence:
- 尚无针对全部冻结旧档、所有比较臂统一执行的作者指标对照；仍需锁定题号/分组、答案接口、提取规则、未提取/冲突/技术失败处理、重试及新增调用预算。相同114题数不足以证明与论文SLAKE题号完全相同。
- 尚不能量化官方/作者答案口径下还有多少真实净增，以及其中多少来自答案内容改变。已有显式answer诊断是归因线索，不是官方重算。
- 如欲提出泛化、Skill/记忆机制效应或SOTA主张，还缺同预算对照、匹配数据/模型/协议、独立未暴露评测及足够重复；这些不是发布当前限定记录的前提。

suggested_claim_revision:
“在反复用于开发的固定胸片问答队列上，保留各数据集既有最强完整方案，对参考无关规则判定不可评分的输出追加一次无工具任务完成请求。按冻结的本项目严格输出契约，CheXbench从458升至466/618，SLAKE从107升至108/114，新增11次主请求且0误改；此前VQA-RAD M42的100/116保持不变。至少四个R43增分项的旧回复已含正确显式答案，因此这是项目端到端输出成绩提升，尚不能量化为医学能力提升，也不构成官方SOTA或一般Skill/记忆有效性的证据。”

next_experiments_needed:
1. 下一步先完成官方/作者指标对齐，再对所有完整冻结旧档做一次统一离线对照，分别报告作者口径、无提取计错敏感性结果及JSON合规率；保留旧严格成绩，另立版本，逐项分开评分变化与新调用变化。CheX随机回退须报告种子、触发数量及其得分影响；不能通过选择种子追逐高分。
2. 完成上述对照后，针对仍然错误的答案设计同预算的实际纠错比较，再决定是否测试短Skill、记忆或工具证据验证。当前没有必要继续付费优化仅由自设格式门槛造成的损失；本判定不启动新实验、消融规划或论文撰写。

source_grounded_contract_check:
- MedRAX用户PDF第6页描述字母提取及对不清楚回复、执行错误或超时的有限重试；并未规定最终answer/reason两键JSON。第7页SLAKE114采用exact-match accuracy及词recall，并指向M4CXR。
- MedRAX固定作者版本d243cc5中，benchmark_medrax的A–F定稿调用属于ChestAgentBench；CheXbench GPT脚本则按去空格、大写后的A/B开头判断。后者最终总体accuracy使用全部结果作分母，batch显示指标使用有效结果，不能混称。
- CheXagent固定版本e4f31e6的BaseLM抽首个括号大写字母，无匹配时随机选项；另有选项似然路径。M4CXR固定版本4dd62e6对outputs答案字符串清除特殊token、首尾空白、句点并转小写后比较，另算BLEU-1/词集合recall；没有本项目两键/300字符规则或true→yes映射。
- CXRAgent用户PDF第7页对非报告任务使用accuracy；报告任务使用RaTEScore、LLMScore、GREEN、RadGraph-F1。所核对固定仓库0514b48中未定位到可据以复现本文benchmark答案提取的独立评分实现，因此具体提取规则仍应标为未知。
- 本判定依据本地原论文文本、固定作者代码、R43 README/EVALUATION_CONTRACT/PLAN、两套全量逐题评分及摘要/诊断/完成复用/资源记录、11份新请求中保留的完整旧回复与新回复，以及R42 VQA摘要/报告和总览。未把文档自己的结论当作独立证明。

publication_factual_corrections:
已指出并确认主执行者修正两处出处细节：SLAKE指标位于MedRAX PDF第7页；A–F答案定稿示例属于ChestAgentBench，不是CheXbench评分器。当前未发现阻止发布上述限定记录的剩余事实错误。官方口径对齐未完成仍限制结论，不能把“可发布项目记录”升级成临床/SOTA主张。
