"""Offline, label-isolated scoring of a predeclared direct/agent diagnostic run.

This module never imports a model runner or writes labels into inference/trace
artifacts. Missing, invalid and failed outcomes stay in the planned denominator.
Only aggregate metrics and question-ID indices are returned, never answer keys.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import re

ARMS = ("direct", "agent")
ARM_ALIASES = {"direct": "direct", "B0": "direct", "agent": "agent", "R0": "agent"}
COMPLETE = {"completed", "ok", "success", "succeeded"}
INVALID = {"invalid", "invalid_answer", "malformed_answer"}
UNRUN = {"unrun", "not_run", "not_run_budget", "skipped"}
DEFAULT_SEED = 20261027
DEFAULT_RESAMPLES = 10000
USAGE_FIELDS = ("input_tokens", "output_tokens", "total_tokens")
CALL_FIELDS = ("actual_model_calls", "actual_tool_attempts", "validated_tool_returns", "repeated_tool_calls")


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def _decode(text):
    return json.loads(text, object_pairs_hook=_unique_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON value")))


def read_jsonl(path):
    rows = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = _decode(line)
        except (ValueError, json.JSONDecodeError):
            raise ValueError(f"Invalid JSONL record at line {line_number}") from None
        if type(row) is not dict:
            raise ValueError(f"Expected a JSON object at line {line_number}")
        rows.append(row)
    return rows


def _identifier(value):
    if type(value) is not str or not value.strip() or len(value) > 256 or any(ord(c) < 32 for c in value):
        raise ValueError("Invalid question identifier")
    return value


def _answer_letter(value):
    # Never extract a favorable letter from a narrative or multiple answers.
    if type(value) is not str:
        return None
    match = re.fullmatch(r"\s*([A-F])[.)]?\s*", value)
    return match.group(1) if match else None


def _planned_rows(rows):
    planned = {}
    for row in rows:
        if type(row) is not dict or set(row) != {"question_id", "question", "images"}:
            raise ValueError("Inference requires exactly question_id, question, images")
        qid = _identifier(row["question_id"])
        if qid in planned:
            raise ValueError("Duplicate question in predeclared inference")
        if type(row["question"]) is not str or type(row["images"]) is not list or not row["images"] or any(type(x) is not str for x in row["images"]):
            raise ValueError("Invalid inference question/images")
        choices = re.findall(r"(?m)^\s*([A-F])[).:]\s+", row["question"])
        if len(choices) < 2 or len(set(choices)) != len(choices):
            raise ValueError(f"Cannot establish unique answer choices for question {qid}")
        planned[qid] = frozenset(choices)
    if not planned:
        raise ValueError("Predeclared inference must contain at least one question")
    return planned


def _label_map(rows, planned):
    labels, observed = {}, set()
    for row in rows:
        if type(row) is not dict or set(row) != {"question_id", "answer"}:
            raise ValueError("Labels require exactly question_id and answer")
        qid = _identifier(row["question_id"])
        if qid in observed:
            raise ValueError("Duplicate question in isolated labels")
        observed.add(qid)
        if qid not in planned:
            continue
        letter = _answer_letter(row["answer"])
        if letter is None or letter not in planned[qid]:
            raise ValueError(f"Invalid isolated label for question {qid}")
        labels[qid] = letter
    if set(labels) != set(planned):
        raise ValueError("Isolated labels do not cover every predeclared question")
    return labels


def _terminal_rows(rows, planned):
    terminals, started = {}, set()
    for row in rows:
        if type(row) is not dict:
            raise ValueError("Result record must be an object")
        qid = _identifier(row.get("question_id"))
        if qid not in planned:
            raise ValueError("Result question is outside the predeclared inference")
        arm = ARM_ALIASES.get(row.get("arm")) if type(row.get("arm")) is str else None
        if arm is None:
            raise ValueError("Result arm must be direct/B0 or agent/R0")
        key = (qid, arm)
        kind = row.get("record_type", "terminal")
        if kind == "started":
            started.add(key)
            continue
        if kind != "terminal":
            raise ValueError("Result record_type must be started or terminal")
        if key in terminals:
            raise ValueError(f"Duplicate terminal outcome for question {qid}, arm {arm}")
        if type(row.get("status")) is not str or not row["status"].strip():
            raise ValueError("Terminal outcome requires a nonempty status")
        terminals[key] = row
    return terminals, started


def _error_kind(status):
    if status in {"case_budget_exceeded", "monetary_budget_exceeded", "monetary_guard_error"}:
        return "budget_error"
    if status in {"missing_image", "invalid_input"}:
        return "input_error"
    if status == "interrupted_no_retry":
        return "interrupted"
    if status in {"model_error", "tool_error"}:
        return status
    return "other_error"


def _outcome(row, choices, label):
    if row is None:
        return "unrun", False
    status = row["status"]
    if status in UNRUN:
        return "unrun", False
    if status in INVALID:
        return "invalid", False
    if status not in COMPLETE:
        return "error", False
    letter = _answer_letter(row.get("answer_letter"))
    if letter is None or letter not in choices:
        return "invalid", False
    correct = letter == label
    return ("correct" if correct else "incorrect_answer"), correct


def _nonnegative_int(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f"Invalid nonnegative usage/call count: {name}")
    return value


def _usage_summary(rows):
    observed = {key: [] for key in USAGE_FIELDS + CALL_FIELDS}
    complete = 0
    for row in rows:
        usage = row.get("observed_usage_sum", row.get("usage"))
        if usage is not None and type(usage) is not dict:
            raise ValueError("Observed usage must be an object or null")
        usage = {} if usage is None else usage
        for key in USAGE_FIELDS:
            if usage.get(key) is not None:
                observed[key].append(_nonnegative_int(usage[key], key))
        declared_complete = row.get("usage_complete", False)
        if type(declared_complete) is not bool:
            raise ValueError("usage_complete must be boolean")
        if declared_complete and not all(usage.get(key) is not None for key in USAGE_FIELDS):
            raise ValueError("Complete usage declaration is missing token counts")
        # Partial aggregates may cover different calls for different token keys.
        # Equality is meaningful only when the runner attests complete usage.
        if declared_complete:
            if usage["total_tokens"] != usage["input_tokens"] + usage["output_tokens"]:
                raise ValueError("Observed token totals disagree")
        complete += int(declared_complete)
        for key in CALL_FIELDS:
            if row.get(key) is not None:
                observed[key].append(_nonnegative_int(row[key], key))
    return {
        "terminal_records": len(rows), "records_with_complete_usage": complete,
        "records_with_partial_or_unknown_usage": len(rows)-complete,
        "observed_sums": {key: sum(values) if values else None for key, values in observed.items()},
        "records_reporting_each_count": {key: len(values) for key, values in observed.items()},
        "cost_note": "Token/call counts are observed totals only; shared monetary ledger remains authoritative. No currency cost is inferred.",
    }


def _percentile(values, fraction):
    position = (len(values)-1)*fraction
    lower = int(position)
    upper = min(lower+1, len(values)-1)
    return values[lower] + (values[upper]-values[lower])*(position-lower)


def paired_cluster_bootstrap(differences, case_by_qid, *, seed=DEFAULT_SEED, resamples=DEFAULT_RESAMPLES):
    """Sample case clusters with replacement, retaining paired outcomes together.

    Each replicate includes every question in each sampled case. Its denominator
    is the total number of questions in those sampled clusters, not cluster count.
    """
    if type(seed) is not int or type(resamples) is not int or resamples < 100:
        raise ValueError("Bootstrap requires an integer seed and at least 100 resamples")
    if not differences or set(differences) != set(case_by_qid):
        raise ValueError("Bootstrap requires case coverage for all planned differences")
    clusters = defaultdict(list)
    for qid, difference in differences.items():
        if type(difference) is not int or difference not in (-1, 0, 1):
            raise ValueError("Paired correctness differences must be -1, 0, or 1")
        case = case_by_qid[qid]
        if type(case) is not str or not case:
            raise ValueError("Every planned question requires a nonempty audit case identifier")
        clusters[case].append(difference)
    aggregates = [(sum(clusters[case]), len(clusters[case])) for case in sorted(clusters)]
    rng, samples = random.Random(seed), []
    for _ in range(resamples):
        numerator = denominator = 0
        for _ in aggregates:
            total, count = aggregates[rng.randrange(len(aggregates))]
            numerator += total
            denominator += count
        samples.append(numerator/denominator)
    samples.sort()
    return {
        "estimate_agent_minus_direct": sum(differences.values())/len(differences),
        "confidence_level": 0.95, "lower": _percentile(samples, 0.025), "upper": _percentile(samples, 0.975),
        "method": "paired case-cluster percentile bootstrap; question-weighted within each resample",
        "seed": seed, "resamples": resamples, "case_count": len(aggregates), "planned_question_count": len(differences),
        "single_case_degenerate": len(aggregates) == 1,
        "interpretation": "Exploratory uncertainty conditional on this fixed diagnostic sample; not evidence of representative population performance or a prespecified held-out efficacy result.",
    }


def score_diagnostics(inference_rows, result_rows, label_rows, case_by_qid, *, seed=DEFAULT_SEED, resamples=DEFAULT_RESAMPLES):
    planned = _planned_rows(inference_rows)
    if set(case_by_qid) != set(planned):
        raise ValueError("Audit cases must cover exactly the predeclared inference")
    labels = _label_map(label_rows, planned)
    terminals, started = _terminal_rows(result_rows, planned)
    outcomes, arms = {}, {}
    for arm in ARMS:
        indices = {name: [] for name in ("correct", "incorrect_answer", "invalid", "unrun", "error")}
        error_indices = defaultdict(list)
        for qid, choices in planned.items():
            row = terminals.get((qid, arm))
            kind, correct = _outcome(row, choices, labels[qid])
            outcomes[(qid, arm)] = correct
            indices[kind].append(qid)
            if kind == "error":
                error_indices[_error_kind(row["status"])].append(qid)
        counts = {key: len(value) for key, value in indices.items()}
        assert sum(counts.values()) == len(planned)
        arms[arm] = {
            "planned_denominator": len(planned), "correct": counts["correct"],
            "accuracy": counts["correct"]/len(planned), "counts": counts,
            "qid_indices": indices,
            "error_categories": {key: {"count": len(value), "question_ids": value} for key, value in sorted(error_indices.items())},
            "started_without_terminal_question_ids": [qid for qid in planned if (qid, arm) in started and (qid, arm) not in terminals],
            "usage": _usage_summary([row for (qid, key), row in terminals.items() if key == arm]),
        }
    paired_indices = {key: [] for key in ("improved", "worsened", "same", "both_correct", "both_not_correct")}
    differences = {}
    for qid in planned:
        direct, agent = outcomes[(qid, "direct")], outcomes[(qid, "agent")]
        difference = int(agent)-int(direct)
        differences[qid] = difference
        paired_indices["improved" if difference > 0 else "worsened" if difference < 0 else "same"].append(qid)
        if direct == agent:
            paired_indices["both_correct" if direct else "both_not_correct"].append(qid)
    return {
        "schema_version": 1, "purpose": "fixed-sample B0/direct versus R0/agent diagnostic comparison",
        "denominator_policy": "Every predeclared question is counted in each arm; invalid, unrun and error outcomes count as not correct. Started records are not outcomes.",
        "planned_question_count": len(planned), "arms": arms,
        "paired": {"planned_denominator": len(planned),
                   "counts": {key: len(value) for key, value in paired_indices.items()}, "qid_indices": paired_indices,
                   "accuracy_difference_agent_minus_direct": sum(differences.values())/len(planned),
                   "cluster_bootstrap": paired_cluster_bootstrap(differences, case_by_qid, seed=seed, resamples=resamples)},
        "label_boundary": "Labels were read only by this offline scorer. Output excludes reference letters, prediction letters, questions, reports, explanations, and raw traces.",
    }


def audit_cases(manifest, inference_rows, inference_digest):
    if type(manifest) is not dict or manifest.get("status") != "complete" or manifest.get("inference_sha256") != inference_digest:
        raise ValueError("Audit manifest is incomplete or inference hash differs from frozen audit")
    planned = _planned_rows(inference_rows)
    if manifest.get("sample_count") != len(planned):
        raise ValueError("Audit sample count differs from predeclared inference")
    cases = {}
    for row in manifest.get("records", []):
        qid = _identifier(row.get("question_id"))
        case = row.get("case_hash")
        if qid in cases or type(case) is not str or re.fullmatch(r"[0-9a-f]{64}", case) is None:
            raise ValueError("Invalid or duplicate case audit record")
        if row.get("split") != "memory_train":
            raise ValueError("Diagnostic sample must come from memory_train")
        cases[qid] = case
    if set(cases) != set(planned) or manifest.get("distinct_case_count") != len(set(cases.values())):
        raise ValueError("Audit cases differ from predeclared inference")
    return cases


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", "--results", dest="results", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--inference", type=Path, required=True)
    parser.add_argument("--audit-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--bootstrap-resamples", type=int, default=DEFAULT_RESAMPLES)
    args = parser.parse_args(argv)
    inputs = (args.results, args.labels, args.inference, args.audit_manifest)
    if len({path.resolve() for path in inputs}) != len(inputs) or args.output.resolve() in {path.resolve() for path in inputs}:
        parser.error("Results, isolated labels, inference, audit and output must be distinct files")
    try:
        inference_rows = read_jsonl(args.inference)
        inference_digest = hashlib.sha256(args.inference.read_bytes()).hexdigest()
        manifest = _decode(args.audit_manifest.read_text(encoding="utf-8-sig"))
        cases = audit_cases(manifest, inference_rows, inference_digest)
        # Labels are loaded only here, after the frozen inference and audit check.
        report = score_diagnostics(inference_rows, read_jsonl(args.results), read_jsonl(args.labels), cases,
                                   seed=args.seed, resamples=args.bootstrap_resamples)
        report["artifact_sha256"] = {key: hashlib.sha256(path.read_bytes()).hexdigest()
                                     for key, path in (("results", args.results), ("inference", args.inference),
                                                       ("audit_manifest", args.audit_manifest), ("isolated_labels", args.labels))}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps({"report": str(args.output), "planned_question_count": report["planned_question_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
