三份 on-disk 边界控制文件与包内主证据及最终 publisher 门限的硬编码期望值完全一致，未发现被改写为“预审 ready”。下面是本次新会话的完整结果审查。

---

# R49 完整结果 / 结果到声明审查（新会话，唯一一次）

## 实际完成的审查范围

本次完成三个范围：**adoption_protocol、request_resource_accounting、complete_results_and_claims**。审查方式为语义/可复现性证据核对：复用已存分数与逐题行交叉验算、核对边界收据与控制文件、检查 verifier/scorer/publisher/writer 源码门限。未重跑代码、未做新评分/推理/导出、未远端核验、未核临床图像、未做字节/像素哈希、未鉴权模型权重。

## 逐范围发现

### 1. adoption_protocol —— 通过，无缺陷

- 实读 `reports/cxr_online_skill_r49_20261108/evidence/recovery/adoption_1/EXECUTION_AUTHORIZATION.json`，如实保留 `verdict=audit_deferred_until_full_generation`、`review_completed=false`、`scope_complete=false`、`exact_user_reply=这个可以跑完再审计？`，未回填为 prelaunch ready。
- 实读 `SCOPE.json` 与 `plan.json`：`assess_only=true`、`write_phase_analysis_unchanged=true`、`representative_index_only=true`、`new_meta_request_limit=2`、`window_index=6`、`activation_committed_questions=210`、`duplicate_skill_id=s_e1a0642fabefb0c7`，与 publisher `adoption_recovery()` 的硬编码期望完全一致；两次代表项选择只用于 assess 边界，MUTATE 仍走原 ANALYZE。
- 发布顺序记录正确：`PUBLICATION_HISTORY.json` 的首次证据推送 commit `628617beb777d4b99aa1cb7110f50fbdfc8fde8c`、base `641746b8680c3b62d655abb154ab773cd57e6388`、`final_result_review_completed_at_first_push=false`、远端核验 `waived_by_user=true/performed=false`，与 git 当前 HEAD 一致；`EXECUTION_AUTHORIZATION.audit_before_publication=true` 作为历史计划值与后续用户“先上传github吧”的时序修订分列保存，未混淆。
- 中间 raw1（依赖缺失、q41 CUDA、120/150 两次 META schema、Embedding 400、168 短语、210 重复 adoption）与各自独立诊断全部保留，未被最终 0 抹去。

### 2. request_resource_accounting —— 通过，无缺陷

- 三组 Agent/META/embedding/tool 分账、token、CNY 代理小计均来自保存 receipts；`provider_invoice=false` 一贯标注。
- 修复子集（`meta_schema_repair/2`、`adoption_repair`、`embedding_http_recovery`）均 `included_in_*_totals=true`，为非附加子集；R49_META 967 请求中已含 4 次修复调用，不会二次计费。
- 算术一致性核对通过：CheX `fresh_backend_attempts 1246 = healthy 1244 + failed 2`（CUDA 1 + phrase 1）；embedding `requests 321 = 成功 320 + 已登记失败 1`，且 `cost_unknown_count=321`、失败/诊断 usage/body 未知如实标 unknown；工具硬件成本、controller 总墙钟、Embedding 单价未知项如实留空。
- CLI 审查 USD/时长与推理 CNY 分列，非发票，不与生产成本相加。

### 3. complete_results_and_claims —— 通过，无缺陷；负结果如实保留

逐题行交叉验算（非重新评分）与已存 summary 完全一致：

- CheX：R49 `465/618`，子集求和 `270+77+118=465`、`380+115+123=618`；窗口 correct 求和 `=465`；skill_hit 窗口求和 `=505`；对 M43 `49 纠正/50 误改/净 -1`（466−465=1 一致）；R47 468 保留为次级不同信息比较器，未替换、未藏输。
- SLAKE：`113/114`，逐题核对恰好 5 处纠正（12011、12327、12348、12361、12392）且 0 处误改，`net +5`（113−108=5）；`skill_hit=0`，故增益不可归因 Skill（同图记忆命中 84）。
- VQA-RAD：`97/116`，逐题核对 4 处纠正（137、325、1355、1948）与 7 处误改（104、113、166、374、648、650、1354），`net -3`（100−97=3）；M43 无独立 VQA 臂、沿用 M42 100/116 表述正确。
- 宏/微、子集、word recall、domain_invalid（CheX 各臂 1/0/1）均与行一致；SLAKE/VQA 窗口数 `30+30+30+24=114`、`30+30+30+26=116` 一致。
- 解释边界正确且保守：848 为题数非独立病例；SLAKE/CheX-SLAKE 共享图重叠、无同期 no-Skill 对照、运行中 MUTATE 字段提示/EOS 策略/采用归因修订、混合 legacy cache 均作为混杂披露，不主张 Skill 因果、同预算收益、闭卷 SOTA、临床能力。
- 公开复现：CheX 两次 verifier（一次操作停止无输出 `exit -1`、一次完成 `exit 0`），SLAKE/VQA 原 normalizer 完成；`PUBLIC_REPRODUCTION_TECHNICAL_CONTINUATION.json` 把停止尝试的内部 metric 阶段标为 unknown 而非 pre-adaptation，诚实。

## 身份与方法限制（不影响本审查范围完成）

- 未逐条独立重算 CheX 618 行的 49/50（复用已存分数，仅核净额与一致性）；“17 共享图 / 64 匹配题”与“真值在自身预测+事件保存后才揭示”的时序按已存协议/report 采信，未逐事件重验。
- 模型身份为 CLI 配置别名 `deepseek-v4-pro`，非权重鉴证；未做临床图像重读、字节/像素哈希、远端核验。

