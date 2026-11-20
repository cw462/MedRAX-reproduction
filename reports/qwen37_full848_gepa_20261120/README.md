# Qwen3.7-Plus：六组 848 题结果与 GEPA 候选回放

六组均已完成 CheXBench 618 题、SLAKE 114 题和 VQA-RAD 116 题，共 **5,088 条逐题结果**。M5 在六组中总正确数最高，为 **654/848（77.12%）**，相对 ReAct 净多答对 23 题。每组使用 Qwen3.7-Plus 和包含原版 CheXagent-8B 的 11 工具配置。

## 下载

- [六组 848 题结果包](downloads/Qwen37_six_848_results.zip)
- [GEPA 全部候选与已保存回放包](downloads/GEPA_candidates_replays_snapshot.zip)
- [848 题逐题对照 CSV](paired_results.csv) · [汇总与改对/改错统计](summary.json) · [原始发布来源](sources.json)

## 六组正式结果

改对、改错和净变化均按相同题目 ID 与参考答案，相对本表中的 ReAct 计算。

| 方法 | CheXBench | SLAKE | VQA-RAD | 总计 | 较 ReAct 改对 | 改错 | 净变化 | 逐题文件 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| M5 · CerebraFusionMemory | 454/618 | 107/114 | 93/116 | 654/848（77.12%） | 82 | 59 | +23 | [JSON](downloads/Qwen37_M5_848.json) · [原记录](arms/M5/README.md) |
| ReAct · ReAct | 440/618 | 100/114 | 91/116 | 631/848（74.41%） | 0 | 0 | +0 | [JSON](downloads/Qwen37_ReAct_848.json) · [原记录](arms/ReAct/README.md) |
| M2 · ExpeL | 450/618 | 103/114 | 90/116 | 643/848（75.83%） | 74 | 62 | +12 | [JSON](downloads/Qwen37_M2_848.json) · [原记录](arms/M2/README.md) |
| M3 · MemP | 444/618 | 106/114 | 90/116 | 640/848（75.47%） | 67 | 58 | +9 | [JSON](downloads/Qwen37_M3_848.json) · [原记录](arms/M3/README.md) |
| M7 · MobileE | 444/618 | 103/114 | 94/116 | 641/848（75.59%） | 72 | 62 | +10 | [JSON](downloads/Qwen37_M7_848.json) · [原记录](arms/M7/README.md) |
| M12 · MemEvolve EvolveR | 420/618 | 104/114 | 95/116 | 619/848（73.00%） | 68 | 80 | -12 | [JSON](downloads/Qwen37_M12_848.json) · [原记录](arms/M12/README.md) |

## GEPA 候选与回放

[候选和回放入口](gepa/README.md)覆盖 **21 次提案尝试、1,909 条已保存回放预测**，采集于北京时间 **2026-11-20 23:49:18**。最新 `GEPA_TOKEN_BUDGET` 保存了 3 次新提案、初始配置及 3 个新配置，共 1,109 条预测；早期独立 GEPA 与组合运行各保存 400 条回放。

每条回放包含实际记忆检索与注入文本、答题决策、工具结果、反馈和写入回执。候选文本、回放完成状态和已有评分分别保留，便于定位提示词、检索与写入行为的变化。

## 协议与资源

六组逐题结果按冻结题号对齐，保留其原始保存答案和正式评分。各组运行配置、模型调用、费用代理、耗时和技术恢复记录见对应 `arms/<方法>/summary.json` 与原始报告。M5 每个数据集从七条通用模式开始；M2、M3、M7、M12 分别使用 ExpeL、MemP、MobileE 和 MemEvolve EvolveR。原图沿用逐题记录中的已公开病例链接。GEPA 的数据清单、原图索引及 SLAKE 图像位于 `gepa/`。

## 已知限制

这些是不同运行条件下的同题结果；记忆组具有逐题反馈和记忆更新，ReAct 按其独立答题协议运行。运行机器、时段、API 路由与工具状态也存在差异，配对统计不单独识别记忆机制的因果效应。GEPA 使用另一套 300/100 开发划分，最新候选尚未完成验证。六组汇总保留已公开的逐题字段；完整原始请求和派生图字节保存在各实验归档。
