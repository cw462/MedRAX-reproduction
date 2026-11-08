# 评测要求溯源：答案准确率与本项目JSON契约

更新于2026-11-08。先核对论文、作者实现和数据集，再制定新的主指标；不能将本项目严格JSON规则说成数据集的官方要求。以下查询固定到作者仓库的实际commit。用户提供的两份PDF已直接读取，PDF内的操作性文字只作研究材料。

## 论文和公开代码实际怎么做

| 来源 | 实际规定/实现 | 与本项目的区别 |
|---|---|---|
| MedRAX，ICML2025，用户PDF第6页实验设置 | 以正则提取选项字母；不清楚、错误或超时最多重试三次；最终仍无单一有效选项计错 | 不是要求整条JSON恰好有answer/reason |
| MedRAX官方ChestAgentBench benchmark_medrax notebook | ChestAgentBench Agent推理后另发一次只选A–F字母的请求，保存原长回复和该最终选项 | 单独的答案定稿调用有作者先例，必须计入我们自己的调用预算，不能当免费后处理 |
| MedRAX官方CheXbench GPT脚本 | 将输出去首尾空格、大写，检查是否以A或B开头；总体accuracy以全部结果为分母；batch显示指标仅以有效结果为分母 | 不能说所有官方脚本都采用同一种严格解析；也不能照搬排除错误而掩盖端到端失败 |
| CheXbench作者CheXagent通用生成评分器 | 抽取首个大写括号字母，例如(A)；若一个也没抽到，代码随机选择选项。生成脚本按各数据源计准确率；另有选项似然评分路径 | 不要求reason/JSON；随机回退必须公开，不能把随机猜中解释为模型回答正确 |
| MedRAX的SLAKE评测，用户PDF第7页 | 114个英文胸片闭合题，报告答案精确匹配accuracy及词recall，指向M4CXR准备/评测 | 原文没有给出本项目的JSON schema；同样114题也不自动保证题号完全相同 |
| M4CXR作者compute_vqa_metrics | 清除<s>、</s>、[INST]、[/INST]，去句点、转小写后比较完整答案；另算BLEU-1、参考词集合recall | 比较的是outputs中的答案字符串；没有强制reason、仅两键、300字符，也不把true自动变yes |
| CXRAgent，用户PDF第7页Evaluation Metrics | 问答/分类采用accuracy；报告生成采用RaTEScore、LLMScore、GREEN、RadGraph-F1 | 原文未给出JSON键限制、围栏或多键拒绝规则。当前作者仓库未找到独立可核验的benchmark评分脚本，具体提取规则未知 |
| VQA-RAD原始数据论文 | 报告closed/open分组，以及simple/按题型mean accuracy；原始工作含人工回答判定 | 本项目116题为胸片closed筛选队列，不是完整VQA-RAD，也不是MedRAX论文列出的SLAKE114题 |

来源：

