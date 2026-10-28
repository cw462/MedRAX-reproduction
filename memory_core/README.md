# 独立结构化规则记忆基础模块

本目录实现离线建库和冻结检索，可用标准 Python 运行，无第三方依赖，也不会导入 MedRAX、访问网络、读取密钥或调用模型。尚未接入 Agent，未运行真实建库或效果比较。

这是附文阶段 3/4 所需的一部分基础设施。当前只允许选择预设的通用适用条件、操作和风险模板，不接受自由轨迹总结。因此它不是已经完成的 R1 原始成功轨迹检索、LLM 总结器、临床经验库或步骤信用方法。所有现有测试均使用合成数据。

## 已实现的边界

- `Experience.from_dict()` 采用精确字段表，顶层和步骤评价的额外字段均被拒绝。没有答案、预测、报告、解释、身份或原始题干存储字段；条件/动作/风险只能从 `schema.py` 固定词表选择。词表内容是通用操作提醒，不是医学诊断。
- `AuditRegistry.from_split_directory()` 读取现有 `data_tools` 产出的 `manifest.json`、`audit_index.jsonl` 和三个分区的 `*.inputs.jsonl`，记录实际文件哈希并核对题目对应关系。文件哈希变化不会阻断加载；重复题目和同病例跨分区仍被拒绝。不会打开任何 `*.labels.jsonl`。`memory_train` 来源和病例对应关系由独立索引核验，不接受条目自报身份替代核验。
- 最终正确/错误是外部开发评分器提供的枚举，不能提供具体答案。默认成功池要求 `task_outcome=correct`，这个反馈不会进入检索文本或提示正文。没有配对回放或独立医学证据接口，故当前严格限定 `clinical_evidence=unknown`、`step_credit=null`；数值 `0`、`verified` 等都被拒绝。
- `evaluate_execution()` 根据调用日志的布尔/未知标志评价执行，检查工具可用、模态、参数、返回、超时及缓存。信息不足仍为 `unknown`；执行成功不会转为医学正确或正信用。调用方须从真实日志产生标志，本模块不读取原始轨迹文件来替调用方证明其真实性。
- 查询必须提供已登记的 `question_id`，从冻结索引获取当前病例。来源为同一病例的所有题目均排除；未知病例查询拒绝执行。查询也使用精确字段表，标签字段不能附带进入接口。
- 先按任务、模态、视角和实际可用工具名称过滤，再做 BM25。未知查询视角只使用 `view=unknown` 的通用规则。查询携带的版本字符串仅作记录，版本变化以及 `unknown/latest/*` 不会阻断匹配；版本内容不进入 BM25 或模型上下文。分词采用小写英文/数字词及单个汉字，无语义嵌入或自动翻译。
- 默认仅检索成功规则；失败反思需要在建库配置中显式开启。无正词汇重合或低于阈值时返回空结果，未来适配器应退回 R0。配置仅允许 Top-1/3/5；阈值等需先在验证集选择，没有声明默认值最优。
- 冻结记录、病例索引、词表、分词版本、BM25 参数及实现源文件哈希。`sha256` 每次从实际内容重新计算；没有检索计数更新或测试时写回。相同输入和快照产生确定排序。BM25 统计在过滤后的固定候选子集上计算，查询历史不会改变统计。
- `FrozenMemory.load()` 不要求预期哈希；可选的 `expected_sha256`、文件内哈希、实际内容哈希及实现源码哈希只通过 `hash_audit` 记录，不作不变性门槛。源码、配置或内容哈希变化不会使快照失效。`assert_frozen()` 为兼容旧调用而保留，只返回是否相同，不抛出阻断异常。结构、标签字段和训练病例来源检查继续生效。快照文件采用新建模式，避免覆盖已有版本。保存的快照包含审计信息，**不要将整份快照传给模型**；只用 `hit.context()` 的允许字段输出。

## 输入结构

条目字段必须恰好为以下内容。这里的标识符与哈希均为占位符，不能直接当作真实经验使用：

