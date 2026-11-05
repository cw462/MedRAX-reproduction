# 第一阶段提示词差异

O 直接调用固定上游版本的 `Agent.workflow.stream`，系统提示词来自上游 `medrax/docs/system_prompts.txt` 的 `MEDICAL_ASSISTANT` 段。保留原版要求对工具输出进行批判性检查的原则。用户消息统一提供原图、图号、题干、选项和最终 `answer` / `reason` 输出约定。工具使用原名和原描述，由绑定适配器调用同版本的本地工具。DICOM 工具仅接受绑定的 DICOM，八工具配置缺 RoentGen。每题新建图检查点，官方入口只传 `thread_id`。固定 LangGraph 0.2.76 实测最多 25 图步，其中 13 次 `process` 和 12 次 `execute`。模型请求与图步独立计数。

M−R 保留 M 的模型、图像绑定、原图优先检查、通用工具不可信提醒、JSON 结构、提前结束、预算和实际工具接口。逐字删去或替换以下模型可见文本。原始工具返回保存在观测文件中。

| 位置 | M | M−R |
|---|---|---|
| Agent 系统消息 | `Tool claims are unverified: inspect original pixels, do not treat classifier scores as severity, and do not infer temporal change from a single-image report.` | `Tool claims are unverified: inspect original pixels.` |
| 分类器工具菜单 | `args={}. Single original CXR finding scores, never severity or localization.` | `args={}. Single original CXR finding scores.` |
| 报告工具菜单 | `args={}. Single original CXR report; temporal claims unsupported.` | `args={}. Single original CXR report.` |
| 分类器观察的 `limitations` | `Operating-point normalized finding scores, not calibrated disease probabilities, severity, localization or temporal change.` | 仅在模型可见投影中移除该字段 |
| 报告观察的 `limitations` | `Unverified single-image report; interval statements have no prior-image evidence.` | 仅在模型可见投影中移除该字段 |
