# R4.4：短任务Skill没有提高本次开发集答案准确率

**完整配对结果：直接回答P0与加短Skill的P1均为21/27，77.78%；27题的显式答案全部相同，纠正0、误改0、净增0。** 两臂各27次实际请求、全部回复保存、退出0，之后才加载开发参考评分。无缺失、无工具、无JSON门槛；未达到事前“净增≥2且误改≤1”的后续优先验证条件。

这是作者SLAKE数据固定HF镜像训练／验证划分上的最小组件试验，开发27题／8图；旧CheX618、SLAKE114、VQA116及其最好整臂466/108/100完全保留。这次结果没有达到用户要求的继续涨点目标，也不支持宣称超过最好Agent、医学能力改善或官方SOTA。完整历史比较见[全部数据集／方法总表](../cxr_author_alignment_20261108/TABLES.md)。

## 同一分母与预算对照

| 方法 | 完整开发题数 | 答案EM正确数 | 准确率 | 缺失 | 新主调用／工具 | 输入／输出token | CNY费用代理 |
|---|---:|---:|---:|---:|---:|---:|---:|
| P0：一次直接回答 | 27 | 21 | 77.78% | 0 | 27／0 | 30059／56 | 0.120908 |
| P1：相同输入＋固定短Skill | 27 | 21 | 77.78% | 0 | 27／0 | 34433／56 | 0.138404 |

同一qwen3.7-plus，temperature0.2、top_p1、thinking=false、max_tokens256；每题每臂1主／0工具，配对顺序交替。P1比P0增加4374输入token和0.017496 CNY代理费用，答案未改变。总54请求、0工具／推理派生图、0重试／补答，合计0.259312 CNY代理，生成墙钟62.50秒（请求耗时总和61.29秒）。Token Plan真实消耗以提供商Credits为准，此代理不是账单或兑换金额；本地／共享服务器GPU费用没有编造。

按8个图像簇作10,000次seed0 bootstrap，两臂各自准确率95%探索区间为55.00%～93.55%，净差区间为0～0pp。因为本次全部配对答案相同，净差重采样退化为0；**这不表示真实效果没有不确定性，也不是等效性证明**。没有重复seed、独立模型快照或患者级独立性的证据。

## 答案正确率与JSON、工具故障分开

两臂均直接输出短答案，整条JSON有效数及原M两键契约合规数都为0；这不妨碍21题获得答案正确性信用。主指标复用[共同显式答案适配器](../../experiments/cxr_author_alignment.py)和M4CXR式规范化EM，辅助词集合recall均77.78%。没有从reason／参考猜答，没有随机回退，也没有格式重发。

每臂0条显式答案缺失、0条技术停止、6条与参考EM不一致。这6条均为已明确生成的答案与标签不同；不能仅凭EM把其全部称为经临床专家确认的诊断错误。下面保留原标签，不据图像印象改判。

| 题型 | 题数 | P0正确 | P1正确 |
|---|---:|---:|---:|
| Abnormality | 19 | 14 | 14 |
| Modality | 2 | 2 | 2 |
| Organ | 3 | 3 | 3 |
| Plane | 2 | 2 | 2 |
| Position | 1 | 0 | 0 |

两臂共同不一致的6题位于4张图，详见[逐题结果](results/per_question.jsonl)与[全部原图／题干／参考](../../data/slake_skill_probe_r44/manifest.json)：

| 题号 | 题干 | 数据参考 | 两臂答案 | 原图 |
|---|---|---|---|---|
| r44_validation_9885 | Are there abnormalities in this image? | Yes | no | xmlab121 |
| r44_validation_9889 | Is the lung healthy? | No | yes | xmlab121 |
| r44_validation_10290 | Is the lung abnormal? | Yes | no | xmlab351 |
| r44_validation_10292 | Can cardiomegaly be observed in this picture? | Yes | no | xmlab351 |
| r44_validation_10345 | Do the organs in the image exist in the abdomen? | No | yes | xmlab366 |
| r44_validation_10412 | Can cardiomegaly be observed in this picture? | Yes | no | xmlab391 |

