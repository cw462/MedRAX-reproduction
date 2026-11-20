"""Run the MedRAX v5 development, snapshot validation, and paired evaluation."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import time

from .data import References
from .dev100_data import prepare_data
from .dev100_metrics import select_snapshot
from .dev100_report import first_pass_records, write_report
from .engine import StreamEngine
from .io import ProtocolError, git, read_json, run_lock, write_json, write_once
from .process_runtime import ProcessRuntime
from .runtime import NativeScorer
from .validation import freeze, verify_frozen


def development_repo(base, task, out):
    repo = out / "upstream"
    initial = task["source"]["initial_program_commit"]
    if not (repo / ".git").is_dir():
        repo.mkdir(exist_ok=True)
        git(repo, "init", "-q")
    if not (repo / "domains/med_m5/harness/agent.py").is_file():
        git(repo, "fetch", "--no-tags", base["upstream_repo"], initial)
        git(repo, "checkout", "-q", "-B", "initial-m5", "FETCH_HEAD")
    if git(repo, "rev-parse", "HEAD") != initial:
        raise ProtocolError("v5 repository HEAD must be the original M5 H0")
    return str(repo)


def phase_config(base, task, resolved, phase, arm, run, commit, checkpoint=None):
    data = resolved["datasets"][phase]
    cfg = deepcopy(base)
    cfg.update(
        phase=phase,
        arm=arm,
        run_dir=str(run),
        upstream_repo=resolved["upstream_repo"],
        initial_commit=commit,
        primary_arms=["rrsi_acc"],
        manifest=data["manifest"],
        references=data["references"],
        seed=task["seed"],
    )
    cfg["runtime"]["case_metadata"] = data["case_metadata"]
    cfg["expected_questions"] = {
        "dev": task["data"]["dev_size"],
        "val": task["validation"]["expected_questions"],
        "test": task["test"]["expected_questions_per_arm"],
    }[phase]
    dev = task["development"]
    cfg["search"].update(
        max_rounds=min(dev["max_rounds"], cfg["expected_questions"]) if phase == "dev" else 0,
        replay_window_cases=dev["replay_window"],
        candidates=dev["candidate_slots"],
        repeats=dev["repeats"],
        draft_parallel=dev["draft_parallel"],
        eval_parallel=dev["eval_parallel"],
        repeat_parallel=dev["repeat_parallel"],
        replay_initial_memory=dev["trial_initial_memory"],
    )
    if checkpoint:
        cfg["checkpoint"] = checkpoint
    return cfg


def execute(cfg, stop_after=None):
    run = Path(cfg["run_dir"])
    if (run / "STOP").exists():
        return False
    run.mkdir(parents=True, exist_ok=True)
    write_once(run / "config.json", cfg)
    complete = run / "phase_complete.json"
    if complete.is_file():
        return True
    if (run / "frozen.json").is_file():
        verify_frozen(cfg)
    else:
        freeze(cfg)
    manifest = read_json(cfg["manifest"])
    refs = References(cfg["references"], [row["id"] for row in manifest["cases"]])
    scorer = NativeScorer(cfg["scorer_command"], cfg["metric_id"])
    runtime = ProcessRuntime(cfg["runtime"], run / "runtime_audit")
    runtime.preflight()
    search = None
    if cfg["phase"] == "dev":
        from .search import OfficialSearch
        search = OfficialSearch(cfg, runtime, scorer)
    timing_path = run / "phase_timing.json"
    timing = read_json(timing_path) if timing_path.exists() else {
        "started_at": time.time(), "seconds": 0.0, "attempts": 0
    }
    start = time.monotonic()
    timing["attempts"] += 1
    try:
        result = StreamEngine(cfg, manifest, refs, runtime, scorer, search).run(stop_after)
    finally:
        timing["seconds"] += time.monotonic() - start
        timing["updated_at"] = time.time()
        write_json(timing_path, timing)
    if result["completed"] != cfg["expected_questions"]:
        return False
    if cfg["phase"] == "dev" and not (run / "snapshots" / f"S{cfg['expected_questions']}.json").is_file():
        raise ProtocolError("Development reached the denominator without its final post-search snapshot")
    write_once(complete, result)
    return True


def run_task(phase, task, v4_root, out, stop_after):
    if phase == "report":
        return write_report(out, task)
    initial = task["source"]["initial_program_commit"]
    base = read_json(v4_root / "configs/run.json")
    if (base["initial_commit"] != initial or base["runtime"]["model"] != task["runtime"]["model"]
            or read_json(base["upstream_lock"])["commit"] != task["source"]["rrsi_commit"]):
        raise ProtocolError("Existing v4 program, model or RRSI source does not match experiment.json")
    out.mkdir(parents=True, exist_ok=True)
    resolved_file = out / "resolved_config.json"
    resolved = {
        "task": task,
        "v4_root": str(v4_root),
        "upstream_repo": development_repo(base, task, out),
        "datasets": prepare_data(task, v4_root, out / "data"),
        "runtime": {"model": base["runtime"]["model"], "metric_id": base["metric_id"],
                    "cross_dataset_memory_reset": False, "provider_seed_forwarded": False},
    }
    write_once(resolved_file, resolved)
    if phase == "prepare":
        return {"status": "prepared", "resolved_config": str(resolved_file)}

    if phase in ("dev", "all"):
        from integration.native_gateway import read_key
        gateway = read_json(base["runtime"]["gateway_config"])
        os.environ[base["search_llm"]["api_key_env"]] = read_key(gateway["key_files"]["main"])
        os.environ[base["search_llm"]["base_url_env"]] = gateway["main_base_url"]
        cfg = phase_config(base, task, resolved, "dev", "RSI", out / "dev", initial)
        prefix = out / "dev/prefix_two.completed.json"
        if phase == "all" and not prefix.is_file() and not (out / "dev/phase_complete.json").is_file():
            execute(cfg, 2)
            rows = first_pass_records(out / "dev", "dev", "RSI")
            rounds = out / "dev/search/checkpoints"
            if len(rows) < 2 or any(not (rounds / f"after_{n:06d}" / "done.json").is_file() for n in (1, 2)):
                return write_report(out, task)
            write_once(prefix, {"primary_completed": 2, "rounds_completed": 2})
            print("Development prefix verified: first two locked answers and search rounds.", flush=True)
        if not execute(cfg, stop_after) or phase == "dev":
            return write_report(out, task)

    if not (out / "dev/phase_complete.json").is_file():
        raise ProtocolError("Complete development before snapshot validation")
    names = tuple(name for name in task["validation"]["checkpoints"]
                  if int(name[1:]) <= task["data"]["dev_size"])
    selected_path = out / "selected_checkpoint.json"
    if phase in ("val", "all"):
        rows = []
        for name in names:
            snapshot = read_json(out / "dev/snapshots" / (name + ".json"))
            run = out / "val" / name
            cfg = phase_config(base, task, resolved, "val", "RSI", run, snapshot["commit"], name)
            if not execute(cfg):
                return write_report(out, task)
            rows.extend(first_pass_records(run, "val", "RSI", name))
        choice = select_snapshot(rows, expected=task["validation"]["expected_questions"], names=names)
        snapshot = read_json(out / "dev/snapshots" / (choice["selected"] + ".json"))
        write_once(selected_path, {**choice, "commit": snapshot["commit"]})
        if phase == "val":
            return write_report(out, task)

    if not selected_path.is_file():
        raise ProtocolError("A completed snapshot validation must select the target program")
    selected = read_json(selected_path)["commit"]
    cfg_rsi = phase_config(base, task, resolved, "test", "RSI_selected", out / "test/RSI_selected", selected)
    if task["test"].get("baseline_mode") == "historical":
        execute(cfg_rsi)
        return write_report(out, task)
    cfg_m = phase_config(base, task, resolved, "test", "M", out / "test/M", initial)
    # Only identical effective harnesses and otherwise identical phase settings can share a run.
    harness_subdir = ":domains/med_m5/harness"
    repo = resolved["upstream_repo"]
    same_harness = git(repo, "rev-parse", initial + harness_subdir) == git(repo, "rev-parse", selected + harness_subdir)
    ignored = {"arm", "run_dir", "initial_commit"}
    if (task["test"]["reuse_baseline_if_selected_runtime_is_identical"] and same_harness
            and {k: v for k, v in cfg_m.items() if k not in ignored}
                == {k: v for k, v in cfg_rsi.items() if k not in ignored}):
        write_once(out / "test/reuse.json", {"arm": "RSI_selected", "source_arm": "M",
                                            "reason": "identical_runtime"})
        execute(cfg_m)
    else:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(execute, (cfg_m, cfg_rsi)))
    return write_report(out, task)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "dev", "val", "test", "report", "all"))
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--v4-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--stop-after", type=int)
    args = parser.parse_args()
    if args.stop_after is not None and (args.phase != "dev" or args.stop_after < 1):
        parser.error("--stop-after takes a positive development prefix length")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    task = read_json(args.task)
    with run_lock(out / "coordinator.lock"):
        result = run_task(args.phase, task, args.v4_root.resolve(), out, args.stop_after)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
