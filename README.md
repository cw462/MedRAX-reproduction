# 医影 RAG 交接包（2026-11-23）

从 `deepseek-harness` 会话导出的完整工作交接。

## 先读
1. `HANDOFF.md` —— 目标、结论、实验结果、服务器状态、待办、踩坑
2. `REPORT.md` —— 正式报告（含三套数据集 RAG 结果、题型分析）

## 目录
- `code/` 全部脚本（RAG 评测、BM25 索引、检索方法、检测器、MedSAM、配对裁剪、AutoDL/实验室 SSH）
- `results/` 全部实验输出 JSON + 576 张配对裁剪图（crops.tar.gz）
- `data/` 848 题元数据与三个数据集的输入清单

## 凭据
`CREDS.md` 只放在 zip 里，**不在 GitHub 上**（仓库是公开的）。

## 关键结论（一句话）
RAG 只在概念型题有效（SLAKE +3.5），看图题无效；
定位失败占 57%，必须靠病灶级 grounding + 几何判定，文本层增强全部实测无效。
