"""Compare frozen v6 programs on the original val_new100 stream."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import time
from unittest.mock import patch

from . import validation
from .dev100 import execute, phase_config
from .dev100_metrics import key, paired_summary, score, summary
from .dev100_report import first_pass_records
from .io import ProtocolError, read_json, run_lock, write_json, write_once


EXPECTED = 100


def status(out, stage, **details):
    write_json(out / "status.json", {"stage": stage, "observed_epoch": time.time(), **details})


def wait_for_pilot(pilot, out):
    event = pilot / "events" / "event_01"
    result = event / "result.json"
    if not result.is_file():
        status(out, "waiting_for_pilot", dependency=str(result))
    while not result.is_file():
        launch = read_json(pilot / "launch.json")
        try:
            cmd = (Path("/proc") / str(launch["pid"]) / "cmdline").read_bytes().split(b"\0")
        except FileNotFoundError:
            cmd = []
        if b"m5rrsi.meta_search" not in cmd or os.fsencode(pilot) not in cmd:
            if result.is_file():
                break
            raise ProtocolError("v6 pilot exited before publishing event_01/result.json")
        if (out / "STOP").is_file():
            raise ProtocolError("validation request stopped while waiting for the pilot")
        time.sleep(10)
    completed = read_json(result)
    if completed["status"] != "complete":
        raise ProtocolError(f"v6 pilot did not complete the paired trial: {completed['status']}")
    return completed, read_json(event / "frozen_P_versions.json")


def collect_programs(initial, initial_repo, pairs):
    if len(pairs) != 2:
        raise ProtocolError("expected two frozen program pairs")
    programs = {initial: {"checkpoint": "H0", "commit": initial, "repo": initial_repo, "origins": []}}
    for index, pair in enumerate(pairs, 1):
        for side in ("old", "new"):
            selected = pair[side]
            commit = selected["selected_P"]
            program = programs.setdefault(commit, {
                "checkpoint": f"P_{commit}", "commit": commit,
                "repo": selected["repo"], "origins": [],
            })
            if commit == initial and not program["origins"]:
                program["repo"] = selected["repo"]
            program["origins"].append({
                "trial": index, "side": side, "R": selected["effective_R_version"],
                "accepted_P": selected["P_selected"],
            })
    return list(programs.values())


def repaired_gateway(pilot):
    launch = read_json(pilot / "trusted" / "gateway.launched.json")
    smoke = read_json(pilot / "trusted" / "roi_smoke.json")
    if smoke["gateway_pid"] != launch["pid"] or smoke["status"] != "completed":
        raise ProtocolError("the active v6 gateway lacks a successful ROI smoke receipt")
    try:
        cmd = (Path("/proc") / str(launch["pid"]) / "cmdline").read_bytes().split(b"\0")
    except FileNotFoundError:
        cmd = []
    if os.fsencode(launch["config"]) not in cmd or not Path(launch["control_socket"]).is_socket():
        raise ProtocolError("the repaired v6 gateway is not running")
    return {"gateway_config": launch["config"], "control_socket": launch["control_socket"],
            "gateway_url": launch["gateway_url"]}


def validate_program(base, task, resolved, program, gateway, out):
    name = program["checkpoint"]
    run = out / "programs" / name
    cfg = phase_config(base, task, resolved, "val", "RSI", run, program["commit"], name)
    cfg["upstream_repo"] = program["repo"]
    cfg["runtime"].update(gateway)
    validate_config = validation.validate_config

    def validate_label(config, template_ok=False):
        if config.get("phase") == "val" and config.get("checkpoint") == name:
            validate_config({**config, "checkpoint": "S0"}, template_ok)
            return config
        return validate_config(config, template_ok)

    status(out, "validating", program=name, program_commit=program["commit"],
           run_dir=str(run), planned=EXPECTED)
    with patch.object(validation, "validate_config", validate_label):
        if not execute(cfg):
            raise ProtocolError(f"validation stopped before completion for {name}")
    rows = first_pass_records(run, "val", "RSI", name)
    if len(rows) != EXPECTED or any(row["program_version"] != program["commit"] for row in rows):
        raise ProtocolError(f"validation stream for {name} is incomplete or changed program version")
    return rows


def compare(baseline, method):
    if len(baseline) != EXPECTED or len(method) != EXPECTED:
        raise ProtocolError(f"paired validation requires {EXPECTED} questions in each stream")
    if [(row["step"], key(row)) for row in baseline] != [(row["step"], key(row)) for row in method]:
        raise ProtocolError("paired validation question order differs")
    rows = []
    for old, new in zip(baseline, method):
        old_correct, new_correct = score(old), score(new)
        rows.append({"step": old["step"], "qid": old["qid"], "dataset": old["dataset"],
                     "baseline_correct": old_correct, "method_correct": new_correct,
                     "corrected": bool(new_correct > old_correct), "harmed": bool(old_correct > new_correct)})
    return paired_summary(baseline, method, planned=EXPECTED), rows


def run_validation(v5_run, pilot, out):
    out.mkdir(parents=True, exist_ok=True)
    with run_lock(out / "coordinator.lock"):
        report_path = out / "summary.json"
        if report_path.is_file():
            status(out, "complete", report=str(report_path))
            return
        pilot_result, pairs = wait_for_pilot(pilot, out)
        resolved = read_json(v5_run / "resolved_config.json")
        task = resolved["task"]
        val = resolved["datasets"]["val"]
        if task["validation"]["expected_questions"] != EXPECTED or read_json(val["manifest"])["n"] != EXPECTED:
            raise ProtocolError("the original validation stream is not the fixed 100-question split")
        programs = collect_programs(task["source"]["initial_program_commit"], resolved["upstream_repo"], pairs)
        gateway = repaired_gateway(pilot)
        write_once(out / "frozen_programs.json", {"validation_inputs": val, "programs": programs})
        base = read_json(v5_run / "dev" / "config.json")
        streams = {}
        comparisons = {}
        for program in programs:
            checkpoint = program["checkpoint"]
            rows = validate_program(base, task, resolved, program, gateway, out)
            streams[checkpoint] = {**program, **summary(rows, EXPECTED)}
            if checkpoint == "H0":
                baseline = rows
                continue
            metrics, paired = compare(baseline, rows)
            paired_path = out / "paired" / f"{checkpoint}.json"
            write_once(paired_path, paired)
            comparisons[checkpoint] = {**metrics, "paired_path": str(paired_path)}
        write_once(report_path, {
            "status": "complete", "n": EXPECTED, "phase": "val", "split": task["data"]["val_split"],
            "baseline": "H0", "programs": streams, "comparisons": comparisons,
            "pilot_R_accepted": pilot_result["accepted"], "evidence_scope": "P_comparison_on_prior_R_diagnosis_split",
            "used_for_R_promotion": False,
        })
        status(out, "complete", report=str(report_path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v5-run", type=Path, required=True)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    v5_run, pilot, out = (args.v5_run.resolve(), args.pilot.resolve(), args.out.resolve())
    if out == pilot or not out.is_relative_to(pilot) or out.is_relative_to(v5_run):
        raise ProtocolError("use a separate validation directory under the v6 pilot")
    try:
        run_validation(v5_run, pilot, out)
    except Exception as error:
        prior = out / "status.json"
        previous = read_json(prior) if prior.is_file() else {}
        status(out, "failed", previous_stage=previous.get("stage"), error_type=type(error).__name__)
        raise


if __name__ == "__main__":
    main()
