# 运行说明（当前仅供审阅，不自动执行）

用户最新指令为先完成计划/代码并上传。本说明列出之后恢复运行时的步骤；
发布本说明不会启动 API 调用，也没有新增定时任务。

## 环境和数据

使用 Python 3.10+ 独立环境。服务器现有解释器检查为 Python 3.10.18、
OpenAI SDK 1.109.1、Pillow 11.3.0；本地合成测试解释器为 Python 3.14.3。
本地旧 OpenAI SDK 0.28.1 不具备新 `OpenAI` 客户端，实际运行应安装
[本轮依赖](../../requirements-vote-gain.txt)，不能把 mock 测试通过当成 SDK 在线验证。

```sh
python -m pip install -r requirements-vote-gain.txt
```

下列命令在代码仓库执行。`PROJECT_ROOT` 是数据/运行目录的绝对根路径，
`CODE_ROOT` 是本仓库的绝对路径，必须位于 PROJECT_ROOT 下（可以相同）。
不要在脚本中写入 API key。Qwen 使用 DASHSCOPE_API_KEY，GPT-4o 使用 APIYI_API_KEY。
以下示例只从环境变量读入 stdin，不把密钥写进 argv、配置或日志；本机已配置的
私有部署器从仓库之外的独立凭据文件读取。不要将凭据文件复制到公开目录。

已有冻结输入的相对位置：

```text
runs/multimodel_vote_gain_20261102/split_inputs/tune.inputs.jsonl
runs/multimodel_vote_gain_20261102/split_inputs/test.inputs.jsonl
runs/multimodel_vote_gain_20261102/isolated_labels/tune.labels.json
runs/multimodel_vote_gain_20261102/isolated_labels/test.labels.json
data/memory_v1/images/
```

本次 GitHub 只包含划分清单，不包含隔离标签。重新构建数据时，使用同一完整
metadata 源及历史排除证据，不另换 seed 或用新分数选病例。脚本直接支持公开
历史排除证据的无损字典压缩格式；已有服务器冻结目录无需重新划分。

```sh
python data_tools/make_heldout.py \
  --metadata "$PROJECT_ROOT/data/chest-agent-bench/metadata.jsonl.new" \
  --history-manifest reports/multimodel_vote_gain_20261102/splits/history_exclusions.json \
  --out /path/to/new-input-directory --labels-out /path/to/separate-label-directory \
  --seed 20261102 --tune-questions 400 --test-questions 1000
```

上例使用相同历史排除来源，不能另扫描一部分报告而声称等同。
完整相对证据见 [排除清单](splits/history_exclusions.json)。划分脚本禁止覆盖
已有输入/标签目录。生成器输入仅允许白名单字段，拒绝标签字段。

## 阶段 0：配置、准备、未来启动

填写既有账本真实的累计已记费用和上限，不能提高旧上限。新的累计 cap 等于
当前已记费用加本轮 ¥200，原账本保留；不同模型串行继承上一组费用。

```sh
python experiments/configure_vote_gain.py \
  --root "$PROJECT_ROOT" --code "$CODE_ROOT" \
  --gpt4o-profile "$CODE_ROOT/configs/gpt4o_apiyi_vote_profile.json" \
  --new-budget-cny 200 \
  --inherited-committed-cny "$RECORDED_COMMITTED_CNY" \
  --original-cap-cny "$RECORDED_ORIGINAL_CAP_CNY" \
  --inherit-ledger reports/api_budget_qwen_100cny_v9.json \
  --budget-authorization 'User 2026-11-02: incremental CNY200, basic and voting phases'
```

此命令只写配置，不打开账本或调用模型。GPT-4o 的公开配置固定 API易接口、
`gpt-4o` 别名、20/80 CNY 每百万 token 保护费率及费率来源，不含密钥。
API易模型目录已通过只读请求确认；首次真实图像调用仍由阶段 0 完成。
旧 60 题回归输入来自原先保存的
`runs/v4_validation60/inputs.jsonl`；case ID 从源元数据明确的两种 question ID
字段映射补齐，绝不拆字符串猜病例。

```sh
CFG="$CODE_ROOT/configs/multimodel_vote_gain_20261102"
export MEDRAX_CODE_COMMIT="$(git rev-parse HEAD)"
python experiments/run_vote_phase.py --manifest "$CFG/phase0.json" --prepare-only
```

`--prepare-only` 无模型调用；阶段协议保存代码提交和完整配置。配置一旦准备即
不可原地修改。之后获得继续运行指令时才执行：

```sh
python -c 'import json,os; print(json.dumps({"dashscope":os.environ["DASHSCOPE_API_KEY"],"apiyi":os.environ["APIYI_API_KEY"]}))' | \
  python -u experiments/run_vote_phase.py --manifest "$CFG/phase0.json" --credentials-json-stdin
```

