# M1：Evo式病例经验与规则更新结果

**本轮是有标签预热＋在线顺序答案反馈，不是无反馈盲测，也没有医学工具/裁剪。**

| 组 | 正确/60 | 准确率 | 有效答 | 缺答 | 反馈条件 |
|---|---:|---:|---:|---:|---|
| D0 | 42/60 | 70.0% | 60 | 0 | 无记忆/无顺序反馈，历史缓存 |
| E | 35/60 | 58.3% | 60 | 0 | 独立训练标签预热＋已完成病例顺序反馈 |
| ES | 38/60 | 63.3% | 60 | 0 | 独立训练标签预热＋已完成病例顺序反馈 |

D0_to_E：合法纠正2，误改9，缺答恢复0，正确变缺答0，净变化-7。

D0_to_ES：合法纠正3，误改7，缺答恢复0，正确变缺答0，净变化-4。

E_to_ES：合法纠正4，误改1，缺答恢复0，正确变缺答0，净变化+3。

实际预热60病例，存储E=60、可注入E=56、seed S=24。正常调用预期332，实际中央请求332、技术额外0。保存费用合计3.433236 CNY，原账本保存增量3.433236 CNY；各阶段见[费用](cost_timing.json)，预热共用一次，不将完整Agent成本缩成最后一次作答费。计价假设不是供应商账单。墙钟约38.9分钟。

| 阶段 | 实际请求 | 输入tokens | 输出tokens | 保存费用CNY |
|---|---:|---:|---:|---:|
| seed_predict | 34 | 44593 | 4283 | 0.229768 |
| seed_reflect | 60 | 111815 | 24572 | 0.742124 |
| answer_E | 60 | 103342 | 8075 | 0.510268 |
| reflect_E | 59 | 94226 | 23253 | 0.655940 |
| answer_ES | 60 | 115660 | 8293 | 0.562156 |
| reflect_ES | 59 | 108044 | 25067 | 0.732980 |

共享seed构建费 0.971892 CNY；E与ES正式作答/在线反思费用分别列出，完整单组路径需加共享seed，但整个实验汇总只计seed一次。缺失结算 0 次，账本增量与已保存结算差额 0.000000 CNY，差额不补写原记录。

## 每12题事后累计

| 截至位置 | D0 | E | ES |
|---|---:|---:|---:|
| 12 | 5/12 | 5/12 | 6/12 |
| 24 | 16/24 | 14/24 | 15/24 |
| 36 | 23/36 | 20/36 | 22/36 |
| 48 | 33/48 | 26/48 | 29/48 |
| 60 | 42/60 | 35/60 | 38/60 |

最后三个12题区段为25–36、37–48、49–60，各自完整分母12；完整5区段与实际题量见metrics.json，仅在流完成后计算，未据此调参。

## 五种任务组合

| 组合 | N | D0 | E | ES |
|---|---:|---:|---:|---:|
| classification,characterization,diagnosis,reasoning | 12 | 11 | 7 | 9 |
| classification,comparison,diagnosis,reasoning | 12 | 9 | 7 | 7 |
| detection,classification,relationship,reasoning | 12 | 6 | 7 | 8 |
| detection,localization,characterization,reasoning | 12 | 8 | 6 | 6 |
| localization,comparison,relationship,reasoning | 12 | 8 | 8 | 8 |

## 七种重叠能力

| 类别 | N | D0 | E | ES |
|---|---:|---:|---:|---:|
| characterization | 24 | 19 | 13 | 15 |
| classification | 36 | 26 | 21 | 24 |
| comparison | 24 | 17 | 15 | 15 |
| detection | 24 | 14 | 13 | 14 |
| diagnosis | 24 | 20 | 14 | 16 |
| localization | 24 | 16 | 14 | 14 |
| relationship | 24 | 14 | 15 | 16 |

能力标签重叠，不能加总；总分始终60。

[实现协议](protocol.md) · [机器协议](protocol.json) · [60题与每题真实记忆/全部过程](cases/README.md) · [seed来源](seed/sources.json) · [seed E](seed/seed_E.jsonl) · [seed S](seed/seed_S.json) · [配对转换](transitions.json) · [失败与具体记忆](failure_analysis.md)

达到45/60才是相对42/60净+5个百分点，48/60才是+10。D0基线使用已发布明确Answer派生解析，旧原解析17/60未被改写。D0与M1还存在固定记忆使用提示、标签预算、反馈条件和服务时间差异；ES−E是本实现规则路径总增量，不是单条规则的因果贡献或步骤信用。

病例排除用显式case_id派生case_hash，未新增全库像素/患者身份独立性审计。当前60题已被反复使用，只跑一个固定顺序；若观察到提升，冻结后仍需独立病例和明确固定记忆/反馈协议验证泛化。两组均不超过42时，不自动在同60题调K/提示重跑。在线记忆保留在本轮namespace，未进入旧memory_train池。

生成提交`62da68410a45aaa7635f0c58223215571656906c`，旧缓存`f31d63225d776ddc4063c33c82b350a721dc4b4d`。实际服务器执行入口：`python experiments/run_evo_pipeline.py --config configs/m1_evo_memory60.json --out "$R/runs/m1_evo_memory60" --resume --api-key-stdin`，工作目录`$R/code_m1`，Python为`$R/.venv/bin/python`，MEDRAX_CODE_COMMIT取本协议。后置评分：`python experiments/score_evo_memory.py --run local_assets/m1_evo_memory60 --d0-public reports/direct_qwen60 --out reports/m1_evo_memory60`。

基准媒体来自[ChestAgentBench固定版本](https://huggingface.co/datasets/wanglab/chest-agent-bench/tree/921e60440927f9893228d843c0206b755744252a)，病例页保留Eurorad来源链接。第三方媒体沿用原来源条款，不作为本仓库代码重新授权；公开仅包含本轮明确使用的病例/图像/可观察记录，不含凭据或模型权重。

[具体纠正、误改及已知实现缺陷](outcome_interpretation.md)：本轮未达到增益目标，保留原预测，不自动调参重跑。
