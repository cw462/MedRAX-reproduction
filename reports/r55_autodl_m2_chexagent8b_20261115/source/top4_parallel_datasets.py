"""Advance the two short cohorts on the existing AutoDL memory reruns."""

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
from shutil import disk_usage
import subprocess
import sys
import time

from top4_chexagent8_queue import ARMS, COUNTS, ENV, METHODS, REVISION, optional, record, replace, run_dataset


SHORT = ("slake", "vqarad")
# Earlier CheXBench finishers take their own remaining work first.
ARM_ORDER = ("M2", "M3", "M7", "M9")
GIB = 1024**3
BEIJING = timezone(timedelta(hours=8))


DATASET_HANDOFF = '''    if args.dataset in ('slake', 'vqarad') and args.phase in ('dataset', 'score'):
        import fcntl

        out = args.root/'generation'/args.arm/args.dataset
        job = args.root/'jobs'/args.arm/args.dataset
        job.mkdir(parents=True, exist_ok=True)
        with (job/'parallel.lock').open('a') as lease:
            fcntl.flock(lease, fcntl.LOCK_EX)
            receipt = (out/'analysis/memory_usage.json' if args.phase == 'score'
                       else out/'memory.completed.json')
            if receipt.is_file():
                path = out/'analysis/summary.json' if args.phase == 'score' else receipt
                result = json.loads(path.read_bytes())
                if result['questions'] != COUNTS[args.dataset] or result['dataset'] != args.dataset:
                    raise ValueError('unexpected completed dataset')
            else:
                result = (score(args.root, args.arm, args.dataset) if args.phase == 'score'
                          else run_dataset(args.root, args.arm, args.dataset))
        print(json.dumps(result, ensure_ascii=False), flush=True)
        raise SystemExit(0)
'''


def install_handoff(root):
    """Join work already done when the original controller reaches either short dataset."""
    path = root / "bin/run_top4_priority.py"
    code = path.read_text(encoding="utf-8")
    if DATASET_HANDOFF in code:
        return
    anchor = "    result = (score(args.root, args.arm, args.dataset) if args.phase == 'score'\n"
    if code.count(anchor) != 1:
        raise ValueError("Dataset runner interface changed")
    result = code.replace(anchor, DATASET_HANDOFF + anchor)
    ast.parse(result)
    previous = path.with_name("run_top4_priority.before_parallel_datasets.py")
    if not previous.exists():
        with previous.open("x", encoding="utf-8") as saved:
            saved.write(code)
    replace(path, result)


def read_exit(path):
    return int(path.read_text()) if path.is_file() else None


def process_identity(pid):
    try:
        p = Path("/proc") / str(pid)
        fields = (p / "stat").read_text().rsplit(") ", 1)[1].split()
        if fields[0] in ("Z", "X"):
            return None
        return {"pid": pid, "start_ticks": int(fields[19]),
                "args": (p / "cmdline").read_bytes().split(b"\0")}
    except FileNotFoundError:
        return None


def dataset_info(root, arm, dataset):
    output = root / "generation" / arm / dataset
    job = root / "jobs" / arm / dataset
    summary = optional(output / "analysis" / "summary.json")
    n = COUNTS[dataset]
    paths = list((output / "predictions" / f"R55-{arm}").glob("*.json"))
    pid = read_exit(job / "runner.pid")
    proc = process_identity(pid) if pid else None
    active = bool(proc and os.fsencode(root / "bin/run_top4_priority.py") in proc["args"]
                  and all(v.encode() in proc["args"] for v in ("dataset", arm, dataset)))
    exits = (read_exit(job / "runner.exitcode"), read_exit(job / "score.exitcode"),
             read_exit(output / "generation.exitcode"))
    correct = None
    if summary and exits == (0, 0, 0):
        if (summary["arm"], summary["dataset"], summary["questions"], len(paths)) != (
                f"R55-{arm}", dataset, n, n):
            raise ValueError(f"Unexpected score identity for {arm}/{dataset}")
        correct = summary["correct"]
    return {"saved": len(paths), "questions": n, "correct": correct, "pid": pid, "active": active,
            "exit": exits}


