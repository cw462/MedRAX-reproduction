已核验核心安全组件（`run_cxr_vqa_toolsets.py`、`cxr_author_alignment.py`），结合主文件给出结论。

## 结论

**score: 8 / 10　verdict: ready**（可启动12源病例的24请求阶段）

**review_completed: true　scope_complete: true**

## 数据隔离与执行门槛（全部通过）

1. **真值揭示顺序安全**：`save()` 是原子写（temp+fsync+`os.link`，拒绝覆盖），`run` 中先 `save(prediction_path,…)` 再 `read(source_labels/…)`，且 `assert prediction_path.is_file()` 兜底——ŷ 确已落盘才读当前源真值。
2. **无开发参考泄漏**：run/prepare/deploy 均不读 `references.jsonl`；`messages()` 断言 row 无 `answer/reference/content_type`（我已核上游 `inputs.jsonl` 确无这些键，不会误触发）；deploy `stage` 断言远端无该文件，preflight 亦确认 `development_reference_not_deployed: true`。
3. **检索只 fit 可用前缀**：`retrieve` 文档仅取过去已接受 episode 的 `question+phi`，DF/query 不含 y/σ/γ；y/σ/γ 只进返回 payload，不进排序；`allowed` 按像素+同 qid 排除；`assert included_ids ≤ 前 index` 阻止未来源病例。
4. **0 工具、τ 如实空**：`terminal` 拒绝 `tool_calls/function_call`（否则 `nonterminal_reply`），`tau=[]`、`actual_tool_trajectory=[]`，无编造。
5. **不自动重试**：`max_retries=0`、`unknown_sent_no_reissue`、started/predictions 存在即停、模型 identity 不符即 raise。
6. **metric 无额外门槛**：`extract` 为共同适配器，评分仅 `m4cxr_normalize` EM；reason/observation 不参与取答。78 调用上限由 complete/文件存在断言强制。
7. **8-Yes 局限已披露**，SOURCE/REFLECTION prompt 明确禁止泛化 Yes/No、禁止 always-choose-a-label。

## 需修复（不阻断本次源阶段，但开发评分前必须处理）

- `experiments/score_cxr_episodic_feedback_r46.py`：`score()` 在同一 `--source` 目录下断言 `source/source.exitcode` 与 `source/development.exitcode` 为 `'0'`，同时断言该目录存在 `protocol.json`；而 deploy `launch` 把 exitcode 写到 `RUN/jobs/{phase}.exitcode`，`protocol.json` 在 `RUN/generation/`。两者路径不一致，开发评分会直接 AssertionError。需统一 exitcode 读取路径，或由取回脚本拷贝进 generation 目录。

## 可接受局限

- `identity_ok` 校验的是返回模型名，非服务器权重认证，如实披露即可。
- 检索 query 仅用 question（当前 case 的 pre-feedback φ 在作答前不可得，属保守设计，非缺陷）；检索为确定性 TF-IDF+灰度描述子，非临床嵌入。
- 27 题已用开发集、12 源小样本且 8/8 Yes 偏斜、负结果风险——均为如实披露项，不阻断已限定的 E 组件验证。

**说明**：ready 仅指代码能正确执行本已限定实验并保证隔离，不保证增分或临床质量。
