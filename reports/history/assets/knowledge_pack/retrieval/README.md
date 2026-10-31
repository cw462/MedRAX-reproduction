# 可运行的静态知识检索模块

这里索引 **K：有来源的医学规则/检查条件**，不索引 E 工具轨迹、实验分析、方法论文或标准答案。输出是供 Agent 核对的条件与知识，不是新增的患者事实。已实现 BM25、真实可选神经向量、RRF、任务/模态过滤、结构化条件与否定处理、父段落扩展、来源多样性及低匹配拒绝；确定性重排**不是 CrossEncoder**。

## 1. 无模型即可运行

从知识包根目录执行，Python ≥ 3.10，无额外 Python 依赖：

```bash
python retrieval/build_index.py \
  --cards knowledge/clinical_cards.jsonl \
  --source-pages knowledge/source_pages.jsonl \
  --out retrieval/index_lexical

python retrieval/retrieve.py \
  --index retrieval/index_lexical \
  --query-json retrieval/query_example.json \
  --out retrieval/result_example.json
```

这个模式明确返回 `mode: lexical_only`，没有把 TF–IDF/BM25 伪称为深度语义向量。

## 2. 真正的 CPU 神经向量混合检索

示例采用官方 `sentence-transformers/all-MiniLM-L6-v2` 的量化 ONNX 权重（约 23 MB，384 维）+ attention-mask mean pooling + L2 normalization。它是真实神经 encoder，面向英文；本包的英文知识总结适用于该演示。模型权重保存在包外 cache，不包含在分发 zip 中。首次构建需要访问模型源；之后复用 cache。

```bash
python -m pip install -r retrieval/requirements-dense.txt
python retrieval/build_index.py \
  --cards knowledge/clinical_cards.jsonl \
  --source-pages knowledge/source_pages.jsonl \
  --out retrieval/index_hybrid \
  --dense-backend onnx \
  --model-cache [private_path_omitted] \
  --allow-model-download

python retrieval/retrieve.py \
  --index retrieval/index_hybrid \
  --query-json retrieval/query_example.json \
  --model-cache [private_path_omitted] \
  --require-dense \
  --out retrieval/result_example.json
```

`--require-dense` 用于预先注册的 dense 实验组：模型不可用即报错，避免将退化运行计入 dense 结果。不加此参数时，缺依赖/权重会明确降为 `lexical_only`，原因写入 `log`。`--lexical-only` 是同索引的纯词法消融。索引构建默认失败即报错；只有显式传入 `--allow-lexical-fallback` 才允许构建退化。

另支持 `--dense-backend sentence_transformers --dense-model MODEL_ID`，需要用户环境自行具备 sentence-transformers。**MedCPT 的 query/article 双 encoder 不是可互换的单 encoder**，本脚本未实现其双塔专用接口；勿将 MiniLM 实验改名 MedCPT。BGE-M3/MedCPT 与学习式 reranker 是后续开发集消融，当前未验证其任务增益。

## 3. 查询契约

参见 `query_example.json`。调用者传：

- `question_stem`：原题题干，不拼答案、解释或候选选项全文。
- `visible_evidence`：当前图像/真实工具已提供的证据。推荐每条用 `entity, attribute, value, status, laterality, time, source`；`status` 为 `affirmed/negated/unknown`。自由文本仍保留原文否定，但不自动证明其真假。
- `candidate_hypotheses`：尚未证实的候选诊断/解释，必须单列。仅作为低权重词法提示，不进入 dense 主查询，也不能单独越过相关性门槛。
- `missing_attributes`：当前位置/时间对应/形态/测量等仍待获得的信息。
- `modality`, `task`（可多值）, `population`：已知的应用范围，未知应明确 `unknown`，不能自行补成人、CT 或影像时间点。

如果 `visible_evidence` 内误放了 `status: suspected/possible/hypothesis/uncertain` 的条目，脚本将其移入候选假设，不把它当已见事实。此过程只整理角色，**不会诊断，也不会验证图像内容本身**。输出始终有 `facts_added_by_retrieval: []`。

对于英文 encoder，应传英文题干与英文观察（保留原始病例语义及否定）；中文查询可先使用词法模式，或在开发集验证多语 encoder。脚本不暗中调用翻译模型。

## 4. 知识卡与来源

主要 schema：`knowledge_id, source_id, title, summary_zh, summary_en, keywords, modality, task_scope, required_patient_evidence, limitations, source_pages, source_file`。

