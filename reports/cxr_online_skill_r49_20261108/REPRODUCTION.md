# R49公开语义复现与实际路径

本页由完成后的实际记录生成；编写器不启动推理、评分、验证器、网络或Git。生成、评分、导出已完成时不重复运行。

## 便携公开复算

完整公开证据含原始终态、完整输入／标注、窗口快照／学习轨迹、Skill版本、逐请求工具与原图派生图。验证器从公开路径重算已冻结主指标和逐题提取；不需私有run或账户账本，0新推理、无文件／像素摘要门槛。

```powershell
python -X utf8 experiments/verify_public_online_skill_r49.py --evidence reports/cxr_online_skill_r49_20261108/evidence/chexbench --out <new-empty-verification-directory-chexbench>
```

```powershell
python -X utf8 experiments/verify_public_online_skill_r49.py --evidence reports/cxr_online_skill_r49_20261108/evidence/slake --out <new-empty-verification-directory-slake>
```

```powershell
python -X utf8 experiments/verify_public_online_skill_r49.py --evidence reports/cxr_online_skill_r49_20261108/evidence/vqarad --out <new-empty-verification-directory-vqarad>
```

## 实际私有归档与一次性离线步骤

以下路径直接来自完成组的真实score receipt；原始score output原样复用，不授权再次评分／导出或重跑旧基线。实际使用private once-wrapper，所有臂先参考无关适配再读评分标签。下列原生接口仅解释等价参数，不表示又执行了一遍评分。CheX首个前置路径失败与唯一显式接续、以及独立references来源见OFFLINE_SCORING_PROVENANCE.md。

```json
{
  "archive_root": "D:/MedRAX_Experiment_Artifacts/online_skill_r49_20261108",
  "preparation_root": "local_assets/online_skill_r49_preparation",
  "score_receipts_root": "local_assets/r49_dataset_score_receipts",
  "public_reporting_provenance_root": "C:\\Users\\cheng\\MedRAX_v9_20261030\\reports\\cxr_online_skill_r49_20261108\\deployment_source\\reporting_provenance",
  "public_recovery_root": "C:\\Users\\cheng\\MedRAX_v9_20261030\\reports\\cxr_online_skill_r49_20261108\\evidence\\recovery\\dependency_1",
  "public_cuda_recovery_root": "C:\\Users\\cheng\\MedRAX_v9_20261030\\reports\\cxr_online_skill_r49_20261108\\evidence\\recovery\\cuda_1",
  "public_meta_schema_recovery_root": "C:\\Users\\cheng\\MedRAX_v9_20261030\\reports\\cxr_online_skill_r49_20261108\\evidence\\recovery\\meta_schema_1",
  "public_mutation_fields_recovery_root": "C:\\Users\\cheng\\MedRAX_v9_20261030\\reports\\cxr_online_skill_r49_20261108\\evidence\\recovery\\mutation_fields_2",
  "public_embedding_recovery_root": "C:\\Users\\cheng\\MedRAX_v9_20261030\\reports\\cxr_online_skill_r49_20261108\\evidence\\recovery\\embedding_arrearage_1",
  "public_phrase_guard_recovery_root": "C:\\Users\\cheng\\MedRAX_v9_20261030\\reports\\cxr_online_skill_r49_20261108\\evidence\\recovery\\phrase_guard_1",
  "public_adoption_recovery_root": "C:\\Users\\cheng\\MedRAX_v9_20261030\\reports\\cxr_online_skill_r49_20261108\\evidence\\recovery\\adoption_1",
  "chexbench_data": "D:\\MedRAX_Experiment_Artifacts\\online_skill_r49_20261108\\dataset_completion\\chexbench\\source_data",
  "chexbench_references": "C:\\Users\\cheng\\MedRAX_v9_20261030\\reports\\cxr_vqa_extension\\results\\chexbench\\references.jsonl",
  "slake_data": "C:\\Users\\cheng\\MedRAX_v9_20261030\\data\\slake_cxr",
  "slake_references": "C:\\Users\\cheng\\MedRAX_v9_20261030\\data\\slake_cxr\\references.jsonl",
  "vqarad_data": "C:\\Users\\cheng\\MedRAX_v9_20261030\\data\\vqarad_cxr",
  "vqarad_references": "C:\\Users\\cheng\\MedRAX_v9_20261030\\data\\vqarad_cxr\\references.jsonl"
}
```

```powershell
python -X utf8 experiments/score_online_skill_r49.py --dataset chexbench --data "D:\MedRAX_Experiment_Artifacts\online_skill_r49_20261108\dataset_completion\chexbench\source_data" --run "D:/MedRAX_Experiment_Artifacts/online_skill_r49_20261108/generation/chexbench" --references "C:\Users\cheng\MedRAX_v9_20261030\reports\cxr_vqa_extension\results\chexbench\references.jsonl" --out <new-empty-score-directory> --r47-frozen <actual-r47-frozen> --r47-run <actual-r47-generation>
```