这些错误分布只用于生成结束后的解释，未用于挑题、改卡或再次付费。心影大小、全肺异常与器官位置的观察是否可靠，是未来需独立检验的候选；本次没有工具或测量证据能归因于某个具体视觉机制。

## 固定来源与规则制定

来源为[BoKelvin/SLAKE固定版本](https://huggingface.co/datasets/BoKelvin/SLAKE/tree/a9083ce6c34ac3ffb17671a605962924d8a8f9e9)，CC-BY-4.0。train.json制定规则，validation.json验证。英文／X-Ray／CLOSED／Lung过滤后有454训练候选、95验证候选；排除当前全部目标队列已有xmlab身份或完全相同解码像素图像，以及验证与合格训练图像重复后，全取剩余27验证题／8图。不是按正确性挑选小样本，也不声称官方test成绩。患者／检查ID缺失，预训练是否见过这些图未知。

训练源按类别／qid的事前机械规则选12题／12图，[完整源例](../../data/slake_skill_probe_r44/source_examples.jsonl)供操作方制定候选程序。8道源异常题恰好全是Yes，已在付费前披露，不向模型传递该答案分布。短Skill区分异常、模态、器官位置、平面；其原图检查／极性程序是操作方假设，不声称自动学习或12例已证明有效。模型没有收到源例答案、开发参考、其他同图题或病史。

准备时已浏览开发题干和类别，方法发现并非严格双盲；开发参考答案仅程序隔离保存，未人工查看或上传服务器。两臂全部结束、凭证齐全且退出0后，所有54回复先完成参考无关适配，之后才打开参考。源／开发原图字节均直接取自该固定镜像，没有图像增强；发布前查阅12源图及8开发图接触表，未见姓名、病历号等私人身份文字，仅常规投照／侧别等标记。

## 审查、完整记录与决策

付费前fresh ARIS [代码／来源审阅](CODE_SOURCE_REVIEW.md)为8/10 ready；实际核对本地和已部署文件、开发参考隔离、0发送状态、输入／预算／停止／评分边界，无实际阻断。same-family/provisional、实际底层模型未知，仅许可这次最多54请求的探索性组件范围。关键未知发送测试通过；已有8项适配器及3项评分边界测试属于前次已完成对齐，未为本轮重复执行。

[事前方案](PLAN.md) · [协议](PROTOCOL.json) · [唯一Skill](SKILL.txt) · [准备检查](PREPARATION.json) · [逐请求原文／发送凭证／usage／退出记录](evidence/README.md) · [机器汇总／区间](results/summary.json) · [0付费复现](REPRODUCTION.md)。全部54请求／回复与原图引用可复核，私有config／密钥不发布；所有历史预测和用户编辑文件保持原状。fresh ARIS [结果主张判定](CLAIMS_FROM_RESULTS.md)为claim_supported=no，确认有限零收益结果可发布，未发现计分或原始证据缺陷；integrity_status=unavailable不等于专项完整性审计通过。

本轮停止推进该通用短清单，保存零收益结果，不追加采样或扩大旧目标付费队列。仍保留总报告最多三个候选方向：任务条件分流、短Skill适用性、证据纳入门槛；本轮只检验第二项的一个具体版本。下一候选可研究有可核验证据的心影／区域／器官核对，需形成新的同预算源／开发方案，再决定是否接入各数据集固定最好整臂。当前阶段仅完成最小验证，整体真实准确率改进目标仍未达成。

## 原图阅读索引

[12张源图接触表](figures/source_contact_sheet.jpg) · [8张开发图接触表](figures/development_contact_sheet.jpg)。这两张缩放拼图仅供读者和发布检查阅读，未用于模型推理；模型实际输入及公开原图仍为完整原始JPEG字节。

Publication text follows the repository Git LF normalization. Saved per-request evidence and original image bytes are copied unchanged; publication-manifest byte counts refer to Git-normalized outgoing files. Newline normalization does not alter answers, JSON values or scores.
