# 运行修订 01：移除账本原始字节一致性停机

2026-10-31 12:40 的第 6 个 B 终态记录 MonetaryStop → LedgerIntegrityError（raw-byte mismatch）。前 6 个共享首读和 B 终态保留，第 6 个 B 的控制器回退继续单列，不重跑或改写。

用户明确要求删除运行中的原始字节一致性停机。v12_ledger.py 的子类仅将 _check_disk 改为 _check_open，run_v12_resume.py 注入该子类后调用原冻结 runner。原账本身份、互斥锁、费用上限、金额验证、预留/结算及 pending 保守恢复规则仍继承；固定输入、模型、提示、调用上限及 B→A 顺序不变。修订来源和实际应用记录见 [修订 JSON](runtime_amendments/01_ledger_byte_check_removed.json)，停机证据见 recovery_history/01_ledger_byte_check_removed/ 的明确允许文件。

恢复过程已确认：12:52 新进程 PID 3130741 启动，12:53 共享首答增至 7/60、正在 B7。原冻结 runner/provider 源码和 effective_config.json 未改，运行修订单独保存。旧 B6 fatal 属于历史停机记录；不重加字节检查或替代扫描。

原 pending 预留额为 0.069056 CNY；本次可见 usage 按既有价格估算为 0.023076 CNY，差额为 0.045980 CNY。保留 pending 后，原开账恢复机制按预留额保守计账。这三项分别是预留额、用量估算和两者差额，不能将保守预留恢复额称为供应商实际账单；也不能直接加到上下文费用中造成重复计数。最终应并列保存上下文费用合计和原账本本轮增量，并据实际保存的结算记录说明差异。

本说明记录故障、授权修订、已确认的恢复进度及费用口径；恢复运行不等于完成实验，本说明也不独立证明具体结算已落盘。后续完成情况和费用以保存的进程/状态/终态、独立评分及结算摘要为准。源预测、历史停机记录和原账本均不由导出器改写或补记。

## 恢复记录 02：费用预留 schema 异常

2026-10-31 北京时间 14:36，A46 在首次费用预留时报 Invalid reservation schema，模型和工具调用均为 0，控制器保留合法首答。一次定向定位显示已落盘 reservation 字段完整、最后请求已 settled，本次报错的候选预留未落盘；进程内根因尚未确定，不能称为坏账或宣称根因已修复。随后沿用同一原接口和 run_v12_resume.py 重新启动 PID 3193115，从 A47 继续，前 106 个分支终态保留，费用和调用上限不变。历史 fatal/status/log/PID/exitcode 及 recovery_note.json 明确保存在 recovery_history/02_reservation_schema/；本导出只保留这些记录，不改写原预测或账本。
