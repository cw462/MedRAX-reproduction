# 逐轮保留记录与执行配置

本表直接读历史 manifest、终态记录和原评分 sidecar。正确数另与已完成后的参考选项联结；两者分别保存在 runs.json。partial 表示当时保存的状态未完成，不能作为整轮成绩。费用只加总终态中原有结算字段，不读取账本；中断重试可能不全在终态，且这些值不是供应商账单。

| 运行 | 完整状态 | 臂 | 终态/计划题数 | 正确 | 合法选项 | 模型/工具调用 | 终态记账 CNY |
|---|---|---|---|---:|---:|---|---:|
| [diagnostic50_v1](records/diagnostic50_v1/manifest.json) | complete | agent | 50/50 | 24 | 49 | 149/49 | 8.26716 |
| [diagnostic50_v1](records/diagnostic50_v1/manifest.json) | complete | direct | 50/50 | 24 | 50 | 100/0 | 3.15254 |
| [length_cap1024_v1](records/length_cap1024_v1/manifest.json) | complete | agent | 10/10 | 6 | 10 | 30/10 | 1.17570 |
| [length_cap1024_v1](records/length_cap1024_v1/manifest.json) | complete | direct | 10/10 | 5 | 10 | 20/0 | 0.71376 |
| [multi_tool_first5_v1](records/multi_tool_first5_v1/manifest.json) | complete | agent | 5/5 | 0 | 5 | 15/10 | 0.68508 |
| [multi_tool_first5_v1](records/multi_tool_first5_v1/manifest.json) | complete | direct | 5/5 | 1 | 4 | 9/0 | 5.50040 |
| [multi_tool_first5_withseg_v1](records/multi_tool_first5_withseg_v1/manifest.json) | complete | agent | 5/5 | 1 | 4 | 13/10 | 0.69390 |
| [multi_tool_first5_withseg_v1](records/multi_tool_first5_withseg_v1/manifest.json) | complete | direct | 5/5 | 2 | 5 | 10/0 | 0.29132 |
| [train60_r0_v2](records/train60_r0_v2/manifest.json) | complete | agent | 60/60 | 35 | 60 | 181/120 | 2.591188 |
| [val30_r0_v1](records/val30_r0_v1/manifest.json) | complete | agent | 30/30 | 12 | 29 | 88/58 | 1.240848 |
| [val30_r1_v1](records/val30_r1_v1/manifest.json) | partial:budget | agent | 8/30 | 5 | 7 | 23/16 | 0.371724 |
| [val30_r1b_v1](records/val30_r1b_v1/manifest.json) | partial:budget | agent | 8/30 | 3 | 7 | 22/14 | 0.312200 |
| [val29_r1c_v1](records/val29_r1c_v1/manifest.json) | complete | agent | 29/29 | 12 | 29 | 89/58 | 1.348132 |
| [val29_r2_v1](records/val29_r2_v1/manifest.json) | partial:budget | agent | 6/29 | 4 | 5 | 17/12 | 0.241012 |
| [val29_r3_v1](records/val29_r3_v1/manifest.json) | partial:running | agent | 19/29 | 10 | 19 | 56/36 | 0.826516 |
| [train60_r0_v3](records/train60_r0_v3/manifest.json) | complete | agent | 60/60 | 36 | 60 | 180/120 | 2.522636 |
| [train60_full_r0](records/train60_full_r0/manifest.json) | complete | agent | 60/60 | 25 | 45 | 274/173 | 4.961484 |
| [val29_full_r0](records/val29_full_r0/manifest.json) | complete | agent | 29/29 | 11 | 20 | 129/76 | 2.288200 |
| [val29_full_r1](records/val29_full_r1/manifest.json) | complete | agent | 29/29 | 14 | 27 | 114/83 | 2.185252 |
| [val29_full_r2](records/val29_full_r2/manifest.json) | complete | agent | 29/29 | 12 | 26 | 122/85 | 2.301884 |
| [val29_full_r3](records/val29_full_r3/manifest.json) | complete | agent | 29/29 | 16 | 28 | 106/81 | 2.027236 |
| [credit_r3_drop1](records/credit_r3_drop1/manifest.json) | partial:running | agent | 13/29 | 8 | 13 | 49/36 | 0.921124 |
| [val8_r0](records/val8_r0/manifest.json) | complete | agent | 29/29 | 7 | 14 | 147/106 | 2.734040 |
| [val8_r1](records/val8_r1/manifest.json) | complete | agent | 29/29 | 9 | 16 | 125/102 | 2.409596 |
| [val8_r5](records/val8_r5/manifest.json) | complete | agent | 29/29 | 4 | 13 | 103/107 | 2.032612 |
| [val8_r57](records/val8_r57/manifest.json) | complete | agent | 29/29 | 9 | 17 | 94/97 | 1.897952 |
| [val8b_r0](records/val8b_r0/manifest.json) | complete | agent | 29/29 | 12 | 25 | 162/124 | 3.256632 |
| [val8b_r1](records/val8b_r1/manifest.json) | complete | agent | 29/29 | 14 | 29 | 171/117 | 3.389736 |
| [val8b_r5](records/val8b_r5/manifest.json) | complete | agent | 29/29 | 11 | 29 | 130/117 | 2.791432 |
| [val8b_r57](records/val8b_r57/manifest.json) | complete | agent | 29/29 | 15 | 29 | 122/114 | 2.559904 |
| [v4_collect60](records/v4_collect60/manifest.json) | partial:running | agent | 17/60 | 9 | 17 | 94/69 | 1.916368 |
| [s0_B](records/s0_B/manifest.json) | complete | agent | 5/5 | 3 | 5 | 24/21 | 0.518672 |
| [s0_A](records/s0_A/manifest.json) | complete | agent | 5/5 | 4 | 5 | 27/17 | 0.512508 |
| [s0_C](records/s0_C/manifest.json) | complete | agent | 5/5 | 3 | 5 | 23/23 | 0.519420 |
| [v4_B_r1](records/v4_B_r1/manifest.json) | complete | agent | 60/60 | 38 | 60 | 294/290 | 7.135308 |
| [v4_A_r1.pre-v9-203336](records/v4_A_r1.pre-v9-203336/manifest.json) | partial:running | agent | 5/60 | 1 | 4 | 19/19 | 0.421736 |
| [v4_A_r1](records/v4_A_r1/manifest.json) | complete | agent | 60/60 | 39 | 60 | 340/300 | 7.698344 |
| [v4_C_r1](records/v4_C_r1/manifest.json) | complete | agent | 60/60 | 33 | 59 | 316/319 | 8.027184 |

模型、工具注册表、各工具版本、提示词、temperature、top_p、output cap、调用上限、输入顺序、包版本与协议偏差以各行链接的原 manifest 为准。部分旧 manifest 的文字说明未随工具集合更新；判断实际可用工具应以 available_tool_names 为准。
