# MedRAX R55 · 三模型八工具评测

批次 `r55_8tools_20261121_001` 在 AutoDL 完成了 11 个模型与方法组合的 33 项逐数据集评测，共有 9,328 条正式评分的预测。DeepSeek V4.1 Flash 的 M5 在三集汇总中得分最高，答对 642/848 题（75.71%），较本批同模型 ReAct 多答对 58 题（6.84 个百分点）。

9,328 行逐题数据含题目、选项、参考答案、模型答案、是否答对、ReAct 对照、工具调用名称、记录数量和证据信息。完整工具观察见各组逐题记录。[逐题 CSV](per_question.csv) · [33 组逐题记录与运行回执](cohorts/README.md)

## 跨批次逐题 CSV

合并表包含 13 个模型与方法组合的 11,024 条独立作答。Qwen3.6-Flash 的 ReAct 和 M5 来自 11 月 16 日的八工具批次，其余 11 组来自 11 月 21 日批次。两批逐题对齐后共用同一套 848 道冻结题。`source_batch` 和 `source_commit` 标记各行来源。历史 M5 逐题耗时在发布档案中缺省。[下载合并逐题 CSV](per_question_extended.csv)

## 正式成绩

表中分数为答对题数除以冻结子集的全部题数。汇总按 848 题计算。

| 主模型 | 方法 | SLAKE | VQA-RAD | CheXBench | 汇总 | 较同模型 ReAct 改对 / 改错 |
|---|---|---:|---:|---:|---:|---:|
| Qwen3.6-Flash | CRITIC | 97/114 | 92/116 | 441/618 | 630/848（74.29%） | 123 / 105 |
| Qwen3.6-Flash | Reflexion | 98/114 | 89/116 | **445/618** | 632/848（74.53%） | 59 / 39 |
| Qwen3.6-Flash | M2 | **103/114** | 90/116 | 431/618 | 624/848（73.58%） | 112 / 100 |
| Qwen3.7-Plus | CRITIC | 98/114 | 91/116 | 429/618 | 618/848（72.88%） | 73 / 83 |
| Qwen3.7-Plus | Reflexion | 101/114 | 90/116 | 439/618 | 630/848（74.29%） | 46 / 44 |
| Qwen3.7-Plus | M2 | 101/114 | 93/116 | 430/618 | 624/848（73.58%） | 69 / 73 |
| DeepSeek V4.1 Flash | ReAct | 86/114 | 93/116 | 405/618 | 584/848（68.87%） | 基线 |
| DeepSeek V4.1 Flash | CRITIC | 90/114 | 88/116 | 426/618 | 604/848（71.23%） | 86 / 66 |
| DeepSeek V4.1 Flash | Reflexion | 87/114 | 89/116 | 409/618 | 585/848（68.99%） | 57 / 56 |
| DeepSeek V4.1 Flash | M2 | 102/114 | 95/116 | 433/618 | 630/848（74.29%） | 114 / 68 |
| DeepSeek V4.1 Flash | M5 | 101/114 | **97/116** | 444/618 | **642/848（75.71%）** | 118 / 60 |

Qwen3.6-Flash M2 在 SLAKE 答对 103 题，Qwen3.6-Flash Reflexion 在 CheXBench 答对 445 题，DeepSeek V4.1 Flash M5 在 VQA-RAD 答对 97 题，分别是本批各数据集的最高分。同模型配对按数据集及题目标识计算。「改对」是 ReAct 答错而该方法答对，「改错」是 ReAct 答对而该方法答错。配对分项见[配对结果](comparisons.csv)。

## 评测协议

R55 冻结了三个数据集的入选题目、原图、参考答案和题序。每组使用相同的 114 道 SLAKE、116 道 VQA-RAD 和 618 道 CheXBench 题目，并沿用 R55 原生评分器。CheXBench 按选择题判分，SLAKE 和 VQA-RAD 按各自的原生答案规则判分。[冻结题目和图像来源](cases/) · [分组配置与回执](cohorts/README.md)

逐题索引保留数据集来源链接，并附有审核通过且可分发的原图样例。随报告提供的原图和工具派生图像均为经审核的选例。[逐题来源索引](cases/) · [派生图像索引](derived_assets.json)

Qwen3.6-Flash 和 Qwen3.7-Plus 分别通过百炼 Token Plan 请求 `qwen3.6-flash` 和 `qwen3.7-plus`。DeepSeek V4.1 Flash 通过 DeepSeek 官方 API 请求 `deepseek-flash`。33 组主模型配置均为 `temperature=0.2`、`top_p=0.95`、`max_output_tokens=2048`、`enable_thinking=false`。M2 和 M5 的记忆模型均使用 DeepSeek 官方 `deepseek-flash`，`enable_thinking` 为 `false`。六个模型工具服务在同一 AutoDL 实例常驻，独立的模型、方法和数据集任务最多三组同时运行。

