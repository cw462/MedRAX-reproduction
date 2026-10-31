# V12 完整 60 题结果

状态：**completed**。固定分母 **60**，顺序 B→A，共用首次读图缓存。

| 组 | 正确/固定分母 | 正确率 | 合法错答纠正 | 首答缺答恢复 | 正确→合法错答 | 正确→缺答 | 总净增益 | 排除恢复后净增益 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 首答 | 39/60 | 65.0% | — | — | — | — | — | — |
| V12-B 取证后候选 | 36/60 | 60.0% | 0 | 1 | 3 | 1 | -3 | -4 |
| V12-B 最终（含明确回退） | 36/60 | 60.0% | 0 | 1 | 4 | 0 | -3 | -4 |
| V12-A 取证后候选 | 39/60 | 65.0% | 2 | 1 | 2 | 1 | +0 | -1 |
| V12-A 最终（含明确回退） | 39/60 | 65.0% | 2 | 1 | 3 | 0 | +0 | -1 |

B−A：**-3/60**；只有 B 正确 1 题，只有 A 正确 4 题。探索性 exact McNemar p=0.375。

B 同时增加知识与经验，因此本轮不分离两者的独立贡献。固定 B→A 顺序也没有消除时段差异。

| 组 | 最终求解完成 | 最终求解正确/完整分母 | 失败后回退首答 | 回退中正确 | 仍无最终答案 |
|---|---:|---:|---:|---:|---:|
| B | 58 | 35/60 | 2 | 1 | 0 |
| A | 58 | 37/60 | 2 | 2 | 0 |

回退仅由控制器保留已有合法首答，首答不进入模型输入；回退不计作新的求解成功或首答失败恢复。候选缺答也保留在完整分母中。

## 七类重叠任务结果

| 类别 | N | 首答正确 | B 候选 | B 最终 | A 候选 | A 最终 | 最终 B−A |
|---|---:|---:|---:|---:|---:|---:|---:|
| detection | 24 | 14 | 13 | 12 | 15 | 14 | -2 |
| classification | 36 | 23 | 21 | 22 | 23 | 23 | -1 |
| localization | 24 | 16 | 15 | 14 | 16 | 16 | -2 |
| comparison | 24 | 16 | 14 | 15 | 14 | 15 | +0 |
| relationship | 24 | 16 | 14 | 14 | 15 | 14 | +0 |
| diagnosis | 24 | 16 | 15 | 16 | 16 | 17 | -1 |
| characterization | 24 | 16 | 16 | 15 | 18 | 18 | -3 |

各类可重叠，Overall 只计每题一次。

## 新增资源与耗时

| 阶段 | 终态数 | 模型调用 | 工具尝试 | 输入 token | 输出 token | 逻辑费用 CNY | 题内耗时之和(秒) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 共享首读 | 60 | 60.0 | 0.0 | 100528.0 | 70825.0 | 1.252012 | 1655.455 |
| B | 60 | 179.0 | 55.0 | 781244.0 | 111782.0 | 4.443284 | 2788.507 |
| A | 60 | 177.0 | 55.0 | 721204.0 | 113238.0 | 4.243672 | 2871.318 |
| 新增合计，首读计一次 | 180 | 416.0 | 110.0 | 1602976.0 | 295845.0 | 9.938968 | 7315.28 |

题内耗时求和不等同端到端墙钟；未知用量字段没有当成零。费用是保存的原记账口径，不是供应商账单。共享首读没有重复计入 A/B。

## V10 历史对照

| 历史组 | 正确/固定分母 |
|---|---:|
| V10 P0 | 39/60 |
| V10 V | 40/60 |
| V10 VK | 39/60 |
| V10 VKE | 40/60 |

V10 调用协议不同，以上仅作历史描述；其费用不进入本轮新增合计。

## 范围与限制

- All planned questions remain in the denominator; a missing answer is not correct.
- Initial, targeted-read candidate and final-controller answers are separate stages, each with the full planned denominator.
- On execution failure only an explicitly saved controller fallback retains the legal initial answer. It is not a new solver success or an initial-failure recovery.
- Candidate or solver answers are never synthesized by scoring; final-versus-candidate missing-answer recovery can include controller fallback and is not a new-solver recovery claim.
- Legal wrong-answer correction, initial missing-answer recovery, legal harm and correct-to-missing failure are separate.
- Seven task categories overlap; their counts/accuracies must not be summed or averaged into Overall.
- Shared first-read calls/costs are counted once; A/B resources include only their additional stages.
- Resource values use saved accounting, not a fresh ledger scan or supplier invoice.
- A/B use a common initial cache and configured equal caps, but realized call counts may differ.
- B is run before A; temporal/provider variation is not randomized away.
- The fixed sixty are a repeatedly inspected development set, not an independent blind test.
- V10 is a historical protocol comparison, not an equal-budget controlled contrast with V12.
- The separate qwen3.8-max cached adjudication experiment is outside this report.
- No prediction record is modified by scoring; labels are read only after complete generation.
