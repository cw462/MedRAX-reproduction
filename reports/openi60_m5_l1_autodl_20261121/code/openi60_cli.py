#!/usr/bin/env python3
"""Prepare/run/analyze the 60-question paired M5 laterality pilot."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from openi60.common import ExperimentError, require, read_json, write_once, write_text_once, file_hash
from openi60.setup import PKG, new_config, load_config, verify_local, prepare, verify_frozen
from openi60.cohort import laterality_signature
from openi60.analysis import analyze, audit_arm, verify_score_receipt

def utc():
    return datetime.now(timezone.utc).isoformat()

@contextmanager
def lock_work(work):
    import fcntl  # Target native runtime is Linux.
    with (work / ".openi60.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ExperimentError("Another OpenI60 controller is using this work directory") from None
        yield

def worker_command(phase, work, arm="B0"):
    return [sys.executable, "-B", "-u", str(PKG / "native_worker.py"), phase,
            "--work", str(work), "--arm", arm]

def preflight(work):
    frozen = verify_frozen(work)
    cfg = frozen["config"]
    # Static existence + imports only. No paid health probes and no model instantiation.
    verify_local(cfg)
    result = subprocess.run(worker_command("check", work), cwd=cfg["native_root"],
                            stdin=subprocess.DEVNULL, text=True, capture_output=True)
    require(result.returncode == 0,
            "Native import/signature check failed (no inference launched):\n" + result.stderr[-12000:])
    return {"status": "offline_preflight_passed", "paid_model_calls": 0,
            "native_check_stdout": result.stdout.strip(),
            "gpu": cfg["gpu"], "n_per_arm": cfg["n"],
            "note": "This does not test remote API availability or actual GPU-tool inference."}

def child(phase, work, arm, cfg, attempt, credentials=b""):
    env = dict(os.environ)
    env.update(CUDA_VISIBLE_DEVICES=cfg["gpu"], R55_MEMEVOLVE_GPU=cfg["gpu"],
               PYTHONDONTWRITEBYTECODE="1", LANGCHAIN_TRACING_V2="false", LANGSMITH_TRACING="false")
    command = worker_command(phase, work, arm)
    write_once(attempt / f"{phase}.started.json", {"utc": utc(), "command": command, "arm": arm})
    with (attempt / f"{phase}.stdout.log").open("xb") as out, (attempt / f"{phase}.stderr.log").open("xb") as err:
        result = subprocess.run(command, cwd=cfg["native_root"], env=env,
                                input=credentials, stdout=out, stderr=err)
    write_once(attempt / f"{phase}.exit.json", {"utc": utc(), "returncode": result.returncode})
    return result.returncode

def run(work, execute, resume, arm):
    require(execute, "No inference started. Add --execute only on the configured model/GPU environment.")
    frozen = verify_frozen(work)
    cfg = frozen["config"]
    plan = cfg["execution_order"] if arm == "all" else [arm]
    # Secrets are not copied into configuration, command-line argv, or audit files.
    preflight(work)
    results = {}
    with lock_work(work):
        for name in plan:
            out = work / name
            per_question = out / "analysis" / "per_question.json"
            if (out / "scoring.completed.json").is_file():
                verify_score_receipt(out)
                audit_arm(work, name, frozen["cohort"]["selected_ids"])
                results[name] = {"status": "already_scored_no_new_inference"}
                continue
            exitfile = out / "generation.exitcode"
            generated = exitfile.is_file() and exitfile.read_text().strip() == "0"
            if not generated:
                dirty = any((out / p).exists() for p in ("storage", "external_memory", "services", "predictions"))
                require(not dirty or resume,
                        f"{name} has existing execution state. Use --resume to invoke native checkpoint checks; do not delete failures.")
            jobs = work / "jobs" / name; jobs.mkdir(parents=True, exist_ok=True)
            existing = sorted(jobs.glob("attempt-*"))
            attempt = jobs / f"attempt-{len(existing)+1:03d}"; attempt.mkdir()
            if not generated:
                main_key = os.environ.get(cfg["main_key_env"], "").strip()
                memory_key = os.environ.get(cfg["memory_key_env"], "").strip()
                require(main_key and memory_key, "Set the two configured credential environment variables; never paste keys into source.")
                require("\n" not in main_key and "\n" not in memory_key, "Credential must be a single line")
                print(f"Running {name}: {cfg['n']} first-answer episodes; logs: {attempt}", flush=True)
                code = child("generate", work, name, cfg, attempt, (main_key + "\n" + memory_key + "\n").encode())
                exitfile.write_text(str(code) + "\n", encoding="utf-8")
                require(code == 0,
                        f"{name} stopped with code {code}; no automatic retry/expansion. Inspect {attempt}/generate.stderr.log")
            audit = audit_arm(work, name, frozen["cohort"]["selected_ids"])
            # Original scorer creates CSV with mode='x'. Keep partial prior scoring artifacts.
            analysis_dir = out / "analysis"
            if analysis_dir.exists():
                require(resume, f"Incomplete previous analysis at {analysis_dir}; use --resume to preserve it and rescore")
                analysis_dir.rename(attempt / "previous_analysis")
            code = child("score", work, name, cfg, attempt)
            require(code == 0, f"Native scoring failed for {name}; inspect {attempt}/score.stderr.log")
            write_once(out / "scoring.completed.json", {
                "returncode": 0, "per_question_sha256": file_hash(out / "analysis" / "per_question.json"),
                "summary_sha256": file_hash(out / "analysis" / "summary.json"),
            })
            results[name] = {"status": "scored", "audit": audit,
                             "score": read_json(out / "analysis" / "summary.json")}
        if all((work / a / "scoring.completed.json").is_file() for a in ("B0", "L1")):
            results["paired"] = analyze(work)
    return results

def status(work):
    frozen = read_json(work / "frozen.json")
    result = {"work": str(work), "n_per_arm": frozen["config"]["n"], "arms": {}}
    for arm in ("B0", "L1"):
        out = work / arm
        native = read_json(out / "manifest.json")["arm"]
        item = {"locked_predictions": len(list((out / "predictions" / native).glob("*.json"))),
                "feedback_records": len(list((out / "feedback").glob("*.json"))),
                "memory_ingest_receipts": len(list((out / "external_memory" / "episodes").glob("*/ingest.json"))),
                "complete": (out / "complete.json").is_file(),
                "scored": (out / "scoring.completed.json").is_file()}
        summary = out / "analysis" / "summary.json"
        if summary.is_file():
            s = read_json(summary)
            item["score"] = {k: s.get(k) for k in ("questions", "correct", "accuracy_pct", "main_calls", "tool_calls", "failed_tool_calls")}
        result["arms"][arm] = item
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("configure", help="Discover paths from the existing LOCAL R55 plan.json")
    s.add_argument("--native-root", type=Path, required=True)
    s.add_argument("--work-dir", type=Path, required=True)
    s.add_argument("--out", type=Path, default=Path("config.local.json"))
    for command in ("inspect", "prepare"):
        s = sub.add_parser(command)
        s.add_argument("--config", type=Path, required=True)
    for command in ("preflight", "status", "analyze", "run"):
        s = sub.add_parser(command)
        s.add_argument("--work", type=Path, required=True)
        if command == "run":
            s.add_argument("--execute", action="store_true")
            s.add_argument("--resume", action="store_true")
            s.add_argument("--arm", choices=("all", "B0", "L1"), default="all")
    a = parser.parse_args()
    if a.command == "configure":
        cfg = new_config(a.native_root, a.work_dir)
        write_once(a.out.resolve(), cfg)
        value = {"config": str(a.out.resolve()), "instruction": "Review paths/model routing before prepare; no inference started."}
    elif a.command in ("inspect", "prepare"):
        cfg = load_config(a.config)
        if a.command == "prepare":
            value = prepare(cfg)
        else:
            from collections import Counter
            m = verify_local(cfg)
            pool = [r for r in m["inputs"] if laterality_signature(r) is not None]
            value = {"pool_size": len(pool), "expected_pool": cfg.get("expected_pool"),
                     "skeleton_counts": dict(Counter(laterality_signature(r) for r in pool)),
                     "question_ids": [r["question_id"] for r in pool], "model_calls": 0}
    else:
        work = a.work.resolve()
        if a.command == "preflight": value = preflight(work)
        elif a.command == "status": value = status(work)
        elif a.command == "analyze": value = analyze(work)
        else: value = run(work, a.execute, a.resume, a.arm)
    print(json.dumps(value, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    try:
        main()
    except (ExperimentError, FileNotFoundError, KeyError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
