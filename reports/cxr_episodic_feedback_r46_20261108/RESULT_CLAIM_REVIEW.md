## R46 独立判定（只读，未重评分/未跑API/未读其他审阅者）

**claim_supported: partial** —— 固定档案只能支持“单点、方向性、未达显著”的观察，**不能**支持“E 提升真实答案正确率”这一显著或可推广的因果主张。

**能支持什么**
- 冻结 27 题/8 图复用验证集上：P1(有 E)=22/27(81.48%) vs P0=21/27(77.78%)，corrections=1、harms=0、net=+1。
- 唯一变化 `r44_validation_9885` **确为显式答案翻转**：已核 predictions 文件——P0 answer "No"（reference=Yes，错）、P1 answer "Yes"（对），两臂均为 `plain_reply` 单 token；P0 `source_memory_ids=[]`、P1=[153,167]。这是真实答案变化，不是 JSON 伪提升：两臂 `whole_json_valid=0`、`original_M_contract_diagnostic=0`，主口径是显式答案 + M4CXR EM，故**不存在“把 JSON 诊断当医学提升”**。

**不能支持什么**
- 无法拒绝零效应：paired-image bootstrap CI=[0.0, 13.64]pp，**下界=0**；27 题仅 8 图、单变化点。
- 门槛未过：`priority_signal` 要求 net≥2 且 harms≤1，实际 net=1 → false；`overall_best_target_goal_achieved=false`。
- `not_unseen_test=true`：dev 27 题 8 图已在 R44 用过，非未见/官方 SOTA/独立患者证明。

**门槛未过与 CI 含 0 的含义**
- gate `net≥2 & harms≤1` 只是“开发优先级信号”，不是目标扩展/发布门槛；net=1 未触发，即连内部优先级信号都未达标，更谈不上最佳目标已达成。
- CI 下界=0.0 表示 bootstrap 2.5% 分位为 0pp，95% 置信**不能排除“E 效应为零”**；上界 13.6pp 是小样本噪声宽度，不是点估计，绝不可解读为“最多提升 13.6%”。

**gamma / 源分布局限**
- 12 源全部 ŷ=y（无纠错案例），9 Yes/3 No、8 abnormality 全 Yes：源库从不含“模型错→被纠正”的样例，E 未暴露任何纠错学习信号。
- gamma 是“if model_answer==source_annotation→acknowledge agreement else flag discrepancy”的**比较元规则**，不是“未知病人如何诊断”的可执行诊断规则；检索到的 E 实质是“相似图像 + 同意确认”。
- 9885 命中的 153/167 两源均 Yes 且 phi 描述肺底模糊/积液，灰度相似→倾向“抄 Yes 标签”；单样本无法区分“被证据说服”与“标签复制”。dev system 虽要求独立判断，但结果层面无从区分。phi/sigma 视觉解读未临床验证；source/dev 像素分离但无患者身份独立证明。

**最多 3 个下一步假设（不执行）**
1. H1：纠正是检索内容驱动还是随机——对 9885 在温度 0.2 下多次采样，或把检索源替换为 No 标注的相似图；若 No→Yes 不稳定/换 No 即回 No，则证明是标签复制而非诊断。
2. H2：gamma 无贡献、phi 才是驱动——消融“只送 gamma / 只送 phi / 全送”，在未见集比较 correction 与 harm；若 gamma 无贡献则移除。
3. H3：源分布偏置——构造含真实 ŷ≠y 纠错案例且 Yes/No 均衡的源库，在非 R44 复用未见集检验能否 net≥2 且 CI 下界>0。

**confidence**：对“1 次显式纠错、0 harm、证据已冻结”这一记录事实＝**高**；对“E 提升真实正确率”＝**低**。

**review_completed / scope_complete**：review_completed=true（对本固定档案）；scope_complete=true（仅限声明的只读范围）。

**实际检查范围**：读 scorer 源码与 `results/summary.json`、`per_question.jsonl`、`RESOURCE_SUMMARY.json`、`PROTOCOL.json`；核实 changed case 的 P0/P1 predictions、contexts，及 frozen_E 中 r44_train_153/167 源条目（phi/sigma/gamma/y_hat/y、`not_clinically_adjudicated:true`）。经 Glob 确认 **EXPERIMENT_AUDIT.json 不存在 → integrity unavailable**，不制造完整性审计。费用 0.457652 CNY 为本地 usage proxy 非发票；原图归档由 exporter 检查，未据收到回复断言供应商视觉解码。
