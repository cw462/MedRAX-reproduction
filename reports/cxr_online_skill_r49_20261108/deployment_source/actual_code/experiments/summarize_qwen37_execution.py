"""Summarize saved execution metadata without inference, scoring, or account reads.

Reads only published phase cost summaries, the two smoke predictions,
pipeline metadata, launch receipt, and recovery records. Does not open
account ledgers, scan hashes, change predictions, or recompute benchmark scores.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path


NAME = "qwen37_token_plan_20261102"
D = Decimal
BJ = timezone(timedelta(hours=8))


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def money(value):
    return f"{D(value):.6f}"


def dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def seconds(start, end):
    delta = dt(end) - dt(start)
    return D(delta.days * 86400 + delta.seconds) + D(delta.microseconds) / 1000000


def local(value):
    return dt(value).astimezone(BJ).isoformat(timespec="microseconds")


def hms(value):
    value = D(value)
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    return f"{hours:02d}:{minutes:02d}:{value % 60:09.6f}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-root", type=Path,
        default=Path(__file__).resolve().parents[1] / "reports" / NAME,
        help="Published report directory; all inputs and both outputs stay here.",
    )
    args = parser.parse_args()
    report = args.report_root.resolve()
    protocol = read(report / "metadata/pipeline_protocol.json")
    status = read(report / "metadata/pipeline_status.json")
    launch = read(report / "launch.json")
    incident_names = [
        "01_media_download_timeout", "02_ledger_checksum",
        "03_unsent_reservation_checksum", "04_ledger_settlement_checksum",
        "05_authorized_ledger_diagnosis", "06_disable_ledger_validation",
    ]
    incidents = {name: read(report / "recovery_history" / name / "incident.json")
                 for name in incident_names}
    receipts = read(report / "recovery_history/06_disable_ledger_validation/operator_pause_receipt.json")
    amendment_files = [
        "01_media_download_timeout.json", "01_media_download_timeout_resume.json",
        "03_unsent_reservation_recovery.json", "05_acknowledged_ledger_startup_resume.json",
        "06_disable_ledger_validation.json",
    ]
    amendments = {name: read(report / "metadata/runtime_amendments" / name)
                  for name in amendment_files}
    phase_costs = {p: read(report / p / "cost_summary.json")
                   for p in ("phase0", "phase1", "phase2")}
    arms = []
    for phase, arm in [("phase0", "D_regression60"), ("phase1", "D"),
                       ("phase1", "HiRes"), ("phase2", "S0")]:
        source = phase_costs[phase]["arms"][arm]
        arms.append({
            "phase": phase, "arm": arm, "saved_attempts": source["saved_attempts"],
            "technical_extra_requests": source["technical_extra_requests"],
            "sample_status_counts": source["sample_status_counts"],
            "input_tokens": source["input_tokens"], "output_tokens": source["output_tokens"],
            "saved_settlements_proxy_cny": source["saved_settlement_cny"],
            "recorded_guard_increment_proxy_cny": source["saved_guard_run_increment_cny"],
            "settlement_missing_attempts": source["settlement_missing_attempts"],
            "first_started_utc": source["first_started_utc"],
            "last_ended_utc": source["last_ended_utc"],
            "sample_window_seconds": money(seconds(source["first_started_utc"], source["last_ended_utc"])),
            "source": f"{phase}/cost_summary.json",
        })
    smoke_qids = ["10569_8353800725393", "11624_8353800763402"]
    smoke_source = "phase0/smoke/evidence/arms/qwen_highres_smoke/predictions.jsonl"
    smoke = [json.loads(line) for line in (report / smoke_source).read_text(encoding="utf-8-sig").splitlines()
             if line.strip()]
    assert len(smoke) == 2 and {t["question_id"] for t in smoke} == set(smoke_qids)
    smoke_attempts = [attempt for terminal in smoke for attempt in terminal["attempts"]]
    smoke_cost = sum(D(a["settlement"]["charged_cny"]) for a in smoke_attempts)
    smoke_guard = read(report / "phase0/smoke/evidence/cost_summary.json")["arms"]["qwen_highres_smoke"]
    arms.insert(1, {
        "phase": "phase0", "arm": "qwen_highres_smoke", "saved_attempts": len(smoke_attempts),
        "technical_extra_requests": sum(len(t["attempts"]) - 1 for t in smoke),
        "sample_status_counts": dict(Counter(t["status"] for t in smoke)),
        "input_tokens": sum(a["usage"]["prompt_tokens"] for a in smoke_attempts),
        "output_tokens": sum(a["usage"]["completion_tokens"] for a in smoke_attempts),
        "saved_settlements_proxy_cny": money(smoke_cost),
        "recorded_guard_increment_proxy_cny": smoke_guard["guard_run_increment_cny"],
        "settlement_missing_attempts": 0,
        "first_started_utc": min(t["started_utc"] for t in smoke),
        "last_ended_utc": max(t["ended_utc"] for t in smoke),
        "sample_window_seconds": money(seconds(min(t["started_utc"] for t in smoke), max(t["ended_utc"] for t in smoke))),
        "source": "phase0/smoke/evidence/cost_summary.json",
        "prediction_source": smoke_source,
    })
    for arm in arms:
        arm["known_usage_proxy_cny"] = money((D(arm["input_tokens"]) * 4 + D(arm["output_tokens"]) * 12) / 1000000)
    sample_counts = Counter()
    for arm in arms:
        sample_counts.update(arm["sample_status_counts"])
    saved = sum(D(a["saved_settlements_proxy_cny"]) for a in arms)
    guard = sum(D(a["recorded_guard_increment_proxy_cny"]) for a in arms)
    usage = sum(D(a["known_usage_proxy_cny"]) for a in arms)
    media, failure2, failure4 = [incidents[incident_names[i]] for i in (0, 1, 3)]
    known_failed_usage = D(failure2["usage_proxy_cost_cny"]) + D(failure4["usage_proxy_cost_cny"])
    media_unknown = D(media["conservative_proxy_charge_cny"])
    prior_authorized_spend = D("3.163412")  # Already disclosed in protocol.md; not an account balance.
    original_budget = D(protocol["original_authorized_budget_cny"])

    downtime = []
    for name in incident_names[:3]:
        event = incidents[name]
        downtime.append({"event": name, "start_utc": event["stopped_utc"],
                         "end_utc": event["resumed_utc"],
                         "start_source": f"recovery_history/{name}/incident.json#stopped_utc",
                         "end_source": f"recovery_history/{name}/incident.json#resumed_utc"})
    downtime.append({
        "event": "04_blocker_through_05_successful_resume",
        "start_utc": failure4["stopped_utc"],
        "end_utc": incidents[incident_names[4]]["recovery_progress"]["resume_utc"],
        "start_source": "recovery_history/04_ledger_settlement_checksum/incident.json#stopped_utc",
        "end_source": "recovery_history/05_authorized_ledger_diagnosis/recovery_progress.json#resume_utc",
        "note": "The failed 02:44:58 resume and 08:29:04 repair are inside this single interval; neither ends downtime.",
    })
    downtime.append({
        "event": "06_operator_pause_and_validation_switch",
        "start_utc": receipts["fatal_error"]["utc"],
        "end_utc": incidents[incident_names[5]]["resumed_utc"],
        "start_source": "recovery_history/06_disable_ledger_validation/operator_pause_receipt.json#fatal_error.utc",
        "end_source": "recovery_history/06_disable_ledger_validation/incident.json#resumed_utc",
        "note": "Uses worker fatal/exit event, not the earlier lock acquisition while the preceding call was allowed to finish.",
    })
    for interval in downtime:
        interval["start_beijing"] = local(interval["start_utc"])
        interval["end_beijing"] = local(interval["end_utc"])
        interval["seconds"] = money(seconds(interval["start_utc"], interval["end_utc"]))
        interval["duration_hms"] = hms(interval["seconds"])
    wall = seconds(launch["started_utc"], status["updated_utc"])
    down = sum(D(i["seconds"]) for i in downtime)
    active = wall - down
    summary = {
        "schema_version": "qwen37-execution-summary-v1", "experiment": NAME,
        "completion": {"pipeline_status": status["status"], "completed_phases": status["completed_phases"],
                       "source": "metadata/pipeline_status.json", "automatic_further_paid_phase": False},
        "accounting_scope": "This Qwen3.7 run only; phase2 D is the phase1 anchor and is counted once. Includes two phase0 smoke requests.",
        "requests": {"normal_planned": protocol["normal_requests"],
                     "saved_attempts": sum(a["saved_attempts"] for a in arms),
                     "technical_extra_requests": sum(a["technical_extra_requests"] for a in arms),
                     "sample_status_counts": dict(sample_counts),
                     "phase2_status_counts": arms[-1]["sample_status_counts"],
                     "phase2_missing_or_unparsed_samples": 8,
                     "phase2_planned_vote_denominator_per_question": 9,
                     "unsent_recovery_events_add_missing_answers": False,
                     "issued_failures_01_02_04_resent": False},
        "costs": {
            "unit": "CNY-denominated bookkeeping proxy only",
            "input_proxy_per_million_tokens": "4", "output_proxy_per_million_tokens": "12",
            "actual_token_plan_credits": None, "actual_provider_cash_charge_cny": None,
            "not_actual_rate_not_charge_upper_bound_not_credits_conversion": True,
            "saved_settlements_proxy_cny": money(saved),
            "recorded_guard_increment_proxy_cny": money(guard),
            "known_usage_proxy_cny": money(usage),
            "known_usage_input_tokens": sum(a["input_tokens"] for a in arms),
            "known_usage_output_tokens": sum(a["output_tokens"] for a in arms),
            "known_usage_request_count": 4483, "request_count_without_usage": 1,
            "saved_settlement_missing_attempts": 2,
            "settlements_include_media_unknown_proxy_cny": money(media_unknown),
            "settlements_exclude_known_usage_failure02_proxy_cny": failure2["usage_proxy_cost_cny"],
            "settlements_exclude_known_usage_failure04_proxy_cny": failure4["usage_proxy_cost_cny"],
            "known_usage_reconciliation": "saved_settlements - media_unknown_reservation + failure02_usage + failure04_usage",
            "phase2_token_totals_already_include_failure02_and_failure04_usage": True,
            "guard_minus_saved_settlements_proxy_cny": money(guard - saved),
            "guard_minus_known_usage_proxy_cny": money(guard - usage),
            "guard_minus_usage_components_proxy_cny": {
                "media01_no_usage_conservative_reservation": money(media_unknown),
                "failure02_conservative_minus_usage": failure2["conservative_minus_usage_proxy_cny"],
                "failure04_conservative_minus_usage": failure4["conservative_minus_usage_proxy_cny"],
            },
            "definitions": {
                "saved_settlements": "Sum of saved per-attempt settlements; includes media01 conservative charge, excludes settlements absent for failures02/04.",
                "recorded_guard_increment": "Sum of already saved per-run guard increments, including conservative pending recovery. Not a fresh account-ledger reconciliation or assurance of historical consistency.",
                "known_usage": "4/12 proxy computed from recorded usage, including responses02/04, excluding media01 where usage is absent; not complete provider billing.",
            },
        },
        "incremental_authorization": {
            "original_authorized_proxy_budget_cny": money(original_budget),
            "old_run_proxy_spend_within_same_authorization_cny": money(prior_authorized_spend),
            "this_run_recorded_guard_increment_proxy_cny": money(guard),
            "combined_proxy_occupation_cny": money(prior_authorized_spend + guard),
            "remaining_authorized_proxy_budget_cny": money(original_budget - prior_authorized_spend - guard),
            "additional_authorization_cny": protocol["additional_budget_granted_cny"],
            "source": "protocol.md#预算与恢复",
            "note": "Only the existing 200 incremental authorization; no private account total, account balance or full cumulative ledger cap.",
        },
        "timing": {
            "timezone": "Asia/Shanghai", "launch_utc": launch["started_utc"],
            "launch_beijing": local(launch["started_utc"]),
            "completed_utc": status["updated_utc"], "completed_beijing": local(status["updated_utc"]),
            "wall_seconds": money(wall), "wall_hms": hms(wall),
            "recorded_downtime_seconds": money(down), "recorded_downtime_hms": hms(down),
            "wall_minus_recorded_downtime_seconds": money(active), "wall_minus_recorded_downtime_hms": hms(active),
            "launch_source": "launch.json#started_utc", "completed_source": "metadata/pipeline_status.json#updated_utc",
            "first_sample_started_utc": arms[0]["first_started_utc"],
            "launch_to_first_sample_seconds": money(seconds(launch["started_utc"], arms[0]["first_started_utc"])),
            "last_sample_ended_utc": arms[-1]["last_ended_utc"],
            "last_sample_to_pipeline_complete_seconds": money(seconds(arms[-1]["last_ended_utc"], status["updated_utc"])),
            "definition": "Wall time is launch receipt to completed pipeline status. Downtime is the union of five saved stopped-to-successful-resume intervals. Wall minus downtime includes API/network waits, serialization, phase transitions and final offline scoring; it is not model compute time, API elapsed-time sum, CPU time or throughput-only time. Exact arithmetic uses saved event timestamps, not an independent scheduler trace.",
            "downtime_intervals": downtime,
        },
        "runtime_amendments": {
            "original_implementation_commit": protocol["implementation_commit"],
            "final_runtime_revision": incidents[incident_names[5]]["runtime_revision"],
            "validation_disabled_by_explicit_user_authorization": True,
            "effective_after_phase2_terminal_count": 2901,
            "remaining_phase2_samples_after_switch": 717,
            "effective_on_resume_utc": incidents[incident_names[5]]["resumed_utc"],
            "disabled": incidents[incident_names[5]]["disabled"],
            "retained": incidents[incident_names[5]]["retained"],
            "historical_ledger_consistency_validated_after_switch": False,
            "predictions_rewritten": False, "generation_protocol_changed": False,
            "unsent_events03_06_create_missing_answers": False,
            "request_failed_terminals_retained": 3, "unparsed_terminals_retained": 5,
            "source": "recovery_history/06_disable_ledger_validation/runtime_amendment.json",
            "read_metadata_files": [f"metadata/runtime_amendments/{name}" for name in amendments],
        },
        "arms": arms,
        "summary_generation": {"inference_calls": 0, "score_reruns": 0, "tests_rerun": 0,
                               "account_ledger_reads": 0, "full_hash_scans": 0,
                               "input_scope": "Published files under --report-root only; Python standard library; no private run data or credentials needed.",
                               "command_from_repository_root": "python -X utf8 experiments/summarize_qwen37_execution.py --report-root reports/qwen37_token_plan_20261102",
                               "original_cost_summaries_modified": False,
                               "script": "../../experiments/summarize_qwen37_execution.py"},
    }
    # Content consistency checks only: no tests, scoring, hashing, or account reads.
    assert status["status"] == "completed" and summary["requests"]["saved_attempts"] == 4484
    assert saved - media_unknown + known_failed_usage == usage
    assert guard - usage == media_unknown + D(failure2["conservative_minus_usage_proxy_cny"]) + D(failure4["conservative_minus_usage_proxy_cny"])
    assert sample_counts == Counter(completed=4476, request_failed=3, unparsed=5)
    report.mkdir(parents=True, exist_ok=True)
    (report / "execution_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    arm_rows = []
    for a in arms:
        counts = a["sample_status_counts"]
        terminal_text = ", ".join(f"{key}={value}" for key, value in counts.items())
        arm_rows.append(f"| {a['phase']} / {a['arm']} | {a['saved_attempts']:,} | {a['input_tokens']:,} / {a['output_tokens']:,} | {a['known_usage_proxy_cny']} | {a['saved_settlements_proxy_cny']} | {a['recorded_guard_increment_proxy_cny']} | {terminal_text} | [{a['source']}]({a['source']}) |")
    downtime_rows = []
    for i in downtime:
        start_path, start_field = i["start_source"].split("#", 1)
        end_path, end_field = i["end_source"].split("#", 1)
        downtime_rows.append(f"| {i['event']} | {i['start_beijing'].replace('T', ' ').replace('+08:00', '')} | {i['end_beijing'].replace('T', ' ').replace('+08:00', '')} | {i['seconds']} | [{start_field}]({start_path}) → [{end_field}]({end_path}) |")
    md = f"""# 本轮执行、成本与时间汇总

