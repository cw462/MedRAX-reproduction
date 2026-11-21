# OpenI60：原始 M5 vs. 左右侧专项提示 L1

目标：先用 **60 道 OpenI 左右侧题 × B0/L1 两组 = 120 次首答评测**，检验一个求解提示补丁。不是 120 次 API 请求；每题仍可能调用主模型、工具与记忆模型多次。

本包提供固定抽样、主求解器提示注入、独立 M5 记忆、原生评分和配对汇总。AutoDL 常驻模型与双组并行运行入口见 [RUN_AUTODL.md](deployment/RUN_AUTODL.md)。32 项离线测试覆盖原生接口模拟与双组并行调度；测试中的模拟评分不作为真实实验结果。

## 1. 使用前提

在**已经跑通原始 R55 / Qwen3.7-Plus / M5 / 11 工具**的同一服务器、同一 Python 环境中运行。本包不重新实现医疗工具、不下载权重、不重新定义 M5，也不替换原评分器。

两个历史结果 ZIP 是分析产物，不是完整可运行环境。本包读取原生产运行目录中的 `plan.json`，复用：

```text
<原生产运行根目录>/
  plan.json
  run_r55_11tools_m5.py
  run_r55_full848_dataset.py
  score_r55_full848_dataset.py
  r55_memevolve_driver003.py
  r55_memory_token_plan.py
  jobs/memory-writer-token-plan.json       # 原环境使用该路由时应存在
  manifests/M5/chexbench.json
  code/M5/experiments/...
```

`plan.json` 中的 `data.chexbench`、`references.chexbench`、`memory_runtime` 用来定位原始输入、隔离标签与 MemEvolve 运行时。目录布局不同时，编辑生成的 `config.local.json` 里的路径即可，不要为了让预检通过而换成无记忆或 8 工具运行器。

包装器自身仅用 Python 标准库，要求 Python 3.10+、Linux；模型、工具及记忆依赖使用原运行环境。不要使用 `python -O`，原生断言需要保留。

## 2. 两组到底有什么不同

| 项目 | B0 | L1 |
|---|---|---|
| 主模型、采样参数、工具版本 | 原生产配置 | 相同 |
| 工具清单与预算规则 | 原 11 工具、原预算规则 | 相同 |
| 题目与顺序 | 新抽取的固定 60 题 | 完全相同 |
| 初始记忆 | 原生七条通用模式 | 独立初始化的同样七条模式 |
| 写入与检索、Verify | 原实现 | 原实现 |
| 唯一模型可见干预 | 无 | 主求解器 system 消息末尾追加 `prompts/L1_zh.txt` |

挂接点是已读源码中的 `skill_services_r55.Services.call(row, arm, ordinal, messages)`；只处理 `arm == "R49-AGENT"`。Verify、反思工具、记忆模型不会通过该分支收到 L1 补丁。B0 的原消息对象原样传给原函数。补丁不复制到工具描述或记忆合成器。

B0/L1 拥有各自的 `storage`、`external_memory`、`services`、预测与工具缓存目录。共享的是只读模型文件与同一批原图副本，不共享可变经验库。运行时继承原有工具权限、费用账本策略和恢复规则，不新增固定工具调用上限，也不自动放宽预算。

这是“主提示修改 + 它对随后记忆轨迹产生的总影响”的试验；不是冻结记忆下的纯单步直接效应。

## 3. 准备与运行

### 3.1 离线自测（不调用模型）

```bash
cd OpenI60_M5_L1_20261121
python -m unittest discover -s tests -v
```

### 3.2 从原生产目录生成配置

只需要首先给出你服务器上真实的原运行目录。下面的路径是占位示例，不是宣称它已存在。

```bash
export M5_NATIVE_ROOT="/你的服务器/原始M5生产运行根目录"
export OPENI60_WORK="$PWD/runs/openi60_s20261121"

python openi60_cli.py configure \
  --native-root "$M5_NATIVE_ROOT" \
  --work-dir "$OPENI60_WORK" \
  --out config.local.json
```

