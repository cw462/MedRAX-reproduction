# V12 实验记录

2026-10-31 已部署并启动 V12，代码目录为独立的 `code_v12`，运行目录为 `runs/v12_ab60`，监控任务 `medrax-v12-b-a` 已激活。12:40 第 6 个 B 分支因账本 raw-byte mismatch 停止；按用户明确要求移除该运行时字节一致性停机后，12:52 已由新进程 PID 3130741 恢复，12:53 共享首答为 7/60、正在 B7。原 6 个共享首读和 B 终态保留，B6 的失败回退不重跑。当前尚未评分，没有 V12 正确率或提升结论；后续实际进度以运行状态及终态记录为准。

- [完整协议](protocol.md)：用户六项要求的实现、两组差异、调用上限、证据与答案隔离、失败回退、评分和发布规则。
- [运行配置](../../configs/v12_ab60.json)：`qwen3-vl-plus`，完整 60 题，B 先于 A，共享首次读图 1 次，每组规划/针对性读图/最终求解各 1 次，每组最多 2 个动作。
- [运行入口](../../experiments/run_v12_ab.py)、[证据解析](../../experiments/v12_evidence.py)、[鉴别检索](../../experiments/v12_retrieval.py)、[独立评分器](../../experiments/v12_metrics.py)。
- [恢复包装入口](../../experiments/run_v12_resume.py)及 [V12 账本子类](../../experiments/v12_ledger.py)：仅移除运行时原始字节相等要求，沿用原费用上限、身份、锁、金额验证、预留/结算和 pending 恢复。原冻结 runner/provider 源码与 `effective_config.json` 未改；修订另记 `runtime_amendments/01_ledger_byte_check_removed.json`，停机证据保存在 `recovery_history/01_ledger_byte_check_removed/`。

分别保留首答、取证后候选与最终答案；首答不进入后续模型输入，候选选择不进入最终求解。最终调用失败时，控制器保留合法首答的情况单独标记和报告。参考标签仅在全部生成终态齐全后由独立评分器读取，费用上限沿用原账本，不重置或提高。

本次故障的 pending 预留额为 0.069056 CNY，可见 usage 按既有价格估算为 0.023076 CNY，差额为 0.045980 CNY。原开账恢复按预留额保守计账；这与用量估算、供应商实际账单分别报告，不能重复加到上下文费用中。最终发布将保留运行修订、历史 fatal/status/log/PID/exitcode 和费用差额说明；本次已恢复运行不等于实验或评分已完成。

完成后补充完整分母成绩、纠正/误改/净增益、七类结果、逐题过程与错误分析、成本和耗时，并按用户要求主动上传 GitHub。V10 为历史对照；反复使用的 60 题属于开发集。独立的 `qwen3.8-max` 缓存裁决实验不并入本报告。