阶段0、1、2已全部完成。正常请求 **4,484次**，技术额外请求 **0次**；包括阶段0的2次HiRes接口检查。阶段2引用的D来自阶段1，未增加请求，也未再次计费汇总。阶段2的3,618个终态为 **3,610 completed、3 request_failed、5 unparsed**，因此无合法票的样本是**8个**，不能只写成3个缺答。5个unparsed及3个技术失败均保留，计划投票分母始终为9。[完成状态](metadata/pipeline_status.json)、[阶段2原始成本摘要](phase2/cost_summary.json)

## 三种记账数值

本轮已保存settlement合计 **{money(saved)}**，已记录guard增量 **{money(guard)}**，已知usage计算代理 **{money(usage)}**，单位均为CNY记账代理。输入/输出4/12每百万tokens只用于延续本地预算规则，**不是实际Token Plan费率、真实收费上界、Credits兑换或供应商实扣账单**。实际Credits消耗与实际现金扣款均未知。原阶段成本摘要原样保留；本表不重新验证历史账户账本。

| 阶段 / 组 | 请求数 | 已知输入 / 输出tokens | usage计算代理 | 已保存settlement | 已记录guard增量 | 终态 | 证据 |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
{chr(10).join(arm_rows)}
| **去重总计** | **4,484** | **4,356,265 / 375,456** | **{money(usage)}** | **{money(saved)}** | **{money(guard)}** | **4,476 completed、3 request_failed、5 unparsed** | — |

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

