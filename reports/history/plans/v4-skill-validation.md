# Codex / DeepSeek Harness 执行计划 V4：Skill、条件分支与工具步骤信用验证

日期：2026-10-29。项目：https://github.com/cw462/MedRAX-reproduction 。

## 0. 直接执行指令

你是项目执行者。请在已有项目、模型、数据和服务器基础上，直接实现并运行本计划，交付真实方法对照结果。不要只写设计、列 TODO 或反复做环境核验后结束。

本次用户明确要求：**不把哈希、图像字节、下载完整性、账本校验、依赖环境重审等工程检查作为前置任务，不再重跑这些检查来代替方案验证。** 沿用已有可用环境和数据；正常报错可就地解决，资源真正缺失时记录具体阻塞并继续其他可完成部分。保留项目已有正常的费用记录和用户最新预算设置，不重置账本，也不要把历史100元限制自动恢复为当前限制；不要擅自扩大当前明确授权。

本计划实现独立的 Skill 驱动工具决策，不是把 Skill 接入或照搬 CXRAgent 的 EDV–Director 模块。目标是通过自己的 Skill、当前步骤评价和工具步骤信用，获得动态选择、补查、替换、局部复看与停止的能力。

先阅读本文件，再查看现有实现和本地数据路径；复用可用代码。按第10节依次真实运行，阶段完成后自动继续后续阶段，除非遇到真实权限/资源或明确预算边界。不要每个小阶段都等待用户确认。只做与实现正确性直接相关的少量测试，随后进入真实方法实验。

## 1. 实验要回答的三个问题

1. 相对当前“问题文本检索＋注入记忆去重”，**带语义信息的 Skill** 是否更有用？
2. Skill 从静态上下文变为**能执行条件分支的工具策略**后，是否改善答案和工具使用？在合适病例中加局部影像复看是否进一步改善？
3. 用**工具调用步骤贡献**筛选动作和更新 Skill，是否优于不使用步骤信用？

研究主线：真实训练轨迹 → 语义 Skill → 当前病例条件触发与动作调整 → 工具步骤配对回放 → 改进 Skill。主模型权重保持不变。

## 2. 现有结果只作历史参考

最后已核对公开版本为 `65da316`，2026-10-29 15:43。开始时只需查看本地当前实现和最新报告，不要求回退到旧版本。已有真实八工具、Qwen3-VL-Plus、29道验证题：

| 历史组 | 答对/29 | 解释 |
|---|---:|---|
| 无记忆 | 12/29 | 4例没有正常完成 |
| 原冻结检索 | 14/29 | 结构轨迹记忆 |
| 问题文本检索 | 11/29 | 改检索本身未提高 |
| 文本检索＋近重复过滤 | 15/29 | 当前小样本最好，尚非独立测试结论 |

这29题已多次用于开发，只用于原型调试和历史连续性，不再拿它们选出最好结果作为最终证据。新一轮必须在同一配置下重跑A/B，不能把历史12/29或15/29与新组不同样本直接相减。

旧编号与实际机制有差异：`memory_credit.py` 删除的是检索记忆条目，不是工具步骤；`memory_rerank.py` 改检索，不是下一动作决策；`memory_capacity.py` 是注入结果去重，不是固定容量池更新。本次用 **A/B/C/D/E** 命名，避免混淆。

## 3. 核心实验组

| 组别 | 方法 | 要检验的变化 |
|---|---|---|
| A | 当前多工具Agent，无跨病例记忆 | 共同基线 |
| B | 当前问题文本检索＋注入记忆去重 | 现有最强小样本方案，必须保留 |
| C | B＋语义Skill表示；相同候选轨迹与检索方式 | 结构事实改成有内容的操作经验 |
| D | C＋条件分支执行；局部复看可在适用状态下触发 | Skill是否实际改变动作并增加相关证据 |
| E | D＋真实工具步骤信用；冻结后指导选择/顺序 | 有贡献评价的动作是否更有效 |

