from __future__ import annotations
import csv
from pathlib import Path
from .common import require, read_json, write_once, object_hash, file_hash
from .setup import verify_frozen
from .hook import BEGIN, END, MAIN_SLOT

def compare_cases(baseline: list[dict], candidate: list[dict], qids: list[str]) -> tuple[list[dict], dict]:
    indexed = []
    for name, records in (("B0", baseline), ("L1", candidate)):
        require(len(records) == len(qids), f"{name}: not a full, scored pilot; no partial denominator")
        by = {r["question_id"]: r for r in records}
        require(len(by) == len(records) and set(by) == set(qids), f"{name}: duplicate/missing/wrong qids")
        for r in records:
            require(type(r.get("correct")) is bool or type(r.get("correct")) is int and r["correct"] in (0, 1),
                    f"{name}: invalid saved correctness; do not infer score from strings")
        indexed.append(by)
    pairs = []
    for q in qids:
        b, c = indexed[0][q], indexed[1][q]
        require(b.get("reference") == c.get("reference"), f"Reference changed between arms: {q}")
        require(b.get("question") == c.get("question") and b.get("options") == c.get("options"), f"Question changed: {q}")
        bc, cc = bool(b["correct"]), bool(c["correct"])
        cat = "gain" if cc and not bc else "harm" if bc and not cc else "both_correct" if bc else "both_wrong"
        pairs.append({"question_id": q, "category": cat, "B0_correct": bc, "L1_correct": cc,
                      "B0_answer": b.get("answer"), "L1_answer": c.get("answer"),
                      "reference": b.get("reference"),
                      "B0_main_calls": b.get("main_calls"), "L1_main_calls": c.get("main_calls"),
                      "B0_tool_calls": b.get("tool_calls"), "L1_tool_calls": c.get("tool_calls"),
                      "B0_failed_tool_calls": b.get("failed_tool_calls"), "L1_failed_tool_calls": c.get("failed_tool_calls")})
    n = len(qids)
    gains = sum(r["category"] == "gain" for r in pairs)
    harms = sum(r["category"] == "harm" for r in pairs)
    bsum = sum(r["B0_correct"] for r in pairs); csum = sum(r["L1_correct"] for r in pairs)
    require(csum - bsum == gains - harms, "Pair arithmetic invariant failed")
    summary = {"n": n, "B0_correct": bsum, "L1_correct": csum, "gains_G": gains, "harms_H": harms,
               "net_G_minus_H": gains - harms, "B0_accuracy_pct": 100 * bsum / n,
               "L1_accuracy_pct": 100 * csum / n, "delta_pp": 100 * (gains - harms) / n,
               "both_correct": sum(r["category"] == "both_correct" for r in pairs),
               "both_wrong": sum(r["category"] == "both_wrong" for r in pairs),
               "interpretation": "Single paired online-stream development pilot; not proof of generalization or statistical significance.",
               "inference_caveat": "Online cross-case memory creates sequential dependence; no iid McNemar/bootstrap claim is made."}
    return pairs, summary

def audit_arm(work: Path, arm: str, qids: list[str]) -> dict:
    out = work / arm
    manifest = read_json(out / "manifest.json")
    native_arm = manifest["arm"]
    require((out / "generation.exitcode").is_file()
            and (out / "generation.exitcode").read_text().strip() == "0", "Generation did not finish successfully")
    done = read_json(out / "complete.json")
    require(done["questions"] == len(qids) and done["status"] == "generation_complete", "Incomplete native stream")
    source_states = set()
    request_total = 0
    for q in qids:
        prediction = read_json(out / "predictions" / native_arm / (q + ".json"))
        feedback = read_json(out / "feedback" / (q + ".json"))
        require(feedback["saved_prediction"] == prediction and feedback["timing"] == "after_immutable_prediction",
                f"Feedback is not bound to locked prediction: {q}")
        from datetime import datetime
        require(datetime.fromisoformat(feedback["released_at"].replace("Z", "+00:00")) >=
                datetime.fromisoformat(prediction["prediction_saved_at"].replace("Z", "+00:00")), "Feedback timing violation")
        episodes = out / "external_memory" / "episodes" / q
        require((episodes / "retrieval.json").is_file() and (episodes / "ingest.json").is_file(), "Missing M5 memory receipts")
        ingest = read_json(episodes / "ingest.json")
        require(ingest["prediction_saved_at"] == prediction["prediction_saved_at"]
                and ingest["feedback_released_at"] == feedback["released_at"], "Ingest timing binding differs")
        audits = sorted((out / "prompt_audit" / q).glob("*.json"))
        require(len(audits) == prediction["main_calls"] and len(audits) > 0, f"Prompt hook did not cover every main call: {q}")
        require({int(p.stem) for p in audits} == set(range(1, prediction["main_calls"] + 1)), "Call audit sequence gap")
        for path in audits:
            info = read_json(path)
            require(info["experiment_arm"] == arm and info["patch_applied"] == (arm == "L1")
                    and info["only_system_suffix_changed"], "Prompt audit contract violation")
            expected = info["effective_system"]
            require(expected.count(BEGIN) == (1 if arm == "L1" else 0)
                    and expected.count(END) == (1 if arm == "L1" else 0), "Suffix missing or duplicated")
            reqpath = out / "services" / "calls" / MAIN_SLOT / q / path.name.replace(".json", "") / "request.json"
            require(reqpath.is_file(), f"Native actual request archive missing: {reqpath}")
            payload = read_json(reqpath)
            messages = payload.get("messages")
            require(isinstance(messages, list), "Unsupported native request archive; expected messages at root")
            systems = [r["content"] for r in messages if r.get("role") == "system"]
            require(systems == [expected], f"Configured prompt differs from actual native request: {q}/{path.stem}")
            source_states.add(info["base_system_sha256"])
            request_total += 1
    seed = read_json(out / "initial_memory.json")
    require(seed["node_count"] == 7 and seed["tool_memory_enabled"] is False, "Initialization mismatch")
    return {"main_requests_checked": request_total, "questions_checked": len(qids),
            "base_system_variants": sorted(source_states), "initial_seed_sha256": seed["semantic_sha256"],
            "passed": True}

