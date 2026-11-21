# OpenI60 共同协议 F：运行命令

已完成离线审计、52 项测试、两套独立目录的 prepare/preflight。下列真实运行命令尚未执行。它们需要用户确认执行、原 API 凭据环境及 GPU 工具运行环境；无卡实例仅用于离线工作。

## 已准备目录上的后续真实实验

在服务器设置已有凭据环境变量 `OPENI60_MAIN_API_KEY`、`OPENI60_MEMORY_API_KEY`，沿用原工具居民进程及注册清单。凭据不写入代码或命令文档。

先运行原顺序前 8 题的共同协议冒烟。内部 B0 槽为 B0-F，L1 槽为 L1-F：

```bash
PYTHON=/root/autodl-tmp/medrax_r55_top4_full848/env/modern/bin/python
"$PYTHON" -B /root/autodl-tmp/openi60_protocol_F_smoke8_20261121/openi60_cli.py run \
  --work /root/autodl-tmp/openi60_protocol_F_smoke8_20261121/runs/evaluation \
  --arm all --execute
```

按协议和工具派发情况验收冒烟后，正式流从自己的新记忆开始，完整保留原 60 题、原顺序和原 seed：

```bash
PYTHON=/root/autodl-tmp/medrax_r55_top4_full848/env/modern/bin/python
"$PYTHON" -B /root/autodl-tmp/openi60_protocol_F_formal60_20261121/openi60_cli.py run \
  --work /root/autodl-tmp/openi60_protocol_F_formal60_20261121/runs/evaluation \
  --arm all --execute
```

两条命令分别运行两组。CLI 沿用原生锁定预测→评分与本题后反馈时序，完成后输出各自 `paired_analysis/summary.json`、`paired_results.csv`。新增格式事件保存在各组 `services/protocol_events/`，逐次步骤和不可变预测同时包含 protocol 字段。8 题与 60 题状态不拼接；如改变代码或提示，应新建运行目录。失败保留日志，停止后先检查错误，不删题、不更换分母或 seed。

## 无卡环境复核

```bash
cd /root/autodl-tmp/openi60_protocol_audit_20261121
PYTHON=/root/autodl-tmp/medrax_r55_top4_full848/env/modern/bin/python
export OPENI60_PACKAGE=/root/autodl-tmp/openi60_m5_l1_20261121
export OPENI60_NATIVE="$OPENI60_PACKAGE/native"
export OPENI60_HISTORY="$OPENI60_PACKAGE/runs/openi60_s20261121_fast"

"$PYTHON" -B audit_protocol.py --root "$OPENI60_HISTORY" --out outputs/lexical_recheck
"$PYTHON" -B native_audit.py --root "$OPENI60_HISTORY" --native "$OPENI60_NATIVE" --out outputs/native_recheck
"$PYTHON" -B run_offline_tests.py --out outputs/tests_recheck
"$PYTHON" -B compare_contract_f.py --root "$OPENI60_HISTORY" --native "$OPENI60_NATIVE" --out outputs/contract_f_recheck
```

输出目录使用新名称，避免覆盖已交付的审计结果。仅离线复核，不构造模型、工具或记忆客户端。

## 在全新独立路径重新准备

已有的两套目录无需重复 prepare。需要重新准备时，`--out` 必须使用不存在的新路径：

```bash
cd /root/autodl-tmp/openi60_protocol_audit_20261121
PYTHON=/root/autodl-tmp/medrax_r55_top4_full848/env/modern/bin/python
"$PYTHON" -B prepare_f.py \
  --base-package /root/autodl-tmp/openi60_m5_l1_20261121 \
  --history /root/autodl-tmp/openi60_m5_l1_20261121/runs/openi60_s20261121_fast \
  --out /root/autodl-tmp/openi60_protocol_F_smoke8_new \
  --count 8
"$PYTHON" -B /root/autodl-tmp/openi60_protocol_F_smoke8_new/openi60_cli.py prepare \
  --config /root/autodl-tmp/openi60_protocol_F_smoke8_new/config.F.json
"$PYTHON" -B /root/autodl-tmp/openi60_protocol_F_smoke8_new/openi60_cli.py preflight \
  --work /root/autodl-tmp/openi60_protocol_F_smoke8_new/runs/evaluation
"$PYTHON" -B check_prepared_f.py --package /root/autodl-tmp/openi60_protocol_F_smoke8_new
```

正式流使用另一个全新 `--out` 并将 `--count` 设为 60。stage 只复制运行代码和固定输入清单，prepare 只复制原图、冻结配置；两步均不复制旧预测、旧记忆或反馈，也不执行推理。
