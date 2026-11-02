"""Offline, complete-phase scoring for independent VLM samples.

No provider, ledger, inference, or prediction writes. All declared runs must have
complete, unique terminal coverage before the separate labels file is opened.
An optional generation_gate names a phase status JSON, relative to the manifest;
it must be generation_complete before any arm or reference labels are read.

Manifest example (paths relative to the manifest):
 {"phase": 2, "split": "tune", "baseline": "D", "arms": [
   {"id": "D", "run": "runs/direct", "role": "direct"},
   {"id": "SC", "run": "runs/samples", "role": "sampled", "direct_arm": "D"}]}

Optional ensemble: {"members": [sampled arm IDs], "weights": {ID: weight},
 "strongest_member": ID, "samples_per_model": 3, "weights_source": "tune report"}.
On tune only, omitted weights/strongest are derived from member direct arms.
Held-out scoring requires explicit frozen weights and strongest member, and
frozen_before_test=true. The scorer never chooses a model or K on test labels.
Primary B2 uses tuning-accuracy-weighted per-model three-sample majorities.
Pooling all nine independent sample votes is a secondary diagnostic only.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
import itertools
import json
import math
from pathlib import Path
import random
import statistics


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def vote(answers, tie_answer=None, weights=None):
    """Plurality; missing is not a vote. No evidence -> missing, not D fallback.

    If the direct anchor is not among tied winners, lexical option order resolves the
    tie. This prevents a non-plurality answer from winning by tie-break privilege.
    """
    if weights is None:
        weights = [1] * len(answers)
    if len(weights) != len(answers):
        raise ValueError("vote_weight_length_mismatch")
    scores = defaultdict(Decimal)
    for answer, weight in zip(answers, weights):
        weight = Decimal(str(weight))
        if not weight.is_finite() or weight < 0:
            raise ValueError("invalid_vote_weight")
        if answer is not None and weight > 0:
            scores[answer] += weight
    if not scores:
        return None
    maximum = max(scores.values())
    winners = sorted(answer for answer, weight in scores.items() if weight == maximum)
    return tie_answer if tie_answer in winners else winners[0]


def totals(predictions, labels, qids):
    n = len(qids)
    correct = sum(predictions[q] == labels[q] for q in qids)
    valid = sum(predictions[q] is not None for q in qids)
    return {"correct": correct, "planned_n": n, "accuracy": correct / n,
            "valid": valid, "missing": n - valid}


def exact_mcnemar(improved, worsened):
    """Two-sided exact conditional binomial McNemar; missing counts incorrect."""
    n = improved + worsened
    if not n:
        return 1.0
    tail = min(improved, worsened)
    log_two = math.log(2)
    probability = math.fsum(math.exp(math.lgamma(n + 1) - math.lgamma(k + 1)
                                    - math.lgamma(n - k + 1) - n * log_two)
                            for k in range(tail + 1))
    return min(1.0, 2 * probability)


def quantile(values, p):
    values = sorted(values)
    position = (len(values) - 1) * p
    low = int(position)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (position - low)


def paired_bootstrap(old, new, labels, qids, case_ids, repeats=2000, seed=20261102):
    """Resample cases, retain all their questions; question-weighted paired delta."""
    if repeats < 1:
        raise ValueError("bootstrap_repeats_must_be_positive")
    groups = defaultdict(list)
    for q in qids:
        if not case_ids.get(q):
            raise ValueError("explicit_case_id_required_for_cluster_bootstrap")
        groups[str(case_ids[q])].append(int(new[q] == labels[q]) - int(old[q] == labels[q]))
    clusters = [(sum(v), len(v)) for _, v in sorted(groups.items())]
    rng = random.Random(seed)
    draws = []
    for _ in range(repeats):
        selected = [clusters[rng.randrange(len(clusters))] for _ in clusters]
        draws.append(sum(v[0] for v in selected) / sum(v[1] for v in selected))
    return {"method": "paired_case_cluster_percentile_question_weighted", "repeats": repeats,
            "seed": seed, "case_n": len(clusters), "delta_ci95": [quantile(draws, .025), quantile(draws, .975)],
            "delta_ci95_pp": [100 * quantile(draws, .025), 100 * quantile(draws, .975)],
            "one_case_limitation": len(clusters) < 2}


def paired(old, new, labels, qids, case_ids, repeats=2000, seed=20261102):
    buckets = {name: [] for name in ("legal_wrong_to_correct", "correct_to_legal_wrong",
                                    "missing_to_correct", "correct_to_missing")}
    for q in qids:
        a, b, gold = old[q], new[q], labels[q]
        if a is not None and a != gold and b == gold:
            buckets["legal_wrong_to_correct"].append(q)
        if a == gold and b is not None and b != gold:
            buckets["correct_to_legal_wrong"].append(q)
        if a is None and b == gold:
            buckets["missing_to_correct"].append(q)
        if a == gold and b is None:
            buckets["correct_to_missing"].append(q)
    counts = {name: len(qs) for name, qs in buckets.items()}
    improved = counts["legal_wrong_to_correct"] + counts["missing_to_correct"]
    worsened = counts["correct_to_legal_wrong"] + counts["correct_to_missing"]
    return {**counts, "net": improved - worsened, "net_excluding_missing_recovery":
            counts["legal_wrong_to_correct"] - counts["correct_to_legal_wrong"],
            "planned_n": len(qids), "delta_pp": 100 * (improved - worsened) / len(qids),
            "exact_mcnemar_p": exact_mcnemar(improved, worsened),
            "mcnemar_note": "question-level exact test; within-case dependence is addressed separately by cluster bootstrap",
            "bootstrap": paired_bootstrap(old, new, labels, qids, case_ids, repeats, seed),
            "question_ids": buckets}


def error_overlap(a, b, labels, qids):
    av = [a[q] == labels[q] for q in qids]
    bv = [b[q] == labels[q] for q in qids]
    n = len(qids)
    both_wrong = sum(not x and not y for x, y in zip(av, bv))
    either_wrong = sum(not x or not y for x, y in zip(av, bv))
    observed = sum(x == y for x, y in zip(av, bv)) / n
    pa, pb = sum(av) / n, sum(bv) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    return {"both_wrong": both_wrong, "either_wrong": either_wrong,
            "error_jaccard": both_wrong / either_wrong if either_wrong else None,
            "correctness_agreement": observed,
            "correctness_cohen_kappa": (observed - expected) / (1 - expected) if expected < 1 else None,
            "answer_disagreement": sum(a[q] != b[q] for q in qids),
            "missing_treated_as_incorrect": True}


def load_complete_run(path):
    """Strict coverage check; called before read_labels."""
    path = Path(path)
    status = read(path / "status.json")
    if status.get("status") != "generation_complete":
        raise ValueError("phase_generation_not_complete:" + path.name)
    protocol = read(path / "protocol.json")
    cfg = protocol.get("config", protocol)
    selection = read(path / "selection.json")
    rows = selection["rows"] if isinstance(selection, dict) else selection
    qids = [str(r["question_id"]) for r in rows]
    if not qids or len(qids) != len(set(qids)):
        raise ValueError("invalid_selection_ids")
    samples = int(cfg.get("samples", status.get("samples", 1)))
    records = [json.loads(s) for s in (path / "predictions.jsonl").read_text(encoding="utf-8").splitlines() if s.strip()]
    expected = {(q, i) for q in qids for i in range(1, samples + 1)}
    actual = [(str(r["question_id"]), int(r["sample_index"])) for r in records]
    if len(records) != len(expected) or set(actual) != expected:
        raise ValueError("complete_unique_terminal_coverage_required")
    for record in records:
        if record.get("status") not in {"completed", "unparsed", "request_failed"}:
            raise ValueError("nonterminal_sample")
        if record.get("status") != "completed" and record.get("answer") is not None:
            raise ValueError("failed_sample_cannot_cast_vote")
        if record.get("status") == "completed" and not record.get("answer"):
            raise ValueError("completed_sample_requires_answer")
    return {"path": path, "config": cfg, "rows": rows, "qids": qids,
            "samples": samples, "records": records,
            "answers": {(str(r["question_id"]), int(r["sample_index"])): r.get("answer") for r in records}}


def read_labels(path, qids):
    value = read(path)
    if isinstance(value, list):
        records = value
    elif isinstance(value, dict) and ("records" in value or "rows" in value):
        records = value.get("records", value.get("rows"))
    elif isinstance(value, dict) and "labels" in value:
        nested = value["labels"]
        records = nested if isinstance(nested, list) else [{"question_id": k, "answer": v} for k, v in nested.items()]
    else:
        records = [{"question_id": k, "answer": v} for k, v in value.items()]
    result = {}
    for record in records:
        q = str(record["question_id"])
        if q in result:
            raise ValueError("duplicate_reference")
        result[q] = record.get("reference", record.get("reference_answer", record.get("answer")))
    if not set(qids) <= set(result) or any(not isinstance(result[q], str) or len(result[q]) != 1 or result[q] not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for q in qids):
        raise ValueError("missing_or_invalid_isolated_reference")
    return {q: result[q] for q in qids}


def sample_predictions(run, k, tie, qids, selected=None):
    if k > run["samples"]:
        raise ValueError("K_exceeds_saved_samples")
    return {q: vote([run["answers"][q, i] for i in (selected[q] if selected else range(1, k + 1))], tie.get(q)) for q in qids}


def sampling_curve(run, tie, labels, qids, ks, repeats=200, seed=20261102):
    curves = []
    rng = random.Random(seed)
    for k in ks:
        if k > run["samples"]:
            continue
        accuracies = []
        for _ in range(repeats):
            selected = {q: rng.sample(range(1, run["samples"] + 1), k) for q in qids}
            pred = sample_predictions(run, k, tie, qids, selected)
            accuracies.append(totals(pred, labels, qids)["accuracy"])
        curves.append({"k": k, "resamples": repeats, "mean_accuracy": statistics.mean(accuracies),
                       "sampling_sd": statistics.pstdev(accuracies),
                       "sampling_percentile95": [quantile(accuracies, .025), quantile(accuracies, .975)],
                       "min_accuracy": min(accuracies), "max_accuracy": max(accuracies),
                       "note": "Monte Carlo variability from this fixed sample pool, not a population confidence interval"})
    return curves


def choose_k(curve, minimum_increment_pp=.5):
    """First plateau: stop before the next K adds <0.5 points; no best-K search."""
    if not curve:
        return None
    curve = sorted(curve, key=lambda x: x["k"])
    for previous, current in zip(curve, curve[1:]):
        if 100 * (current["mean_accuracy"] - previous["mean_accuracy"]) < minimum_increment_pp - 1e-10:
            return previous["k"]
    return curve[-1]["k"]


def resources(records):
    attempts = [attempt for record in records for attempt in record.get("attempts", [])]
    amounts = [(a.get("settlement") or {}).get("charged_cny") for a in attempts]
    start = [r.get("started_utc") for r in records if r.get("started_utc")]
    end = [r.get("ended_utc") for r in records if r.get("ended_utc")]
    result = {"saved_attempts": len(attempts), "technical_extra_requests": sum(a.get("ordinal", 1) > 1 for a in attempts),
              "saved_settlement_cny": str(sum((Decimal(str(v)) for v in amounts if v is not None), Decimal(0))),
              "settlement_missing_attempts": sum(v is None for v in amounts),
              "input_tokens": sum((a.get("usage") or {}).get("input_tokens", (a.get("usage") or {}).get("prompt_tokens", 0)) or 0 for a in attempts),
              "output_tokens": sum((a.get("usage") or {}).get("output_tokens", (a.get("usage") or {}).get("completion_tokens", 0)) or 0 for a in attempts),
              "sample_status_counts": dict(Counter(r["status"] for r in records)),
              "cost_is_not_supplier_invoice": True}
    if start and end:
        result.update(first_started_utc=min(start), last_ended_utc=max(end),
                      wall_seconds=(datetime.fromisoformat(max(end)) - datetime.fromisoformat(min(start))).total_seconds())
    return result


def score(manifest_path, labels_path, out):
    manifest_path, out = Path(manifest_path).resolve(), Path(out).resolve()
    manifest = read(manifest_path)
    if manifest.get("generation_gate"):
        gate = read((manifest_path.parent / manifest["generation_gate"]).resolve())
        if gate.get("status") != "generation_complete":
            raise ValueError("phase_generation_gate_not_complete")
    arms = manifest["arms"]
    if not arms or len({a["id"] for a in arms}) != len(arms):
        raise ValueError("unique_nonempty_arm_ids_required")
    runs = {}
    specs = {a["id"]: a for a in arms}
    for arm in arms:
        path = (manifest_path.parent / arm["run"]).resolve()
        if out == path or out.is_relative_to(path):
            raise ValueError("scoring_output_must_be_outside_frozen_run")
        runs[arm["id"]] = load_complete_run(path)
    qids = next(iter(runs.values()))["qids"]
    if any(run["qids"] != qids for run in runs.values()):
        raise ValueError("all_arms_must_use_identical_question_order")
    case_ids = {str(r["question_id"]): str(r["case_id"]) if r.get("case_id") is not None else None
                for r in next(iter(runs.values()))["rows"]}
    if any(not case_ids[q] for q in qids):
        raise ValueError("explicit_case_ids_required")
    for run in runs.values():
        if any(str(r.get("case_id")) != case_ids[str(r["question_id"])] for r in run["rows"]):
            raise ValueError("cross_arm_case_id_mismatch")
    baseline = manifest["baseline"]
    if baseline not in runs or runs[baseline]["samples"] != 1:
        raise ValueError("single_call_baseline_required")
    split = manifest.get("split", "tune")
    tune = split == "tune"
    ensemble = manifest.get("ensemble")
    if ensemble and not tune and not (manifest.get("frozen_before_test") and ensemble.get("weights")
                                     and ensemble.get("strongest_member") and ensemble.get("weights_source")):
        raise ValueError("heldout_ensemble_requires_frozen_tuning_choices")
    # FIRST reference access occurs only after every declared run has passed coverage.
    labels = read_labels(labels_path, qids)
    seed = int(manifest.get("seed", 20261102))
    bootstrap_n = int(manifest.get("bootstrap_repeats", 2000))
    repeats = int(manifest.get("subsample_repeats", 200))
    if repeats < 1:
        raise ValueError("positive_subsample_repeats_required")
    views, curves, decisions = {}, {}, {}
    for arm_id, run in runs.items():
        if run["samples"] == 1:
            views[arm_id] = {q: run["answers"][q, 1] for q in qids}
    baseline_predictions = views[baseline]
    for arm_id, run in runs.items():
        if run["samples"] == 1:
            continue
        tie_id = specs[arm_id].get("direct_arm")
        if tie_id not in views or runs[tie_id]["samples"] != 1:
            raise ValueError("sampled_arm_requires_saved_direct_tiebreak")
        tie = views[tie_id]
        ks = [int(k) for k in manifest.get("ks", [1, 3, 5, 7, 9]) if int(k) <= run["samples"]]
        if not ks or any(k < 1 for k in ks):
            raise ValueError("valid_K_values_required")
        for k in ks:
            views[f"{arm_id}/K{k}"] = sample_predictions(run, k, tie, qids)
        if tune:
            curves[arm_id] = sampling_curve(run, tie, labels, qids, ks, repeats, seed)
            decisions[arm_id + "_selected_K"] = choose_k(curves[arm_id])
    direct_candidates = manifest.get("selection", {}).get("candidates", [])
    if direct_candidates and tune:
        if any(c not in views or runs[c]["samples"] != 1 for c in direct_candidates):
            raise ValueError("selection_candidates_must_be_single_call_arms")
        best = max(direct_candidates, key=lambda c: (totals(views[c], labels, qids)["correct"], -direct_candidates.index(c)))
        delta_pp = 100 * (totals(views[best], labels, qids)["accuracy"] - totals(baseline_predictions, labels, qids)["accuracy"])
        threshold = float(manifest.get("selection", {}).get("minimum_gain_pp", 1.5))
        decisions["phase1"] = {"candidate": best, "gain_pp": delta_pp, "threshold_pp": threshold,
                               "selected": best if delta_pp >= threshold - 1e-10 else baseline,
                               "gate_passed": delta_pp >= threshold - 1e-10}
    ensemble_info = None
    if ensemble:
        members = ensemble["members"]
        if len(members) != 3 or len(set(members)) != 3 or any(m not in runs for m in members):
            raise ValueError("ensemble_requires_three_distinct_member_arms")
        if len({runs[m]["config"]["model"] for m in members}) != 3:
            raise ValueError("ensemble_requires_three_distinct_models")
        direct = {m: specs[m]["direct_arm"] for m in members}
        weights = ensemble.get("weights")
        if weights is None:
            weights = {m: totals(views[direct[m]], labels, qids)["accuracy"] for m in members}
        if set(weights) != set(members) or any(not math.isfinite(float(v)) or float(v) < 0 for v in weights.values()) or not any(float(v) > 0 for v in weights.values()):
            raise ValueError("positive_finite_frozen_member_weights_required")
        strongest = ensemble.get("strongest_member") or max(members, key=lambda m: (weights[m], -members.index(m)))
        if strongest not in members:
            raise ValueError("strongest_member_not_in_ensemble")
        k = int(ensemble.get("samples_per_model", 3))
        if k != 3 or runs[strongest]["samples"] < 9:
            raise ValueError("B2_requires_3x3_and_B1_requires_nine_saved_samples")
        member_predictions = {m: sample_predictions(runs[m], 3, views[direct[m]], qids) for m in members}
        views["B1_best_member_K9"] = sample_predictions(runs[strongest], 9, views[direct[strongest]], qids)
        views["B2_pooled_nine_samples_secondary"] = {q: vote([runs[m]["answers"][q, i] for m in members for i in range(1, 4)],
                                              views[direct[strongest]][q]) for q in qids}
        views["B2_three_models_3x3"] = {q: vote([member_predictions[m][q] for m in members],
                                              views[direct[strongest]][q], [weights[m] for m in members]) for q in qids}
        remaining = [m for m in members if m != strongest]
        remaining_anchor = max(remaining, key=lambda m: (weights[m], -remaining.index(m)))
        views["B3_pooled_six_samples_secondary"] = {q: vote([runs[m]["answers"][q, i] for m in remaining for i in range(1, 4)],
                                               views[direct[remaining_anchor]][q]) for q in qids}
        views["B3_without_strongest"] = {q: vote([member_predictions[m][q] for m in remaining],
                                               views[direct[remaining_anchor]][q], [weights[m] for m in remaining]) for q in qids}
        ensemble_info = {"members": members, "weights": weights, "strongest_member": strongest,
                         "weights_source": ensemble.get("weights_source", "this tuning phase direct accuracy"),
                         "member_direct_arms": direct, "B1_sample_calls": 9, "B2_sample_calls": 9,
                         "primary_vote_rule": "three-sample plurality per model, then tuning-accuracy-weighted model votes, following plan S4",
                         "secondary_vote_rule": "pool all independent sample votes; no per-model compression or weights; diagnostic only",
                         "direct_anchor_temperatures": {m: runs[direct[m]]["config"].get("temperature") for m in members},
                         "B3_sample_calls": 6, "tiebreak_direct_calls_reused_but_not_free": True,
                         "B1_direct_anchor_calls": 1, "B2_direct_anchor_calls": 3, "B3_direct_anchor_calls": 2,
                         "compute_limitation": "B0 direct anchors are a shared fixed acquisition cost. B1/B2 match nine sampled calls, not token or monetary compute. Standalone deployment including model-specific direct anchors is B1 10, B2 12, B3 8 logical calls. Kimi's anchor remains its supported T1.0 thinking configuration, not T0.2."}
    scored = {name: totals(pred, labels, qids) for name, pred in views.items()}
    comparisons = {baseline + "_to_" + name: paired(baseline_predictions, pred, labels, qids, case_ids, bootstrap_n, seed)
                   for name, pred in views.items() if name != baseline}
    if ensemble:
        contrast = paired(views["B1_best_member_K9"], views["B2_three_models_3x3"], labels, qids, case_ids, bootstrap_n, seed)
        comparisons["B1_to_B2"] = contrast
        ensemble_info["B2_exceeds_B1_ci95_above_zero"] = contrast["bootstrap"]["delta_ci95"][0] > 0
        ensemble_info["B2_beats_every_direct_member"] = all(scored["B2_three_models_3x3"]["correct"] > scored[a]["correct"] for a in ensemble_info["member_direct_arms"].values())
        ensemble_info["B3_beats_each_remaining_member_direct"] = all(scored["B3_without_strongest"]["correct"] > scored[ensemble_info["member_direct_arms"][m]]["correct"] for m in ensemble_info["members"] if m != ensemble_info["strongest_member"])
    overlaps = {a + "__" + b: error_overlap(views[a], views[b], labels, qids)
                for a, b in itertools.combinations([a for a in runs if runs[a]["samples"] == 1], 2)}
    costs = {name: resources(run["records"]) for name, run in runs.items()}
    for name, run in runs.items():
        summary_path = run["path"] / "ledger_final_summary.json"
        if summary_path.exists():
            summary = read(summary_path)
            increment = summary.get("run_increment_cny")
            costs[name]["saved_guard_run_increment_cny"] = increment
            costs[name]["price_basis"] = summary.get("price_basis")
            if increment is not None:
                costs[name]["guard_minus_saved_settlements_cny"] = str(Decimal(str(increment)) - Decimal(costs[name]["saved_settlement_cny"]))
            costs[name]["recovery_cost_note"] = "Guard summary can include conservative recovery charges absent from per-request settlement records; neither source is rewritten."
    result = {"status": "completed", "phase": manifest.get("phase"), "split": split, "planned_n": len(qids),
              "case_n": len(set(case_ids.values())), "baseline": baseline, "totals": scored,
              "comparisons": comparisons, "sampling_curves": curves, "tuning_decisions": decisions if tune else {},
              "ensemble": ensemble_info, "pairwise_direct_error_overlap": overlaps, "resources": costs,
              "new_inference": 0, "prediction_records_modified": False,
              "vote_rule": "plurality valid votes only; saved direct anchor if among tied winners, else alphabetical; all missing stays missing",
              "direct_anchor_configurations": {a: {
                  **{k: runs[a]["config"].get(k) for k in ("model", "temperature", "top_p", "prompt_variant")},
                  **{k: runs[a]["config"].get("extra_body", {}).get(k) for k in ("enable_thinking", "reasoning_effort")}
              } for a in runs if runs[a]["samples"] == 1},
              "deployed_K_rule": "first K saved samples; Monte Carlo subsampling is diagnostic, not oracle selection",
              "test_selection_performed": False, "paper_GPT4o_attribution_arms_executed": False}
    out.mkdir(parents=True, exist_ok=True)
    write(out / "metrics.json", result)
    write(out / "cost_summary.json", {"arms": costs, "new_inference": 0,
                                     "shared_direct_anchors_are_fixed_acquisition_cost": True,
                                     "sample_call_matching_does_not_match_tokens_or_money": True})
    write(out / "per_question.json", {"records": [{"question_id": q, "case_id": case_ids[q], "reference": labels[q],
                                                   "answers": {a: v[q] for a, v in views.items()},
                                                   "sample_status_counts": {a: dict(Counter(r["status"] for r in run["records"] if str(r["question_id"]) == q)) for a, run in runs.items()}} for q in qids]})
    write(out / "scoring_manifest.json", {**manifest, "arms": [{**a, "run": Path(a["run"]).name} for a in arms]})
    report = "# Independent-sample VLM phase results\n\nAll declared samples are terminal; scoring is offline.\n\n|Arm|Correct / planned|Accuracy|Missing|\n|---|---:|---:|---:|\n"
    for name, values in scored.items():
        report += f"|{name}|{values['correct']}/{values['planned_n']}|{values['accuracy']:.2%}|{values['missing']}|\n"
    report += "\n[Complete metrics](metrics.json) · [Per-question scores](per_question.json) · [Costs](cost_summary.json).\n\nMissing and technical failures remain in the denominator. Sampling-curve spread is not a population CI. Paired uncertainty resamples complete cases; exact McNemar remains a question-level test. All model/K choices are tuning-only; held-out labels never select weights or a winner.\n"
    if ensemble_info:
        report += "\nPrimary B2/B3 first take each model's own three-sample plurality, then weight those model votes by frozen tuning-pool accuracy (plan S4). Pooled nine/six-sample votes are secondary diagnostics. B2−B1 and its confidence interval use the weighted primary B2.\n\n" + ensemble_info["compute_limitation"] + "\n"
    report += "\nThis phase has no GPT-4o matched attribution arm. A subset score cannot be directly compared with the paper's full-benchmark headline. No parser or technical recovery is counted as mechanism gain.\n"
    (out / "README.md").write_text(report, encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = score(args.manifest, args.labels, args.out)
    print(json.dumps({"status": "scored", "planned_n": result["planned_n"], "scores": {a: v["correct"] for a, v in result["totals"].items()}, "new_inference": 0}))


if __name__ == "__main__":
    main()
