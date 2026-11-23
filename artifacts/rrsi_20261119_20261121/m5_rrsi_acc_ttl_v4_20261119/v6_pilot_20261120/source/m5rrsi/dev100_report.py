"""Build v5 reports from closed stream, replay, and usage records."""
from __future__ import annotations

import json
from pathlib import Path
import re

from . import dev100_metrics as metrics
from .io import ProtocolError, read_json


def _json_if_present(path: Path, default=None):
    return read_json(path) if path.is_file() else default


def first_pass_records(run: Path, phase: str, arm: str, checkpoint: str | None = None) -> list:
    rows = []
    for path in sorted((run / "primary").glob("q*/completed.json")):
        record = read_json(path)
        normalized = record.get("first_pass")
        if normalized is None:
            raise ProtocolError(f"Missing v5 first-pass fields in {path}")
        selected = metrics.first_pass(normalized, phase, arm, checkpoint)
        if len(selected) != 1:
            raise ProtocolError(f"Expected one closed first-pass record for {arm} in {path}")
        rows.extend(selected)
    picked = metrics.first_pass(rows, phase, arm, checkpoint)
    if [int(row["step"]) for row in picked] != list(range(1, len(picked) + 1)):
        raise ProtocolError(f"Noncontiguous first-pass stream in {run}")
    return picked


def _job(name: str) -> tuple[int, str] | None:
    parent = re.fullmatch(r"online_parent_(\d+)", name)
    if parent:
        return int(parent[1]) + 1, "incumbent"
    candidate = re.fullmatch(r"r(\d+)([A-Z])", name)
    if candidate:
        return int(candidate[1]) + 1, candidate[2]
    return None


def _replay_records(official: Path) -> list:
    rows = []
    for trace in sorted((official / "jobs").glob("*/trial_*/q*/trace.json")):
        job = _job(trace.parents[2].name)
        if job is None:
            continue
        row = read_json(trace).get("replay")
        if row is None or (row["round"], row["variant"]) != job:
            raise ProtocolError(f"Invalid v5 replay metric in {trace}")
        rows.append(row)
    return rows


def _usage_totals() -> dict:
    return dict.fromkeys(
        ("runtime_operations", "failed_runtime_operations", "incomplete_runtime_operations",
         "native_model_calls", "tool_calls", "embedding_calls", "native_reported_tokens",
         "runtime_seconds_sum", "native_usage_unknown_operations", "search_model_calls",
         "search_failed_calls", "search_reported_tokens", "search_seconds_sum"), 0,
    )


def _add_native(totals: dict, receipt: dict, usage: dict) -> None:
    totals["runtime_operations"] += 1
    totals["failed_runtime_operations"] += receipt.get("status") == "failed"
    totals["incomplete_runtime_operations"] += not bool(receipt)
    totals["runtime_seconds_sum"] += receipt.get("seconds") or 0
    totals["native_usage_unknown_operations"] += not usage or bool(usage.get("usage_unknown"))
    for output, source in (("native_model_calls", "model_calls"), ("tool_calls", "tool_calls"),
                           ("embedding_calls", "embedding_calls"), ("native_reported_tokens", "total_tokens")):
        totals[output] += usage.get(source) or 0


def _add_search(totals: dict, entry: dict) -> None:
    totals["search_model_calls"] += 1
    totals["search_failed_calls"] += entry.get("event") != "search_call"
    totals["search_reported_tokens"] += (entry.get("usage") or {}).get("total_tokens") or 0
    totals["search_seconds_sum"] += entry.get("seconds") or 0