def ready(root):
    plan = optional(root / "plan.json") or {}
    gate = optional(root / "jobs/baseline_gate.accepted.json") or {}
    if (plan.get("revision"), gate.get("revision")) != (REVISION, REVISION):
        raise ValueError("Missing original CheXagent-8B baseline completion")
    methods = gate["methods"]
    if set(methods) != set(METHODS) or any(
        methods[m]["exit"] != 0 or set(methods[m]["datasets"]) != set(COUNTS)
        for m in METHODS
    ):
        raise ValueError("The three Qwen baseline methods must finish before starting memory reruns")
    for arm in ARMS:
        for dataset in SHORT:
            m = optional(root / "manifests" / arm / f"{dataset}.json")
            if (m["arm"], m["dataset"], m["initial_repo"], m["memory_provider"],
                    m["chexagent"]["revision"], len(m["inputs"])) != (
                    f"R55-{arm}", dataset, "empty", ARMS[arm], REVISION, COUNTS[dataset]):
                raise ValueError(f"Unexpected frozen cohort for {arm}/{dataset}")


def run_lane(root, dataset, keys):
    log = root / "jobs/parallel-datasets" / dataset
    log.mkdir(parents=True, exist_ok=True)
    state = log / "state.json"
    done, errors = {}, {}
    for arm in ARM_ORDER:
        if (status := dataset_info(root, arm, dataset))["correct"] is not None:
            done[arm] = status["correct"]
            continue
        record(state, {"active_arm": arm, "completed": done, "failed": errors, "epoch": time.time()})
        job = root / "jobs" / arm / dataset
        job.mkdir(parents=True, exist_ok=True)
        try:
            done[arm] = run_dataset(root, arm, dataset, keys)["correct"]
        except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
            errors[arm] = str(error)
    record(state, {"active_arm": None, "completed": done, "failed": errors, "epoch": time.time()})
    return not errors


def run(root, keys):
    if len(keys.splitlines()) != 2 or not all(keys.splitlines()):
        raise ValueError("Missing experiment credentials")
    ready(root)
    with (root / "jobs/parallel-datasets/run.lock").open("a") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with ThreadPoolExecutor(max_workers=len(SHORT)) as pool:
            jobs = [pool.submit(run_lane, root, ds, keys) for ds in SHORT]
            complete = [j.result() for j in jobs]
    return int(not all(complete))


def launch(root, keys):
    ready(root)
    if len(keys.splitlines()) != 2 or not all(keys.splitlines()):
        raise ValueError("Missing experiment credentials")
    for p in (root, Path("/dev/shm")):
        if disk_usage(p).free < GIB:
            raise RuntimeError(f"Insufficient space to start additional datasets on {p}")
    jobs = root / "jobs/parallel-datasets"
    jobs.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (jobs / "launch.lock").open("a") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        existing = optional(jobs / "controller.started.json")
        proc = process_identity(existing["pid"]) if existing else None
        script = Path(__file__).resolve()
        if (proc and proc["start_ticks"] == existing["start_ticks"] and
                os.fsencode(script) in proc["args"]):
            return existing
        install_handoff(root)
        with (jobs / "controller.stdout.log").open("ab") as out, \
                (jobs / "controller.stderr.log").open("ab") as err:
            child = subprocess.Popen([sys.executable, "-B", "-u", str(script), "run", str(root)],
                                     stdin=subprocess.PIPE, stdout=out, stderr=err,
                                     env={**os.environ, **ENV}, cwd=root, start_new_session=True)
            child.stdin.write(keys)
            child.stdin.close()
        receipt = {"pid": child.pid, "start_ticks": process_identity(child.pid)["start_ticks"],
                   "epoch": time.time(), "datasets": SHORT, "arm_order": ARM_ORDER}
        record(jobs / "controller.started.json", receipt)
        return receipt


def status(root):
    jobs = root / "jobs/parallel-datasets"
    return {
        "as_of": datetime.now(BEIJING).isoformat(timespec="seconds"),
        "datasets": {a: {ds: dataset_info(root, a, ds) for ds in COUNTS} for a in ARMS},
        "lanes": {s: optional(jobs / s / "state.json") for s in SHORT},
        "storage": {str(p): round(disk_usage(p).free / GIB, 2) for p in (root, Path("/dev/shm"))},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "run", "status"))
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    if args.mode == "status":
        result = status(args.root)
    else:
        keys = sys.stdin.buffer.read()
        if args.mode == "run":
            raise SystemExit(run(args.root, keys))
        result = launch(args.root, keys)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
