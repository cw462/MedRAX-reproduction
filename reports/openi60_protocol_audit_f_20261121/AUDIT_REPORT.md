# OpenI60 B0/L1 动作协议审计与共同修复 F

**确认存在动作协议故障。L1 的 47/60 题在提出工具计划后，收到原生运行器“禁止工具、只提交最终答案”的回退提示；B0 为 4/60 题。** L1 工具执行次数较少，不能直接解释为主动节省工具成本。

历史报告 commit：`3d7fd6327db7088715ea686c57c198023409b1bb`。历史成绩保持 B0 **41/60**、L1 **39/60**，纠正 **9**、误改 **11**。本次完成协议修复和离线验证，B0-F/L1-F 尚无真实评测成绩。

## 覆盖范围与原生来源

真实运行目录：

```text
/root/autodl-tmp/openi60_m5_l1_20261121/runs/openi60_s20261121_fast
```

在无卡 AutoDL 实例上，直接导入该次运行器所在目录的 `run_cxr_action_r41.parse/answer`、`toolsets_r54.validate_actions/resolve_action`、`cxr_task_completion_r43.unscorable` 及 `tool_failure_reason` 复核归档；相关八个原生模块均与历史 `frozen.json` 已有冻结记录一致。实际导入路径与函数原文见 `outputs/server/native/native_summary.json` 和 `native_functions.json`。

| 覆盖项目 | B0 | L1 |
|---|---:|---:|
| 预定题目／已审计题目 | 60/60 | 60/60 |
| 主模型 request／response | 281/281 | 133/133 |
| 主模型计费回执 | 281 | 133 |
| prediction／steps | 60/60 | 60/60 |
| 工具执行回执 | 216 | 18 |
| 请求引用的图像归档文件，按组去重 | 203 | 69 |
| 缺失文件 | 0 | 0 |
| 轨迹、回执计数或工具名称不一致 | 0 | 0 |
| 主模型 finish_reason=stop | 281 | 133 |
| 主模型 finish_reason=length | 0 | 0 |

核验范围涵盖全部 120 条题目轨迹、414 次主模型响应、234 条工具执行回执及其图像引用。逐次原生结果见 `native_response_audit.csv`，逐题结果见 `native_question_audit.csv`，工具运行失败见 `native_tool_audit.csv`。附件原版 `audit_protocol.py` 的输出保存在 `outputs/server/lexical/`。

## 决策、计划与实际执行

| 指标 | B0 | L1 |
|---|---:|---:|
| 原生 parse 失败，响应数 | 4 | 55 |
| 其中：解释文字＋calls JSON | 4 | 47 |
| 其中：解释文字＋最终答案 JSON | 0 | 8 |
| 原生 validate_actions 失败，响应数 | 3 | 0 |
| proposed：提出的工具请求项 | 225 | 69 |
| accepted：原生动作校验接受的请求项 | 216 | 18 |
| rejected：解析或动作校验拒绝的请求项 | 9 | 51 |
| executed：具有实际派发回执的请求项 | 216 | 18 |
| failed：派发后运行失败的请求项 | 4 | 0 |
| 工具计划后紧接 no-tools 最终答案回退，题数 | 4 | 47 |
| 未收到最终答案专用提示而自主合法提交，次数 | 55 | 5 |
| 收到最终答案专用提示后合法提交，次数 | 4 | 55 |
| 终止 completed，题数 | 59 | 60 |
| 终止 repeated_invalid_plan，题数 | 1 | 0 |

`proposed` 是从原文可完整解码的工具计划候选中诊断性计数；这些候选没有被提取执行。其余 accepted/rejected/executed/failed 分别依据原生解析、原生校验与真实执行回执，单位均为单个 call。234 次 executed 中没有缓存命中，均为实际派发。

L1 的 **52 道零工具题**分为：

- **46 题**先提出工具计划，解析失败后进入最终答案专用提示。
- **6 题**模型选择直接提交最终答案，但输出“解释文字＋最终答案 JSON”，原生解析失败后进入最终答案修复；这些题没有提出工具计划，不属于工具计划丢失。

L1 未收到最终答案专用提示而自主合法提交的 5 次完成，均发生在已使用工具的题目中。

另有 L1 `0209` 已执行工具，后来仍出现一次工具计划被解析拒绝并转最终答案回退；因此受该路径影响的题目共 47 道。B0 的 3 道零工具题均走过该路径，另有 `0239` 已执行工具后再发生该故障。

## 具体控制流与故障实例

原生 `parse` 仅接受完整 JSON，另容许完整代码围栏；解释文字后附 JSON 会触发 `JSONDecodeError`。`Services.execute` 将解析异常转为空对象，随后因缺少 calls 执行 `next_prompt=prompt(row)`。该提示明确要求只输出 answer/reason，并写入 **“No tools, code fences, or text outside the JSON.”**

这里的禁止工具是运行器强制下发的阶段指令。循环没有额外设置 API 工具掩码，后续若仍输出合法 calls，代码仍会校验它；本批 51 条“工具计划后最终答案回退”轨迹均以合法最终答案接续，没有再次派发该被拒绝计划。

