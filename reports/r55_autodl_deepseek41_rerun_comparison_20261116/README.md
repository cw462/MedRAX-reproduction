# MedRAX R55 · DeepSeek V4.1 Flash 五组对照

五组使用官方 DeepSeek V4.1 Flash 主模型、同一组冻结的 848 题、11 个工具和原版 CheXagent-8B。
七个受影响的子集从头复跑。M2 的 SLAKE 从空记忆启动，M5 的 SLAKE 从七个初始模式启动。
CRITIC 的 SLAKE 复用原来由同模型生成的 CoT 初答。Reflexion 的两组短集复用新版 ReAct 的同题首轮。
合并结果采用原来修复后生成的八个子集。每个子集的来源和运行时间记在 [summary.json](summary.json)。

| 组别 | CheXBench | SLAKE | VQA-RAD | 总分 | 较 ReAct 改对 | 较 ReAct 改错 | 净变化 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ReAct | 422/618 | 88/114 | 89/116 | 599/848 (70.64%) | 0 | 0 | +0 |
| M2 | 428/618 | 103/114 | 98/116 | 629/848 (74.17%) | 110 | 80 | +30 |
| M5 | 427/618 | 102/114 | 97/116 | 626/848 (73.82%) | 109 | 82 | +27 |
| CRITIC | 412/618 | 86/114 | 93/116 | 591/848 (69.69%) | 80 | 88 | -8 |
| Reflexion | 421/618 | 87/114 | 90/116 | 598/848 (70.52%) | 51 | 52 | -1 |

显存保护使用同一时刻一个驻留 GPU 工具。本次重跑捕捉了 0 条 GPU 保护事件。成功采纳的逐题工具观察中 CUDA OOM 数为 0。

净变化按同题的改对减去改错计算。两次运行之间的变化还包含模型采样与后续工具选择的差异。

逐题记录包含题目、工具观察、已有对照和最终评分。GPU 保护事件和恢复状态见运行摘要。

生成与显存保护入口见 [启动器](source/local/r55_rerun_deepseek41.py) 和 [运行控制](source/bin/r55_deepseek_rerun_runtime.py)。

原始报告 [ReAct](https://github.com/cw462/MedRAX-reproduction/blob/a459642b1e33386be62f41930d42143350ddf1c8/reports/r55_autodl_deepseek41_main_deepseek_flash_react_20261115/README.md) · [M2](https://github.com/cw462/MedRAX-reproduction/blob/53b24c0e6f02813c732355d183b2a0b8477c96d3/reports/r55_autodl_deepseek41_main_deepseek_flash_m2_20261115/README.md) · [M5](https://github.com/cw462/MedRAX-reproduction/blob/34acbe279843076576eab5ff219ab681c39d4e0c/reports/r55_autodl_deepseek41_main_deepseek_flash_m5_20261115/README.md) · [CRITIC](https://github.com/cw462/MedRAX-reproduction/blob/f9bdc97fc462464621960c59604b8a9b56b8f91a/reports/r55_autodl_deepseek41_main_deepseek_flash_critic_20261115/README.md) · [Reflexion](https://github.com/cw462/MedRAX-reproduction/blob/fc0754ca786515ff0312a0312ff7540492cff03f/reports/r55_autodl_deepseek41_main_deepseek_flash_reflexion_20261115/README.md)