C应尽量保持B检索到的来源轨迹、Top-K、纳入成功/失败的范围相同，先只改变表示。若B原来只使用成功经验，先跑 `C_success` 对齐，再另跑 `C_success_failure`；若B已纳入失败，则C同样纳入。读取实际运行配置决定，不因旧组名推测。避免把“增加失败经验”和“语义表示”两种变化混成一个因素。

D的必要拆分：
- `D_branch` = C＋条件动作调整，不用新ROI图像；
- `D_roi` = D_branch＋条件触发的全图＋ROI复看；
- 主表D默认是D_roi，但两种结果都必须报告，以拆开动作策略与新增图像信息的作用。

E与对应D使用完全相同的动作空间，只增加信用引导。若开发实验选定不采用ROI，则将D和E都设为无ROI，并记录这一开发决策，不能根据测试结果临时选择。额外 `C_roi`（无分支而固定复看）可用来评估按需复看的效率；仅在需要支持相关结论时增加。

## 4. 数据与样本安排

复用已有病例级 memory_train / validation / heldout_test，及已经确定的跨组重复排除结果，不重新分组，不重做图像审计。相同病例全部问题同组；病例ID不自动等于患者ID。

建议默认规模：

| 阶段 | 规模 | 用途 |
|---|---|---|
| 功能试跑 | 原29题中固定5题 | 看语义Skill是否生成、分支是否真正执行、图像是否真正被复看；不作效果结论 |
| 首批语义轨迹 | memory_train中60个不同病例，每例1题 | 尽快产出可运行Skill v0 |
| 正式建库 | 扩展到memory_train中120个不同病例，每例至少1题 | 覆盖成功、失败、不同题型与工具使用 |
| 工具步骤信用回放 | 其中20个训练病例，每例1个关键状态，2分支×3重复 | 估计特定工具步骤的贡献，后续可扩展 |
| 新开发验证 | validation中60个不同病例，每例1题，优先未用于此前试验的病例 | 比较A/B/C/D/E；主要比较默认3轮重复 |
| 最终独立测试 | 已有派生heldout：505题、122病例 | 冻结全部方法后，默认A/B/C/D/E各运行1轮 |

当前全部元数据约609病例；以上并非新增大量病例，也不是每个实验组使用不同病例。若符合条件的病例不足，预先明确实际样本与原因，不按答对与否替换。新验证集优先从原121个validation病例中剔除已开发使用病例后选取。题型尽量覆盖论文的检测、分类、定位、比较、关系、诊断与特征描述；多图也可进入，但须保留题目原有全部图像。首轮可沿用单图便于开发，正式验证须报告图像数分布。

官方题型标签可用时直接对齐；不存在时可基于不含答案的题干做可复核标注，并明确是后标注而非官方标签。多标签题可进入多个分项，不强迫各类计数之和等于总题数。

训练标签用于建库结果反馈；validation标签用于方法选择；heldout标签只用于评分，不进入总结器、检索、信用更新或工具决策。此为实验隔离要求，不开展新的工程审计流程。

## 5. 任务一：采集可用于语义总结的真实轨迹

### 5.1 先复用，再补跑必要样本

已有日志如果有可读取的真实问题、工具输出和动作记录，直接复用。若旧记录只有输出长度、工具名和哈希，它无法还原语义；在现有八工具配置下重新采集必要训练样本，不为“补哈希”重跑。

第一批60病例生成Skill后就开始C试跑；不等所有120病例和信用回放结束才查看首个方法结果。正式A/B/C/D/E需使用相同正式训练来源及固定Skill版本。

### 5.2 记录什么

每一步至少保存以下可见、可观察信息：
- 当前问题与任务信息需求；当前图像/区域引用；
- 实际工具名称、参数和调用位置；
- 工具输出中的相关事实、测量或位置描述；记录这是工具声明还是另有核验；
- 执行状态；当前已获得信息、缺口、可比较的矛盾；
- 下一动作及简短决策依据；最后回答与独立评分反馈。

只需保存简洁事实与动作理由，不要求模型暴露完整内部思维链。对原报告和工具声明可以结构化摘取，但不能因为该题答对就把声明全部标为医学真值。日志和当前病例内容保存在项目既有私有运行目录；Git只提交代码与脱敏汇总。

