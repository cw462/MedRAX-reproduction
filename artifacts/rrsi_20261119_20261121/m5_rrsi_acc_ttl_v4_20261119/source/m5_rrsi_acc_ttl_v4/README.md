# M5–RRSI–Acc–TTL v4.0：官方核心接入包

日期：2026-11-19。替代 v3.1 四文本字段版本；不是在旧包上原地覆盖。

## 这份代码是什么

本包包含逐题 TTL 控制器、医学 Domain、准确率选择补丁、Qwen 兼容搜索客户端、隔离执行接口、历史顺序回放、状态迁移、断点续跑、报告、测试及服务器 Codex 任务书。

**真正的搜索循环由 `m5rrsi/search.py` 调用官方 `rrsi.loop.Run.round(t)`。**没有复制一套四字段 proposer 冒充官方循环。官方的 proposer、analyst/digester、critic、repair、组件归类、退火预算、修改历史、停滞探索、剪枝建议和 git worktree 由上游执行。

当前环境能通过 web 阅读官方源码，但容器 `git clone` 失败（GitHub DNS 无法解析），所以本 ZIP **不包含一个声称已经下载/验证的上游快照**。`scripts/fetch_upstream.py` 需在有网络的服务器执行，获取官方仓库，记录完整 commit 与全部 rrsi Python 文件 SHA256。后续运行逐一校验锁定文件，不自动升级上游。

**真实 M5 的源代码、原图、工具环境、评分器和 API 凭据不在本会话里。**因此 `domain_template/harness/agent.py`、`integration/native_bridge.py`、`integration/native_score.py` 是明确会报错的接入点，必须由服务器 Codex 接到现有实现；它们不是能冒充真实 M5 的演示程序。不要声称解压后无需接线就能跑 848 题。

## 固定的研究决策

只做两组：原始 M5（机制固定、正常逐题写记忆）与 M5-RRSI-Acc-TTL。没有 GEPA，没有强制 300/100/448 离线划分。

两组同原始 H0、空初始记忆、Qwen3.7-Plus、医学工具、原图、选项、顺序、评分器、单题资源上限。每题先把两组预测分别锁定，再对本题反馈和写记忆，**不等待关联题整组完成**。第 i 题反馈可以帮助同图第 i+1 题。

默认 `full_label`：当前题锁定后，writer 可以看到该题对错与参考答案。这是用户原实验协议的适配目标，不是 EvoClinician 隐藏标准诊断反馈接口的完整复现。

## 外层何时执行

本版 TTL 调度为：**每完成一题的反馈和记忆更新，且仍有后续题、仍有预注册搜索轮次预算，就调用一轮官方 `Run.round()`。**从首题结束后即可尝试，不设置“30 题预热、每 10 题一次”。末题之后不再进化。

这是 TTL 接入层的事件调度选择，不是声称官方离线 RRSI 本身按题触发。原版按搜索轮次运行。停滞只影响探索方向，不是开始进化的唯一条件。一次搜索轮次可以没有候选被接受。

## 允许修改什么

允许在 `domains/med_m5/harness/` 中编辑真实源文件：prompt、规划与控制流、写入和抽取、图维护与检索、上下文组织、现有工具封装、技能和预算内子智能体。没有四字段限制，也不再套用旧的每字段 2400 字符上限。仍沿用官方“每个候选最多若干项独立修改”的退火约束。

禁止修改主模型权重、外层改进器代码、评分器、标签释放、输入图像绑定、工具后端版本、凭据和固定资源上限。源码可编辑不等于整个服务器可编辑。

## 历史评估与选择

为了让 writer/图维护修改有机会在后续问题生效，使用最近最多 20 道已完成题做**顺序历史回放**，而不是把各题放在当前已知答案的记忆库里独立重答。当前版本与候选均从这段历史开始前的**同一实验组记忆快照**出发，各重复 2 次；每个回放题也先预测、后评分与写记忆。回放结束后，再验证候选能迁移真实的当前记忆状态。

每个新回放面板都重评父版本。旧面板的最高分不能用来判断新面板的候选。平均准确率必须严格提升，且每次重复都不能下降；成本和新颖性不抵扣掉分。没有通过就保留原版本。

历史回放不是独立验证集，也不是统计显著性证明。原有标签反馈和代码提案可能已间接影响历史面板；接受不保证未来题目涨分。主成绩只计算每个流题反馈前锁定的那次答案，绝不把回放成绩混入分母。

## 先看计算量

```bash
python -m m5rrsi.cli budget --config configs/ttl_official.json
```

默认 848 题、最多 847 轮、每轮 2 候选、2 重复、20 题历史窗口：两组首遍共 1696 次病例预测；所有候选都通过前置筛查且无失败重试时，历史回放最多 **100500 次病例预测**，还有同量级 writer 操作、分析/提议/审查/修复和迁移检查。这不是 848 次额外调用。单题涉及几次 Qwen/工具调用，以真实轨迹为准。

预算较小时，可以在**首次计分前**缩小 `max_rounds`、`replay_window_cases`、`candidates` 或 `repeats` 并记录；达到轮次上限后，余下流仍继续作答和写记忆，只停止源码搜索。不要运行后按效果改预算并续同一实验，也不要私下改回每十题触发。

## 快速入口：给 Codex，不是无需配置的一键医学复现

先阅读 `CODEX_TASK.md` 与 `docs/NATIVE_CONTRACT.md`。

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python scripts/fetch_upstream.py --dest /absolute/path/rrsi-m5-v4 --ref main
```

然后由 Codex：移植原始 M5 到可编辑树；接通受保护的服务桥与原评分器；完成同图连续两题、H0 等价性、模型/工具限额及隔离测试；填真实配置。

```bash
python scripts/check_real_upstream.py \
  --repo /absolute/path/rrsi-m5-v4 \
  --lock /absolute/path/rrsi-m5-v4.upstream.lock.json \
  --report /absolute/path/evidence/upstream_contract.json

python -m m5rrsi.cli prepare --inputs /absolute/path/public_cases.jsonl --out /absolute/path/stream.json
python -m m5rrsi.cli validate --config configs/ttl_official.json
python -m m5rrsi.cli freeze --config configs/ttl_official.json
python -m m5rrsi.cli run --config configs/ttl_official.json --stop-after 5
python -m m5rrsi.cli run --config configs/ttl_official.json --resume
python -m m5rrsi.cli report --run-dir /absolute/path/runs/m5_rrsi_ttl_v4_s42
```

先 5 题再 resume 仅在源码、配置、数据、反馈权限都不变时成立。原生接线测试必须在正式流外完成；不得看过这 5 题标签调策略后仍把它们算作未经调整的首遍结果。

## 已测试和未测试

本包本地 51 项软件测试通过，日志在 `docs/LOCAL_TEST_LOG.txt`。测试使用显式合成夹具，不是医学成绩。

尚未在本环境执行：实际上游仓库联调脚本、Docker 原生医学容器、Qwen API、你的 M5、848 题。`scripts/check_real_upstream.py` 必须服务器执行，它使用真正的官方代码加脚本化 LLM 响应和合成运行器，不产生医学结论；真实原生服务测试还必须单独通过。

上游 Apache-2.0 许可证由安装脚本克隆时保留。本包为研究工程适配代码，不是临床安全验证。