```powershell
python -X utf8 experiments/score_online_skill_r49.py --dataset slake --data "C:\Users\cheng\MedRAX_v9_20261030\data\slake_cxr" --run "D:/MedRAX_Experiment_Artifacts/online_skill_r49_20261108/generation/slake" --references "C:\Users\cheng\MedRAX_v9_20261030\data\slake_cxr\references.jsonl" --out <new-empty-score-directory>
```

```powershell
python -X utf8 experiments/score_online_skill_r49.py --dataset vqarad --data "C:\Users\cheng\MedRAX_v9_20261030\data\vqarad_cxr" --run "D:/MedRAX_Experiment_Artifacts/online_skill_r49_20261108/generation/vqarad" --references "C:\Users\cheng\MedRAX_v9_20261030\data\vqarad_cxr\references.jsonl" --out <new-empty-score-directory>
```

## 已发生的依赖故障与接续

首次CheX／controller原始退出1，第一题预测／事件／反馈已保存。补齐既有答案适配依赖，经实际窄范围审阅和守卫后从同一已提交前缀继续。第一题3次主请求和2工具没有重做，费用已在主表中一次计入；依赖接续在40题后遇到CUDA故障再次退出1，保留为中间失败。最终完整原runner退出0不抹去这些失败。没有技术空答、effective-exit或R48恢复。

[恢复说明](DEPENDENCY_RECOVERY.md) · [恢复树与初始原始证明](evidence/recovery/dependency_1) · [接续审阅](DEPENDENCY_REPAIR_REVIEW.md) · [实际元数据](DEPENDENCY_REPAIR_METADATA.json)

## 一次登记CUDA生产复试

GEN/failure_events的登记与原失败选择、旧坏cache、健康新cache、独立诊断和共享恢复树均保留。只有这一已关闭失败被登记一次原设置生产复试；原40个预测和第41题已有主计划不重做。旧失败另加为一个物理生产尝试，健康复试已包含活跃cache，不重复加算；debug诊断不进入生产尝试或推理上下文。不是根因修复证明。

[操作修订](CUDA_PRODUCTION_RECOVERY.md) · [实际审阅](CUDA_PRODUCTION_RECOVERY_REVIEW.md) · [元数据](CUDA_PRODUCTION_RECOVERY_METADATA.json) · [完整CUDA恢复树](evidence/recovery/cuda_1)

## 一次META schema澄清与完整恢复链

CUDA接续在120个预测／反馈、3个完整窗口后因已关闭mutation回复PATCH/c停止。保持原无效回复，独立新增一个同历史payload＋schema说明的META事件；只能原目标合法单字段PATCH或模型真实NONE，不能操作方强制NONE。旧、新META均正常计费一次，Agent／Embedding／工具均无额外修复调用。前120题／前三窗口不重跑，恢复wrapper叠加既有CUDAcache路由而不再执行其controller或生产复试。全部先前原始退出1保留，最终完成0不抹去历史失败。

[META方案](META_SCHEMA_RECOVERY_PLAN.md) · [实际META操作审阅](META_SCHEMA_RECOVERY_REVIEW.md) · [META恢复树与原始日志](evidence/recovery/meta_schema_1)

## 第二次特定事件与普通MUTATE字段提示修订

meta_schema_1在150题／4个完整窗口后遇到PATCH/content再次原始退出1，完整保留。只对这一已知闭合事件新增一份独立schema澄清回复；后续普通MUTATE增加固定原六字段提示，不增加普通事件调用，不改变历史payload或临床规则。三个流均有独立激活声明，CheX旧缓存提示按保护清单回放，SLAKE／VQA各自冷启动。不重做150题／前四窗口，不重新运行CUDA复试；新失败停止，无自动循环。旧、新费用已在META总数中一次计入。

[字段修订方案](MUTATION_FIELDS_RECOVERY_PLAN.md) · [实际操作审阅](MUTATION_FIELDS_RECOVERY_REVIEW.md) · [150题失败与完整新恢复树](evidence/recovery/mutation_fields_2)

## 已知SDK400、独立欠费诊断与一次生产Embedding恢复

原000063仅留SDK BadRequestError类别、started和失败receipt，HTTPbody／usage缺失；不制造原response，也不把后来中性诊断的Arrearage body当原错误。用户确认DashScope充值并经实际新操作审阅后，原input/model/defaultSDK参数只新增000063_arrearage_1一次，真实健康向量才可供精确身份别名。启动／最终闭合检查对这一已封存SDK400作明确登记例外，其它未知或失败仍停止。旧失败和新健康尝试均已在生产Embedding总量一次计入，单独失败欠费诊断另计且费用未知。150题／4repo／此前所有包装器保留，fields2退出1保持；Embedding接续又在168题／5repo后因MAIRA未闭合格式退出1，其controller2645757／CheX2645763的失败原样保留，不能将中间尝试改记0。

