# MedRAX R55 · Qwen 八工具对照

AutoDL 使用原版 CheXagent-8B，与原 11 工具方案共用三个冻结数据集。八工具方案移除了 MedRet、Reflect 和 Verify。
Qwen 主回答走百炼 Token Plan。M5 每个数据集以七个 CerebraFusionMemory 模式启动，记忆调用使用官方 DeepSeek Flash。

| 主模型 | 组别 | CheXBench | SLAKE | VQA-RAD | 总分 | 较同模型 ReAct 改对 | 改错 |
|---|---|---:|---:|---:|---:|---:|---:|
| qwen3.6-flash | ReAct | 431/618 | 94/114 | 87/116 | 612/848 | 0 | 0 |
| qwen3.6-flash | M5 | 451/618 | 108/114 | 99/116 | 658/848 | 120 | 74 |
| qwen3.7-plus | ReAct | 439/618 | 101/114 | 88/116 | 628/848 | 0 | 0 |
| qwen3.7-plus | M5 | 433/618 | 104/114 | 93/116 | 630/848 | 73 | 71 |

逐题记录含题目、选项、原图来源、模型答案、工具观察和同模型 ReAct 对照。
`summary.json` 记录原始退出、运行时间、请求用量和实际模型。Token Plan 费用以账单为准。
配对变化按同一题计算。不同方法的工具选择、调用次数与模型采样均可能影响结果。

- qwen3.6-flash ReAct · [CheXBench](flash/react/chexbench.jsonl) · [SLAKE](flash/react/slake.jsonl) · [VQA-RAD](flash/react/vqarad.jsonl)
- qwen3.6-flash M5 · [CheXBench](flash/m5/chexbench.jsonl) · [SLAKE](flash/m5/slake.jsonl) · [VQA-RAD](flash/m5/vqarad.jsonl)
- qwen3.7-plus ReAct · [CheXBench](plus/react/chexbench.jsonl) · [SLAKE](plus/react/slake.jsonl) · [VQA-RAD](plus/react/vqarad.jsonl)
- qwen3.7-plus M5 · [CheXBench](plus/m5/chexbench.jsonl) · [SLAKE](plus/m5/slake.jsonl) · [VQA-RAD](plus/m5/vqarad.jsonl)
