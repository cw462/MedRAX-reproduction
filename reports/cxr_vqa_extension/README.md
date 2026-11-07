# CheXbench 与胸片问答扩展实验

2026-11-07：全部授权生成完成或确认不适用，详见[最终完成报告](FINAL_REPORT.md)、[第二阶段](results/stage2/README.md)与[第三阶段](results/stage3/README.md)。后文保留原设计与修订记录。

第一阶段复用 SLAKE 与 VQA-RAD 已完成的 D/M/C/X，新增 O 和 M−R。CheXbench 使用 Stanford AIMI 的 gated `data.json`，按作者任务和数据源筛选 Rad-ReStruct VQA 115 题、SLAKE VQA 123 题和 OpenI Fine-Grained Reasoning 380 题。数量是筛选后的核验条件。报告以三子集等权宏平均为主，同时提供 618 题微平均。 [MedRAX 论文](https://arxiv.org/abs/2502.02673) · [CheXbench 官方发布](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [已完成的基线报告](../cxr_vqa_toolsets/results/README.md)

服务器已具备原比较运行配置和固定 MedRAX 源码。授权下载的 `data.json` 已传到服务器，其 Git blob 与固定的官方版本完全一致，筛选得到 618 题。原图准备完成后才冻结生成输入。CheXbench 的 SLAKE 子集与独立 SLAKE 114 题有 17 张解码像素完全相同的原图；这些图像上的 64 道题均匹配独立 SLAKE 的规范化题干。因此两项结果不能视为完全独立的泛化证据。 [协议](protocol.json) · [官方 commit](official_medrax_commit.txt) · [提示词差异](prompt_differences.md) · [工具部署记录](tool_deployment.json)

| 阶段 | 新增主模型调用上界 |
|---|---:|
| 第一阶段 CheXbench 六组 | 17,304 |
| 第一阶段 SLAKE 与 VQA-RAD 补 O、M−R | 3,910 |
| 第一阶段合计 | 21,214 |
| 第二阶段 M-S、M-E 的目标评测 | 6,784，另计待冻结的源学习上限 |
| H 配对的理论上界 | 4,240，按实际独立病史字段缩减 |
| Q 配对的理论上界 | 4,240，按可靠多题组覆盖缩减 |

调用上界用于排程。2026-11-07，用户撤销了这项扩展实验的金额上限，并要求移除共享账本依赖。后续费用估算直接记录在各请求的结果文件中，未知用量标记为未知。各请求的发送标记和已保存回复用于断点复用及防重复发送。原共享账本作为历史记录保留。第一阶段在新目录运行，已付费结果继续复用。新请求原始像素以内容引用归档，重放时检查完整请求字段。评分入口在生成完成后读取独立参考答案，并按可靠患者、检查或同图关系聚类。 [运行入口](../../experiments/run_cxr_vqa_extension.py) · [评分入口](../../experiments/score_cxr_vqa_extension.py)

2026-11-06，D、M、C 三组的离线检查发现，原规则把带字母的完整选项文本判成缺答。评分器现接受字母与原选项全文一致的组合写法，例如 `B. 选项全文`。有冲突的组合写法计为缺答，组合校验只读取题目选项与预测的答案字段。所有 CheXbench 组统一采用修订后的规则。报告保留原规则结果用于说明格式对分数的影响。

各组独立记录进度。初期的并行请求使用共享 SQLite 账本预留和结算，后续按上述修订使用各请求的独立费用记录。共享工具后端逐次执行。模型、提示词、输入、工具选择规则、调用上界和评分采用冻结协议。

2026-11-07，第一阶段剩余五组改为同时运行。运行检查发现专家工具所在的 GPU 1 被另一个进程占用约 11GB，最近 20 道 CheXbench O 题的工具记录中有 9 次显存不足失败。工具工作进程改用空闲的 GPU 0，并在后续工具结果中记录设备编号。已保存的预测和工具结果继续保留。

SLAKE 的 30 个同图多题组覆盖 114 题。VQA-RAD 的 36 组覆盖 94 题，另外 22 题是单题图像。独立 SLAKE、VQA-RAD 及已取得的 CheXbench 官方题目文件均无独立年龄、性别和病史字段。CheXbench 的 Q 组以原图准备完成后的同图分组为准。ChestAgentBench SkeMex tools-v2 暂作源候选，纳入、隔离和用途均以最终源清单为准。 [源数据清单](memory_source_manifest.json)
