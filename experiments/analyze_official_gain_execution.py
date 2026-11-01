"""Reproduce post-run D/M/P execution statistics from saved observables.

Usage:
  python experiments/analyze_official_gain_execution.py \
      --run local_assets/official_gain60 --out reports/official_gain60

Writes tool_execution_details.json only. It does not run inference, read labels
or ledgers, connect to the network, modify source predictions, or regenerate the
human-authored tool_execution_analysis.md interpretation.
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def analyze(run, out):
    run, out = Path(run).resolve(), Path(out).resolve()
    if out == run or out.is_relative_to(run):
        raise ValueError("publication_output_must_be_outside_original_run")
    status = read(run / "status.json")
    if (status.get("status") != "generation_complete"
            or status.get("completed") != {"D": 60, "M": 60, "P": 60}):
        raise ValueError("all_180_predictions_must_be_complete")
    rows = [json.loads(line) for line in
            (run / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    qids = {row["question_id"] for row in rows}
    expected = {(q, arm) for q in qids for arm in ("D", "M", "P")}
    if (len(rows) != 180 or len(qids) != 60
            or {(r["question_id"], r["arm"]) for r in rows} != expected):
        raise ValueError("complete_unique_prediction_coverage_required")
    predictions = run / "predictions"

    summary, details, lost, oom = {}, [], [], []
    cache_times = defaultdict(list)
    # Saved tool outputs only, never the account ledger or model weight files.
    for path in (run / "tool_cache").glob("*.json"):
        record = read(path)
        if "tool" in record:
            cache_times[record["tool"]].append(record["elapsed_s"])
    for arm in ("M", "P"):
        counts, cases = defaultdict(Counter), set()
        for path in predictions.glob("*/" + arm + "/tools/*/result.json"):
            record = read(path)
            qid = path.relative_to(predictions).parts[0]
            cases.add(qid)
            started = (path.parent / "started.json").exists()
            errors = record.get("errors", [])
            if any("interrupted_tool_result_unavailable_not_reissued" in x
                   for x in errors):
                category = "interrupted_output_unavailable"
            elif any("CUDA out of memory" in x for x in errors):
                category = "cuda_out_of_memory"
            elif record["execution"] == "returned":
                category = "returned"
            else:
                category = "other_failure"
            counts[record["tool"]][
                "new_execution_started" if started else "raw_cache_reuse"] += 1
            counts[record["tool"]][category] += 1
            item = {
                "question_id": qid, "arm": arm,
                "ordinal": record["tool_call_ordinal"], "tool": record["tool"],
                "new_execution_started": started, "result_category": category,
                "box_count": len(record["original_pixel_boxes"]),
                "artifact_kinds": [x["kind"] for x in record["artifacts"]],
            }
            details.append(item)
            if category == "interrupted_output_unavailable":
                lost.append(item)
            if category == "cuda_out_of_memory":
                oom.append(item)
        arm_rows = [row for row in rows if row["arm"] == arm]
        summary[arm] = {
            "terminal_requested": sum(r.get("tool_requested", 0) for r in arm_rows),
            "new_execution_started": sum(r.get("tool_actual", 0) for r in arm_rows),
            "cache_hits": sum(r.get("tool_cache_hits", 0) for r in arm_rows),
            "questions_with_medical_tools": len(cases),
            "actual_execution_histogram": dict(sorted(Counter(
                r.get("tool_actual", 0) for r in arm_rows).items())),
            "per_tool": {key: dict(value) for key, value in sorted(counts.items())},
        }

    # Count actual stored wire blocks; do not decode, synthesize or rewrite media.
    wire, wire_details = defaultdict(Counter), []
    for path in predictions.glob("*/P/calls/*/request.json"):
        phase = path.parent.name
        qid = path.relative_to(predictions).parts[0]
        metadata = None
        original = derived = bytes_n = 0
        kinds = Counter()
        for message in read(path)["messages"]:
            content = message.get("content", [])
            for item in content if isinstance(content, list) else []:
                if (item.get("type") == "text" and
                        str(item.get("text", "")).startswith("BOUND CURRENT IMAGE: ")):
                    metadata = json.loads(item["text"].split(": ", 1)[1])
                elif item.get("type") == "image_url":
                    url = item["image_url"]["url"]
                    bytes_n += int(url.startswith("data:image/") and
                                   ";base64," in url and len(url) > 100)
                    if metadata and metadata.get("parent_image_id"):
                        derived += 1
                        kinds[metadata.get("kind", "unknown")] += 1
                    else:
                        original += 1
                    metadata = None
        wire[phase].update({
            "requests": 1, "original_blocks": original, "derived_blocks": derived,
            "actual_image_byte_blocks": bytes_n,
            "questions_with_derived": int(derived > 0),
        })
        wire_details.append({
            "question_id": qid, "phase": phase, "original_blocks": original,
            "derived_blocks": derived, "actual_image_byte_blocks": bytes_n,
            "derived_kinds": dict(kinds),
        })

    # The same tool_call can appear in multiple later requests. Deduplicate by
    # case/id. Parameter counts target the concrete defects of this fixed run;
    # this is not a general JSON-schema validator or a new runtime safeguard.
    calls, messages, invalid, unknown = {}, {}, [], []
    for path in predictions.glob("*/M/calls/*/attempt_1/response.json"):
        qid = path.relative_to(predictions).parts[0]
        request = read(path.parent.parent / "request.json")
        schemas = {t["function"]["name"]: t["function"]["parameters"]
                   for t in request.get("tools", [])}
        for call in read(path).get("tool_calls", []):
            item = {"question_id": qid, "phase": path.parent.parent.name,
                    "tool": call["name"]}
            calls[qid, call["id"]] = item
            if call["name"] not in schemas:
                unknown.append(item)
                continue
            reasons = []
            schema, args = schemas[call["name"]], call["args"]
            missing = [key for key in schema.get("required", []) if key not in args]
            if missing:
                reasons.append("missing_required:" + ",".join(missing))
            if (call["name"] == "chest_xray_segmentation"
                    and isinstance(args.get("organs"), str)):
                reasons.append("organs_string_instead_of_array")
            if reasons:
                invalid.append({**item, "reasons": reasons})
    for path in predictions.glob("*/M/calls/*/request.json"):
        qid = path.relative_to(predictions).parts[0]
        for message in read(path)["messages"]:
            if message.get("role") == "tool":
                messages[qid, message["tool_call_id"]] = str(message.get("content"))
    feedback = {
        "schema_validation_error": sum("TOOL_ARGUMENT_ERROR" in v
                                       for v in messages.values()),
        "budget_exhausted": sum("experimental_four_medical_tool_budget_exhausted" in v
                                for v in messages.values()),
    }

    events, event_counts, empty_targets = [], Counter(), []
    views, view_questions = Counter(), []
    for path in predictions.glob("*/P/action_events.json"):
        qid = path.relative_to(predictions).parts[0]
        plan = read(path.parent / "plan.json")
        for event in read(path):
            action = plan["actions"][event["action"] - 1]
            events.append({
                "question_id": qid, "action": event["action"], "kind": action["kind"],
                "image_ids": action.get("image_ids", []), "status": event["status"],
                "error": event.get("error"),
            })
            event_counts[event.get("error", event["status"])] += 1
    for path in predictions.glob("*/P/observer_payload.json"):
        if not read(path)["neutral_attribute_questions"]:
            empty_targets.append(path.relative_to(predictions).parts[0])
    for path in predictions.glob("*/P/views.json"):
        records = read(path)
        if records:
            view_questions.append(path.relative_to(predictions).parts[0])
        for record in records:
            views[record["kind"]] += 1

    phases = defaultdict(list)
    for path in predictions.glob("*/*/calls/*/attempt_*/result.json"):
        parts = path.relative_to(predictions).parts
        phases[parts[1] + ":" + parts[3]].append(read(path))
    timing = {
        key: {
            "requests": len(records),
            "request_seconds_sum": round(sum(r["elapsed_s"] for r in records), 3),
            "first_request_utc": min(r["started_utc"] for r in records),
            "last_response_utc": max(r["ended_utc"] for r in records),
        }
        for key, records in sorted(phases.items())
    }
    for arm in ("M", "P"):
        records = [r for key, group in phases.items()
                   if key.startswith(arm + ":") for r in group]
        start = min(r["started_utc"] for r in records)
        end = max(r["ended_utc"] for r in records)
        timing[arm + "_first_to_last_request"] = {
            "first_request_utc": start, "last_response_utc": end,
            "wall_seconds_including_gaps": round(
                (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds(), 3),
        }

    result = {
        "post_generation_analysis": True, "predictions_modified": False,
        "new_inference": 0, "tool_counts": summary,
        "M_model_tool_call_count": len(calls),
        "M_model_tool_calls_by_name": dict(Counter(r["tool"] for r in calls.values())),
        "M_parameter_errors": invalid, "M_unknown_tool_calls": unknown,
        "M_saved_next_request_error_feedback_count": feedback,
        "M_budget_refusals_inferred_from_requested_minus_started":
            summary["M"]["terminal_requested"] - summary["M"]["new_execution_started"],
        "M_unavailable_outputs": lost,
        "M_terminal_unresolved_prior_sum": sum(r.get("unresolved_prior_tool_results", 0)
                                              for r in rows if r["arm"] == "M"),
        "M_cuda_oom_outputs": oom, "P_action_counts": dict(event_counts),
        "P_action_events": events, "P_empty_neutral_target_question_ids": empty_targets,
        "P_distinct_view_instances_by_kind": dict(views),
        "P_questions_with_derived_views": view_questions,
        "P_actual_request_image_blocks": {k: dict(v) for k, v in sorted(wire.items())},
        "P_actual_request_image_details": wire_details,
        "model_phase_timing": timing,
        "saved_tool_output_elapsed_seconds": {
            key: {"outputs": len(values), "seconds_sum": round(sum(values), 3)}
            for key, values in sorted(cache_times.items())
        },
        "tool_records": details,
    }
    out.mkdir(parents=True, exist_ok=True)
    target = out / "tool_execution_details.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "execution_statistics_written", "new_inference": 0,
                      "file": str(target)}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("reports/official_gain60"))
    args = parser.parse_args()
    analyze(args.run, args.out)


if __name__ == "__main__":
    main()
