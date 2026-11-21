# OpenI60 动作协议审计与共同修复 F

服务器原地复核全部 120 条题目轨迹、414 次主模型响应，缺档为零。L1 有 47 题在提出工具计划后收到禁止工具的最终答案回退，B0 为 4 题。历史成绩保留 B0 41/60、L1 39/60，G9/H11。

共享修复采用单 JSON 契约和每决策最多两次同阶段重试，错误后继续允许工具。52 项离线测试在本机及 AutoDL 原环境全部通过。8 题和 60 题的独立目录已准备，仅完成离线预检；没有启动真实推理。

| 文件 | 内容 |
|---|---|
| [AUDIT_REPORT.md](AUDIT_REPORT.md) | 完整审计、故障实例、修复说明和评分语义限制 |
| [audit_summary.json](audit_summary.json) | 结构化汇总、覆盖范围和测试结果 |
| [protocol_f.diff](protocol_f.diff) | 共同执行器及新协议模块的代码 diff |
| [repair/](repair/) | 已测试的两份运行时代码 |
| [RUN_COMMANDS.md](RUN_COMMANDS.md) | 后续 B0-F/L1-F 命令及无卡复核命令 |
| [outputs/server/native/](outputs/server/native/) | 逐次、逐题、逐工具原生核验和全部故障原文 |
| [outputs/server/lexical/](outputs/server/lexical/) | 附件审计脚本的完整输出 |
| [outputs/server/tests/](outputs/server/tests/) | 服务器 52 项离线测试明细 |
| [outputs/server/prepared/](outputs/server/prepared/) | 两套待运行目录的准备和预检回执 |
| [outputs/patch/patch_check.json](outputs/patch/patch_check.json) | diff 应用成功且与交付代码一致 |

真实 B0-F/L1-F 成绩尚待后续共同协议实验。原始实验数据、医学规则、记忆算法、工具实现和评分器保持原样。

历史 B0/L1 的配对结果、原始轨迹和工具回执见[原实验报告](../openi60_m5_l1_autodl_20261121/README.md)。准备目录中的 `*_config.F.public.json` 保留实验参数，用占位符表示运行环境路径。