## 6. 任务二：实现语义Skill总结器（C）

### 6.1 输入与输出

输入来自memory_train的真实轨迹，以及仅表示整体成功/失败的开发反馈。先从成功轨迹生成，再加入有信息的失败轨迹；不要把纯超时无观察或没有可归纳内容的失败硬总结为医学经验。

输出字段示例（目标schema，不是假装真实Skill）：

```json
{
  "skill_id": "S001",
  "task_types": ["localization"],
  "trigger": "The question requires location but current observations contain only image-level findings.",
  "required_information": ["finding", "location_or_laterality"],
  "required_capabilities": ["visual_localization"],
  "actions": [
    {"action_id": "a1", "operation": "select_capable_tool", "capability": "visual_localization"}
  ],
  "checkpoints": ["Does the result provide location relevant to the current question?"],
  "fallbacks": [
    {"when": "no_usable_region", "operation": "ask_alternative_available_tool"},
    {"when": "conflict_unresolved", "operation": "stop_with_uncertainty"}
  ],
  "stop_conditions": ["required_information_satisfied", "no_available_action_adds_information"],
  "avoid": ["treat_image_level_classification_as_location_evidence"],
  "source_trace_ids": ["train_trace_001"],
  "evidence_status": "unverified_clinical_contribution",
  "step_credit": null
}
```

工具能力别名要映射到当前实际工具：分类、报告、视觉问答、定位、分割/测量、显示/裁剪、DICOM处理。未部署或不支持某项能力的工具不能写成实际已可用动作。

### 6.2 给总结器的任务要求

可直接作为系统提示词核心：

```text
You summarize reusable tool-use skills from observed training trajectories.
Return JSON with a concrete trigger, required information, actionable operations,
checkpoints, fallback branches, stop conditions, and provenance.
Separate observed facts, task outcomes, and hypotheses about why an action helped.
Do not copy answer letters, option-specific conclusions, identities, or the source
patient's final diagnosis as an instruction for future patients.
Do not infer medical correctness or step contribution from final correctness alone.
If a failure cause is uncertain, mark it as a hypothesis and suggest an observable check.
Write in concise English for consistency with the benchmark prompts.
```

先提炼轨迹模式，再输出可执行结构。每条Skill必须有“条件→动作→检查/后续分支”，拒绝空泛的“仔细分析/使用合适工具”。正式效果来自后续执行实验，不靠总结器自评。

### 6.3 保持C与B可比

- 初期一条训练轨迹对应一个Skill并保留来源映射，避免一边改表示一边合并数据来源；大规模融合和容量治理稍后做。
- 首先沿用B的文本检索与去重来源，C把相同来源替换成语义Skill；Top-K默认3，沿用现有1400字符注入上限，压缩渲染为trigger/action/check/fallback/stop要点。存储可完整，注入应紧凑。
- 记录B/C实际注入token；补一个B＋等长通用工具说明的控制，以区分有用Skill与更多提示文字。
- 临床经验可以描述有条件的核查步骤，但不得注入历史病人的答案或将假设包装为已验证医学规则。

验收：至少5个真实训练Skill具有不同具体触发场景及可执行动作；5题试跑中能看到Skill被检索和引用；实际输出与旧结构记忆不同。通过后继续新验证集，不停留在样例展示。

## 7. 任务三：让Skill执行条件分支，并支持局部复看（D）

### 7.1 真正执行闭环

在工具返回之后更新以下显式状态：

```text
required_information
observations
missing_information
comparable_conflicts
available_actions
active_skill / applicable_branch
remaining_calls_and_time
```

当前Agent根据状态和Skill选择以下动作之一：
- 继续当前工具链；
- 调用能补足缺口的其他工具；
- 调整参数后重试；
- 定位并对当前病例做局部影像复看；
- 信息足够后输出；
- 无法继续获得信息时停止并报告不确定。

同一发现/同一属性才比较冲突；缺少输出不是反驳，分类分数也不能凭空提供左右侧依据。步骤检查依据任务、当前图像及工具观察，不用历史Skill高分代替当前病例依据。