北京时间从原[启动回执](launch.json)的 **2026-11-02 23:44:41.108080** 到[流水线完成](metadata/pipeline_status.json)的 **2026-11-03 09:19:49.033146**，总墙钟为 **{hms(wall)}（{money(wall)}秒）**。首次样本开始在23:44:41.645746，比启动晚0.537666秒；最后样本结束在09:19:42.167522，随后6.865624秒至流水线完成。因此主墙钟起点采用原启动回执，不用首样本时间替代。

下表以保存的停止事件至成功恢复事件计算；同一故障的失败恢复尝试不产生新的独立停机段。所有时点为北京时间，保留原记录的微秒精度。

| 区间 | 停止 | 成功恢复 | 停机秒数 | 时点证据及字段 |
| --- | --- | --- | ---: | --- |
{chr(10).join(downtime_rows)}

五段停机合计 **{hms(down)}（{money(down)}秒）**。恢复04于02:44:58失败、恢复05于08:29:04完成定点修复，都在02:41:41至08:31:59这一连续停机内；只有成功恢复才结束该区间。修订06采用worker fatal时点08:42:53.417267；08:42:51.193359取得计数锁时允许上一请求正常完成，不提前把在途调用时间计入停机。

总墙钟减去上述停机为 **{hms(active)}（{money(active)}秒，约3小时20分12秒）**。这是按已保存事件计算的**非停机运行窗口**，仍含API及网络等待、序列化、阶段切换和最终离线评分；不是模型纯计算耗时、CPU耗时、API耗时之和或仅推理吞吐时间，也不包含之后下载与发布报告的时间。没有独立调度器轨迹可用于进一步细分。

