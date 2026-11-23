# 医影 RAG 项目 · 2026-11-23 续跑快照

这是从另一台机器接手后，在 AutoDL `connect.weste.seetacloud.com:32922` 上继续推进的完整状态。

## 建议阅读顺序

1. `HANDOFF.md` —— 项目背景与当前基础设施状态（§4 已更新为实测值）
2. `RESULTS_MAIRA2_20261123.md` —— 本轮 MAIRA-2 实验的完整阴性结果 + 三条死路记录
3. `RRSI_ARCHIVE_NOTE.md` —— 旧 RRSI 实验的归档与清理记录
4. `REPORT.md` —— 早前 848 题 RAG 增益实验报告（§11 新增 MAIRA-2 一节）

## 本轮三个结论

1. **MAIRA-2 对 CheXBench 定位题无效**。短语 grounding 框 → 质心判左右只有 **49.7%**（随机水平），
   且框与模型自己的报告只有 55.2% 一致，确认是噪声而非方向约定问题；心脏框位置显示图像为
   标准位，排除翻转。接地报告路线覆盖只有 15–42%，与 M5 路由混合后仅 **+1.7**。
   → 交接文档里"MAIRA 框是决定性变量"的假设被证伪，配对裁剪实验前提不成立。
2. **CheXBench 定位题的口径需要修正**：291 道是"同一病灶选不同侧/不同叶"的二选一，
   不是"病灶在图哪一侧"；291 张图各不相同、全部来自 OpenI。组先验就有 54.0%，
   M5 65.0%，纯视觉 DeepSeek 52.6%。
3. **三条无人工捷径都不成立**（详见 RESULTS §8）：MAIRA 当独立读片者有分层选择效应；
   二选一错误重合判别是结构性恒等式；CheXBench 官方人类基线不可得（HF 数据集 gated）。

## 目录

| 路径 | 内容 |
|---|---|
| `code/` | 158 个脚本（上一台机器交接 + 本轮新增 `maira*`、`mk_tasks_maira.py`、`make_human_packet.py`） |
| `data/` | 冻结题目、gold、输入 |
| `results/` | 全部实验产物；`maira2_20261123/` 是本轮逐题框/报告/评分；`human_lat_packet_50.html` 是待人工作答的判读包 |
| `tools/` | 本轮新增的工具：`rsh.py`（远程执行）、`score_human.py`（判读评分）、`proxy_ceiling.py`、`disentangle_bias.py` 等 |

## 当前唯一待办

50 题人工盲测判读尚未回收（`results/human_lat_packet_50.html`）。
答完后用 `tools/score_human.py "<答案串>"` 即可得到 `h_wrong` 与加权人类上限，
据此决定是否投入自训 CXR 检测器。

## 凭据

本分支所有凭据已移除，见 `SECURITY.md`。