该入口串行运行 D60 和四组两题接口检查；共用整个实验的执行锁。失败即保留状态
并停止，先确认具体异常；不得重新发出结果未知的请求。恢复时沿用同一入口和
冻结配置，已完成样本会跳过。不存在自动额外跑一遍来修复低分的路径。

阶段 0、3a、3b 含两种 credential_slot，必须使用上述凭据映射；每个模型子进程
只收到自己的密钥。仅 Qwen 的阶段 1/2 可继续使用 `--api-key-stdin`，也可统一使用
凭据映射。混合阶段会拒绝单密钥入口，不会把 Qwen 密钥误传到 API易。

## 完成后评分和晋级

只有阶段 0 整体 `generation_complete` 后，才运行旧 60 题回归评分。
`generation_gate` 会在读取参考前检查这一点。历史参考文件已在仓库公开。

```sh
REPORT="$PROJECT_ROOT/reports/multimodel_vote_gain_20261102"
python experiments/score_votes.py --manifest "$CFG/phase0.score.json" \
  --labels "$CODE_ROOT/reports/direct_qwen60/per_question.json" --out "$REPORT/phase0"
```

后续物化配置也不启动推理。阶段 1 自动检查 D60 在 40–44/60、缺答为 0、四组
接口检查已完成且有合法答案。不满足条件先解释问题，不靠修改标签或盲重跑过门。

```sh
python experiments/configure_vote_tune.py --phase 1 \
  --root "$PROJECT_ROOT" --code "$CODE_ROOT" \
  --phase0-manifest "$CFG/phase0.json" --phase0-metrics "$REPORT/phase0/metrics.json"
```

阶段 1 的准备/运行入口与阶段 0 相同，仅替换 manifest 为 `phase1.json`。
完成后使用 `phase1.score.json` 和隔离的 `tune.labels.json` 评分。

```sh
python experiments/score_votes.py --manifest "$CFG/phase1.score.json" \
  --labels "$PROJECT_ROOT/runs/multimodel_vote_gain_20261102/isolated_labels/tune.labels.json" \
  --out "$REPORT/phase1"
```

阶段 2 和 3a 均需要阶段 1 的固定决策；3a 还要求阶段 2 全部采样已完成。
每次只物化当前阶段，按同样的 prepare→run→offline score 顺序执行。

```sh
python experiments/configure_vote_tune.py --phase 2 \
  --root "$PROJECT_ROOT" --code "$CODE_ROOT" \
  --phase0-manifest "$CFG/phase0.json" --phase0-metrics "$REPORT/phase0/metrics.json" \
  --phase1-metrics "$REPORT/phase1/metrics.json"
```

将上例 `--phase 2` 改为 `--phase 3a` 可在阶段 2 完成后生成 B0 对照组。
阶段 3a 全部生成并用 `phase3a.score.json` 评分后：

```sh
python experiments/configure_vote_tune.py --phase 3b \
  --root "$PROJECT_ROOT" --code "$CODE_ROOT" \
  --phase0-manifest "$CFG/phase0.json" --phase0-metrics "$REPORT/phase0/metrics.json" \
  --phase1-metrics "$REPORT/phase1/metrics.json" \
  --phase3a-metrics "$REPORT/phase3a/metrics.json"
```

阶段 3b 将 B0 调参权重及最强模型写入新冻结清单，复用阶段 2 已保存的 Qwen
九样本。只为另外两模型生成需要的 3/9 样本，不复制或重跑旧终态。
主 B2/B3 为模型内多数后的加权投票，池化样本另存诊断结果。

这套配置器没有阶段 5 或全 2,500 题自动入口；这些不在当前首次运行范围内。
剩余预算不足时保留所有已完成记录，不增额、不清账本。阶段报告必须说明实际完成
数量；评分器拒绝把不完整阶段当完整分母结果。

## 导出、发布与检查

完整阶段的评分清单同时可交给导出器，导出不调用模型。

```sh
python experiments/export_vote_phase.py --manifest "$CFG/phase1.score.json" \
  --out "$REPORT/phase1" --image-root "$PROJECT_ROOT/data/memory_v1/images"
```

阶段 0 的 D60 用 `phase0.score.json` 导出；四组两题接口检查单独用
`phase0.smokes.export.json` 导出到另一个报告目录，避免混用分母。
`evidence/publication_manifest.json` 是显式发布文件清单。检查本次出站内容和
链接后按清单暂存，忽略的 jsonl/图片仅对清单路径 force add，禁止整个私有 run
或账本目录入库。Push 后核对远端 commit 才报告上传完成。

本轮合成验证命令：

```sh
python -m unittest tests.test_sampled_vlm tests.test_vote_phase \
  tests.test_vote_split tests.test_score_votes tests.test_export_vote_phase \
  tests.test_configure_vote_tune
```

这些测试验证执行契约、费用继承、恢复、投票、标签门禁和导出，不产生医学准确率。