## 恢复与保护边界

恢复01、02、04对应已发出的请求，失败终态和原响应保留，均未重发。恢复03与修订06发生在下一请求发送前，恢复后执行的是尚未发出的计划样本，**不新增缺答、不新增补票**。5个unparsed保持原样，没有格式失败付费重试。[恢复记录](recovery_history/01_media_download_timeout/incident.json)、[未发送恢复03](recovery_history/03_unsent_reservation_checksum/incident.json)、[切换回执06](recovery_history/06_disable_ledger_validation/operator_pause_receipt.json)

原冻结实现为`{protocol['implementation_commit']}`；实际运行经过已记录的恢复修订。用户明确要求取消账本检验后，在阶段2已保存 **2,901个终态**、下一请求尚未预留和发送时暂停；**08:45:35.864819**新进程恢复后，对余下717个样本生效。最终修订`{incidents[incident_names[5]]['runtime_revision']}`关闭V12启动/提交checksum、schema、策略快照、全表金额一致性及继承账本checksum检查，不能宣称全程校验保持不变或后段历史账本一致性已验证。[修订06](recovery_history/06_disable_ledger_validation/runtime_amendment.json)

金额上限、费用继承、预留与结算算术、可读JSON及必要字段、身份anchor、进程锁、重复请求拒绝、token/请求次数硬限制及pending保守恢复继续保留；原ProviderLedger未改。模型、输入、提示、温度、投票和既有终态不变。定点修复及管理修订不能当作医学方法改进或准确率收益。

