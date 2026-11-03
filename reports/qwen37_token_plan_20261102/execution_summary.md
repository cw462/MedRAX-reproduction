# 本轮执行、成本与时间汇总

阶段0、1、2已全部完成。正常请求 **4,484次**，技术额外请求 **0次**；包括阶段0的2次HiRes接口检查。阶段2引用的D来自阶段1，未增加请求，也未再次计费汇总。阶段2的3,618个终态为 **3,610 completed、3 request_failed、5 unparsed**，因此无合法票的样本是**8个**，不能只写成3个缺答。5个unparsed及3个技术失败均保留，计划投票分母始终为9。[完成状态](metadata/pipeline_status.json)、[阶段2原始成本摘要](phase2/cost_summary.json)

## 三种记账数值

本轮已保存settlement合计 **22.472916**，已记录guard增量 **23.570644**，已知usage计算代理 **21.930532**，单位均为CNY记账代理。输入/输出4/12每百万tokens只用于延续本地预算规则，**不是实际Token Plan费率、真实收费上界、Credits兑换或供应商实扣账单**。实际Credits消耗与实际现金扣款均未知。原阶段成本摘要原样保留；本表不重新验证历史账户账本。

| 阶段 / 组 | 请求数 | 已知输入 / 输出tokens | usage计算代理 | 已保存settlement | 已记录guard增量 | 终态 | 证据 |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| phase0 / D_regression60 | 60 | 59,456 / 4,508 | 0.291920 | 0.291920 | 0.291920 | completed=60 | [phase0/cost_summary.json](phase0/cost_summary.json) |
| phase0 / qwen_highres_smoke | 2 | 2,174 / 139 | 0.010364 | 0.010364 | 0.010364 | completed=2 | [phase0/smoke/evidence/cost_summary.json](phase0/smoke/evidence/cost_summary.json) |
| phase1 / D | 402 | 390,281 / 34,637 | 1.976768 | 1.976768 | 1.976768 | completed=402 | [phase1/cost_summary.json](phase1/cost_summary.json) |
| phase1 / HiRes | 402 | 393,625 / 35,041 | 1.994992 | 1.994992 | 1.994992 | completed=402 | [phase1/cost_summary.json](phase1/cost_summary.json) |
| phase2 / S0 | 3,618 | 3,510,729 / 301,131 | 17.656488 | 18.198872 | 19.296600 | completed=3610, request_failed=3, unparsed=5 | [phase2/cost_summary.json](phase2/cost_summary.json) |
| **去重总计** | **4,484** | **4,356,265 / 375,456** | **21.930532** | **22.472916** | **23.570644** | **4,476 completed、3 request_failed、5 unparsed** | — |

已知usage涵盖4,483次请求；媒体下载超时的1次没有usage。阶段2的Token汇总**已经包含**恢复02与04中已收到响应但结算失败的usage；这两次不能再次加到Token总数。

| 事件 | 已知usage代理 | guard保守占用 | guard减usage | 证据 |
| --- | ---: | ---: | ---: | --- |
| 01 媒体下载超时 | 未知 | 0.548864 | 0.548864仅为无usage的占用，非已知实费差 | [incident](recovery_history/01_media_download_timeout/incident.json) |
| 02 已收响应、结算失败 | 0.003140 | 0.548864 | 0.545724 | [incident](recovery_history/02_ledger_checksum/incident.json) |
| 04 已收响应、结算失败 | 0.003340 | 0.548864 | 0.545524 | [incident](recovery_history/04_ledger_settlement_checksum/incident.json) |

settlement汇总包括媒体超时的0.548864保守占用，但缺少02、04两次结算记录。因此：

```text
已知usage代理 = 22.472916 − 0.548864 + 0.003140 + 0.003340 = 21.930532
guard − settlement = 23.570644 − 22.472916 = 1.097728 = 2 × 0.548864
guard − 已知usage = 0.548864 + 0.545724 + 0.545524 = 1.640112
```

这里第二行比较的是缺失结算记录的完整保守占用；第三行才区分未知usage的媒体占用与两次已知usage之外的保守差。阶段2对应值为saved settlement 18.198872、guard 19.296600、已知usage代理17.656488；这些来源均不被改写。

沿用原增量授权200，前轮已公开占用3.163412，加本轮guard增量23.570644后占用 **26.734056**，剩余 **173.265944** 记账代理。没有追加预算。这里只计算该次增量授权，不披露账户总额或完整私有账本上限。[预算协议](protocol.md)

## 实际执行时间

北京时间从原[启动回执](launch.json)的 **2026-11-02 23:44:41.108080** 到[流水线完成](metadata/pipeline_status.json)的 **2026-11-03 09:19:49.033146**，总墙钟为 **09:35:07.925066（34507.925066秒）**。首次样本开始在23:44:41.645746，比启动晚0.537666秒；最后样本结束在09:19:42.167522，随后6.865624秒至流水线完成。因此主墙钟起点采用原启动回执，不用首样本时间替代。

下表以保存的停止事件至成功恢复事件计算；同一故障的失败恢复尝试不产生新的独立停机段。所有时点为北京时间，保留原记录的微秒精度。