def _native_costs(run: Path, *, split_dev: bool = False) -> tuple[dict, dict]:
    phases = {name: _usage_totals() for name in
              (("first_pass", "search_replay", "unattributed") if split_dev else ("all",))}
    rounds = {}
    audit = run / "runtime_audit"
    for work in audit.iterdir() if audit.is_dir() else ():
        receipt = _json_if_present(work / "receipt.json", {})
        gateway = _json_if_present(work / "gateway_receipt.json", {})
        if not receipt and not gateway:
            if not (work / "rootfs" / "request.json").is_file() and not (work / "request.json").is_file():
                continue
        usage = gateway or receipt.get("usage") or {}
        if not split_dev:
            _add_native(phases["all"], receipt, usage)
            continue
        retained = receipt.get("retained_state")
        relative = Path(retained).relative_to(run).parts if retained else ()
        if relative and relative[0] in {"initial", "primary"}:
            phase = "first_pass"
        elif relative and relative[0] == "search":
            phase = "search_replay"
            if len(relative) > 4 and relative[3] == "jobs":
                job = _job(relative[4].removesuffix("_smoke"))
                if job:
                    _add_native(rounds.setdefault(job[0], _usage_totals()), receipt, usage)
        else:
            phase = "unattributed"
        _add_native(phases[phase], receipt, usage)
    return phases, rounds


def _search_costs(dev: Path, checkpoints: dict, totals: dict, rounds: dict) -> None:
    usage = dev / "search" / "search_usage.jsonl"
    if not usage.is_file():
        return
    spans = iter(sorted((record["search_usage_start"], number, record.get("search_usage_end"))
                        for number, record in checkpoints.items() if "search_usage_start" in record))
    current, following = next(spans, None), next(spans, None)
    with usage.open("rb") as handle:
        while True:
            offset = handle.tell()
            line = handle.readline()
            if not line.endswith(b"\n"):
                break
            entry = json.loads(line)
            _add_search(totals, entry)
            while following is not None and offset >= following[0]:
                current, following = following, next(spans, None)
            if current is not None:
                start, round_no, end = current
                if offset >= start and (end is None or offset < end):
                    _add_search(rounds.setdefault(round_no, _usage_totals()), entry)


def _checkpoints(dev: Path) -> dict:
    records = {}
    for path in sorted((dev / "search" / "checkpoints").glob("after_*")):
        done = _json_if_present(path / "done.json")
        if done is not None:
            if done["round"] is not None:
                records[done["round"] + 1] = {**done, "status": "complete"}
        else:
            intent = _json_if_present(path / "intent.json")
            if intent is not None:
                records[intent["round"] + 1] = {**intent, "status": "partial"}
    return records


def _round_report(official: Path, checkpoints: dict, usage: dict) -> list:
    rows = []
    for number, checkpoint in sorted(checkpoints.items()):
        rdir = official / f"r{number - 1}"
        decisions = _json_if_present(rdir / "decisions.json", [])
        accepted = checkpoint.get("accepted")
        finished = checkpoint.get("finished_at")
        started = checkpoint.get("started_at")
        variants = []
        for decision in decisions:
            prep = _json_if_present(rdir / decision["variant"] / "prep.json", {})
            promoted = None if accepted is None else bool(accepted and prep.get("commit") == checkpoint["commit"])
            variants.append({
                "variant": decision["variant"],
                "program_version": prep.get("commit"),
                "changed_components": sorted({edit["component"] for edit in prep.get("edits") or []
                                              if edit.get("component")}),
                "promoted": promoted,
                "admissible": decision.get("admissible"),
                "accuracy": decision.get("S"),
                "delta_accuracy": decision.get("delta_S"),
                "decision": decision.get("reason"),
            })
        rows.append({
            "round": number,
            "status": checkpoint["status"],
            "parent_commit": checkpoint["parent_commit"],
            "selected_commit": checkpoint.get("commit"),
            "accepted": accepted,
            "changed_components": checkpoint.get("changed_components"),
            "parent_replay_accuracy": checkpoint.get("parent_replay_accuracy"),
            "selected_replay_accuracy": checkpoint.get("selected_replay_accuracy"),
            "elapsed_seconds_including_pauses": finished - started if started is not None and finished is not None else None,
            "variants": variants,
            "usage": usage.get(number, _usage_totals()),
        })
    return rows