本汇总只读取公开报告目录内的成本摘要、[两个smoke预测](phase0/smoke/evidence/arms/qwen_highres_smoke/predictions.jsonl)、启动/完成元数据与恢复记录；没有访问账户ledger、重跑推理或评分、追加测试或全量哈希。结构化数据见[execution_summary.json](execution_summary.json)，生成脚本见[summarize_qwen37_execution.py](../../experiments/summarize_qwen37_execution.py)。

## 从公开材料复现汇总

克隆仓库后，在仓库根目录执行以下命令即可重新生成本Markdown与JSON，仅需Python标准库，无需私有运行目录、凭据或模型API：

```sh
python -X utf8 experiments/summarize_qwen37_execution.py --report-root reports/qwen37_token_plan_20261102
```

省略`--report-root`时默认读取脚本所属仓库的同一公开目录；指定参数可读取其他位置的完整报告副本。脚本仅重新汇总保存记录，不重新评分或推理。
"""
    (report / "execution_summary.md").write_text(md, encoding="utf-8")
    print(json.dumps({"requests": summary["requests"]["saved_attempts"],
                      "saved_settlements_proxy_cny": money(saved), "recorded_guard_increment_proxy_cny": money(guard),
                      "known_usage_proxy_cny": money(usage), "wall_seconds": money(wall),
                      "downtime_seconds": money(down), "non_downtime_window_seconds": money(active)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