| 区间 | 停止 | 成功恢复 | 停机秒数 | 时点证据及字段 |
| --- | --- | --- | ---: | --- |
| 01_media_download_timeout | 2026-11-03 01:12:30.510516 | 2026-11-03 01:18:54.036922 | 383.526406 | [stopped_utc](recovery_history/01_media_download_timeout/incident.json) → [resumed_utc](recovery_history/01_media_download_timeout/incident.json) |
| 02_ledger_checksum | 2026-11-03 01:37:45.445655 | 2026-11-03 01:43:25.874502 | 340.428847 | [stopped_utc](recovery_history/02_ledger_checksum/incident.json) → [resumed_utc](recovery_history/02_ledger_checksum/incident.json) |
| 03_unsent_reservation_checksum | 2026-11-03 01:50:52.289310 | 2026-11-03 02:00:43.701843 | 591.412533 | [stopped_utc](recovery_history/03_unsent_reservation_checksum/incident.json) → [resumed_utc](recovery_history/03_unsent_reservation_checksum/incident.json) |
| 04_blocker_through_05_successful_resume | 2026-11-03 02:41:41.588425 | 2026-11-03 08:31:59.688304 | 21018.099879 | [stopped_utc](recovery_history/04_ledger_settlement_checksum/incident.json) → [resume_utc](recovery_history/05_authorized_ledger_diagnosis/recovery_progress.json) |
| 06_operator_pause_and_validation_switch | 2026-11-03 08:42:53.417267 | 2026-11-03 08:45:35.864819 | 162.447552 | [fatal_error.utc](recovery_history/06_disable_ledger_validation/operator_pause_receipt.json) → [resumed_utc](recovery_history/06_disable_ledger_validation/incident.json) |

五段停机合计 **06:14:55.915217（22495.915217秒）**。恢复04于02:44:58失败、恢复05于08:29:04完成定点修复，都在02:41:41至08:31:59这一连续停机内；只有成功恢复才结束该区间。修订06采用worker fatal时点08:42:53.417267；08:42:51.193359取得计数锁时允许上一请求正常完成，不提前把在途调用时间计入停机。

总墙钟减去上述停机为 **03:20:12.009849（12012.009849秒，约3小时20分12秒）**。这是按已保存事件计算的**非停机运行窗口**，仍含API及网络等待、序列化、阶段切换和最终离线评分；不是模型纯计算耗时、CPU耗时、API耗时之和或仅推理吞吐时间，也不包含之后下载与发布报告的时间。没有独立调度器轨迹可用于进一步细分。

## 恢复与保护边界

恢复01、02、04对应已发出的请求，失败终态和原响应保留，均未重发。恢复03与修订06发生在下一请求发送前，恢复后执行的是尚未发出的计划样本，**不新增缺答、不新增补票**。5个unparsed保持原样，没有格式失败付费重试。[恢复记录](recovery_history/01_media_download_timeout/incident.json)、[未发送恢复03](recovery_history/03_unsent_reservation_checksum/incident.json)、[切换回执06](recovery_history/06_disable_ledger_validation/operator_pause_receipt.json)

原冻结实现为`3916851437e1177f15f358bf49641b3e34844926`；实际运行经过已记录的恢复修订。用户明确要求取消账本检验后，在阶段2已保存 **2,901个终态**、下一请求尚未预留和发送时暂停；**08:45:35.864819**新进程恢复后，对余下717个样本生效。最终修订`096a7586ae43cbd9e4acf1e729083236ee648f0f`关闭V12启动/提交checksum、schema、策略快照、全表金额一致性及继承账本checksum检查，不能宣称全程校验保持不变或后段历史账本一致性已验证。[修订06](recovery_history/06_disable_ledger_validation/runtime_amendment.json)

金额上限、费用继承、预留与结算算术、可读JSON及必要字段、身份anchor、进程锁、重复请求拒绝、token/请求次数硬限制及pending保守恢复继续保留；原ProviderLedger未改。模型、输入、提示、温度、投票和既有终态不变。定点修复及管理修订不能当作医学方法改进或准确率收益。

本汇总只读取公开报告目录内的成本摘要、[两个smoke预测](phase0/smoke/evidence/arms/qwen_highres_smoke/predictions.jsonl)、启动/完成元数据与恢复记录；没有访问账户ledger、重跑推理或评分、追加测试或全量哈希。结构化数据见[execution_summary.json](execution_summary.json)，生成脚本见[summarize_qwen37_execution.py](../../experiments/summarize_qwen37_execution.py)。

## 从公开材料复现汇总

克隆仓库后，在仓库根目录执行以下命令即可重新生成本Markdown与JSON，仅需Python标准库，无需私有运行目录、凭据或模型API：

```sh
python -X utf8 experiments/summarize_qwen37_execution.py --report-root reports/qwen37_token_plan_20261102
```

省略`--report-root`时默认读取脚本所属仓库的同一公开目录；指定参数可读取其他位置的完整报告副本。脚本仅重新汇总保存记录，不重新评分或推理。