def _score_text(score: dict) -> str:
    return f'{score["correct"]}/{score["n"]} ({score["accuracy"]:.1%})' if score["n"] else "—"


def _archived_score(archive: dict, rows: list, planned: int) -> dict:
    aggregate = archive.get("aggregate")
    if aggregate is None:
        score = metrics.summary(rows, planned)
        if not rows:
            score["correct"] = None
        return {**score, "source_status": "archived" if rows else "unavailable"}

    parts = aggregate.get("per_dataset", {})
    for counts in (aggregate, *parts.values()):
        if (type(counts["n"]) is not int or type(counts["correct"]) is not int
                or not 0 <= counts["correct"] <= counts["n"] <= planned):
            raise ProtocolError("Invalid historical M denominator or correct count")
    if parts and any(sum(row[key] for row in parts.values()) != aggregate[key] for key in ("n", "correct")):
        raise ProtocolError("Historical M dataset counts disagree with the overall count")
    n, correct = aggregate["n"], aggregate["correct"]
    if len(rows) > n or (len(rows) == n and sum(metrics.score(row) for row in rows) != correct):
        raise ProtocolError("Historical M question scores disagree with the aggregate")
    return {"n": n, "planned": planned, "correct": correct if n else None,
            "accuracy": correct / n if n else None, "status": "complete" if n == planned else "partial",
            "source_status": "archived" if n else "unavailable",
            "per_dataset": {dataset: {"n": item["n"], "correct": item["correct"],
                                      "accuracy": item["correct"] / item["n"] if item["n"] else None}
                            for dataset, item in parts.items()}}


def _test_report(out: Path, task: dict) -> dict:
    planned = task["test"]["expected_questions_per_arm"]
    historical = task["test"].get("baseline_mode") == "historical"
    test = out / "test"
    method = first_pass_records(test / "RSI_selected", "test", "RSI_selected")
    reuse = _json_if_present(test / "reuse.json")
    method_score = metrics.summary(method, planned)
    if historical:
        if reuse is not None:
            raise ProtocolError("A historical M import cannot supply RSI_selected predictions")
        archive = _json_if_present(test / "historical_M.json", {})
        baseline = metrics.first_pass(archive.get("rows", []), "test", "M")
        baseline_score = _archived_score(archive, baseline, planned)
    else:
        archive = {}
        baseline = first_pass_records(test / "M", "test", "M")
        baseline_score = metrics.summary(baseline, planned)
        if reuse is not None:
            if reuse != {"arm": "RSI_selected", "source_arm": "M", "reason": "identical_runtime"} or method:
                raise ProtocolError("Conflicting evidence for paired-test result reuse")
            method = [{**row, "arm": "RSI_selected"} for row in baseline]
            method_score = metrics.summary(method, planned)

    paired_n = min(len(baseline), len(method))
    paired = None
    pairing_status = "awaiting_question_results" if baseline or not historical else "historical_question_results_unavailable"
    if paired_n:
        matching = all(metrics.key(old) == metrics.key(new) and int(old["step"]) == int(new["step"])
                       for old, new in zip(baseline[:paired_n], method[:paired_n]))
        if matching:
            paired = metrics.paired_summary(baseline[:paired_n], method[:paired_n], planned)
            pairing_status = "complete" if paired_n == planned else "matched_prefix"
        elif historical:
            pairing_status = "question_order_or_ids_differ"
        else:
            raise ProtocolError("Test arms must preserve identical question IDs and stream order")
    return {
        "M": baseline_score,
        "RSI_selected": method_score,
        "comparison_basis": "historical_M" if historical else "fresh_M",
        "pairing_status": pairing_status,
        "paired": paired,
        "historical_M": {"source": archive.get("source"),
                         "protocol_differences": archive.get("protocol_differences", [])} if historical else None,
        "reuse": reuse,
    }


