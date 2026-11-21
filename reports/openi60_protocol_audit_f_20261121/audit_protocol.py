#!/usr/bin/env python3
"""Read-only audit of archived OpenI60 solver requests/responses. No network or models.

This is a lexical/shape diagnostic, NOT the production parser, action validator,
scorer, or a tool executor. Embedded JSON is inspected, never executed.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import re
import sys
from typing import Any


def reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON constant: {value}")


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


DECODER = json.JSONDecoder(object_pairs_hook=unique_object, parse_constant=reject_constant)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def shape(obj: Any) -> str:
    """Only checks the two generic shapes; no runtime tool/argument validation."""
    if not isinstance(obj, dict):
        return "other"
    if "calls" in obj and "answer" in obj:
        return "ambiguous"
    if "calls" in obj:
        calls = obj["calls"]
        if not isinstance(calls, list) or not calls or not isinstance(obj.get("reason"), str):
            return "calls_bad_shape"
        if set(obj) - {"calls", "reason"}:
            return "calls_bad_shape"
        for call in calls:
            if not isinstance(call, dict):
                return "calls_bad_shape"
            if set(call) - {"tool", "args", "image_index"}:
                return "calls_bad_shape"
            if not isinstance(call.get("tool"), str) or not call["tool"].strip():
                return "calls_bad_shape"
            if not isinstance(call.get("args"), dict):
                return "calls_bad_shape"
            if "image_index" in call and (type(call["image_index"]) is not int or call["image_index"] < 1):
                return "calls_bad_shape"
        return "calls"
    if "answer" in obj:
        if set(obj) == {"answer", "reason"} and all(isinstance(obj[k], str) for k in obj):
            return "answer"
        return "answer_bad_shape"
    return "other"


def objects_in_text(text: str) -> list[dict[str, Any]]:
    """Locate decoded objects for diagnostics. Never repair/execute their content."""
    found: list[dict[str, Any]] = []
    i = 0
    while i < len(text):
        i = text.find("{", i)
        if i < 0:
            break
        try:
            obj, end = DECODER.raw_decode(text, i)
        except (ValueError, RecursionError):
            i += 1
            continue
        if isinstance(obj, dict):
            found.append(obj)
        i = max(end, i + 1)
    return found


def classify(text: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"lexical_class": "non_string_content", "whole_json": False,
                              "calls_object_candidates": 0, "shaped_action_candidates": 0}
    if not isinstance(text, str):
        return result
    text = text.strip()
    try:
        obj = DECODER.decode(text)
        result["whole_json"] = True
        result["lexical_class"] = "whole_json_" + shape(obj)
        candidates = [obj] if isinstance(obj, dict) else []
    except (ValueError, RecursionError):
        candidates = objects_in_text(text)
        shaped = [o for o in candidates if shape(o) in {"calls", "answer"}]
        if len(shaped) == 1:
            result["lexical_class"] = "mixed_text_one_" + shape(shaped[0])
        elif len(shaped) > 1:
            result["lexical_class"] = "mixed_text_multiple_action_candidates"
        else:
            result["lexical_class"] = "non_json_without_clear_action"
    result["calls_object_candidates"] = sum("calls" in o for o in candidates)
    result["shaped_action_candidates"] = sum(shape(o) in {"calls", "answer"} for o in candidates)
    return result


def message_from_response(obj: Any) -> tuple[dict[str, Any], Any]:
    if not isinstance(obj, dict):
        raise ValueError("Response must be a JSON object")
    choices = obj.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message")
        if isinstance(message, dict):
            return message, choices[0].get("finish_reason")
    if isinstance(obj.get("message"), dict):
        return obj["message"], obj.get("finish_reason")
    if "content" in obj:
        return obj, obj.get("finish_reason")
    raise ValueError("Unknown response envelope; do not silently count it as valid")


def plain(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(x.get("text", "") for x in content
                         if isinstance(x, dict) and x.get("type") == "text")
    return ""


def final_only(request: Any) -> bool:
    if not isinstance(request, dict):
        return False
    users = [m for m in request.get("messages", []) if isinstance(m, dict) and m.get("role") == "user"]
    if not users:
        return False
    text = plain(users[-1].get("content")).lower()
    return ("no tools" in text and "answer" in text and "reason" in text
            and ("previous response" in text or "original task" in text))


def order(path: Path) -> tuple[int, str]:
    name = path.parent.name
    return (int(name), name) if name.isdigit() else (10**12, name)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def audit(root: Path, out: Path, arms: list[str]) -> dict[str, Any]:
    if not root.is_dir():
        raise ValueError(f"Missing run/report directory: {root}")
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"Output directory is not empty: {out}; choose a new directory")
    paired = root / "paired_analysis" / "paired_results.csv"
    pairs: dict[str, dict[str, str]] = {}
    if paired.is_file():
        with paired.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                qid = row.get("question_id", "")
                if not qid or qid in pairs:
                    raise ValueError("Missing/duplicate question_id in paired CSV")
                pairs[qid] = row
    responses: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    errors: list[str] = []
    for arm in arms:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", arm):
            raise ValueError("Unsafe arm name")
        base = root / arm / "services" / "calls" / "R49-AGENT"
        if not base.is_dir():
            raise ValueError(f"Missing solver response archive: {base}")
        grouped: dict[str, list[Path]] = defaultdict(list)
        for response_path in base.glob("*/*/response.json"):
            grouped[response_path.parent.parent.name].append(response_path)
        if not grouped:
            raise ValueError(f"No response.json files in {base}")
        arm_rows: list[dict[str, Any]] = []
        missing_requests = 0
        observed_next_requests = 0
        for qid, paths in sorted(grouped.items()):
            paths.sort(key=order)
            qrows: list[dict[str, Any]] = []
            for index, path in enumerate(paths):
                try:
                    msg, finish = message_from_response(load(path))
                    entry = {"arm": arm, "question_id": qid, "call": path.parent.name,
                             "finish_reason": finish, "structured_tool_calls": bool(msg.get("tool_calls")),
                             **classify(msg.get("content"))}
                    entry["next_request_present"] = False
                    entry["next_forced_final_only"] = False
                    if index + 1 < len(paths):
                        request_path = paths[index + 1].parent / "request.json"
                        if request_path.is_file():
                            entry["next_request_present"] = True
                            observed_next_requests += 1
                            entry["next_forced_final_only"] = final_only(load(request_path))
                        else:
                            missing_requests += 1
                    entry["calls_candidate_then_final_only_flag"] = bool(
                        entry["calls_object_candidates"] and entry["next_forced_final_only"])
                    entry["response_path"] = str(path.relative_to(root))
                    qrows.append(entry)
                    responses.append(entry)
                    arm_rows.append(entry)
                except (OSError, ValueError, TypeError, RecursionError) as error:
                    errors.append(f"{path.relative_to(root)}: {error}")
            row = pairs.get(qid, {})
            tool_count = row.get(arm + "_tool_calls")
            prediction_status = None
            prediction_paths = list((root / arm / "predictions").glob("*/" + qid + ".json"))
            if len(prediction_paths) == 1:
                try:
                    prediction = load(prediction_paths[0])
                    prediction_status = prediction.get("status")
                    if tool_count in (None, ""):
                        tool_count = prediction.get("tool_calls")
                except (OSError, ValueError, AttributeError) as error:
                    errors.append(f"{prediction_paths[0]}: {error}")
            if tool_count in (None, ""):
                tool_count = None
            if tool_count is not None:
                try:
                    tool_count = int(tool_count)
                except (ValueError, TypeError):
                    errors.append(f"{arm}/{qid}: nonnumeric tool count")
                    tool_count = None
            questions.append({"arm": arm, "question_id": qid, "category": row.get("category"),
                              "archived_solver_responses": len(paths), "readable_solver_responses": len(qrows),
                              "tool_calls": tool_count, "prediction_status": prediction_status,
                              "mixed_text_calls_responses": sum(r["lexical_class"] == "mixed_text_one_calls" for r in qrows),
                              "forced_final_after_calls_flags": sum(r["calls_candidate_then_final_only_flag"] for r in qrows),
                              "finish_reason_length_count": sum(r["finish_reason"] == "length" for r in qrows)})
        counts = Counter(r["lexical_class"] for r in arm_rows)
        aq = [q for q in questions if q["arm"] == arm]
        summaries[arm] = {
            "archived_questions": len(grouped), "readable_solver_responses": len(arm_rows),
            "expected_solver_responses_from_paired_csv": sum(int(r.get(arm + "_main_calls") or 0) for r in pairs.values()) if pairs else None,
            "questions_expected_from_paired_csv": len(pairs) if pairs else None,
            "lexical_class_counts": dict(counts),
            "questions_with_recorded_tool_count": sum(q["tool_calls"] is not None for q in aq),
            "zero_tool_questions": sum(q["tool_calls"] == 0 for q in aq),
            "calls_candidate_then_final_only_flags": sum(r["calls_candidate_then_final_only_flag"] for r in arm_rows),
            "questions_with_calls_candidate_then_final_only_flag": sum(q["forced_final_after_calls_flags"] > 0 for q in aq),
            "readable_next_requests": observed_next_requests, "missing_next_requests": missing_requests,
            "finish_reason_length_count": sum(r["finish_reason"] == "length" for r in arm_rows),
        }
    result = {"root": str(root), "model_calls_made_by_this_script": 0,
              "read_only_source": True, "coverage": summaries, "read_errors": errors,
              "limits": ["Generic JSON shape checks are not the native parser/validator.",
                         "Embedded JSON is inspected only, never executed.",
                         "A flag is not a causal accuracy-loss estimate.",
                         "Missing/unreadable files are reported, not treated as valid.",
                         "No original score, prediction, feedback or memory is modified."]}
    out.mkdir(parents=True, exist_ok=True)
    (out / "protocol_audit_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out / "response_audit.csv", responses,
              ["arm", "question_id", "call", "lexical_class", "whole_json", "calls_object_candidates",
               "shaped_action_candidates", "structured_tool_calls", "finish_reason", "next_request_present",
               "next_forced_final_only", "calls_candidate_then_final_only_flag", "response_path"])
    write_csv(out / "question_audit.csv", questions,
              ["arm", "question_id", "category", "archived_solver_responses", "readable_solver_responses",
               "tool_calls", "prediction_status", "mixed_text_calls_responses",
               "forced_final_after_calls_flags", "finish_reason_length_count"])
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True, help="Directory containing B0/, L1/ and paired_analysis/")
    p.add_argument("--out", type=Path, required=True, help="New/empty output directory")
    p.add_argument("--arms", nargs="+", default=["B0", "L1"])
    args = p.parse_args()
    try:
        result = audit(args.root.resolve(), args.out.resolve(), args.arms)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["read_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
