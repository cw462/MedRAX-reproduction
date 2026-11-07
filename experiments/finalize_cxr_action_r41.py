"""Completed-only R4.1 scoring, diagnostics and allowlisted target publication.

Does not launch inference or edit frozen predictions, cards, masks or runtime.
Reuses the repository's existing grade, paired bootstrap and evidence exporter.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path

import numpy as np

from export_cxr_vqa_extension import RequestEvidencePublisher, export
from export_vote_phase import read
from score_cxr_vqa_extension import bootstrap, cluster_keys, rows, score

ARMS = ("M-S41", "M-C41")


def completion_gate(root, dataset, data, run):
    """Check completion and membership before any reference file is opened."""
    inputs = rows(data / "inputs.jsonl")
    ids = {r["question_id"] for r in inputs}
    if len(ids) != len(inputs):
        raise ValueError("duplicate_input_ids")
    receipts = {}
    for arm in ARMS:
        receipt = run / f"complete_{arm}.json"
        if not receipt.is_file():
            raise ValueError("generation_incomplete:" + arm)
        receipts[arm] = read(receipt)
        if receipts[arm].get("questions") != len(inputs):
            raise ValueError("wrong_completion_denominator:" + arm)
        if {p.stem for p in (run / "predictions" / arm).glob("*.json")} != ids:
            raise ValueError("incomplete_prediction_membership:" + arm)
    exitfile = root / "jobs" / (dataset + ".exitcode")
    if not exitfile.is_file() or exitfile.read_text().strip() != "0":
        raise ValueError("dataset_job_not_successfully_exited")
    pid = (root / "jobs" / (dataset + ".pid")).read_text().strip()
    if Path("/proc", pid).exists():
        raise ValueError("dataset_job_still_alive")
    return {"questions": len(inputs), "receipts": receipts, "effective_job_exit": 0,
            "effective_job_pid": pid, "references_opened_after_completion_gate": True}


def reuse_check(frozen, run, historical):
    values = {a: {p.stem: read(p) for p in (run / "predictions" / a).glob("*.json")}
              for a in ARMS}
    old = {r["question_id"]: r for r in rows(historical / "predictions_M.jsonl")}
    if set(old) != set(frozen["mask"]):
        raise ValueError("historical_membership_mismatch")
    selected, reused = [], []
    for qid, item in frozen["mask"].items():
        history = frozen["history"][qid]
        for field in ("answer", "reason", "status"):
            if old[qid].get(field) != history.get(field):
                raise ValueError("historical_value_changed:" + qid + ":" + field)
        if item["selected_ids"]:
            selected.append(qid)
            for arm in ARMS:
                p = values[arm][qid]
                if p["reused_historical_M"] or p["main_calls"] > 6 or p["tool_calls"] > 4:
                    raise ValueError("invalid_selected_execution:" + qid)
        else:
            reused.append(qid)
            for arm in ARMS:
                p = values[arm][qid]
                if not p["reused_historical_M"] or p["main_calls"] != 0 or p["tool_calls"] != 0:
                    raise ValueError("nonselected_has_new_calls:" + qid)
                if any(p.get(k) != history.get(k) for k in ("answer", "reason", "status")):
                    raise ValueError("nonselected_history_changed:" + qid)
                if list((run / "calls" / arm / qid).glob("*/started.json")) or list((run / "tool_selections" / arm / qid).glob("*.json")):
                    raise ValueError("nonselected_has_request_artifacts:" + qid)
    return {"status": "passed", "questions": len(old), "selected": len(selected),
            "exact_historical_reuse": len(reused), "answer_reason_status_preserved": True,
            "nonselected_new_main_and_tool_calls": 0}, values


def diagnostics(data, run, frozen, historical, summary, reuse):
    inputs = rows(data / "inputs.jsonl")
    details = {(r["arm"], r["question_id"]): r for r in rows(run / "offline_r41" / "per_question.jsonl")}
    predictions = {a: {p.stem: read(p) for p in (run / "predictions" / a).glob("*.json")} for a in ARMS}
    predictions["M"] = {r["question_id"]: r for r in rows(historical / "predictions_M.jsonl")}
    subsets = np.array([r.get("source", {}).get("subset", "all") for r in inputs])
    clusters = np.asarray(cluster_keys(inputs))
    selected = np.array([bool(frozen["mask"][r["question_id"]]["selected_ids"]) for r in inputs])
    group_results = {}
    for label, mask in (("selected", selected), ("exact_historical_reuse", ~selected)):
        indices = np.flatnonzero(mask)
        group = {"n": len(indices), "arms": {}, "comparisons": {}}
        for arm in ("M", *ARMS):
            scored = [details[arm, inputs[i]["question_id"]] for i in indices]
            group["arms"][arm] = {"correct": sum(v["correct"] for v in scored),
                "missing": sum(v["missing"] for v in scored),
                "accuracy_pct": 100 * sum(v["correct"] for v in scored) / len(indices) if len(indices) else None}
        delta = np.array([int(details["M-S41", r["question_id"]]["correct"]) - int(details["M-C41", r["question_id"]]["correct"]) for r in inputs])[mask]
        confidence = bootstrap(delta, clusters[mask], subsets[mask]) if len(delta) and np.any(delta) else {"micro_pp": [0.0, 0.0], "macro_pp": [0.0, 0.0]}
        group["comparisons"]["M-S41 vs M-C41"] = {"corrections": int(sum(delta > 0)), "harms": int(sum(delta < 0)), "net": int(delta.sum()), "confidence": confidence}
        group_results[label] = group
    changes = []
    for row in inputs:
        qid = row["question_id"]
        a, b = details["M-S41", qid], details["M-C41", qid]
        pa, pb = predictions["M-S41"][qid], predictions["M-C41"][qid]
        if pa.get("answer") != pb.get("answer") or pa["status"] != pb["status"] or a["correct"] != b["correct"]:
            changes.append({"question_id": qid, "selected_skill_ids": frozen["mask"][qid]["selected_ids"],
                "skill": a | {"status": pa["status"]}, "control": b | {"status": pb["status"]},
                "delta": int(a["correct"]) - int(b["correct"]),
                "missing_transition": bool(a["missing"] or b["missing"])})
    behavior = {}
    for arm in ARMS:
        values = list(predictions[arm].values())
        calls = [read(p) for p in (run / "calls" / arm).glob("*/*/result.json")]
        starts = [read(p)["utc"] for p in (run / "calls" / arm).glob("*/*/started.json")]
        observations = [read(p) for p in (run / "tool_selections" / arm).glob("*/*.json")]
        end = read(run / f"complete_{arm}.json")["utc"]
        behavior[arm] = {"full_denominator": len(inputs), "selected_denominator": int(selected.sum()),
            "questions_with_tools": sum(v.get("tool_calls", 0) > 0 for v in values),
            "main_limit_hits": sum(v.get("main_calls", 0) == 6 for v in values),
            "tool_limit_hits": sum(v.get("tool_calls", 0) == 4 for v in values),
            "main_limit_hits_pct_all": 100 * sum(v.get("main_calls", 0) == 6 for v in values) / len(inputs),
            "tool_limit_hits_pct_all": 100 * sum(v.get("tool_calls", 0) == 4 for v in values) / len(inputs),
            "status_counts": dict(Counter(v["status"] for v in values)),
            "tool_selection_counts": dict(Counter(v["tool"] for v in observations)),
            "tool_status_counts": dict(Counter(v["status"] for v in observations)),
            "returned_model_counts": dict(Counter(str(v.get("model_returned")) for v in calls)),
            "generation_wall_seconds_including_recovery_pause": (datetime.fromisoformat(end) - min(datetime.fromisoformat(t) for t in starts)).total_seconds() if starts else 0,
            "main_api_seconds_sum": sum(v.get("elapsed_s") or 0 for v in calls),
            "missing": [{"question_id": qid, "status": predictions[arm][qid]["status"], "answer": predictions[arm][qid].get("answer"), "technical_failure": predictions[arm][qid].get("technical_failure", False)} for qid in predictions[arm] if details[arm, qid]["missing"]],
            "resources": summary["arms"][arm]["resources"]}
    return {"reuse_integrity": reuse, "groups": group_results, "card_frequency": dict(Counter(card for item in frozen["mask"].values() for card in item["selected_ids"])),
            "paired_changes": changes, "behavior": behavior,
            "limitations": ["Single sequential sample per arm; sampling and service time may contribute.", "Historical M comparisons mix implementation, call budget and service time.", "OpenI zero selected coverage cannot measure Skill benefit.", "Missing outcomes remain in all denominators; technical missing is not a corrected legal answer."]}


def finalize(root, code, dataset, historical, historical_url):
    data = code / "data" / ("chexbench" if dataset == "chexbench" else dataset + "_cxr")
    run = root / dataset
    gate = completion_gate(root, dataset, data, run)
    cfg = read(root / "configs" / dataset / "config.json")
    frozen = read(Path(cfg["action_r41_frozen"]))
    reuse, _ = reuse_check(frozen, run, historical)
    score_dir = run / "offline_r41"
    if not (score_dir / "summary.json").is_file():
        score(data, run, historical, score_dir, ["M", *ARMS], [("M-S41", "M-C41"), ("M-S41", "M"), ("M-C41", "M")])
    summary = read(score_dir / "summary.json")
    analysis_file = score_dir / "analysis.json"
    if not analysis_file.exists():
        analysis_file.write_text(json.dumps(diagnostics(data, run, frozen, historical, summary, reuse), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out = root / "public_export" / dataset
    if (out / "r41_target_export_complete.json").is_file():
        return summary
    export(data, run, score_dir, out, list(ARMS), historical_url)
    manifest = read(out / "publication_manifest.json")
    pub = RequestEvidencePublisher(out, data / "manifest.json")
    for source, target in [(run / "r41_run.json", "frozen_run.json"), (Path(cfg["action_r41_frozen"]), "frozen_selection_and_history.json"), (analysis_file, "analysis.json"), (historical / "predictions_M.jsonl", "predictions_M.jsonl"), (historical / "complete_M.json", "complete_M.json"), (historical / "summary.json", "historical_summary.json")]:
        pub.copy_json(source, out / target)
    pub.emit(out / "completion_gate.json", gate)
    gpu = code / "configs/cxr_vqa_tool_worker_gpu.json"
    if gpu.is_file():
        pub.copy_json(gpu, out / "tool_worker_gpu.json")
    if dataset == "chexbench":
        recovery = root / "recovery_maira_20261108_0134"
        if recovery.is_dir():
            request = read(recovery / "request.json")
            health = json.loads((recovery / "stdout.log").read_text().split("CXR_VQA_RESULT=")[-1])
            for name in [request["image"], *health.get("derived_images", [])]:
                pub.alias(name, pub.put_image(pub.read_image(Path(name))))
            for name in ("request.json", "recovery.json"):
                pub.copy_json(recovery / name, out / "recovery" / name)
            pub.emit(out / "recovery/health_result.json", health)
            pub.copy_json(recovery / "artifacts/raw.json", out / "recovery/health_raw.json")
            pub.emit(out / "recovery/health_stderr.txt", (recovery / "stderr.log").read_text())
            pub.emit(out / "recovery/initial_job_failure.txt", (recovery / "original_jobs/chexbench.log").read_text())
            pub.emit(out / "recovery/initial_job_markers.json", {"pid": (recovery / "original_jobs/chexbench.pid").read_text().strip(), "exit_code": (recovery / "original_jobs/chexbench.exitcode").read_text().strip()})
    pub.emit(out / "recovery_image_assets.json", [{k: v for k, v in item.items() if k != "target"} | {"path": pub.rel(item["target"], out / "recovery_image_assets.json")} for item in pub.assets.values()])
    pub.emit(out / "r41_target_export_complete.json", {"status": "completed", "dataset": dataset, "generation_gate": gate, "reuse_audit": reuse, "new_inference_requests_from_publication": 0})
    pub.emit(out / "publication_manifest.json", {"files": sorted(set(manifest["files"]) | {p.relative_to(out).as_posix() for p in pub.files}), "redactions": dict(Counter(manifest["redactions"]) + pub.redactions)})
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for name in ("root", "code", "historical"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--dataset", choices=("chexbench", "slake", "vqarad"), required=True)
    p.add_argument("--historical-url", required=True)
    a = p.parse_args()
    result = finalize(a.root, a.code, a.dataset, a.historical, a.historical_url)
    print(json.dumps({"dataset": a.dataset, "questions": result["questions"], "arms": {k: {x: v[x] for x in ("correct", "missing", "micro_pct", "macro_pct")} for k, v in result["arms"].items()}, "comparisons": result["comparisons"]}, ensure_ascii=False))