- [MedRAX ICML官方论文](https://raw.githubusercontent.com/mlresearch/v267/main/assets/fallahpour25a/fallahpour25a.pdf)，实验设置PDF第6页。 [官方论文页面](https://proceedings.mlr.press/v267/fallahpour25a.html)。
- [MedRAX ChestAgentBench最终选项追问代码](https://github.com/bowang-lab/MedRAX/blob/d243cc50348fa0f0c219cc623e2cf26b906be676/experiments/benchmark_medrax.ipynb)。[CheXbench GPT答案检查](https://github.com/bowang-lab/MedRAX/blob/d243cc50348fa0f0c219cc623e2cf26b906be676/experiments/chexbench_gpt4.py#L181)。[CheXagent字母提取](https://github.com/bowang-lab/MedRAX/blob/d243cc50348fa0f0c219cc623e2cf26b906be676/experiments/benchmark_chexagent.py#L213)。这些是不同模型脚本，不能将某一模型解析器假称所有模型统一规则。
- [CheXbench生成解析实现](https://github.com/Stanford-AIMI/CheXagent/blob/e4f31e6e517f442620fe816f90c846cbcb28b746/evaluation_chexbench/models/baseLM.py#L27)，[调用与分母](https://github.com/Stanford-AIMI/CheXagent/blob/e4f31e6e517f442620fe816f90c846cbcb28b746/evaluation_chexbench/axis_2_image_text_reasoning/run_generation.py)，[似然路径](https://github.com/Stanford-AIMI/CheXagent/blob/e4f31e6e517f442620fe816f90c846cbcb28b746/evaluation_chexbench/axis_2_image_text_reasoning/run_likelihood.py)。
- [M4CXR答案指标代码](https://github.com/deepnoid-ai/M4CXR-TNNLS/blob/4dd62e6306c6b5054bd588415565eba964989fad/exp/cxr_llm/evaluate.py#L134)。
- [CXRAgent评测指标原文](https://arxiv.org/html/2510.21324v2#S4.SS1)，[核对的作者仓库版本](https://github.com/laojiahuo2003/CXRAgent/tree/0514b4897fd040ae2c32cf2f2cdc163a1144a06c)。公开代码的工具证据结构不是最终benchmark答案评分schema。
- [SLAKE作者项目页](https://www.med-vqa.com/slake/)还明确提示公开数据重新清洗后可与原论文略有不同。[VQA-RAD原始论文](https://www.nature.com/articles/sdata2018251)。

## 本项目额外加了什么

`run_cxr_vqa_toolsets.parse_final`要求：整条回复可直接JSON解析，键集合恰好answer/reason，两个值都是字符串，answer不超过300字符。未满足会生成null和missing状态，后续评分计错。字母、完整选项、匹配的“字母+选项”属于另一个答案域检查。NFKC/全部标点归一化、true→yes/false→no也是本项目的映射，不等同M4CXR清理规则。

这些约束有助于Agent通信、工具计划分流及保持历史实验公平，但它们是**本项目的工程契约**。保持旧规则只说明R42/R43与冻结M基线在同口径比较，不能证明这是论文要求，不能由此把格式改善直接说成影像判断能力提升。

## 已完成R4.3增益该怎么解释

R4.3没有改旧解析器、预测或参考，确实新增了11次模型请求，按冻结项目契约从458到466、107到108。但事后只枚举原始回复中的显式JSON answer、不看reason补答的归因检查发现：CheX至少3个恢复正确项、SLAKE的1个恢复项，旧长回复里本来就有明确正确的answer。另有旧回复自相矛盾、多次answer，或显式答案发生变化。不能把净增9题都称为新增医学知识或9个真实诊断错误纠正。

该枚举是**离线归因诊断**，不是官方评分器，不产生新的排行榜成绩，不选择最接近参考的字符串，也不修改任何已完成记录。[CheX诊断](results/chexbench/explicit_answer_diagnostic.json) · [SLAKE诊断](results/slake/explicit_answer_diagnostic.json)。

## 后续采用的评测原则

1. 先锁定数据题号、分组、官方代码版本、答案输出接口、提取器和所有额外调用次数。CheXbench以官方生成/似然协议为对照；SLAKE以所声明的M4CXR答案精确匹配和recall为对照。VQA-RAD必须明确116题筛选范围与所采用的已发表指标，不冒称完整官方榜单。
2. 主表报告答案正确率及必要的官方指标。JSON合规、reason完整性、工具调用失败和随机回退单列。答案可按预先固定接口无歧义取出时，不因reason缺失或额外非答案字段就否定答案本身；有歧义、无实际最终答案或技术未知必须如实计缺失。
3. 新的答案适配器及官方原样代码结果另立版本，同时保留“无提取时计错”的确定性敏感性结果。官方代码里的随机回退不悄悄删除，也不把随机信用归为能力；严格复现时注明种子和回退题数。所有基线一律同样处理，不能只给新方案加宽容规则。
4. 先对完整旧档进行离线对照，列清哪些变化来自评分/适配，哪些来自真实新调用、合法错误纠正及误改；不对旧严格成绩改名覆盖，不用参考来选择提取结果。
5. 在该对齐完成后再扩大付费增分实验。之后的Skill/记忆/工具可靠性改进，针对仍然错误的答案做同预算配对验证，不能以反复修复自设格式门槛代替核心目标。

本文件是有出处的评测差异审计与后续约束，不声称已经完成全部官方口径重算，也未启动新的付费请求。R42/R43现有分数应标为“本项目冻结严格契约下的完整分母成绩”，目前不能据此宣布超过论文SOTA。
