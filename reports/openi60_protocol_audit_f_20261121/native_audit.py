"""Replay historical control flow with the frozen native parser and validator."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import sys

from audit_protocol import classify, final_only, message_from_response, objects_in_text


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path, values):
    if not values:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(values[0]))
        writer.writeheader()
        writer.writerows(values)


def native_modules(native, frozen):
    original = frozen["config"]["native_root"]
    names = ["run_cxr_action_r41", "toolsets_r54", "cxr_task_completion_r43",
             "skill_services_r54", "skill_services_r55", "cxr_image_memory_r44",
             "cxr_online_primitives_r49", "score_cxr_vqa_extension"]
    provenance = []
    for name in names:
        relative = "code/M5/experiments/" + name + ".py"
        path = native / relative
        expected = frozen["source_files"][original + "/" + relative]
        # Reuse the experiment's existing frozen identity to select its actual source version.
        matches = hashlib.sha256(path.read_bytes()).hexdigest() == expected
        provenance.append({"module": name, "historical_server_path": original + "/" + relative,
                           "local_path": str(path), "matches_existing_frozen_identity": matches})
        if not matches:
            raise ValueError("Native source differs from frozen run: " + name)
    sys.path[:0] = [str(native), str(native / "code/M5/experiments"), str(native / "code/M5")]
    modules = {name: importlib.import_module(name) for name in names}
    for name, module in modules.items():
        if Path(module.__file__).resolve() != (native / "code/M5/experiments" / (name + ".py")).resolve():
            raise ValueError("Unexpected native import: " + name)
    return modules, provenance


def audit(root, native, out):
    if out.exists() and any(out.iterdir()):
        raise ValueError("Choose a new output directory")
    out.mkdir(parents=True, exist_ok=True)
    frozen = read(root / "frozen.json")
    modules, provenance = native_modules(native, frozen)
    parser = modules["run_cxr_action_r41"]
    base = modules["toolsets_r54"]
    completion = modules["cxr_task_completion_r43"]
    failure_reason = modules["cxr_image_memory_r44"].tool_failure_reason
    digest = modules["cxr_online_primitives_r49"].digest
    snapshots = {"parse": inspect.getsource(parser.parse), "answer": inspect.getsource(parser.answer),
                 "validate_actions": inspect.getsource(base.validate_actions),
                 "resolve_action": inspect.getsource(base.resolve_action),
                 "execute": inspect.getsource(modules["skill_services_r54"].Services.execute),
                 "forced_final_prompt": inspect.getsource(completion.prompt)}
    write_json(out / "native_functions.json", snapshots)
    expected_ids = frozen["cohort"]["selected_ids"]
    decisions, questions, missing, discrepancies, examples, tool_rows = [], [], [], [], [], []
    summaries = {}
    for arm in ("B0", "L1"):
        armroot = root / arm
        manifest = read(armroot / "manifest.json")
        runtime = manifest["runtime"]
        rows = {row["question_id"]: row for row in manifest["inputs"]}
        counts = Counter()
        image_assets = set()
        archive = armroot / "services/calls/R49-AGENT"
        for qid in expected_ids:
            row = rows[qid]
            predpath = armroot / "predictions" / manifest["arm"] / (qid + ".json")
            steppath = armroot / "steps" / (qid + ".json")
            for path in (predpath, steppath):
                if not path.is_file():
                    missing.append(str(path.relative_to(root)))
            if not predpath.is_file() or not steppath.is_file():
                continue
            prediction, steps = read(predpath), read(steppath)
            expected_calls = prediction["main_calls"]
            seen, observations, used = {}, [], 0
            qstats = Counter()
            prior_invalid = False
            invalid_total = 0
            for ordinal in range(1, expected_calls + 1):
                folder = archive / qid / str(ordinal)
                request_path, response_path = folder / "request.json", folder / "response.json"
                for path in (request_path, response_path, folder / "result.json"):
                    if not path.is_file():
                        missing.append(str(path.relative_to(root)))
                if not request_path.is_file() or not response_path.is_file():
                    continue
                response = read(response_path)
                message, finish = message_from_response(response)
                raw = message["content"]
                request = read(request_path)
                def collect_assets(value):
                    if isinstance(value, dict):
                        if "cxr_request_image_base64_sha256" in value:
                            image_assets.add(value["cxr_request_image_base64_sha256"])
                        for child in value.values():collect_assets(child)
                    elif isinstance(value, list):
                        for child in value:collect_assets(child)
                collect_assets(request)
                counts["request_archives"] += 1
                counts["accounting_receipts"] += (folder / "result.json").is_file()
                next_path = archive / qid / str(ordinal + 1) / "request.json"
                next_final = next_path.is_file() and final_only(read(next_path))
                current_final = final_only(request)
                if ordinal > len(steps) or steps[ordinal-1]["response"] != raw:
                    discrepancies.append(f"{arm}/{qid}/{ordinal}: step/archive mismatch")
                lexical = classify(raw)
                candidates = [obj for obj in objects_in_text(raw) if isinstance(obj.get("calls"), list)]
                proposed = sum(len(obj["calls"]) for obj in candidates)
                record = dict(arm=arm, question_id=qid, call=ordinal,
                              decision_phase="forced_final_only" if current_final else "tools_or_final",
                              lexical_class=lexical["lexical_class"], parse_ok=False,
                              parse_error_type="", parse_error="", native_answer_present=False,
                              native_answer_legal=False, validate_attempted=False, validate_ok=False,
                              validate_error_type="", validate_error="", outcome="",
                              proposed=proposed, accepted=0, rejected=0, executed=0, failed=0,
                              native_retry_call=prior_invalid,
                              native_invalid_count_before=invalid_total,
                              next_forced_final_only=bool(next_final),
                              calls_candidate_then_final_only=bool(candidates and next_final),
                              finish_reason=finish, prompt_tokens=response.get("usage", {}).get("prompt_tokens"),
                              completion_tokens=response.get("usage", {}).get("completion_tokens"),
                              response_path=response_path.relative_to(root).as_posix())
                obj = {}
                try:
                    obj = parser.parse(raw)
                    record["parse_ok"] = True
                except (ValueError, IndexError) as error:
                    record["parse_error_type"] = type(error).__name__
                    record["parse_error"] = str(error)
                result = parser.answer(obj)
                record["native_answer_present"] = bool(result)
                legal = result is not None and not completion.unscorable(row, result)
                record["native_answer_legal"] = legal
                actions = obj.get("calls")
                invalid = False
                if legal:
                    record["outcome"] = "forced_final_answer" if current_final else "model_final_answer"
                elif not isinstance(actions, list) or not actions:
                    invalid = True
                    record["outcome"] = "parse_rejected_plan" if proposed else "invalid_nonplan_output"
                    record["rejected"] = proposed
                else:
                    record["validate_attempted"] = True
                    try:
                        actions = base.validate_actions(obj, runtime, "M", len(actions), len(row["images"]))
                        record["validate_ok"] = True
                    except (ValueError, TypeError, KeyError) as error:
                        invalid = True
                        record["outcome"] = "validation_rejected_plan"
                        record["validate_error_type"] = type(error).__name__
                        record["validate_error"] = str(error)
                        record["rejected"] = len(actions)
                    if record["validate_ok"]:
                        record["accepted"] = len(actions)
                        record["outcome"] = "accepted_tool_plan"
                        for action in actions:
                            actual = base.resolve_action(action, observations)
                            signature = digest(actual)
                            seen[signature] = seen.get(signature, 0) + 1
                            if seen[signature] >= 3:
                                record["outcome"] = "accepted_not_dispatched_no_progress"
                                break
                            used += 1
                            selection = armroot / "services/tool_selections/R49-AGENT" / qid / f"{used}.json"
                            if not selection.is_file():
                                missing.append(selection.relative_to(root).as_posix())
                                continue
                            obs = read(selection)
                            fail = failure_reason(obs)
                            tool_rows.append(dict(arm=arm, question_id=qid, call=ordinal, tool_ordinal=used,
                                                  tool=actual["tool"], selection_tool=obs.get("tool"),
                                                  args=json.dumps(actual["args"], ensure_ascii=False),
                                                  image_index=actual.get("image_index", 1), status=obs["status"],
                                                  failed=bool(fail), failure_reason=fail or "",
                                                  error=obs.get("error", ""),
                                                  cache_hit=obs.get("cache_hit"),
                                                  path=selection.relative_to(root).as_posix()))
                            if actual["tool"] != obs.get("tool"):
                                discrepancies.append(f"{arm}/{qid}/{ordinal}: tool receipt mismatch")
                            record["executed"] += 1
                            record["failed"] += bool(fail)
                            observations.append(obs)
                if invalid:
                    invalid_total += 1
                prior_invalid = invalid
                for field in ("proposed", "accepted", "rejected", "executed", "failed"):
                    qstats[field] += record[field]
                qstats["parse_errors"] += not record["parse_ok"]
                qstats["validation_errors"] += record["validate_attempted"] and not record["validate_ok"]
                qstats["calls_then_forced_final"] += record["calls_candidate_then_final_only"]
                qstats["native_retry_calls"] += record["native_retry_call"]
                qstats[record["outcome"]] += 1
                qstats["responses"] += 1
                decisions.append(record)
                if record["calls_candidate_then_final_only"] or record["validate_error"]:
                    examples.append({"arm": arm, "question_id": qid, "call": ordinal,
                                     "raw": raw, "native_result": record,
                                     "following_last_user": read(next_path)["messages"][-1] if next_path.is_file() else None})
            selection_ordinals = {p.stem for p in (armroot / "services/tool_selections/R49-AGENT" / qid).glob("*.json")}
            if selection_ordinals != {str(i) for i in range(1, prediction["tool_calls"] + 1)}:
                discrepancies.append(f"{arm}/{qid}: selection coverage differs from prediction")
            if used != prediction["tool_calls"] or used != len(prediction.get("observations", [])):
                discrepancies.append(f"{arm}/{qid}: dispatch/observation count mismatch")
            observed_ordinals = {p.name for p in (archive / qid).iterdir() if p.is_dir()}
            if observed_ordinals != {str(i) for i in range(1, expected_calls + 1)}:
                discrepancies.append(f"{arm}/{qid}: response ordinals differ from main_calls")
            qrecord = dict(arm=arm, question_id=qid, expected_main_calls=expected_calls,
                           archived_responses=qstats["responses"], proposed=qstats["proposed"],
                           accepted=qstats["accepted"], rejected=qstats["rejected"],
                           executed=qstats["executed"], failed=qstats["failed"],
                           parse_errors=qstats["parse_errors"], validation_errors=qstats["validation_errors"],
                           calls_then_forced_final=qstats["calls_then_forced_final"],
                           native_retry_calls=qstats["native_retry_calls"],
                           voluntary_final_answers=qstats["model_final_answer"],
                           forced_final_answers=qstats["forced_final_answer"],
                           terminal_status=prediction["status"])
            questions.append(qrecord)
            counts.update(qstats)
        for asset in sorted(image_assets):
            path = armroot / "services/request_image_base64" / asset
            if not path.is_file():missing.append(path.relative_to(root).as_posix())
        extras = sorted({p.name for p in archive.iterdir() if p.is_dir()} - set(expected_ids))
        summaries[arm] = {**dict(counts), "expected_questions": len(expected_ids),
                          "questions_audited": sum(q["arm"] == arm for q in questions),
                          "zero_tool_questions": sum(q["arm"] == arm and q["executed"] == 0 for q in questions),
                          "zero_tool_with_calls_then_forced_final": sum(q["arm"] == arm and q["executed"] == 0 and q["calls_then_forced_final"] > 0 for q in questions),
                          "zero_tool_with_no_proposed_calls": sum(q["arm"] == arm and q["executed"] == 0 and q["proposed"] == 0 for q in questions),
                          "questions_calls_then_forced_final": sum(q["arm"] == arm and q["calls_then_forced_final"] > 0 for q in questions),
                          "extra_archived_questions": extras,
                          "referenced_image_assets": len(image_assets),
                          "terminal_statuses": dict(Counter(q["terminal_status"] for q in questions if q["arm"] == arm)),
                          "finish_reasons": dict(Counter(r["finish_reason"] for r in decisions if r["arm"] == arm))}
    on_server = native.as_posix() == frozen["config"]["native_root"] and root.as_posix() == frozen["config"]["work_dir"]
    summary = {"historical_server_root": frozen["config"]["work_dir"], "read_root": str(root),
               "source_provenance": provenance,
               "native_verification_mode": "imported actual frozen server modules in place" if on_server else "imported frozen-identical server source locally",
               "server_live_import_status": "verified in place" if on_server else "not performed by this local replay",
               "models_called": 0, "tools_called": 0, "memory_writes": 0,
               "coverage": summaries, "missing_files": missing, "discrepancies": discrepancies,
               "count_units": {"proposed": "calls items in diagnostically decoded candidate objects, never executed by this audit",
                               "accepted": "calls items accepted by unchanged native validate_actions",
                               "rejected": "proposed calls items rejected by native parse or validate_actions",
                               "executed": "dispatch receipts in tool_selections, including cache hits and failed returns",
                               "failed": "executed receipts classified by native tool_failure_reason"},
               "scope": "All expected cohort questions and main-call ordinals; no reference labels read by native replay"}
    write_csv(out / "native_response_audit.csv", decisions)
    write_csv(out / "native_question_audit.csv", questions)
    write_csv(out / "native_tool_audit.csv", tool_rows)
    write_json(out / "failure_examples.json", examples)
    write_json(out / "native_summary.json", summary)
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--native", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    result = audit(args.root.resolve(), args.native.resolve(), args.out.resolve())
    print(json.dumps({k: v for k, v in result.items() if k != "source_provenance"}, ensure_ascii=False, indent=2))
    raise SystemExit(bool(result["missing_files"] or result["discrepancies"]))