def write_report(out: Path, task: dict) -> dict:
    out = out.resolve()
    dev = out / "dev"
    official = dev / "search" / "official" / "med_m5"
    dev_planned = task["data"]["dev_size"]
    planned_rounds = min(dev_planned, task["development"]["max_rounds"])
    val_planned = task["validation"]["expected_questions"]
    test_planned = task["test"]["expected_questions_per_arm"]
    snapshots = [name for name in task["validation"]["checkpoints"] if int(name[1:]) <= dev_planned]
    dev_rows = first_pass_records(dev, "dev", "RSI")
    checkpoints = _checkpoints(dev)
    completed_rounds = sum(record["status"] == "complete" for record in checkpoints.values())
    dev_summary = metrics.summary(dev_rows, dev_planned)
    dev_summary.update(rounds_planned=planned_rounds, rounds_completed=completed_rounds,
                       accepted_rounds=sum(record.get("accepted") is True for record in checkpoints.values()))
    snapshots_ready = all((dev / "snapshots" / f"{name}.json").is_file() for name in snapshots)
    if completed_rounds != planned_rounds or not snapshots_ready:
        dev_summary["status"] = "partial"

    val_rows = {name: first_pass_records(out / "val" / name, "val", "RSI", name) for name in snapshots}
    val_summary = {name: metrics.summary(rows, val_planned) for name, rows in val_rows.items()}
    selection = _json_if_present(out / "selected_checkpoint.json")
    test_summary = _test_report(out, task)
    historical = test_summary["comparison_basis"] == "historical_M"
    reuse = test_summary["reuse"]

    dev_cost, round_cost = _native_costs(dev, split_dev=True)
    _search_costs(dev, checkpoints, dev_cost["search_replay"], round_cost)
    cost = {
        "dev": {**dev_cost, "phase_wall_time": _json_if_present(dev / "phase_timing.json")},
        "validation": {},
        "test": {},
        "units": "Provider-reported tokens and recorded calls. Worker and search-request seconds are sums across concurrent operations.",
        "limitations": "Phase wall time comes from the phase runner. Failed requests may have unknown token use. Usage records do not establish provider charges.",
    }
    for name in snapshots:
        run = out / "val" / name
        cost["validation"][name] = {**_native_costs(run)[0]["all"],
                                    "phase_wall_time": _json_if_present(run / "phase_timing.json")}
    for arm in (("RSI_selected",) if historical else ("M", "RSI_selected")):
        run = out / "test" / arm
        cost["test"][arm] = {**_native_costs(run)[0]["all"],
                             "phase_wall_time": _json_if_present(run / "phase_timing.json")}
    if historical:
        cost["test"]["M"] = {"execution": "historical_archive", "new_runtime_operations": 0}
    if reuse is not None:
        cost["test"]["RSI_selected"]["usage_from"] = "M"

    metrics.write_csv(out / "dev_curve.csv", metrics.online_curve(dev_rows, task["reporting"]["rolling_window"]))
    metrics.write_csv(out / "replay_summary.csv", metrics.replay_summary(_replay_records(official)))
    metrics.write_json(out / "dev_summary.json", dev_summary)
    metrics.write_json(out / "round_summary.json", _round_report(official, checkpoints, round_cost))
    metrics.write_json(out / "validation_summary.json", {"checkpoints": val_summary, "selection": selection})
    metrics.write_json(out / "test_summary.json", test_summary)
    metrics.write_json(out / "cost_summary.json", cost)

    execution_complete = (dev_summary["status"] == "complete" and selection is not None
                          and all(score["status"] == "complete" for score in val_summary.values())
                          and test_summary["RSI_selected"]["status"] == "complete"
                          and (historical or test_summary["M"]["status"] == "complete"))
    complete = execution_complete and test_summary["M"]["status"] == "complete"
    result = {
        "status": "complete" if complete else "partial",
        "execution_complete": execution_complete,
        "development": dev_summary,
        "validation": val_summary,
        "selected_checkpoint": selection["selected"] if selection else None,
        "test": test_summary,
        "report": str(out / "README.md"),
    }
    lines = [
        "# M5–RRSI development, validation and evaluation",
        "",
        f'Run status is **{result["status"]}**. Accuracy uses the original aligned-correct scorer on locked first answers. '
        "The scored rows below use the completed denominator for each sequence.",
        "",
        "| Sequence | Scored / planned | First-answer accuracy |",
        "| --- | ---: | ---: |",
    ]
    baseline_label = "Historical test M" if historical else "Test M"
    for label, score in [("Development RSI", dev_summary), *val_summary.items(),
                         (baseline_label, test_summary["M"]), ("Test RSI selected", test_summary["RSI_selected"])]:
        lines.append(f'| {label} | {score["n"]}/{score["planned"]} | {_score_text(score)} |')
    lines.extend(["", f'{completed_rounds}/{planned_rounds} search rounds completed. '
                         f'{dev_summary["accepted_rounds"]} rounds promoted a candidate.'])
    if selection:
        lines.append(f'Validation selected **{selection["selected"]}** by micro accuracy, with ties resolved in favor of the earlier snapshot.')
    if historical:
        lines.extend(["", "M uses results from the earlier 11-tool run. RSI selected has its own new evaluation."])
        if test_summary["M"]["source_status"] == "unavailable":
            lines.append("Historical M scores are unavailable in the local import.")
        for difference in test_summary["historical_M"]["protocol_differences"]:
            lines.append(f"- {difference}")
        if test_summary["pairing_status"] == "question_order_or_ids_differ":
            lines.append("Question IDs or order differ between runs. Only individual run scores are available.")
        elif test_summary["pairing_status"] == "historical_question_results_unavailable":
            lines.append("Per-question corrections and harms require historical question scores in the original order.")
    if test_summary["paired"]:
        paired = test_summary["paired"]
        lines.extend(["", f'Among {paired["compared_n"]}/{test_planned} paired questions, '
                          f'{paired["corrections"]} predictions changed from incorrect to correct and '
                          f'{paired["harms"]} changed from correct to incorrect. '
                          f'The net change was {paired["net"]:+d} ({paired["delta_pp"]:+.2f} percentage points).'])
    if reuse is not None:
        lines.append("The selected program and M had identical execution settings. The M run supplies both test columns.")
    if complete:
        lines.extend(["", "| Test dataset | M | RSI selected | Corrections | Harms | Net |",
                      "| --- | ---: | ---: | ---: | ---: | ---: |"])
        base_datasets = test_summary["M"]["per_dataset"]
        new_datasets = test_summary["RSI_selected"]["per_dataset"]
        paired_datasets = test_summary["paired"]["per_dataset"] if test_summary["paired"] else {}
        for dataset in sorted(base_datasets.keys() | new_datasets.keys()):
            base_score = base_datasets.get(dataset, {"n": 0})
            new_score = new_datasets.get(dataset, {"n": 0})
            stats = paired_datasets.get(dataset)
            effects = "— | — | —"
            if stats and stats["n"] == base_score["n"] == new_score["n"]:
                effects = f'{stats["corrections"]} | {stats["harms"]} | {stats["net"]:+d}'
            lines.append(f'| {dataset} | {_score_text(base_score)} | {_score_text(new_score)} | '
                         f'{effects} |')
    lines.extend(["", "[Development curve](dev_curve.csv) · [Replay scores](replay_summary.csv) · "
                   "[Search rounds](round_summary.json) · [Validation](validation_summary.json) · "
                   "[Target evaluation](test_summary.json) · [Compute usage](cost_summary.json)", ""])
    (out / "README.md").write_text("\n".join(lines), encoding="utf-8")
    return result