[Embedding方案](EMBEDDING_ARREARAGE_RECOVERY_PLAN.md) · [实际操作审阅](EMBEDDING_ARREARAGE_RECOVERY_REVIEW.md) · [原失败／诊断／充值证明／完整恢复树](evidence/recovery/embedding_arrearage_1)

## MAIRA格式失败与EOS生成策略修订

原第169题工具生成在13token正常EOS时留下未闭合obj，原closing token非special且根本未生成，未到max300；原parser严格拒绝。独立原设置诊断也失败，其结果不进入生产。保留原坏cache／selection、此前168题／5repo及本题已保存主计划；只登记这一已知闭合失败一次新guarded生产尝试。CheX168后全部新物理MAIRA、另两组冷启动后的全部新物理MAIRA统一在后缀obj／box未闭合时屏蔽EOS；旧健康cache／selection保留legacy。该自定义生成策略可能改变文本／坐标／耗时／正确性，不能称官方方案、原设置相同或语义无影响。没有补标签、强制box、猜阴性或解析回退；max后不完整、未正常EOS或原parser失败仍停止。新生产尝试包含在实际物理工具总量一次，原坏尝试另计一次，独立失败诊断仅单列硬件时间，0主／元／Embedding调用，不重复计算此前主费用。

[EOS守卫恢复方案](PHRASE_GROUNDING_EOS_GUARD_RECOVERY_PLAN.md) · [实际操作审阅](PHRASE_GUARD_RECOVERY_REVIEW.md) · [168题失败／独立失败诊断／完整新恢复树](evidence/recovery/phrase_guard_1) · [实际guard源码](deployment_source/r49_phrase_grounding_eos_guard_candidate.py)

phrase_guard_1又在210题／六个完整窗口后因duplicate_skill_adoption停止，controller2722301／CheX2722307原始退出1完整保留；原MAIRA守卫及所有更早恢复包装器继续保留。

## 210题采用项代表选择、唯一项提示与完成后统一审计

两个已闭合ANALYZE事件各为同一注入Skill输出两份不同step／evidence的POSITIVE项，不按完全相同重复静默删除。只各新增一次META，返回selected_duplicate_index为0或1；原完整所选项及第三个唯一项原样保留，有效列表只供assess使用。原分析、MUTATE输入、210题／六窗口、缓存请求与全部付费记录保持，不由操作方择优、不重写证据／状态。后续未缓存普通ANALYZE在原事件边界加每Skill至多一项的固定提示，原payload不改、无额外普通调用；新错误继续停。原／新META均已在总量一次计入，非附加拆分不重复加费。

用户明确选择跑完再审计，EXECUTION_AUTHORIZATION.json保留真实deferred verdict、review_completed=false和scope_complete=false，不改写为预审ready。完整848之后，同一次实际RESULT_CLAIM DeepSeek审阅涵盖adoption协议、逐请求资源账与完整结果声明，并有真实scope_complete及audit_scope结论；此处不新增另一份预执行审阅要求。

[采用项恢复方案](ADOPTION_RECOVERY_PLAN.md) · [完成后实际统一审计](RESULT_CLAIM_REVIEW.md) · [实际审计元数据](RESULT_CLAIM_METADATA.json) · [初始后审授权／210题失败／完整恢复树](evidence/recovery/adoption_1)

只有最后adoption_1 controller与三组原runner均有实际原始退出0，所有初始／中间1记录均保留；没有effective-exit、技术空答或全尝试健康的主张。

## 解释限制

848题为三个独立重置的题目流，不是848个独立病例；SLAKE同源重叠、CheX跨子集同图与VQA复述保留。历史比较不是同期无Skill反事实。线上学习可在已保存预测后读取自身标签，闭卷准确率、在线反馈准确率与JSON合规分开。最后窗口新Skill不改善本轮既有分数。

[实际结果审阅](RESULT_CLAIM_REVIEW.md) · [结果声明](CLAIMS_FROM_RESULTS.md) · [完整资源原字段](RESOURCE_SUMMARY.json)

## 用户修订后的实际发布顺序

用户后续明确要求先上传，完整已完成证据已先行推送，最终结果审阅发生在首次证据推送之后、最终报告补充推送之前。原始后审授权和原定发布前审计文字作为历史记录保留，不改写为曾经预审通过。用户另明确不需要推送后的远端核验；以实际Git推送成功和本地commit记录报告，不能称额外远端核验已完成。

[实际首次推送与发布控制记录](PUBLICATION_HISTORY.json) · [最新用户顺序／核验指示](PUBLICATION_SEQUENCE_AMENDMENT.md)

## 保存的评分尝试与原始控制记录

已记录4次原生评分函数进入、3次完整指标计算、1次适配前失败。这里没有评分调用，已保存summary／per_question全部复用。

[真实来源、首个失败／接续及公开凭证清单](OFFLINE_SCORING_PROVENANCE.md)