## 结论

无真实发布阻断项。负结果（CheX `-1`、VQA `-3`）与 SLAKE 增益均被按受限解释如实保留，发布顺序与豁免按用户最新指示记录。可按当前范围发布。

```json
BEGIN_RESULT_CLAIM_JSON
{
  "scope_complete": true,
  "audit_scope": ["adoption_protocol", "request_resource_accounting", "complete_results_and_claims"],
  "claim_supported": "yes",
  "confidence": "high",
  "publication_verdict": "无真实发布阻断项。三个范围均完成语义/可复现性核验：数字与逐题行一致，负结果（CheX 465 vs 466、VQA 97 vs 100）如实保留，SLAKE 零 Skill 命中的增益不作因果主张，发布顺序与远端核验豁免按用户最新指示记录，可依当前范围发布。",
  "publication_blockers": [],
  "checked_artifacts": [
    "reports/cxr_online_skill_r49_20261108/PUBLICATION_SEQUENCE_AMENDMENT.md",
    "reports/cxr_online_skill_r49_20261108/PUBLICATION_HISTORY.json",
    "reports/cxr_online_skill_r49_20261108/PUBLIC_REPRODUCTION_TECHNICAL_CONTINUATION.json",
    "reports/cxr_online_skill_r49_20261108/PROTOCOL.json",
    "reports/cxr_online_skill_r49_20261108/results/chexbench/summary.json",
    "reports/cxr_online_skill_r49_20261108/results/slake/summary.json",
    "reports/cxr_online_skill_r49_20261108/results/vqarad/summary.json",
    "reports/cxr_online_skill_r49_20261108/deployment_source/reporting_provenance/score_receipts/chexbench.json",
    "reports/cxr_online_skill_r49_20261108/evidence/recovery/adoption_1/EXECUTION_AUTHORIZATION.json",
    "reports/cxr_online_skill_r49_20261108/evidence/recovery/adoption_1/SCOPE.json",
    "reports/cxr_online_skill_r49_20261108/evidence/recovery/adoption_1/plan.json",
    "experiments/verify_public_online_skill_r49.py",
    "local_assets/score_completed_r49_dataset_once.py",
    "local_assets/publish_cxr_online_skill_r49.py",
    "local_assets/publish_r49_evidence_first.py",
    "local_assets/finalize_r49_report.py"
  ],
  "claims_markdown": "# CLAIMS_FROM_RESULTS（结果到声明）\n\n## 允许且已核验\n- 三个流全新生成：CheX 618、SLAKE 114、VQA-RAD 116，共 848 个题目级记录；不是 848 个独立病例。\n- 常用显式答案口径：CheX 465/618（历史整臂 M43 466/618，纠正 49 / 误改 50 / 净 -1）；SLAKE 113/114（M43 108/114，5/0/+5）；VQA-RAD 97/116（M42 100/116，4/7/-3）。M43 无独立 VQA 臂，沿用 M42 100/116。\n- CheX R47 在线 GT 468/618 为次级、不同信息条件比较器，不替换、不隐藏损失。\n- Skill 命中 505/618、0/114、0/116；同图记忆命中 130/618、84/114、58/116。SLAKE 零 Skill 命中的增益不能归因 Skill。\n- 逐数据集报告宏/微、子集、word recall、成对问题级变化与成对图像/病例簇 bootstrap 描述区间（描述性，非病人泛化、非因果）。\n- 失败与恢复历史如实：初始依赖缺失、q41 CUDA（1 次登记生产复试＋独立诊断）、120/150 两次 META schema、Embedding 400（原 body/usage 未知＋1 次充值后生产复试＋独立欠费诊断）、168 短语 EOS 策略修订、210 重复 adoption 两代表项选择。全部中间 raw1 保留，不称所有尝试 exit0。\n- 首次证据推送 628617beb 在最终结果审阅之前；最终审阅发生在全部 848 题与首次推送之后、最终报告补充推送之前；远端核验被用户豁免。\n- 资源/费用：主/元/embedding/工具分账来自保存 receipts；未知用量/费用、硬件价格、controller 总墙钟如实标 unknown；CLI 审查 USD/时长与推理 CNY 分列且非发票。\n\n## 禁止（不成立/不得主张）\n- 不得主张 Skill 单独因果、同预算 Skill 收益、闭卷/未见测试 SOTA、官方 SkeMex/Evo-MedAgent 复现、临床正确性或医学能力验证。\n- 不得把 848 题合并为独立病例总体准确率；不得忽略 SLAKE/CheX-SLAKE 共享图与 VQA 同图复述依赖。\n- 不得把首个预适配失败（manifest_semantic_input_order_changed）称第二套已完成成绩；不得把诊断输出当生产结果。\n- 不得把修复 META/embedding 子集再次加费；不得把未知用量/费用读作 0 或免费。\n- 不得声称审阅发生在首次发布之前、模型权重身份已独立鉴证、或已做字节/像素哈希/临床重读。",
  "identity_limit": "未重跑代码、未新评分/推理/导出、未远端核验、未核临床图像、未鉴权模型权重、未做字节/像素哈希；模型身份为 CLI 配置别名 deepseek-v4-pro 而非权重鉴证；17 共享图/64 匹配题与 save-before-reveal 时序、以及 CheX 49/50 全量逐条，按已存协议与已存分数采信，未逐事件独立重算。"
}
END_RESULT_CLAIM_JSON
```