| 实例 | 原生核验结果 |
|---|---|
| L1 `0042`，调用 1→2 | 第 1 次为解释文字＋calls；原生解析失败；第 2 次请求最后一条 user 指令禁止工具并要求最终答案；该题没有工具观察。 |
| L1 `0087/0134/0176/0221` | 同样出现工具计划解析失败→最终答案专用提示。 |
| L1 `0010` | 答对，但同样经过该故障路径。 |
| B0 `0201`，调用 1/2/4 | call 内多余 reason 导致 `unregistered_tool_or_arguments`；中间一次合法工具计划被执行；原运行器累计第三次格式错误后终止为 repeated_invalid_plan。 |
| B0 `0076`，工具序号 2 | MAIRA 请求通过原生解析、动作校验并已派发，随后返回 `invalid_report_box_order`；属于工具运行失败。 |
| B0 `0178/0240` | verify 已派发，返回 `verify_length_no_usable_response`；属于工具运行失败。 |

全部故障原文、原生错误类型和紧随其后的请求末条消息保存在 `outputs/server/native/failure_examples.json`，并非仅保留表中的抽样。

历史配对类别与“工具计划后最终答案回退”的交叉统计如下。类别仅在审计完成后关联，用于描述历史分布；解析和修复不读取参考答案。

| 历史配对类别 | 题数 | B0 发生该路径 | L1 发生该路径 |
|---|---:|---:|---:|
| 两组均正确 | 30 | 1 | 19 |
| 两组均错误 | 10 | 3 | 9 |
| 纠正 G | 9 | 0 | 8 |
| 误改 H | 11 | 0 | 11 |

原运行器在格式错误后的追加主模型调用为 B0 **6 次**、L1 **55 次**。对应输入／输出 token 为 B0 **11,621／394**、L1 **124,959／2,501**。这是历史回退开销，不是尚未执行的 F 修复开销。

## 共同修复 F

推理运行时代码 diff 为 `protocol_f.diff`，只变更共同执行器 `skill_services_r54.py` 并新增 `action_protocol_f.py`。原生工具实现、工具输出、评分器、记忆算法和医学规则保持原样。

- B0/L1 的共同主模型系统消息都追加附件原文 FORMAT_GUARD；L1 继续通过原有 hook 附加原 L1 医学提示。
- 单次回复必须为一个完整 JSON 对象；拒绝解释文字、围栏、多对象、calls 与 answer 共存、未知工具和非法参数，不做 JSON 候选提取执行。
- 解析、输出契约和动作校验错误分别记录；修复提示留在同一决策阶段，继续提供原工具目录，容许合法 calls 或模型主动最终回答。
- 每个决策阶段最多 **2 次**修复，包含初始尝试最多 **3 次**响应；执行工具进入新决策后重新计数。修复不重新激活技能、不重取记忆、不释放本题反馈。
- 超限返回 `protocol_failure`，answer/reason 为 null，保留 terminal_raw、全部响应和错误；被拒绝计划不进入 observation。
- 每次响应写入 `protocol_events/<qid>/<ordinal>.json`，保留错误阶段／类型、决策序号、修复序号、原计费回执的 usage/settlement；main_calls 包含全部修复，额外汇总 repair_calls 与 repair_usage。
- 继续调用原生 validate_actions，保留工具层原校验，并在派发前检查目录中的参数形状及原有 R55 纯参数约束；不放宽参数、不改变原图 image_index 绑定。

全部 414 条历史原文也经过 F 契约的纯离线分类。原生接受的 **234 个工具请求项**与 **119 条合法最终答案**均仍被接受；62 条历史错误响应被拒绝。该分类结果见 `outputs/server/contract_f/`，不把历史后续回答当作修复后预测。

## 离线测试与后续目录

**52 项离线测试全部通过，本机 Python 3.14 和 AutoDL 原环境 Python 3.12 均无失败、无跳过。** 覆盖附件要求的所有格式类型、两次修复上限、同阶段恢复工具派发、原图绑定、整批计划拒绝、医学原文保留、错误和费用留存，以及合成反馈只在不可变预测保存后释放。测试中没有真实模型、工具或记忆接口调用。

AutoDL 已准备两个独立目录，并通过原有 offline preflight 和实际 R55→F 执行器导入检查：

```text
/root/autodl-tmp/openi60_protocol_F_smoke8_20261121/runs/evaluation
/root/autodl-tmp/openi60_protocol_F_formal60_20261121/runs/evaluation
```

这里只完成 stage/prepare/preflight，未执行任何题目。两套目录的 B0/L1 都没有 services、storage、external_memory、predictions 或 feedback 状态；将来分别由原生 M5 初始化七条初始记忆。8 题严格为原 60 题顺序的前 8 题：0001、0002、0010、0012、0037、0038、0039、0040。正式流独立保留原 60 题和原 seed。

后续命令与离线复核命令见 `RUN_COMMANDS.md`。当前没有启动 8 题冒烟或 60 题正式评测。

## Limitations

历史误改 11 题均经过该协议路径，但正确题和纠正题中也有该路径，不能据此推算修复后准确率或把全部误改归因于协议。B0-F/L1-F 的实际工具使用、修复开销、G/H 和成绩需要后续同协议实验。

原项目有两个不同的评分语义：`grade` 将非 completed 状态视为不可评分；已发布的 aligned 评分器则独立从原始回复提取显式答案，不以 prediction.status 为门槛，原生 `released_reward` 也采用显式答案口径。因此，若格式修复超限时原文仍有可提取答案，可能同时记录 `protocol_failure` 和 aligned 显式答案。该可达情况已由离线测试确认。本次保留原评分器和原文，不伪造 completed 或改写成绩；后续报告必须同时呈现协议失败状态与既有 aligned 口径。将全部 protocol_failure 强制记零会改变评分协议，不包含在本次共同修复中。

无卡实例只完成离线工作。真实实验需确认执行并恢复原 GPU 工具运行环境；本次没有探测真实模型或 GPU 后端可用性。