检查 `config.local.json`，尤其是路径、`gpu`（核对过的原运行器支持 `0` 或 `1`）、凭据环境变量名。默认 n=60，seed=20261121。不要用挑出来的有利 seed 替换初次结果。

### 3.3 检查题池，创建新实验，离线预检

```bash
python openi60_cli.py inspect --config config.local.json
python openi60_cli.py prepare --config config.local.json
python openi60_cli.py preflight --work "$OPENI60_WORK"
```

`inspect` 只读原生无标签输入，显示侧别题数、目标类型与题号。默认预期 293 题；检测规则是**两个选项仅一个完整 left/right 词相反，其余归一化文本相同**。数量不符会停下，先审查过滤规则与原 manifest，不要改成抽“历史 M5 错题”。

`prepare` 不发模型请求、不解析参考答案。它固定名单、重建题序、复制原图、重映射图像视图路径并保存源代码哈希。原图使用字节复制而不是指向目录外的符号链接，因为原发送器检查图像必须位于数据根目录内。

`preflight` 检查文件、哈希、原生接口和导入。不执行真实 API/GPU 健康探针，不能据此宣称工具在线健康。正式运行前使用你已验证的工具环境；环境修复应同时覆盖两组。

### 3.4 配置已有凭据

默认读取以下两个环境变量；也可把配置里的 `main_key_env`、`memory_key_env` 改为服务器已有的凭据环境变量名。

```bash
read -r -s -p "Main API key: " OPENI60_MAIN_API_KEY; echo
export OPENI60_MAIN_API_KEY
read -r -s -p "Memory API key: " OPENI60_MEMORY_API_KEY; echo
export OPENI60_MEMORY_API_KEY
```

不把 key 写入命令参数、配置或源码。运行器按原协议通过标准输入接收两行凭据。原 Verify/其它工具的环境变量与模型路由继续使用原生产配置。

### 3.5 正式执行，仅 B0/L1，不自动扩大

```bash
python openi60_cli.py run --work "$OPENI60_WORK" --execute
```

默认前台串行执行 B0 后 L1，使用同一 GPU 配置。每组内部严格按同题序运行。绝不在一组内部并行打乱在线反馈顺序。时间段差异仍可能影响外部服务，这次短试验没有消除该因素。

在已配置常驻模型服务的 AutoDL 环境中，可使用 `python -m openi60.parallel --work "$OPENI60_WORK" --execute` 并行推进两个独立组。每组内部仍按题序执行，GPU 请求使用原常驻服务的执行锁；两组的预测、工具缓存和记忆目录保持独立。

可以单独跑一组：

```bash
python openi60_cli.py run --work "$OPENI60_WORK" --arm B0 --execute
python openi60_cli.py run --work "$OPENI60_WORK" --arm L1 --execute
```

关闭终端可能中断前台任务。需要持久终端时使用你自己的终端会话管理；本包没有隐式后台调度。

### 3.6 状态、明确恢复和重新汇总

```bash
python openi60_cli.py status --work "$OPENI60_WORK"
python openi60_cli.py run --work "$OPENI60_WORK" --execute --resume
python openi60_cli.py analyze --work "$OPENI60_WORK"
```

`--resume` 不是盲目重发请求：沿用原生 `CheckpointMemory` 的冻结前缀、调用回执、反馈和图状态校验。未知发送、损坏检查点或不匹配会停下；不能删掉失败记录伪装成初次运行。已成功完成评分的组不会重新推理。源码或提示改变时旧目录不能续跑，需要新实验目录。

## 4. 选题、时序与隔离

抽样只用无标签题目和选项，不读取六组的正确性表。以固定随机种子从候选题中均匀抽取 60 个题号，再保留它们在原 manifest 中的相对顺序。

对抽样后的实际题流，重新计算 `previous_ids`，不会保留被抽掉题目的“过去反馈”。每题时序仍为：

