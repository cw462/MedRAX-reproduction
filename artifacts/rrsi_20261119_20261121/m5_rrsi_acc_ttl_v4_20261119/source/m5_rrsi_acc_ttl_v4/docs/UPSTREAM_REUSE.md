# 上游复用与改动台账

2026-11-19通过web读取以下真实上游文件，接口据此编写。本地git clone失败，因此没有在打包时运行实际上游测试；服务器必须用安装脚本下载、记录commit、验证接口并联调。

上游：https://github.com/google-research/rrsi

| 模块 | 使用方式 |
|---|---|
| rrsi.loop.Run.round | 直接导入调用，不替换整个主循环 |
| propose / Workspace | 官方源码编辑与action协议；搜索客户端替换；提示词只修正同模型和授权TTL记忆措辞 |
| analyst / digester | 官方轨迹分析；禁用digester shell，强化文件路径边界 |
| critic | 官方预检/模型审查；只替换与合法跨题记忆冲突的第5条 |
| history / components / schedule | 官方记录、标签、退火、探索与剪枝建议；停滞输入改为每轮配对接受收益累积 |
| gitops | 官方候选worktree、commit、fast-forward |
| evaluate | 官方TaskResult/EvalResult/evaluate；医疗Domain提供真实顺序回放 |
| selection | 明确替换准确率优先规则；成本与新颖性只记录不补偿准确率 |
| llm | 兼容接口替换到已配置Qwen endpoint，不使用AnthropicVertex |
| driver | 不用离线驱动；TTL协调器在每个已完成反馈检查点调用一轮 |

文件级原文：
- https://raw.githubusercontent.com/google-research/rrsi/main/rrsi/loop.py
- https://raw.githubusercontent.com/google-research/rrsi/main/rrsi/domain.py
- https://raw.githubusercontent.com/google-research/rrsi/main/rrsi/propose.py
- https://raw.githubusercontent.com/google-research/rrsi/main/rrsi/selection.py
- https://raw.githubusercontent.com/google-research/rrsi/main/rrsi/critic.py
- https://raw.githubusercontent.com/google-research/rrsi/main/rrsi/history.py
- https://raw.githubusercontent.com/google-research/rrsi/main/rrsi/llm.py
- https://raw.githubusercontent.com/google-research/rrsi/main/rrsi/evaluate.py

运行时猴补丁全部在m5rrsi/upstream.py/selection.py公开，记录runtime_hooks.json；上游磁盘源码未偷偷修改。相关模板标记不匹配就失败，避免升级后悄悄改错位置。

动态TTL面板的S不可跨轮直接比较。每轮刷新父评估和panel_id；选择器要求panel_id、起始记忆哈希、题ID、重复数、metric_id一致。上游frontier轨迹保留记录，但不直接用跨面板绝对分数判停滞。

暂停恢复包装器保留官方轮次产物；若只完成branch推进、未完成frontier提交，仅在分支tip确属本轮已记录候选时恢复到本轮父状态再续。任何不明外部改动一律停止。不得人工re-adjudicate已产生后续主流成绩的历史轮次。
