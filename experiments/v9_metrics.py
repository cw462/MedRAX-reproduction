"""Label-isolated V9 scoring with planned denominators and paired gate controls.

Run only after generation has ended. This module imports no inference component,
does not call a model, and never writes reference labels back into run results.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import statistics

GROUPS = ("D", "DK", "DKB", "DKC")
FAILED = {"p0_failed", "preflight_failed", "failed", "error", "invalid_answer", "not_run", "skipped"}


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if line.strip():
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path.name}:{number}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Expected object at {path.name}:{number}")
            rows.append(value)
    return rows


def letter(value):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*([A-F])[.)]?\s*", value)
    return match.group(1) if match else None


def _ratio(numerator, denominator):
    return round(numerator / denominator, 6) if denominator else None


def _qid(row):
    value = row.get("question_id", row.get("qid"))
    if not isinstance(value, str) or not value:
        raise ValueError("A result or selection row lacks question_id")
    return value


def _unique(rows, planned, *, grouped=False):
    indexed = {}
    for row in rows:
        if row.get("record_type") in ("started", "start"):
            continue
        qid = _qid(row)
        if qid not in planned:
            raise ValueError(f"Unplanned question in results: {qid}")
        if grouped:
            group = row.get("group")
            if group not in GROUPS:
                raise ValueError(f"Unknown group for {qid}: {group}")
            key = (qid, group)
        else:
            key = qid
        if key in indexed:
            raise ValueError(f"Duplicate terminal result: {key}")
        indexed[key] = row
    return indexed


def _labels(path, planned):
    result, seen = {}, set()
    for row in read_jsonl(path):
        qid = _qid(row)
        if qid in seen:
            raise ValueError(f"Duplicate isolated label: {qid}")
        seen.add(qid)
        if qid not in planned:
            continue
        answer = letter(row.get("answer"))
        if answer is None:
            raise ValueError(f"Invalid isolated label: {qid}")
        result[qid] = answer
    if set(result) != set(planned):
        raise ValueError("Isolated labels must cover every planned question")
    return result


def _prediction(row, key, *, p0=False):
    if not row or (p0 and row.get("status") in FAILED):
        return None
    value = row.get(key)
    if p0 and value is None:
        value = row.get("letter")
    return letter(value)


def _summary(predictions, labels, qids):
    counts = Counter(correct=0, incorrect=0, missing=0)
    for qid in qids:
        prediction = predictions.get(qid)
        counts["missing" if prediction is None else "correct" if prediction == labels[qid] else "incorrect"] += 1
    completed = counts["correct"] + counts["incorrect"]
    return {**counts, "planned_n": len(qids), "completed_n": completed,
            "accuracy_over_planned": _ratio(counts["correct"], len(qids)),
            "accuracy_among_completed": _ratio(counts["correct"], completed)}


def _paired(initial, predictions, labels, qids):
    indices = {key: [] for key in ("corrections", "harms", "harms_missing", "harms_wrong_answer",
                                  "kept_correct", "still_not_correct", "p0_failed", "recovered_from_p0_failure")}
    for qid in qids:
        first, answer, gold = initial.get(qid), predictions.get(qid), labels[qid]
        if first is None:
            indices["p0_failed"].append(qid)
            if answer == gold:
                indices["recovered_from_p0_failure"].append(qid)
        elif first != gold and answer == gold:
            indices["corrections"].append(qid)
        elif first == gold and answer != gold:
            indices["harms"].append(qid)
            indices["harms_missing" if answer is None else "harms_wrong_answer"].append(qid)
        else:
            indices["kept_correct" if first == gold else "still_not_correct"].append(qid)
    result = {key: len(value) for key, value in indices.items()}
    result.update(net=result["corrections"] - result["harms"], question_ids=indices)
    return result


def _gate_stats(records, initial, valid_candidates, finals, labels, qids):
    indices = {key: [] for key in ("correction_candidates", "harmful_candidates", "corrections_retained",
                                  "harms_prevented", "false_rejected_corrections", "wrong_acceptances",
                                  "corrections_lost_to_error", "harms_saved_by_fallback", "candidate_errors",
                                  "gate_errors", "exception_fallbacks", "uncertain_candidates", "skipped_p0_failures")}
    counts = Counter()
    for qid in qids:
        row = records.get(qid) or {}
        first, cand, final, gold = initial.get(qid), valid_candidates.get(qid), finals.get(qid), labels[qid]
        gate = row.get("gate") or {}
        decision = gate.get("decision")
        candidate_error = first is not None and bool(row.get("candidate_error"))
        gate_error = first is not None and (bool(row.get("gate_error")) or decision == "gate_error")
        fallback = first is not None and (candidate_error or gate_error or row.get("fallback") in ("candidate_error", "gate_error"))
        adjudicated = not candidate_error and not gate_error and not fallback
        counts[str(decision or "not_called")] += 1
        for key, present in (("candidate_errors", candidate_error), ("gate_errors", gate_error),
                             ("exception_fallbacks", fallback),
                             ("uncertain_candidates", first is not None and cand is None and not candidate_error),
                             ("skipped_p0_failures", bool(row) and first is None)):
            if present:
                indices[key].append(qid)
        if first is None or cand is None or cand == first:
            continue
        if first != gold and cand == gold:
            indices["correction_candidates"].append(qid)
            if adjudicated and decision == "accept" and final == cand:
                indices["corrections_retained"].append(qid)
            elif adjudicated and decision == "retain" and final == first:
                indices["false_rejected_corrections"].append(qid)
            elif fallback:
                indices["corrections_lost_to_error"].append(qid)
        elif first == gold and cand != gold:
            indices["harmful_candidates"].append(qid)
            if adjudicated and decision == "retain" and final == first:
                indices["harms_prevented"].append(qid)
            elif adjudicated and decision == "accept" and final == cand:
                indices["wrong_acceptances"].append(qid)
            elif fallback and final == first:
                indices["harms_saved_by_fallback"].append(qid)
    result = {key: len(value) for key, value in indices.items()}
    result.update(correction_retention_rate=_ratio(result["corrections_retained"], result["correction_candidates"]),
                  harm_prevention_rate=_ratio(result["harms_prevented"], result["harmful_candidates"]),
                  decisions=dict(counts), question_ids=indices)
    return result


def _finite_number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def _sum_report(values):
    known = [number for value in values if (number := _finite_number(value)) is not None]
    return {"sum_observed": round(sum(known), 6) if known else None,
            "observed_n": len(known), "missing_n": len(values) - len(known)}


def _resources(rows):
    rows = list(rows)
    elapsed = []
    for row in rows:
        timing = row.get("timing") or {}
        elapsed.append(timing.get("elapsed_s", timing.get("elapsed_seconds", row.get("elapsed_s"))))
    known_elapsed = [number for value in elapsed if (number := _finite_number(value)) is not None]
    report = {"records_n": len(rows), "elapsed_s": _sum_report(elapsed),
              "elapsed_s_median": statistics.median(known_elapsed) if known_elapsed else None,
              "elapsed_s_max": max(known_elapsed) if known_elapsed else None}
    aliases = {"model_calls": ("model_calls", "actual_model_calls"),
               "tool_calls": ("tool_calls", "actual_tool_attempts"),
               "input_tokens": ("input_tokens",), "output_tokens": ("output_tokens",),
               "total_tokens": ("total_tokens",), "k_tokens": ("k_tokens",), "e_tokens": ("e_tokens",),
               "logical_cost_cny": ("logical_cost_cny",), "incremental_cost_cny": ("incremental_cost_cny",),
               "provider_actual_cost_cny": ("provider_actual_cost_cny",)}
    for canonical, keys in aliases.items():
        values = []
        for row in rows:
            accounting = row.get("accounting") or {}
            value = None
            for key in keys:
                if key in accounting:
                    value = accounting[key]
                    break
                if key in row:
                    value = row[key]
                    break
            values.append(value)
        report[canonical] = _sum_report(values)
    report["cost_note"] = ("Logical and incremental costs are runner-recorded estimates/settlements, not independently "
                           "verified provider billing. Shared P0 cost is reported once, outside branch totals.")
    report["cost_bases"] = sorted({str((row.get("accounting") or {}).get("cost_basis")) for row in rows
                                  if (row.get("accounting") or {}).get("cost_basis")})
    report["memory_context_token_estimates"] = {
        "knowledge": _sum_report([(row.get("memory_tokens") or {}).get("k_token_estimate") for row in rows]),
        "experience": _sum_report([(row.get("memory_tokens") or {}).get("e_token_estimate") for row in rows]),
        "methods": sorted({str((row.get("memory_tokens") or {}).get("token_count_method")) for row in rows
                           if (row.get("memory_tokens") or {}).get("token_count_method")}),
        "note": "Injected context token estimates; these are separate from total provider-recorded request usage."}
    return report


def _observations(rows):
    total, known_new, known_no, unknown, branches_with_new = 0, 0, 0, 0, 0
    for row in rows:
        usable = 0
        for item in row.get("new_observations") or []:
            total += 1
            flag = item.get("is_new_usable") if isinstance(item, dict) else None
            if flag is None and isinstance(item, dict):
                flag = item.get("new_information")
            if flag is True:
                usable += 1
                known_new += 1
            elif flag is False:
                known_no += 1
            else:
                unknown += 1
        branches_with_new += usable > 0
    return {"collected_observations": total, "explicit_new_usable": known_new,
            "explicit_not_new_usable": known_no, "unadjudicated": unknown,
            "branches_with_explicit_new_usable": branches_with_new,
            "note": "A tool call or a repeated diagnosis is not itself new usable evidence."}


def score(selection, p0_rows, candidate_rows, labels, *, allow_partial=False):
    """Pure scoring API; labels must be a mapping covering the selection exactly."""
    rows = selection.get("rows", [])
    planned = [_qid(row) for row in rows]
    if not planned or len(planned) != len(set(planned)):
        raise ValueError("Selection must contain unique planned questions")
    if selection.get("planned_n", len(planned)) != len(planned):
        raise ValueError("selection.planned_n differs from its rows")
    if set(labels) != set(planned) or any(letter(labels[qid]) is None for qid in planned):
        raise ValueError("Labels must cover exactly the planned selection")
    labels = {qid: letter(labels[qid]) for qid in planned}
    p0 = _unique(p0_rows, planned)
    candidates = _unique(candidate_rows, planned, grouped=True)
    complete = len(p0) == len(planned) and len(candidates) == len(planned) * len(GROUPS)
    if not complete and not allow_partial:
        raise ValueError("Generation has incomplete terminals; do not score with labels while inference is running")
    initial = {qid: _prediction(p0.get(qid), "initial", p0=True) for qid in planned}
    groups, details = {}, []
    common_all = [qid for qid in planned if initial[qid] is not None and all(
        _prediction(candidates.get((qid, group)), "candidate") is not None
        and _prediction(candidates.get((qid, group)), "final") is not None for group in GROUPS)]
    for group in GROUPS:
        records = {qid: candidates[(qid, group)] for qid in planned if (qid, group) in candidates}
        raw = {qid: _prediction(records.get(qid), "candidate") for qid in planned}
        valid = {qid: raw[qid] if not (records.get(qid) or {}).get("candidate_error") else None for qid in planned}
        final = {qid: _prediction(records.get(qid), "final") for qid in planned}
        accepted = {qid: valid[qid] if valid[qid] is not None else initial[qid] for qid in planned}
        for qid, row in records.items():
            declared = _prediction(row, "initial")
            if declared != initial[qid]:
                raise ValueError(f"Branch does not share recorded P0: {qid}/{group}")
            if initial[qid] is None and final[qid] is not None:
                raise ValueError(f"P0 failure cannot acquire a fabricated final: {qid}/{group}")
            if valid[qid] is not None and initial[qid] is not None and final[qid] not in (initial[qid], valid[qid], None):
                raise ValueError(f"Gate produced a third answer: {qid}/{group}")
        common = [qid for qid in planned if initial[qid] is not None and raw[qid] is not None and final[qid] is not None]
        groups[group] = {
            "terminal_records_n": len(records), "status": "未运行" if not records else "completed" if len(records) == len(planned) else "incomplete",
            "raw_candidate": _summary(raw, labels, planned), "candidate_paired": _paired(initial, raw, labels, planned),
            "valid_candidate_n": sum(value is not None for value in valid.values()),
            "policies": {"always_retain": {"summary": _summary(initial, labels, planned), "paired": _paired(initial, initial, labels, planned)},
                         "always_accept": {"summary": _summary(accepted, labels, planned), "paired": _paired(initial, accepted, labels, planned)},
                         "evidence_gate": {"summary": _summary(final, labels, planned), "paired": _paired(initial, final, labels, planned)}},
            "gate": _gate_stats(records, initial, valid, final, labels, planned),
            "common_completed": {"n": len(common), "p0": _summary(initial, labels, common),
                                 "candidate": _summary(raw, labels, common), "final": _summary(final, labels, common)},
            "resources": _resources(records.values()), "observations": _observations(records.values())}
        for qid in planned:
            first, cand, answer, gold = initial[qid], raw[qid], final[qid], labels[qid]
            events = []
            for name, value in (("candidate", cand), ("final", answer)):
                if first is not None and first != gold and value == gold:
                    events.append(name + "_correction")
                elif first == gold and value != gold:
                    events.append(name + ("_harm_missing" if value is None else "_harm_wrong_answer"))
            if events:
                row = records.get(qid) or {}
                details.append({"question_id": qid, "group": group, "events": events, "initial": first,
                                "candidate": cand, "final": answer, "reference": gold,
                                "gate_decision": (row.get("gate") or {}).get("decision"),
                                "candidate_error": bool(row.get("candidate_error")), "gate_error": bool(row.get("gate_error")),
                                "fallback": bool(row.get("fallback")), "changed_attributes": row.get("changed_attributes"),
                                "original_observation_refs": row.get("original_observation_refs", row.get("observation_refs", [])),
                                "new_observation_refs": [item.get("evidence_ref", item.get("id", item.get("observation_id"))) if isinstance(item, dict) else item
                                                         for item in row.get("new_observations") or []],
                                "evidence_refs": (row.get("gate") or {}).get("evidence_refs", []),
                                "candidate_record_present": bool(row)})
    return {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
            "run_status": "completed" if complete else "incomplete_provisional", "planned_n": len(planned),
            "planned_groups": list(GROUPS), "p0_terminal_n": len(p0), "candidate_terminal_n": len(candidates),
            "p0": _summary(initial, labels, planned), "p0_resources": _resources(p0.values()), "groups": groups,
            "all_groups_common_completed": {"n": len(common_all), "question_ids": common_all}, "case_events": details,
            "case_clustering": {"unit": "case_id if supplied by selection; otherwise qid prefix",
                                "case_ids": {qid: str(row.get("case_id", qid.split("_", 1)[0])) for qid, row in zip(planned, rows)},
                                "note": "No independent-sample p-values are claimed across repeated branches of one case."},
            "limitations": ["Fixed development diagnostic; not an independent test or a stable effect estimate.",
                            "Missing answers count as not correct in planned denominators.",
                            "Exception fallback is not a successful gate rejection.",
                            "Candidate harms include failures; gate opportunity denominators include only legal changed candidates.",
                            "Clinical evidence quality is not inferred from tool calls, citations or model self-report.",
                            "No inference-stage file has been modified by scoring."]}


def _percent(value):
    return "N/A" if value is None else f"{100 * value:.1f}%"


def _markdown(payload):
    lines = ["# V9 paired diagnostic metrics", "", f"Run status: **{payload['run_status']}**. Planned N={payload['planned_n']}; failures remain in this denominator.", "",
             "| Group/policy | Correct/N | Missing | Accuracy | Corrections | Harms | Net |", "|---|---:|---:|---:|---:|---:|---:|"]
    p0 = payload["p0"]
    lines.append(f"| P0 | {p0['correct']}/{p0['planned_n']} | {p0['missing']} | {_percent(p0['accuracy_over_planned'])} | — | — | — |")
    for group, data in payload["groups"].items():
        display_group = group + (" (未运行)" if data["status"] == "未运行" else "")
        for name, summary, paired in [("raw candidate", data["raw_candidate"], data["candidate_paired"])]+[
                (name, policy["summary"], policy["paired"]) for name, policy in data["policies"].items()]:
            lines.append(f"| {display_group} {name} | {summary['correct']}/{summary['planned_n']} | {summary['missing']} | "
                         f"{_percent(summary['accuracy_over_planned'])} | {paired['corrections']} | {paired['harms']} | {paired['net']:+d} |")
    lines += ["", "## Gate decisions on the same legal changed candidates", "",
              "| Group | Corrections retained/available | Retention | Harms prevented/available | Prevention | False rejects | Wrong accepts | Error fallbacks |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for group, data in payload["groups"].items():
        gate = data["gate"]
        lines.append(f"| {group} | {gate['corrections_retained']}/{gate['correction_candidates']} | {_percent(gate['correction_retention_rate'])} | "
                     f"{gate['harms_prevented']}/{gate['harmful_candidates']} | {_percent(gate['harm_prevention_rate'])} | "
                     f"{gate['false_rejected_corrections']} | {gate['wrong_acceptances']} | {gate['exception_fallbacks']} |")
    lines += ["", "Fallbacks are counted separately and never credited as successful harm prevention.", "", "## Common completed samples (secondary)", "",
              "| Group | Common N | P0 correct | Candidate correct | Final correct |", "|---|---:|---:|---:|---:|"]
    for group, data in payload["groups"].items():
        common = data["common_completed"]
        lines.append(f"| {group} | {common['n']} | {common['p0']['correct']} | {common['candidate']['correct']} | {common['final']['correct']} |")
    lines += ["", f"All-four-group common completed N={payload['all_groups_common_completed']['n']}.", "",
              "## Recorded time and resources", "", "| Stage | Timed records | Elapsed total (s) | Median (s) | Model calls | Tool calls | Input tokens | Output tokens | Logical CNY | Incremental CNY |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, res in [("shared P0", payload["p0_resources"])]+[(name, group["resources"]) for name, group in payload["groups"].items()]:
        def value(key):
            result = res[key]["sum_observed"]
            return "N/A" if result is None else str(result)
        median = res["elapsed_s_median"]
        lines.append(f"| {name} | {res['elapsed_s']['observed_n']}/{res['records_n']} | {value('elapsed_s')} | "
                     f"{'N/A' if median is None else round(median, 3)} | {value('model_calls')} | {value('tool_calls')} | "
                     f"{value('input_tokens')} | {value('output_tokens')} | {value('logical_cost_cny')} | {value('incremental_cost_cny')} |")
    lines += ["", "Missing accounting fields remain N/A. Call counts do not substitute for measured duration. Shared P0 is charged once; branch totals exclude it. Cost is not independently verified provider billing.", "",
              "## Injected context token estimates", "",
              "| Group | Knowledge token estimate | Experience token estimate | Method |", "|---|---:|---:|---|"]
    for group, data in payload["groups"].items():
        mem = data["resources"]["memory_context_token_estimates"]
        def estimate(key):
            value = mem[key]["sum_observed"]
            return "N/A" if value is None else str(value)
        lines.append(f"| {group} | {estimate('knowledge')} | {estimate('experience')} | {', '.join(mem['methods']) or 'N/A'} |")
    lines += ["", "Knowledge and experience values are injected-context estimates, separate from provider request usage.", "",
              "## New observations", "", "| Group | Collected | Explicit new usable | Explicit not new usable | Unadjudicated |", "|---|---:|---:|---:|---:|"]
    for group, data in payload["groups"].items():
        obs = data["observations"]
        lines.append(f"| {group} | {obs['collected_observations']} | {obs['explicit_new_usable']} | {obs['explicit_not_new_usable']} | {obs['unadjudicated']} |")
    lines += ["", "## Limits", ""] + ["- " + item for item in payload["limitations"]]
    if payload["run_status"] != "completed":
        lines += ["", "**Provisional:** missing unfinished groups are marked 未运行/incomplete in JSON; no continuation or efficacy conclusion is drawn."]
    return "\n".join(lines) + "\n"


def _review(payload):
    lines = ["# V9 correction and harm case review", "", f"Status: {payload['run_status']}. All candidate/final correction and harm events are included; missing candidates are retained as harm events where P0 was correct.", ""]
    if not payload["case_events"]:
        lines += ["No correction or harm events were observed in the available records.", ""]
    for event in payload["case_events"]:
        lines += [f"## {event['question_id']} / {event['group']}", "",
                  "Observed scoring facts:", "",
                  f"- Event(s): {', '.join(event['events'])}.",
                  f"- P0={event['initial']}; candidate={event['candidate']}; final={event['final']}; isolated reference={event['reference']}.",
                  f"- Gate={event['gate_decision']}; candidate_error={event['candidate_error']}; gate_error={event['gate_error']}; fallback={event['fallback']}.",
                  f"- Candidate terminal present: {event['candidate_record_present']}.",
                  f"- Original observation refs: {json.dumps(event['original_observation_refs'], ensure_ascii=False)}.",
                  f"- New observation refs: {json.dumps(event['new_observation_refs'], ensure_ascii=False)}.",
                  f"- Gate evidence refs: {json.dumps(event['evidence_refs'], ensure_ascii=False)}.", "",
                  "Model-reported changed attributes (hypotheses until checked against the image/tool evidence):", "",
                  "```json", json.dumps(event["changed_attributes"], ensure_ascii=False, indent=2), "```", "",
                  "Evidence interpretation: not independently adjudicated here. Open the recorded evidence/checkpoint to verify morphology, object/image/time binding, conflict handling and any claimed new information. The answer change alone does not establish the mechanism.", ""]
    return "\n".join(lines) + "\n"


def _atomic(path, content):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def generate_report(run_dir, labels_path, *, allow_partial=False):
    run_dir = Path(run_dir)
    selection = json.loads((run_dir / "selection.json").read_text(encoding="utf-8-sig"))
    planned = [_qid(row) for row in selection["rows"]]
    p0_rows = read_jsonl(run_dir / "p0_results.jsonl")
    candidate_rows = read_jsonl(run_dir / "candidate_results.jsonl")
    # Check generation completeness before opening the isolated answer key.
    p0 = _unique(p0_rows, planned)
    candidates = _unique(candidate_rows, planned, grouped=True)
    if not allow_partial and (len(p0) != len(planned) or len(candidates) != len(planned) * len(GROUPS)):
        raise ValueError("Generation has incomplete terminals; isolated labels have not been opened")
    payload = score(selection, p0_rows, candidate_rows, _labels(labels_path, planned),
                    allow_partial=allow_partial)
    _atomic(run_dir / "paired_metrics.json", json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    _atomic(run_dir / "paired_metrics.md", _markdown(payload))
    _atomic(run_dir / "case_review.md", _review(payload))
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--allow-partial", action="store_true", help="Explicit provisional scoring after generation has stopped")
    args = parser.parse_args(argv)
    payload = generate_report(args.run, args.labels, allow_partial=args.allow_partial)
    print(json.dumps({"run_status": payload["run_status"], "planned_n": payload["planned_n"],
                      "p0": payload["p0"], "written": ["paired_metrics.json", "paired_metrics.md", "case_review.md"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