```python
{
    "source_split": "memory_train",
    "source_question_id": "已登记的训练问题编号",
    "source_audit_ref": "对应病例的64位小写SHA256",
    "source_trace_sha256": "源轨迹文件的64位小写SHA256",
    "task": "laterality",
    "modality": "CXR",
    "view": "unknown",
    "conditions": ["orientation_uncertain"],
    "action": "check_orientation",
    "risks": ["unknown_evidence"],
    "tool_versions": {"grounding": "实际固定版本或内容指纹"},
    "outcome_kind": "success",
    "evaluation": {
        "execution": "unknown",
        "task_outcome": "correct",
        "clinical_evidence": "unknown",
        "step_credit": None,
    },
    "memory_version": 1,
}
```

`task_outcome=correct` 只可来自 `memory_train` 的已授权开发评分。本文例子不表示任何真实题目已答对。`source_trace_sha256` 用于审计定位；本模块不会自动打开轨迹或验证某条规则确由该轨迹得出。当前注册的工具名是本模块的显式通用别名，未来与 MedRAX 实际工具名映射时须单独记录，不可默认为已经完成映射。

## 调用方式

从仓库根目录运行 Python，将已清洗并人工/规则审核的结构化条目交给模块。示意中的路径和条目对象须换成实际开发产物：

```python
from memory_core import (
    AuditRegistry, BM25Config, Experience, MemoryBuilder,
    FrozenMemory, RetrievalQuery,
)

registry = AuditRegistry.from_split_directory("/path/to/frozen-case-splits")
builder = MemoryBuilder(registry, BM25Config(top_k=3, min_score=0.1))
builder.add(Experience.from_dict(approved_training_record))
snapshot = builder.freeze()
pinned_hash = snapshot.save("/path/to/new-memory-snapshot.json")
# 将内容指纹写入本次评测记录，便于后续追溯。

memory = FrozenMemory.load("/path/to/new-memory-snapshot.json")
before = memory.sha256
query = RetrievalQuery.from_dict({
    "question_id": inference_row["question_id"],
    "text": inference_row["question"],
    "task": "laterality", "modality": "CXR", "view": "unknown",
    "available_tools": {"grounding": "实际固定版本或内容指纹"},
})
hits = memory.search(query)
safe_rule_context = [hit.context() for hit in hits]
hash_unchanged = memory.assert_frozen(before)  # 仅返回 bool，不阻断运行。
```

查询文本必须来自已隔离的推理输入；严格字段不能判断调用者是否把标签偷偷拼入允许的文本字段，仍须维持评分器与推理器的数据权限隔离。审计输入包含全分区的题目/病例对应信息，但不包含标签。外部数据的病例关联必须预先加入独立冻结索引；不能在未知病例时跳过同病例排除。

源码哈希对 Windows/Linux 换行作归一化，用于记录本次运行代码。源码或快照哈希改变后仍可加载结构有效的已有记忆；运行记录可据此识别各次使用的版本，无需为哈希变化重建记忆池。

## 离线验证

```sh
python -m unittest memory_core.test_memory_core -v
```

测试覆盖标签字段/自由文本旁路、伪造训练来源、同病例不同题、未知病例、无标签文件读取、任务/模态/视角/工具可用性过滤、版本变化兼容、未知信用、失败池开关、无重合回退、快照深度不可变、旧哈希和旧源码记录兼容、结构有效内容变更加载及查询顺序独立性。`AuditRegistry.synthetic()` 专供合成测试；建库时还需显式 `allow_synthetic=True`，快照会标记 `synthetic_fixture_only`。

## 尚未实现或证明

没有 LLM 总结、自动工具轨迹转换、真实成功经验提取、独立临床核验、步骤配对回放、候选动作执行、冲突处理、容量淘汰、语义去重或在线更新。未接入 Agent，也没有真实检索质量、费用、准确率或涨点结果。

文件哈希仅是内容指纹，不证明数据来源真实、规则适用或版本字符串可信。病例索引质量依赖上游数据；现有分区仅有病例分组及相同路径/URL 检查，不等于患者独立、图像内容去重或隐私匿名化。源码词表也是可信边界，后续修改仍需防泄漏审核。后续效果比较仍应记录各组实际使用的设置、训练来源和评测分母。
