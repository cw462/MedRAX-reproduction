结论：**ready**（预执行审阅通过，第1轮）。`scope_complete` = **true**（仅授权单臂 M43-IM-GT，无 E/反思/新消融/GT 对照）。

**核查（直接读主源，非仅凭执行者声明）**
- 时序：`run_..._r47.generate` 每题先 `save_once(predictions/ARM/qid.json)` 再 `feedback_after_save`；`ReferenceVault.after_prediction` 校验 `prediction_path.is_file()`+`question_id` 一致后才读单份真值；feedback 事件存 `prediction_sha256` 绑定。评分 `validate_feedback_prefix` 复算 `created<=saved<=released` 且逐题顺序、`current_reference_available=False`。正确。
- 不可变/重启：`save_once` 用临时文件+`os.link` 原子发布，重放同值返回 False、异值抛 `immutable_artifact_changed`；`validate_resume_prefix` 允许"预测已存/反馈未写"前缀；重启不重发/不重开参考/不重写（tests 覆盖）。正确。
- 作用域与数据流：618/488/130；488 复用 frozen baseline，130 重跑；`context` 仅收 `previous_ids`+同 `image_key`+`ordinal<当前`，禁当前/未来题与标注；保留原 answer/reason/status，另加 `reference_annotation`+选项文本。正确。
- 预算/停止：C41 6/4、M 4/2（含 R43 定稿，`completion.decision` 在有余量时 `complete_once`，test 断言 3→4）；`BoundTools` 工具失败即停；主轮异常写 progress 后 raise、不写预测/反馈/重试。正确。
- 契约一致性（关键）：`run_cxr_action_r41.episode(base,row,arm,data,protocol,runtime,out,paid,tools,conditioning)` 9 位置参数与 R47 调用匹配，且以单条 `{'role':'user','content':conditioning}` 注入；`PaidCalls.call` 产出 `started.json(request_id/utc)`、`result.json(request_id/usage/settlement.charged_cny/model_returned)`、`response.json(choices[0].message)`；R47 评分 `request_evidence` 与 R45 `new_terminal` 同格式解析，`actual_request_missing_exact_prior_feedback` 复算一致。正确。
- 离线评分：先 adapt 全部 arm，再开 context/feedback/references；`exit0`+`complete_*`+618 三目录门禁；`before.sum()==466` 绑定历史口径。正确。

**model identity limits**：frozen R45 protocol（qwen3.7-plus，temp0.2/top_p0.95/thinking=false/2048 输出）；payload 用 `protocol['model']`，`PaidCalls` 以 `profile.identity_ok(raw.get('model'))` 强制返回模型一致（不符抛 `returned_model_identity_mismatch`）。`validate_frozen` 只校验 protocol 键存在与 thinking=false，不校验 temp/top_p/model 字面值（由 frozen hash 绑定）；评分层 `resource_report` 仅报告 `model_ids`、不在评分层硬失败（传输层已拦）。低风险注：评分 `utc()` 要求带时区，与 `run_cxr_vqa_toolsets` 现有时间戳约定一致，若遇 naive 时间会响亮失败而非误判。

**Memory update（供记录）**：R47 M43-IM-GT 过 round1 预执行审阅——单臂在线真值反馈、预测先落盘后开标注、不可变绑定/恢复前缀/预算/评分导出契约均经主源核实，无阻断缺陷，可进入 GPU 队列执行。