| 工具标识 | 后端 |
|---|---|
| `chest_xray_expert` | Stanford CheXagent-8B 原版检查点，`chexagent` 常驻服务 |
| `llava_med_qa` | LLaVA-Med，`llava-med` 常驻服务 |
| `medgemma` | MedGemma，`medgemma` 常驻服务 |
| `llava_rad` | LLaVA-Rad，`llava-rad` 常驻服务 |
| `medvlm_r1` | MedVLM-R1，`medvlm-r1` 常驻服务 |
| `maira2_grounded_report` | MAIRA-2 定位报告，`maira` 常驻服务 |
| `xray_phrase_grounding` | MAIRA-2 短语定位，同一 `maira` 常驻服务 |
| `roi_crop` | 本地 CPU 图像裁剪 |

八工具配置从十一工具菜单中移除了 `medret`、`reflect` 和 `verify`，并关闭 Skill。Reflexion 的评估与反思由该方法本身执行。

| 方法 | 本批执行方式 |
|---|---|
| ReAct | 依据问题、原图和工具观察迭代作答。本批 DeepSeek ReAct 同时提供 DeepSeek Reflexion 的第一次试答和同模型的配对基线。 |
| CRITIC | 读取同模型、同题的冻结无工具 CoT 初答，在工具证据支持下检查和修订。 |
| Reflexion | 读取第一次试答及其交互上下文，完成评估和反思后执行第二次试答。两种 Qwen 的第一次试答来自历史同模型八工具 ReAct。 |
| M2 | 使用 ExpeL，按冻结题序检索已积累的经验并作答。每个模型和数据集从单独的记忆库开始。 |
| M5 | 使用 CerebraFusionMemory，每个数据集从七个预置模式开始，按冻结题序检索和更新记忆。 |

M2 和 M5 均先保存当前预测，再将当前题的参考答案和反馈用于更新记忆。历史 Qwen 八工具 ReAct 的三集汇总分别为 Qwen3.6-Flash 612/848 和 Qwen3.7-Plus 628/848。两种 Qwen 的逐题配对也以对应的历史 ReAct 为基线。[历史 Qwen 八工具评测](https://github.com/cw462/MedRAX-reproduction/blob/39c598862713f730c0710054e4f74e842b263531/reports/r55_autodl_qwen8_20261116/README.md)

## 运行恢复

M2 和 M5 在部分检索或记忆写入请求超时后按冻结题序续跑。恢复入口依据已保存的预测、记忆提交和 API 请求回执定位中断步骤。已落盘的模型回复用于本地恢复，缺少有效回复时重发对应请求。DeepSeek M5 的 SLAKE 和 CheXBench 都出现过检索及写入阶段的恢复。DeepSeek M2 的 SLAKE 与两种 Qwen M2 的 VQA-RAD 出现过写入阶段的恢复。Qwen3.6-Flash Reflexion 的 CheXBench 在保存 197 道题的预测后遇到图片请求被拒，校对该题 JPEG 与冻结 ReAct 输入一致后续跑。正式成绩保留了各组续跑前已保存的预测。[分组回执](cohorts/README.md)

首组启动至末组正式评分约 12 小时 47 分钟。运行回执记录了主模型 24,371 次 API 请求及 89,971,215 个已计量 token，记忆模型 6,765 次 API 请求及 3,614,351 个已计量 token。Token Plan 和记忆 API 的实际费用以服务商账单为准。[分组回执](cohorts/README.md)

## 复现与范围

复核时按冻结题序对齐逐题记录，将 `correct` 为真的条数和记录总数与正式评分核对。配对变化按 `dataset` 和 `question_id` 对齐到对应的 ReAct 试答。[结构化汇总](summary.json) · [逐题 CSV](per_question.csv) · [配对汇总 CSV](comparisons.csv)

重跑需准备相同的冻结数据、原始模型检查点、历史试答和六个常驻工具服务，并配置模型 API 访问。批次初始化、任务调度、记忆运行和原生评分的入口见复现材料。历史试答的来源及各组实际配置以分组记录为准。[批次初始化](reproduction/bin/deploy_r55.py) · [任务调度](reproduction/bin/queue_r55.py) · [记忆运行](reproduction/bin/run_qwen8_memory.py) · [原生评分](reproduction/bin/score_r55_full848_dataset.py) · [分组配置](cohorts/README.md)

结果描述本批冻结样本、模型及运行配置下的观测成绩。同模型方法之间的配对差包含实际工具选择、调用次数和模型采样的共同影响。