def verify_score_receipt(out: Path) -> dict:
    marker = out / "scoring.completed.json"
    require(marker.is_file(), f"Native scorer has no confirmed successful exit: {out}")
    receipt = read_json(marker)
    require(receipt.get("returncode") == 0, "Native scorer failed")
    require(file_hash(out / "analysis" / "per_question.json") == receipt["per_question_sha256"], "Native scored cases changed")
    require(file_hash(out / "analysis" / "summary.json") == receipt["summary_sha256"], "Native score summary changed")
    return receipt


def analyze(work: Path) -> dict:
    work = work.resolve()
    frozen = verify_frozen(work)
    qids = frozen["cohort"]["selected_ids"]
    audits = {a: audit_arm(work, a, qids) for a in ("B0", "L1")}
    require(audits["B0"]["initial_seed_sha256"] == audits["L1"]["initial_seed_sha256"], "Different seed memory")
    arms = {}
    for arm in ("B0", "L1"):
        out = work / arm
        verify_score_receipt(out)
        require((out / "analysis" / "per_question.json").is_file(), f"Run the native scorer for {arm} first")
        arms[arm] = read_json(out / "analysis" / "per_question.json")
    pairs, summary = compare_cases(arms["B0"], arms["L1"], qids)
    summary["prompt_and_feedback_audit"] = audits
    summary["resources"] = {a: {
        "main_calls": sum(r["main_calls"] for r in arms[a]),
        "tool_calls": sum(r["tool_calls"] for r in arms[a]),
        "failed_tool_calls": sum(r["failed_tool_calls"] for r in arms[a]),
        "memory_model_calls": read_json(work / a / "memory.completed.json")["memory_model_calls"],
        "native_model_usage_by_role": read_json(work / a / "analysis" / "summary.json").get("model_usage_by_role"),
    } for a in ("B0", "L1")}
    summary["missing_memory_token_cost_notice"] = "Native score resources may omit memory tokens/cost; use external_memory/model_calls receipts. Unknown costs are not zero."
    for row in pairs:
        row["case_group"] = frozen["cohort"]["selected_groups"][row["question_id"]]
    result = work / "paired_analysis"
    result.mkdir(exist_ok=True)
    write_once(result / "summary.json", summary)
    write_once(result / "pairs.json", pairs)
    csvpath = result / "paired_results.csv"
    if not csvpath.exists():
        with csvpath.open("x", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(pairs[0])); writer.writeheader(); writer.writerows(pairs)
    report = (
        "# OpenI 左右侧 M5 配对试验\n\n"
        f"B0：{summary['B0_correct']}/{summary['n']}（{summary['B0_accuracy_pct']:.2f}%）。\n\n"
        f"L1：{summary['L1_correct']}/{summary['n']}（{summary['L1_accuracy_pct']:.2f}%）。\n\n"
        f"纠正 G={summary['gains_G']}；误改 H={summary['harms_H']}；净增 {summary['net_G_minus_H']:+d} 题，"
        f"差值 {summary['delta_pp']:+.2f} pp。\n\n"
        "这是一次同环境、同题序的在线记忆开发筛查，不是未见测试，也不证明稳定超越 M5。"
        "本结果与完整 848 题历史记忆状态不同；分母没有删除工具失败题。"
        "各题受此前跨病例记忆影响，未套用独立样本显著性检验。\n\n"
        "完整原评分与资源统计保留在 B0/analysis、L1/analysis；记忆调用详见 external_memory/model_calls。\n"
    )
    target = result / "REPORT.md"
    if target.exists():
        require(target.read_text(encoding="utf-8") == report, "Existing report differs")
    else:
        target.write_text(report, encoding="utf-8")
    return summary
