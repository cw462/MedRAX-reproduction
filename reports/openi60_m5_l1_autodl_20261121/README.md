# OpenI60：原始 M5 与左右侧提示 L1

在同一批 60 道 OpenI 左右侧辨别题上，B0 正确 41 题，L1 正确 39 题。L1 的工具调用从 216 次降至 18 次，生成时间从 35.2 分钟降至 16.0 分钟。

| 组别 | 正确 / 总题数 | 准确率 | 主求解器调用 | 工具调用 | 工具失败 | 生成时间 |
|---|---:|---:|---:|---:|---:|---:|
| B0 · 原始 M5 | 41/60 | 68.33% | 281 | 216 | 4 | 35.2 分钟 |
| L1 · M5 + 左右侧提示 | 39/60 | 65.00% | 133 | 18 | 0 | 16.0 分钟 |

**纠正 G=9，误改 H=11，净增 −2 题，准确率差 −3.33 个百分点。** 两组共同正确 30 题，共同错误 10 题。L1 工具调用减少 91.67%，当前配置呈现准确率与调用量之间的取舍。

## 文件

- [配对摘要](paired_analysis/summary.json) · [逐题配对 CSV](paired_analysis/paired_results.csv) · [完整题号](cohort.json)
- [B0 原评分](B0/analysis/summary.json) · [L1 原评分](L1/analysis/summary.json)
- [实际协议](protocol.json) · [脱敏配置](config.public.json) · [资源与失败记录](resources.json)
- [实验代码](code/) · [代码差异](code/deployment/autodl.patch) · [AutoDL 运行命令](code/deployment/RUN_AUTODL.md)

## 记忆与干预

B0 和 L1 均使用原 M5 CerebraFusionMemory，从相同的七条通用模式开始。两组各自检索、写入和保存记忆；锁定首答后释放本题反馈，再更新记忆。唯一直接干预是在 L1 主求解器 system 末尾追加 [左右侧提示](code/prompts/L1_zh.txt)。Verify、反思与记忆模型沿用原实现。

两组在 AutoDL RTX 6000D 上并行推进，每组内部保持同一题序。六个原影像模型常驻 GPU；预测、工具缓存、反馈和可变记忆各自独立。主模型实际返回 qwen3.7-plus；Verify 返回 deepseek-v4.1-flash-1017；记忆模型返回 deepseek-v4.1-flash。

固定 seed=20261121，从 293 道候选中抽取 60 题，并保留原相对顺序。原评分器使用完整 60 题分母，失败题全部保留。414 次主求解器请求的提示与反馈审计通过，两组初始记忆语义一致。

## 纠正与误改轨迹

| 类别 | 题号 | B0 | L1 | 参考标注 |
|---|---|---|---|---|
| 纠正 | [chexbench_openi_0010](cases/chexbench_openi_0010.md) | A. right lung opacity | B | B |
| 纠正 | [chexbench_openi_0038](cases/chexbench_openi_0038.md) | A. left indwelling catheter | B | B |
| 误改 | [chexbench_openi_0042](cases/chexbench_openi_0042.md) | B. right base pulmonary atelectasis | A | B |
| 纠正 | [chexbench_openi_0060](cases/chexbench_openi_0060.md) | B. right indwelling catheter | A | A |
| 误改 | [chexbench_openi_0087](cases/chexbench_openi_0087.md) | B. right indwelling catheter | A | B |
| 误改 | [chexbench_openi_0134](cases/chexbench_openi_0134.md) | A. right indwelling catheter | B | A |
| 误改 | [chexbench_openi_0135](cases/chexbench_openi_0135.md) | A. right lower lobe pulmonary atelectasis | B | A |
| 纠正 | [chexbench_openi_0157](cases/chexbench_openi_0157.md) | A. small right pleural effusion | B | B |
| 纠正 | [chexbench_openi_0159](cases/chexbench_openi_0159.md) | B. small right pleural effusion | A | A |
| 误改 | [chexbench_openi_0167](cases/chexbench_openi_0167.md) | B. right abdominal calcinosis | A | B |
| 纠正 | [chexbench_openi_0175](cases/chexbench_openi_0175.md) | B. surgical instruments in the left abdomen | A | A |
| 误改 | [chexbench_openi_0176](cases/chexbench_openi_0176.md) | B. right indwelling catheter | A | B |
| 误改 | [chexbench_openi_0178](cases/chexbench_openi_0178.md) | B. right upper lobe pulmonary atelectasis | A | B |
| 误改 | [chexbench_openi_0189](cases/chexbench_openi_0189.md) | B. right indwelling catheter | A | B |
| 纠正 | [chexbench_openi_0201](cases/chexbench_openi_0201.md) | None | A. small right pleural effusion | A |
| 误改 | [chexbench_openi_0221](cases/chexbench_openi_0221.md) | A. left indwelling catheter | B | A |
| 误改 | [chexbench_openi_0222](cases/chexbench_openi_0222.md) | A. small right pleural effusion | B | A |
| 纠正 | [chexbench_openi_0235](cases/chexbench_openi_0235.md) | B. small left pleural effusion | A | A |
| 纠正 | [chexbench_openi_0236](cases/chexbench_openi_0236.md) | A. right base pulmonary atelectasis | B | B |
| 误改 | [chexbench_openi_0241](cases/chexbench_openi_0241.md) | A. small right pleural effusion | B | A |

每题页面含原图、完整选项、两组主模型回复、工具观察，以及步骤、首答、反馈和记忆检索的原始文件链接。B0/L1 目录保存全部 60 题轨迹；data 保存原图及无标签输入。

## 调用与 token

| 组别 | API 调用总数 | 记忆调用 | 总 token |
|---|---:|---:|---:|
| B0 | 488 | 160 | 1,717,689 |
| L1 | 294 | 158 | 436,204 |

API 调用含主求解器、反思/检索合成、Verify 与记忆模型；GPU 工具执行另计。token 为实际返回 usage，记忆 token 已纳入。

## 已知问题与限制

B0 有两次 MAIRA 后端失败和两次 Verify 输出长度耗尽，均保留原始日志和计分。L1 无工具失败。服务方 Credits、实际账单和 GPU 租赁费用未核实；原日志中的 CNY 代理记账不作为实际费用。

本轮为单个在线记忆流的开发试验，衡量提示及后续记忆轨迹的总影响。跨题依赖不支持直接套用 iid 显著性结论；结果不代表未见测试或临床收益。病例隔离使用已有标识，未证明患者独立。

## 数据与源码来源

- [CheXBench](https://huggingface.co/datasets/StanfordAIMI/chexbench) 的 OpenI 子集；原图文件名及来源记录保存在 data/inputs.jsonl。
- [原 M5 源码与接口来源](code/SOURCES.md)。原模型权重不在本报告中。