兼容 `card_id/id`, `retrieval_terms_en`, `task_tags`, `required_evidence`。可选 `population`，以及严格结构化的 `applicability_conditions: [{entity, attribute, value, status}]`。只有后者能确定性核对是否冲突；自由文本所述的必需证据保持为核对清单，脚本不假装已判定其满足。`structured_conditions_satisfied` 仅表示已提供的符号条件满足；自然语言前提仍须核对。`recommendation_applicable` 在已知条件冲突时为 false，其余为 null（未完成临床适用性判定），不会仅凭匹配词和条件就宣称建议可用。

显式 `kind/card_type` 属于 methods/evaluation/dev_analysis/experience/benchmark_answer 等会排除，`split: test/validation/dev` 或 `contains_reference_answer` 也排除。构建器只接收明确指定的卡 JSONL，**不会递归扫描 PDF、实验报告、方法论文目录**。未标注污染来源的输入无法由脚本自动识别，供卡方仍须保证来源。

`source_pages.jsonl` 每行格式：

```json
{"source_id":"SOURCE_01","page":2,"text":"该PDF第2页抽取正文","source_file":"pdfs/clinical/document.pdf"}
```

页码为 **PDF 文件中的第几页，1 起算**。检索后仅在命中卡所引页中寻找相关父段及邻段，输出 `parent_passage.mode=source_page_paragraph_neighbors`。没有可用原页时明确回退 `curated_card_only_parent_unavailable`；原页抽取中完全找不到卡的标题/关键词锚点时回退 `curated_card_only_no_parent_keyword_match` 并提示核对 PDF/OCR，不拿章节标题冒充支持段落。页文本需与卡页码使用同一约定；本模块不 OCR 扫描图片。

## 5. 排序与拒绝的实际规则

1. 当前非假设信息生成 BM25 主查询；候选假设单独算低权重辅助分。
2. 明确冲突的 modality/task/population 先排除；范围未知时不假装匹配。
3. 非假设 BM25 至少命中一个实词，或真实 dense cosine 达默认 0.36 才成为候选。只靠猜测病名命中的卡拒绝。
4. BM25 与神经 cosine 的各自有效候选排名进行 RRF；词法零分不获得词法排名票，低于 dense 门槛不获得语义排名票。向量未启用时仅词法排名。
5. 按缺失属性覆盖、范围不明及结构化适用条件冲突进行小幅确定性重排。显式负证据保留在结构化查询及dense原文中；no/not等独立否定词不单独算作词法主题命中，不将规则里的疾病特征倒灌为该患者特征。
6. 融合重排分低于首位的 0.55 倍时拒绝（启动参数待开发集校准）。默认每来源最多 1 卡、至多 3 卡；不足就少返回，不用低相关卡补齐。
7. 扩展有页码的父段，限制总上下文字符；返回来源、卡 ID、全部分数组件、各路排名、拒绝理由与适用性警告。

默认阈值只是可复现的启动配置，**未在 MedRAX 上证明是最优值**。需要在训练/开发病例上校准后锁定，独立测试阶段不得再调参。源文中出现“没有某征象时……”不是简单负相关，应通过规则条件核对，不应删除所有与否定词同现的知识。

## 6. Agent 接入与实验记录

K 模块调用点放在“暂定答案/当前证据形成后，识别缺口时”。Agent 输入 `knowledge_card` 与 `parent_passage`，可据此检查已有证据或提出有理由的新工具动作。是否改变答案仍由真实当前图像/工具证据支持，来源权威不能替代病例证据。

每题保存完整 JSON 输出，汇总 `mode`、命中来源/页码、注入率、拒绝率、任务覆盖、后续工具动作、最终答案迁移和增量成本。不要只报告 recall；本实验重点是纠错数与把原正确题弄错的数同时变化。控制臂同等工具/输出预算，K-on/K-off 使用同一批病例和固定记忆；不得让 K-on 额外免费获得不可见病例信息。

## 7. 行为验证

```bash
cd retrieval
python -m unittest -v test_retrieval.py
```

六项测试覆盖：同疾病但任务不合适的干扰卡、假设单独命中时拒绝且不变成观察、负证据使条件未满足但保留教育性访问、来源去冗余、不相关/模态不合时拒绝、开发/方法材料排除和真实页父段扩展。测试是合成规则，不含开发集答案。

这些测试证明代码行为；不证明临床正确性或最终准确率提升。真实 dense 的演示结果和检索耗时另见运行生成的 JSON，不与诊断任务涨点混淆。

## 8. 已附带的真实运行文件

`index_hybrid/` 和 `index_lexical/` 均由本包59张静态卡构建；前者有真实384维向量、无模型权重。`demos/` 包含4个透明合成查询、两个检索模式的完整排名与来源结果。运行 `python retrieval/run_demos.py --model-cache YOUR_CACHE` 可重新生成。细节、实际参数及局限见 `VALIDATION_REPORT.md`。
