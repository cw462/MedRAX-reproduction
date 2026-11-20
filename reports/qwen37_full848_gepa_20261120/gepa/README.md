# GEPA 候选与回放

记录采集时间为北京时间 **2026-11-20 23:49:18**。本目录包含 21 次 GEPA 提案尝试和 1,909 条已保存回放预测。

## 候选

- [全部提案文本与处置](all_proposals.json) · [保存范围与统计](summary.json)
- `GEPA_TOKEN_BUDGET`：3 次新提案，对应求解指令、记忆写入和建议综合；4 个配置包含初始配置。
- `GEPA`：早期独立运行的 12 次提案尝试；10 次文本超过当时的长度限制，2 次请求未产出文本，实际回放保持初始配置。
- `GEPA_META`：组合运行中 GEPA 阶段的 6 次提案及该运行的已保存回放。

## 逐题回放

| 运行 | 配置 | 划分 | 已保存/计划题数 | 已有评分 | 完成状态 |
|---|---|---|---:|---:|---|
| GEPA_TOKEN_BUDGET | [4aad3606](GEPA_TOKEN_BUDGET/replays/4aad36069877835660d23b594c8d956ab18641670db0d5c98c64c8975f642f8c/candidate.json) | train | [300/300](GEPA_TOKEN_BUDGET/replays/4aad36069877835660d23b594c8d956ab18641670db0d5c98c64c8975f642f8c/train.jsonl) | 185/300 | 完整 |
| GEPA_TOKEN_BUDGET | [4aad3606](GEPA_TOKEN_BUDGET/replays/4aad36069877835660d23b594c8d956ab18641670db0d5c98c64c8975f642f8c/candidate.json) | val | [100/100](GEPA_TOKEN_BUDGET/replays/4aad36069877835660d23b594c8d956ab18641670db0d5c98c64c8975f642f8c/val.jsonl) | 65/100 | 完整 |
| GEPA_TOKEN_BUDGET | [86764350](GEPA_TOKEN_BUDGET/replays/86764350dc42db1f995b3f8b36b97eac30670993eeb5a30f7522ed61f69d8d94/candidate.json) | train | [158/300](GEPA_TOKEN_BUDGET/replays/86764350dc42db1f995b3f8b36b97eac30670993eeb5a30f7522ed61f69d8d94/train.jsonl) | 未评分 | 部分 |
| GEPA_TOKEN_BUDGET | [ac727913](GEPA_TOKEN_BUDGET/replays/ac727913ee9f3a86d4e90ee44c2eaea61ce37353de020bce1d08a937a590a0a2/candidate.json) | train | [300/300](GEPA_TOKEN_BUDGET/replays/ac727913ee9f3a86d4e90ee44c2eaea61ce37353de020bce1d08a937a590a0a2/train.jsonl) | 178/300 | 完整 |
| GEPA_TOKEN_BUDGET | [fc3496bf](GEPA_TOKEN_BUDGET/replays/fc3496bfdebf5945548270804230a379020bf724fcdab60a28264d55fd39312f/candidate.json) | train | [251/300](GEPA_TOKEN_BUDGET/replays/fc3496bfdebf5945548270804230a379020bf724fcdab60a28264d55fd39312f/train.jsonl) | 158/251 | 部分 |
| GEPA | [2ca53010](GEPA/replays/2ca530108ad33f8658c4d7322da131e6e6983419064a5b423bc8ab66b4c8585f/candidate.json) | train | [300/300](GEPA/replays/2ca530108ad33f8658c4d7322da131e6e6983419064a5b423bc8ab66b4c8585f/train.jsonl) | 184/300 | 完整 |
| GEPA | [2ca53010](GEPA/replays/2ca530108ad33f8658c4d7322da131e6e6983419064a5b423bc8ab66b4c8585f/candidate.json) | val | [100/100](GEPA/replays/2ca530108ad33f8658c4d7322da131e6e6983419064a5b423bc8ab66b4c8585f/val.jsonl) | 69/100 | 完整 |
| GEPA_META | [99102c09](GEPA_META/replays/99102c09457b4a7ae280fa2ae2116c3123cf453da5e8a087bd2944e959b68397/candidate.json) | train | [300/300](GEPA_META/replays/99102c09457b4a7ae280fa2ae2116c3123cf453da5e8a087bd2944e959b68397/train.jsonl) | 190/300 | 完整 |
| GEPA_META | [99102c09](GEPA_META/replays/99102c09457b4a7ae280fa2ae2116c3123cf453da5e8a087bd2944e959b68397/candidate.json) | val | [100/100](GEPA_META/replays/99102c09457b4a7ae280fa2ae2116c3123cf453da5e8a087bd2944e959b68397/val.jsonl) | 65/100 | 完整 |

逐题 JSONL 保留问题、选项、参考答案、预测、分步决策、工具观察、同图上下文、实际注入的记忆、写入回执和记忆版本位置。各配置目录另有候选完整文本、已保存评分、回放完成标记、评估尝试记录及最终记忆图。

## 协议与来源

开发集包含 300 道训练题与 100 道验证题，来自 Rad-ReStruct 和 SLAKE，使用八个工具。验证会从该配置的训练记忆快照继续，验证分数参与候选选择。[训练题清单](manifests/train_new.json) · [验证题清单](manifests/val_new.json) · [图像索引](images/index.json)。SLAKE 原图按 CC BY 4.0 附在 `images/slake/`；OpenI 原图链接到逐图来源页。

## 已知限制

最新运行停在搜索阶段，尚无最终选中配置和新候选验证成绩。251 题和 158 题回放为部分记录；251 题已有保存的前缀评分，158 题没有评分。工具派生图保留在逐题记录中的原始生成路径；图像索引提供原图。开发回放与六组 848 题属于不同题集和协议，不能合并为同一次测试。