**实现要求：** 不是只把if/then文本放在最初prompt，也不是仅在最终回答前加一句“再想想”。必须有可观测的中间状态、触发分支、实际动作与新观察。优先在现有Agent图的model/tool节点或wrapper中增加状态与动作选择；如无法支持中途控制，新增独立执行器。若改执行框架，A/B/C也用同执行框架关闭新策略重跑，避免框架差异造成假增益。

### 7.2 ROI真正提供视觉信息

满足任务需要且当前病例定位结果可用时：
1. 依据当前病例的框或区域生成裁剪，适度保留周边上下文；
2. 将原始全图与ROI作为图像输入一起交给当前VLM，附清楚的原图坐标/方向对应；
3. 由模型基于这些图像返回补充观察；
4. 把新观察纳入当前状态，而不是直接把框当作诊断结论。

只生成裁剪文件、打印路径或把报告文字再读一遍，不算ROI视觉复看。没有可用定位/框时正常回到其他可用动作，不伪造框；不得借用历史病例的框。

为公平，ROI适配能力向A–E共同开放（例如现有显示工具的裁剪/重看接口）。如果新增独立ROI工具，所有组都具有同一工具集；重跑A/B。D的差异应是Skill决定何时使用，而不是D独占一个新工具。另记录原八工具B作为历史比较，不能把新工具带来的收益全算给记忆。

### 7.3 D的输出与验收

逐步记录trigger、observed_gap/conflict、skill_id、action、为什么该动作能提供相关信息、是否调用ROI、实际新观察、停止原因。至少展示一个自然病例或明确标注的功能样例中“观察→触发→不同工具/参数→新观察”；功能样例不能混入效果统计。

在新验证集运行C、D_branch、D_roi，分开报告正确率、错→对/对→错、额外工具和token。若某触发在样本中从未发生，标明未覆盖，不用编造成功案例证明。

## 8. 任务四：真正的工具步骤信用（E）

### 8.1 不使用旧的删记忆实验冒充步骤信用

复用旧评分/比较代码可以，但新建工具步骤回放器。删除记忆卡片衡量记忆条目；本任务操作的是一个真实工具动作及其观察。

选择20个memory_train病例，每例一个有实际意义的已发生工具动作状态；尽量覆盖定位复看、替换工具、追加VQA等。保存或重建同一可见前缀：问题、图像、已有工具观察、Skill和剩余预算。

默认分支：
- do_action：执行这个真实工具步骤，再继续统一后续策略；
- skip_action：不执行该步骤，从同一状态继续；
- alternate_action：有可用、能力相近工具时可另加替代分支，不强制所有状态都有。

每个默认分支先运行3次，记录服务随机性。API设置相同不保证输出完全可复现，重复就是为了观察波动。各分支以相同初始总剩余预算开始，工具动作本身的消耗纳入成本；不凭空给某分支额外轮次。跳过后若后续策略又调用同一工具，要记为补偿动作，不假称完成了严格删除。

### 8.2 如何形成信用

使用训练参考答案的独立评分：

`delta_step = mean(score_do_action - score_skip_or_alternate)`

同时报告费用、token、耗时和信息缺口变化。保存样本数、重复结果、适用任务、工具能力和不确定性。这个差值是给定状态和后续策略下的估计，不是精确因果真值。

执行状态、整题对错、医学证据核验、贡献估计分开：
- 没有独立医学依据时 clinical_evidence=unknown；
- 没有可靠配对结果时 step_credit=null；
- 最终正确不使每个步骤都获得正信用；
- 最终错误不使所有步骤都获得负信用。

### 8.3 E如何用信用

按“任务/触发条件＋动作能力”聚合训练回放，信用只用于候选动作排序、Skill内动作优先级和明显有害分支的降权。未知贡献采用中性处理而非负分。可用收缩估计 `n/(n+5) * delta_step` 抑制少量样本的极端权重；这是待验证默认设置，不是最佳公式。先简单实现，不把大量时间花在复杂评分器。