```text
检索本组过去经验 → 当前题独立推理并锁定首答 → 释放本题反馈
→ 更新本组记忆 → 下一题
```

不改为整组病例结束后更新。用原 `ReferenceVault` 与原评分器，标签不得在本题锁定前提供给模型。

划分时联合已有 image_key、image_id、像素标识、图片路径和 OpenI CXR study 标识；已选病例/图像的其它题，不进入后续确认候选名单。这是已知标识层面的隔离，不能宣称已经核实患者独立，也没有额外运行感知去重或患者身份核验。

脚本生成 `remaining_case_disjoint_candidate_ids` 和 `excluded_related_ids`，不会假定剩余确认集正好等于 293−60。此前已曝光的题仍属开发/历史回归，不能当全新未见测试。

## 5. 运行器适配与评分

原生成器与评分器把 CheXBench 题数断言为 618。包装器只在当前子进程中把共享 `COUNTS['chexbench']` 改为这次冻结的 n；其余评分、答案抽取和 reward 逻辑保持原实现。不能把新样本命名为另一个数据集来绕过 CheXBench 评分。

实际调用主模型前记录补丁及 system 哈希；评分前再次逐条读取原生请求归档，核对 `messages` 中的 system 文本确实收到补丁且未重复。没有符合记录就报错，不把“配置了 L1”当成“模型收到了 L1”。

保留每题首答、工具执行失败和无法解析的输出；原评分器如何计分仍如何计分。不删掉工具失败题提高准确率。生成或评分未完整完成时，不以较小分母发布正式双组比较。

`G = B0 错、L1 对`；`H = B0 对、L1 错`；`净提升 = (G−H)/60`。工具失败、真实调用量、token 由原生日志保留。原 scorer 的 usage 不一定包括记忆模型，因此未知的记忆费用不会记作 0。跨题在线记忆造成依赖，本包不附一个不适用的 iid 显著性结论。

## 6. 输出

```text
runs/openi60_s20261121/
  frozen.json                         # 配置、源文件/图像/manifest/提示哈希
  cohort.json                         # 名单、种子、病例隔离的后续候选
  selected_questions.csv              # 只有无标签输入
  data/inputs.jsonl + images/...       # 本次原图副本
  B0/                                 # 原生M5，新增审计但不改提示
  L1/                                 # 原生M5 + 求解器system后缀
    manifest.json
    solver_suffix.txt
    initial_memory.json               # 7节点初始语义状态
    prompt_audit/<qid>/<call>.json
    predictions/...  feedback/...  services/...
    external_memory/episodes/...
    external_memory/model_calls/...
    analysis/per_question.json        # 原评分器结果
    analysis/summary.json
    scoring.completed.json            # 成功退出与原评分文件哈希
  jobs/<arm>/attempt-*/                # stdout、stderr、退出码；无自动无限重试
  paired_analysis/
    summary.json
    paired_results.csv
    pairs.json
    REPORT.md
```

实验后优先提供 `paired_analysis/summary.json`、`paired_results.csv`，以及 gain/harm 对应题的两组轨迹。共享完整日志前检查其中是否含服务地址、账号信息或其它私有元数据。

## 7. 验证与结果

- 离线验证：32 项测试；抽样、过滤、题序、提示注入、冻结保护、模拟原生接口完整双组执行、并行调度及原评分结果配对统计。
- 已阅读核对：原生生成/评分入口、主求解器调用接口、反馈时序、M5 初始化/检查点与原图路径约束，见 SOURCES.md。
- 运行记录：原生依赖导入、真实 API/GPU 请求、初始化与提示审计、完整 60+60 题成绩均保存在对应运行目录；正式双组比较使用 `paired_analysis/` 的完整输出。
- 本包不是独立 MedRAX 发行版；本机路径、权重、生产依赖和凭据必须由已有 M5 环境提供。接口不符时停止并定位真实实现，不得偷偷降级为 mock/Direct/无记忆运行。
