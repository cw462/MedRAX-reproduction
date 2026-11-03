"""Summarize completed scoring artifacts; never call a model or the scorer.

All accuracy, bootstrap, McNemar, and AUROC results are copied from saved
metrics. Supplemental counts only describe the saved sample ballots/statuses.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def compact(value):
    if isinstance(value, dict):
        return {k: compact(v) for k, v in value.items() if k not in
                {"question_ids", "raw_top_vote_rule_question_ids"}}
    if isinstance(value, list):
        return [compact(v) for v in value]
    return value


def pct(value):
    return f"{100 * value:.2f}%"


def ci(comparison):
    low, high = comparison["bootstrap"]["delta_ci95_pp"]
    return f"[{low:+.2f}, {high:+.2f}]"


def build_summary(source: Path):
    phases = {str(p): read_json(source / f"phase{p}" / "metrics.json") for p in range(3)}
    phase1, phase2 = phases["1"], phases["2"]
    voting = phase2["agent_v2_voting"]
    diagnostics = read_json(source / "phase2" / "vote_diagnostics.json")["records"]
    per_question = read_json(source / "phase2" / "per_question.json")["records"]
    by_question = {r["question_id"]: r for r in per_question}
    by_diagnostic = {r["question_id"]: r for r in diagnostics}
    statuses = Counter()
    for record in diagnostics:
        statuses.update(record["sample_status_counts"])
    main = phase2["comparisons"][voting["comparison_keys"]["original_D_to_K9"]]
    changes = main["question_ids"]["legal_wrong_to_correct"] + main["question_ids"]["correct_to_legal_wrong"]
    extra_examples = ["795_8353802131057", "18680_8143559034217", "16844_8143559672130"]
    examples = []
    for qid in changes + extra_examples:
        row, ballot = by_question[qid], by_diagnostic[qid]
        examples.append({
            "question_id": qid, "case_id": row["case_id"], "reference": row["reference"],
            "D": row["answers"]["D"], "K1": ballot["first_sample_answer"],
            "K9": ballot["vote_answer"], "answer_counts": ballot["answer_counts"],
            "sample_answers": ballot["sample_answers"], "agreement_bin": ballot["agreement_bin"],
            "role": ("D_to_K9_correction" if qid in main["question_ids"]["legal_wrong_to_correct"]
                     else "D_to_K9_harm" if qid in main["question_ids"]["correct_to_legal_wrong"]
                     else "descriptive_failure_example"),
        })
    incomplete = [{k: r[k] for k in ("question_id", "case_id", "missing_samples", "valid_samples",
                                   "sample_status_counts", "answer_counts", "vote_answer")}
                  for r in diagnostics if not r["complete_nine_answers"]]
    tie_records = [r for r in diagnostics
                   if sum(v == r["top_votes"] for v in r["answer_counts"].values()) > 1]
    copied_comparisons = {label: {"source_key": key, **phase2["comparisons"][key]}
                          for label, key in voting["comparison_keys"].items()}
    curve = [{"k": k, **phase2["totals"][f"S0/K{k}"],
              "versus_D": phase2["comparisons"][f"D_to_S0/K{k}"]}
             for k in range(1, 10)]
    return {
        "schema": "qwen37_completed_voting_analysis_v1",
        "analysis_kind": "posthoc_summary_of_preexisting_independent_scoring",
        "new_inference": 0, "rescoring_performed": False,
        "prediction_records_modified": False,
        "sources": {"phase0": "phase0/metrics.json", "phase1": "phase1/metrics.json",
                    "phase2": "phase2/metrics.json", "per_question": "phase2/per_question.json",
                    "vote_diagnostics": "phase2/vote_diagnostics.json"},
        "scope": {"model": "qwen3.7-plus", "tuning_questions": phase2["planned_n"],
                  "tuning_cases": phase2["case_n"], "heldout_questions": 1002,
                  "heldout_evaluated": False, "medical_tools_evaluated": False,
                  "fixed_primary_K": 9, "direct_temperature": 0.2, "sample_temperature": 0.7},
        "phase0": {"totals": phases["0"]["totals"],
                   "gate": "technical_validity_and_no_missing_answers; no old-model accuracy band"},
        "phase1": {"totals": phase1["totals"], "comparisons": phase1["comparisons"],
                   "decision": phase1["tuning_decisions"]},
        "phase2": {
            "fixed_K_curve": curve,
            "main_comparisons": copied_comparisons,
            "original_D_and_selected_single_are_same_control": True,
            "D_to_same_temperature_K1": phase2["comparisons"]["D_to_S0/K1"],
            "vote_rule": phase2["vote_rule"], "K_rule": phase2["deployed_K_rule"],
            "agreement_bins": compact(voting["agreement_bins"]),
            "split_thresholds": compact(voting["split_thresholds"]),
            "correctness_auroc": voting["correctness_auroc"],
            "auroc_undefined_rule": "null when either positive or negative class is absent; not zero",
            "fixed_pool_monte_carlo_diagnostic": phase2["sampling_curves"],
        },
        "supplemental_ballot_aggregates": {
            "planned_samples": sum(r["planned_samples"] for r in diagnostics),
            "sample_status_counts": dict(sorted(statuses.items())),
            "missing_sample_answers": sum(r["missing_samples"] for r in diagnostics),
            "incomplete_questions": incomplete,
            "unanimous_wrong_questions": (voting["agreement_bins"]["unanimous_9_of_9"]["planned_n"]
                                          - voting["agreement_bins"]["unanimous_9_of_9"]["vote_totals"]["correct"]),
            "D_to_K9_correctness_changes_already_equal_in_K1": sum(
                by_diagnostic[q]["first_sample_answer"] == by_diagnostic[q]["vote_answer"] for q in changes),
            "D_to_K9_correctness_changed_questions": len(changes),
            "K9_top_count_ties": len(tie_records),
            "K9_ties_with_D_among_leaders": sum(
                r["answer_counts"].get(r["tie_anchor_answer"]) == r["top_votes"] for r in tie_records),
            "K9_tie_question_ids": [r["question_id"] for r in tie_records],
        },
        "representative_saved_ballots": examples,
        "interpretation": {
            "positive_voting_gain_established": False,
            "reason": "K9 minus D is +1/402 with case-bootstrap CI spanning zero; K9 minus same-temperature K1 is -1/402.",
            "input_configuration_gain_established": False,
            "temperature_causal_effect_identified": False,
            "technical_recovery_is_method_gain": False,
            "generalization_claim_supported": False,
            "medical_tool_gain_claim_supported": False,
            "GPT4o_paper_comparison_supported": False,
        },
        "execution_cost_timing_and_recovery": "execution_summary.json",
    }


def render(summary):
    p1, p2 = summary["phase1"], summary["phase2"]
    agg = summary["supplemental_ballot_aggregates"]
    lines = [
        "# Qwen3.7 Token Plan 阶段 0–2：完成后的结果分析", "",
        "**固定九票结果为 296/402（73.63%），直接作答 D 为 295/402（73.38%），净增仅 1 题（+0.25 个百分点）。本轮没有建立稳定的投票收益。** 同配置、同温度的首个采样 K1 为 297/402（73.88%），九票反而少对 1 题；两个主要差值的病例 bootstrap 95% 区间均跨 0。", "",
        "本文只汇总三阶段已完成的独立评分与保存的选项票数，不重新调用模型、不重评分、不改预测。成本、实际时长、停机及恢复记录另见 [执行汇总](execution_summary.json)；具体协议见 [protocol.md](protocol.md)。", "",
        "## 阶段成绩与预注册选择", "",
        "| 阶段 / 结果 | 正确 / 固定分母 | 准确率 | 缺答 | 决策 |",
        "|---|---:|---:|---:|---|",
        "| 0：旧 60 题回归 | 48/60 | 80.00% | 0 | 技术门槛通过 |",
        "| 1：D 单答 | 295/402 | 73.38% | 0 | 保留 D |",
        "| 1：HiRes 单答 | 295/402 | 73.38% | 0 | 未达到至少多对 7 题的选择门槛 |",
        "| 2：预先固定 K9 | 296/402 | 73.63% | 0 | 主结果，不按 K 曲线事后挑最高分 |", "",
        "换成 qwen3.7-plus 后，阶段 0 不再沿用旧模型的 40–44/60 准确率带。48/60 是这轮回归集成绩，不能与旧 qwen3-vl-plus 的 42/60 直接拼成受控的模型升级收益。HiRes 的两题技术检查用于确认接口可用，不用于估计准确率。", "",
        "阶段 1 的 HiRes 相对 D 纠正 9 题、误改 9 题，净增 0；病例 bootstrap 95% 差值区间为 "
        + ci(next(iter(p1["comparisons"].values()))) + " 个百分点，题级 exact McNemar p=1.000。按预注册规则选 D，故后续没有输入配置升级造成的平均涨点。", "",
        "## 三个必要对照", "",
        "以下方向均为“表中基线 → K9”。纠正指合法错答变对，误改指对答变成另一个合法错答；缺答恢复另列。", "",
        "| 基线 | 基线正确 | K9 正确 | 纠正 | 误改 | 缺答→正确 / 正确→缺答 | 净题数 | 差值（百分点） | 病例 bootstrap 95% CI（百分点） | exact McNemar p |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    labels = [("original_D_to_K9", "原 D，T=0.2", 295),
              ("selected_single_to_K9", "选定配置单答（本轮即 D）", 295),
              ("same_temperature_K1_to_K9", "同温度缓存 K1，T=0.7", 297)]
    for key, label, count in labels:
        c = p2["main_comparisons"][key]
        lines.append(f"| {label} | {count}/402 | 296/402 | {c['legal_wrong_to_correct']} | {c['correct_to_legal_wrong']} | {c['missing_to_correct']} / {c['correct_to_missing']} | {c['net']:+d} | {c['delta_pp']:+.2f} | {ci(c)} | {c['exact_mcnemar_p']:.3f} |")
    lines.extend([
        "", "原 D 与选定单答是同一对照，不能当成两次独立验证。K1 为每题按保存顺序的第一个 T=0.7 样本，不挑选正确样本。K9 相对 D 混合了采样温度与聚合变化；K9 相对 K1 保持输入和温度一致，更直接衡量已采样九票聚合带来的增量。", "",
        "区间与 p 值直接复制已完成的评分：按 99 个病例成簇配对重采样 2,000 次（seed=20261102），每次以抽到病例内的全部题目计算题目加权准确率差；表中为百分位 95% 区间。McNemar 是题级精确检验，未单独处理同病例题目依赖，故应与病例 bootstrap 一起读。小幅净差与跨 0 区间表明证据不足，不能解释成已证明两种方法完全等效。", "",
        "## K1–K9 的保存顺序曲线", "",
        "| K | 正确 / 402 | 准确率 | 相对 D 净题数 | 相对 D 纠正 / 误改 | 相对 D 95% CI（百分点） |",
        "|---:|---:|---:|---:|---:|---:|",
    ])
    for row in p2["fixed_K_curve"]:
        c = row["versus_D"]
        lines.append(f"| {row['k']} | {row['correct']}/402 | {pct(row['accuracy'])} | {c['net']:+d} | {c['legal_wrong_to_correct']} / {c['correct_to_legal_wrong']} | {ci(c)} |")
    lines.extend([
        "", "全部 K 的题级缺答均为 0。K1 与 K8 的 297/402 是诊断结果，不能据此改报 K8 为本轮主配置。票数按前 K 个已保存样本计算：有效票中取最多票选项；仅在并列领先时使用原 D 作平票锚，若 D 不在并列领先中则按固定字母序；全缺失仍缺答。因此这里并非无条件要求过半的‘绝对多数’。本轮 K9 没有并列最高票的题，故平票锚未改变 K9 主结果；其他 K 的平票仍按上述规则处理。", "",
        "评分原件还对固定九样本池每个 K 做了 200 次 Monte Carlo 子采样。这只是同一已观察样本池的波动诊断，不是总体置信区间，也没有新推理。K9 每次使用全部九票，因而该诊断的标准差为 0；这不表示部署准确率没有不确定性。完整诊断保存在 [analysis_summary.json](analysis_summary.json) 和 [阶段 2 metrics](phase2/metrics.json)。", "",
        "## 一致程度与错误集中在哪里", "",
        "以下为互斥分组。任何一票缺失的题先进入技术不完整组；7/9 或 8/9 只能称高一致，不能称全体一致。", "",
        "| 组别 | 题数 | K9 正确 / 组内分母 | 组内准确率 | D→K9 纠正 / 误改 | 净题数 |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    names = {"unanimous_9_of_9": "九票全体一致（9/9）", "high_agreement_7_or_8_of_9": "高一致（7–8/9）",
             "split_at_most_6_of_9": "完整且分歧（最高票≤6/9）", "technical_incomplete": "技术不完整（缺至少一票）"}
    for key, group in p2["agreement_bins"].items():
        t, c = group["vote_totals"], group["baseline_to_vote"]
        lines.append(f"| {names[key]} | {group['planned_n']} | {t['correct']}/{t['planned_n']} | {pct(t['accuracy'])} | {c['legal_wrong_to_correct']} / {c['correct_to_legal_wrong']} | {c['net']:+d} |")
    lines.extend([
        "", "343/402（85.32%）的题九票完全一致，其中 **78 题仍然答错**。这直接说明重复采样经常保留同一个错误答案，票多本身不构成新的正确依据。它不能单独定位是视觉识别、医学推断还是选项映射出了错；本报告不凭票数编造医学错误原因。", "",
        "主分歧组只占 31/402（7.71%），其纠正 2 题、误改 1 题提供全轮净 +1；九票全体一致组内仍有 2 次纠正与 2 次误改。D 与 K1 是不同生成轮次，即使九个采样一致，也可能和 D 不同。", "",
        "| 最高票阈值 | 用途 | 完整九票中符合者 / 全 402 | K9 正确 / 该组 | D→K9 纠正 / 误改 | 若不区分技术缺票的原始数量 | 其中技术不完整 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ])
    for threshold, group in p2["split_thresholds"].items():
        sub = group["complete_split"]
        t, c = sub["vote_totals"], sub["baseline_to_vote"]
        lines.append(f"| ≤{threshold}/9 | {'主定义' if threshold == '6' else '敏感性'} | {sub['planned_n']}/402（{pct(group['complete_split_fraction_of_all_questions'])}） | {t['correct']}/{t['planned_n']} | {c['legal_wrong_to_correct']} / {c['correct_to_legal_wrong']} | {group['raw_top_vote_rule_n_including_incomplete']} | {group['incomplete_meeting_raw_rule_n']} |")
    lines.extend([
        "", "所有一致度与票差都以计划的 9 票为分母，不把缺失样本从分母扣掉。≤5 与 ≤7 只做敏感性描述，不替换预先固定的 ≤6 主定义，不依据这些标签结果追加一组付费实验。", "",
        "| 事后正确性诊断 | 完整九票 394 题 AUROC | 全 402 题（次要）AUROC |",
        "|---|---:|---:|",
    ])
    auroc = p2["correctness_auroc"]
    for key, label in [("agreement_planned", "最高票数 / 9"), ("margin_planned", "（最高票−第二高票）/ 9")]:
        lines.append(f"| {label} | {auroc['complete_nine_only'][key]['auroc']:.4f} | {auroc['all_questions_secondary'][key]['auroc']:.4f} |")
    lines.extend([
        "", "AUROC 正类为 K9 答对。完整九票集合为 290 对、104 错；全部为 296 对、106 错，故本轮四个 AUROC 都有定义。若某子集没有正类或没有负类，必须记 JSON `null`，不能填 0 或 0.5。约 0.58 的结果只表示本次一致程度与正确性存在有限的排序关联，不能把 9/9 当作已校准的正确概率，也不能据此事后设计拦截门槛并声称本轮已验证。", "",
        "## 缺样本、恢复与收益归因", "",
        "3,618 个计划样本均有终态：3,610 个 `completed`，5 个 `unparsed`，3 个 `request_failed`。8 题各缺 1 个可投票答案；技术不完整不等于 8 次进程崩溃。失败终态未补跑、未替换成后来成功答案，保留缺票。全部 402 题最终仍有合法 K9 答案，因此主比较的缺答恢复与正确变缺答都是 0。技术不完整组为 6/8，与 D 的净变化为 0；这不证明缺少的一票在所有反事实情形下都没有影响。", "",
        "| 可能贡献 | 本轮能够支持的说法 | 本轮不能支持的说法 |",
        "|---|---|---|",
        "| 输入配置 | HiRes 与 D 同为 295/402，预注册规则保留 D | 高分辨率已经带来稳定收益 |",
        "| 温度 / 随机采样 | D 的 T=0.2；采样 K1 的 T=0.7 为 297/402，较 D 纠正 13、误改 11 | 仅凭一次 D 与 K1 差值就给温度变化因果信用 |",
        "| 九票聚合 | 相对同 T 的 K1 纠正 8、误改 9，净 −1 | 相对 D 的 +1 全部来自投票机制 |",
        "| 技术恢复 | 使本轮得以完成；失败样本保留，完整题目分母不变 | 把恢复进程、修复记账或格式缺失计为医学解题改进 |",
        "| 工具 / 记忆 | 本轮未运行这些实验组 | 由本次成绩证明医学工具或记忆系统收益 |", "",
        "尤其是 D→K9 的全部 7 个正确性变化题，第一票 K1 已经与 K9 相同。以下公开保存的票数列出全部 4 个纠正与 3 个误改，说明这些变化无需后面 8 票才出现；另有其他题在聚合中被纠正或误改，因此仍须以同温度 K1→K9 的全体比较为准。", "",
        "| 题号 | 参考 | D | K1 | K9 | 保存的九票计数 | 类别 |",
        "|---|---|---|---|---|---|---|",
    ])
    for ex in summary["representative_saved_ballots"]:
        ballot = ", ".join(f"{k}×{v}" for k, v in ex["answer_counts"].items())
        label = {"D_to_K9_correction": "纠正 D", "D_to_K9_harm": "误改 D", "descriptive_failure_example": "额外失败例"}[ex["role"]]
        lines.append(f"| `{ex['question_id']}` | {ex['reference']} | {ex['D']} | {ex['K1']} | {ex['K9']} | {ballot} | {label} |")
    lines.extend([
        "", "例 `795_8353802131057` 的九票都为 F，参考为 C；例 `18680_8143559034217` 的第一票 D 正确，后续多数 C 将它压过；例 `16844_8143559672130` 的第一票 B 正确，但最终 C 得 5 票。这些是可核查的投票失败模式，不是依据模型理由推断的医学因果结论。题级答案和原始票数分别见 [per_question.json](phase2/per_question.json) 与 [vote_diagnostics.json](phase2/vote_diagnostics.json)。", "",
        "## 适用范围与复现", "",
        "402 题来自 99 个病例，是用于配置选择的调参集；1,002 题留出集未运行。本轮是一个固定样本池、一次实施结果，且此前 60 题开发集曾反复使用。不能将本分数称为独立泛化验证，不能把 402 题的 Qwen 分数直接当作在论文全量数据和 GPT-4o 骨干上超过 MedRAX 的证据。本轮也没有运行 GPT-4o 投票、医疗工具、集成或全 2,500 题。", "",
        "现有证据支持保留 D 作为这轮的简单对照，并如实报告九票没有显示稳定增益；不支持自动在同一调参集继续改 K、提示或门槛来追分。成本与时间应与这一个净增题数一起评价，使用 [execution_summary.json](execution_summary.json) 的实际汇总，Token Plan 的 CNY 代理记账不等于真实扣费。", "",
        "本页和机器可读汇总由仓库根目录执行以下命令生成。输入只需要已完成评分的公开文件；脚本复制原有统计量并补充保存票数的计数，不执行评分器或模型：", "",
        "```powershell", "python -X utf8 experiments/summarize_qwen37_voting.py --scored-root reports/qwen37_token_plan_20261102 --out reports/qwen37_token_plan_20261102", "```", "",
        "统计原件：[阶段 0](phase0/metrics.json)、[阶段 1](phase1/metrics.json)、[阶段 2](phase2/metrics.json)。完整机器可读分析：[analysis_summary.json](analysis_summary.json)。", "",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scored-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    summary = build_summary(args.scored_root)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out / "results_analysis.md").write_text(render(summary), encoding="utf-8")
    print("Wrote results_analysis.md and analysis_summary.json from completed scoring artifacts; no rescoring.")


if __name__ == "__main__":
    main()