E与D保持相同Skill内容、工具能力和预算；仅启用训练中估计并冻结的信用权重。分别报告E是否真的改变动作、改变了几例，以及结果变化。若信用没有可用数据，明确标未完成，不把全null方案改名E。

## 9. 共同运行设置与评分

共同模型：沿用当前实际可用的 `qwen3-vl-plus`；若用户已改模型，则所有组统一。避免在方法验证过程中同时升级基础模型。

默认继承最新真实实验：工具调用上限12、模型调用上限16、图递归40、每例240秒、每请求输出上限1024、temperature0.2、top_p0.95、现有网络超时/重试方式。它们不是论文规定或已知最优，只是本轮共同配置；若局部复看需要调整，在开发阶段统一修改所有组，不把重测上限当本项目主要任务。统计附加评估调用、ROI图像输入、总结及信用回放成本。

各组相同测试病例/图像和工具库、提示主体、总调用/时间上限，允许按策略使用不同数量的调用，但必须记录真实开销。增加B+等长度说明控制；D若明显使用更多调用，再加同额外调用数量的固定策略控制，避免把更多计算全部归因于Skill。

每轮各case的组别顺序随机化或轮转，默认3个预先固定运行轮次；记录种子/轮次但不假定API支持完全确定性。报告：
- 全部预定问题的准确率，失败/超时/无效保留分母；
- 完成率、API/工具失败、相同病例共同完成子集的准确率作为辅助；
- A→B、B→C、C→D_branch、D_branch→D_roi、D→E的配对差和错→对/对→错；
- 题型分项及各项题数，不强解读小子组；
- Skill命中/采用/触发、补查/替换/ROI/停止次数；
- 单例平均调用、token、时延、费用以及训练建库和信用回放的一次性成本；
- 以case为单位的配对bootstrap 95%区间，重复轮次同时报告均值/波动；不能把同病例多题当独立样本。

主要比较B→C、C→D、D→E；不能只挑和A差异最大的一个结果。开发集多个方法选择造成的偏倚由锁定后的独立测试评价，不靠对同一29题反复运行来证明泛化。

## 10. 实施和真实运行顺序

### S0：接续代码与最小真实试跑

用约5个训练/旧开发病例做A/B/C；优先复用现有runner和脚本。仅补齐本方案所需的接口与方法测试，不重建全部环境和审计体系。看到真实Skill内容和真实调用后继续。

### S1：首批60例语义轨迹与Skill

采集有语义信息的当前工具轨迹，生成成功Skill，运行小批C；随后生成有信息的失败Skill并独立记录差异。首批结果用于开发，不等信用模块完成才启动C。

### S2：扩到正式120例，固定新的验证60例

一次选好病例并保存普通清单。扩建共用训练池；用新验证60例跑A、B、C。首次完整轮后立刻产出表格和错误分组，不只写“执行成功”。

### S3：执行分支与ROI，跑D_branch/D_roi

尽量与S2使用同一验证病例和共同工具配置；如共同工具接口改变，重跑必要的A/B/C，不混用旧配置。记录实际触发和新证据。

### S4：工具步骤信用训练与E

20状态×2分支×3重复=120次续跑起步。生成信用权重后在相同验证60例跑E，补齐A/B/C/D/E的3轮开发比较。无法回放同一前缀时实现相同输入的近似配对并清楚标记限制，不能伪造checkpoint。

### S5：锁定后跑独立heldout

固定Skill、分支和信用、共同模型与工具及评分规则；默认505题上跑A/B/C/D/E各1轮（另有D_branch分项则按需要增加）。五臂是2525题次、122个测试病例，不是2525名患者。如果当前授权资源不足，预先固定A/B/验证阶段选定的最终方案三臂共1515题次，其他组明确列后续，不能看测试结果后再挑“最终方法”。

### S6：产出真实结果和下一轮决定

给出总体、题型、成本和失败转移；列每项是否被实现、是否真实运行、是否有支持增益的证据。无增益照实报告，并根据验证错误类型决定再改什么；不得按test结果更新Skill再把同一test称独立。

## 11. 建议的新增文件与可执行入口

按当前仓库结构合理适配，避免重复造已有组件：

```text
experiments/semantic_trace.py        # 可见语义观察、动作与状态记录
experiments/skill_distill.py         # 轨迹→语义Skill，生成/修订
experiments/skill_render.py          # 紧凑Skill上下文
experiments/skill_policy.py          # 触发、缺口、动作选择与停止
experiments/roi_reinspect.py         # 当前全图+ROI实际图像复看
experiments/tool_step_replay.py      # 工具动作do/skip/alternate续跑
experiments/tool_step_credit.py      # 步骤效应聚合，区别旧memory_credit
experiments/run_skill_validation.py # 任务编排、分组、续跑、评分
configs/skill_validation_v4.yaml
reports/skill_v4_progress.md
reports/skill_v4_validation.md
reports/skill_v4_heldout.md
```

已有重要入口：`memory_agent_eval.py::initial_messages`可注入Skill；`TrackedTool.invoke`可采集真实语义输出；`run_arm`和现有图节点可承载逐步状态与分支；`memory_rerank.py`和`memory_capacity.py`可复用B；`score_memory_runs.py`和`compare_memory_arms.py`复用评分与配对。按真实代码检查具体接口，不假装新增文件已经存在。

**要求执行者新增并实现以下命令，随后实际运行：**

```bash
python experiments/run_skill_validation.py --config configs/skill_validation_v4.yaml --stage all --resume
```

`--stage all`应顺序执行S0–S6，不是只打印计划；可以提供collect、distill、validate、replay、test、report子阶段用于恢复。一次中断后只续跑未完成项，保留原失败记录，不通过挑最好一次来合并结果。

配置模板（由执行者写入项目并对接实际路径）：

```yaml
experiment: skill_method_validation_v4
central_model: qwen3-vl-plus
train_cases: 120
pilot_train_cases: 60
validation_cases: 60
prefer_unused_validation_cases: true
validation_repeats: 3
heldout_input: use_existing_505_question_input
heldout_arms: [A, B, C, D, E]
heldout_repeats: 1
arms: [A, B, C, D, E]
extra_ablations: [C_success, C_success_failure, D_branch, D_roi, B_length_control]
retrieval_top_k: 3
memory_max_chars: 1400
credit_states: 20
credit_branches: [do_action, skip_action]
credit_repeats: 3
max_tool_calls: 12
max_model_calls: 16
recursion_limit: 40
max_case_seconds: 240
max_output_tokens: 1024
temperature: 0.2
top_p: 0.95
engineering_reaudits_as_prerequisite: false
paid_budget_policy: inherit_latest_user_authorization
```

路径通过本地已有配置发现并填入；不要把模板值当作已找到数据。新增代码先用少量有意义的测试证明方法差别，再直接运行真实实验。

## 12. 时长和费用预期，只用于排程

按最新八工具约47–54秒/题/组粗算：
- 新验证60题×5核心组×1轮：约4–4.5小时；3轮约12–13.5小时；
- heldout505题×5组：约33–38小时；三组约20–23小时；
- 还需120例建库、总结器、120次步骤续跑以及额外消融，ROI和新策略可能改变耗时。

最新29题×4组内部估算约12元，简单线性外推505×5组约260元，但总结/ROI/信用回放、输入长度及服务价格会变化，这不是报价或真实账单。读取用户最新授权即可，不重新要求旧100元上限，也不擅自追加额度；遇到当前真实授权边界时保存已完成结果并说明余下具体任务。

## 13. 完成标准

满足以下才称“方法验证已跑”，无需任何新的哈希审计：
1. C有来自真实轨迹的语义Skill，不是只有工具名/输出长度；
2. D有真实中间触发与动作调整，ROI分支实际向VLM发送当前全图及区域图像；
3. E有工具动作配对回放及非空、可追溯贡献估计，不是删除记忆卡片；
4. 新验证病例有A/B/C/D/E结果与必要拆分、相同样本和完整失败分母；
5. 报告各模块贡献与成本，锁定后独立测试；未完成部分如实标注。

启动即开始S0和S1，在当前可用环境和授权内持续推进，优先产出真实实验结果。
