"""Run two laboratory experiment arms at a time on the RTX 3090 pair."""

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import os
from pathlib import Path
from shutil import copytree, disk_usage, ignore_patterns
import signal
import subprocess
import sys
import time

import queue_r55_11tools_lab as base


ROOT, JOBS, DATASETS = base.ROOT, base.JOBS, base.DATASETS
WAVES = (("D",), ("M5", "E"), ("D8",))
ARM_ORDER = tuple(arm for wave in WAVES for arm in wave)
D8 = "R55-D-8tools-CheXagent8B"
REMOVED = ("medret", "reflect", "verify")
HANDOFF = JOBS / "parallel.handoff.json"


def install(path, content):
    ast.parse(content)
    pending = path.with_suffix(".parallel-tmp")
    pending.write_text(content, encoding="utf-8")
    pending.replace(path)


def stage():
    plan = base.read(ROOT / "plan.json")
    if plan.get("waves") == [list(wave) for wave in WAVES]:
        return plan["waves"]
    if plan["arms"].get("D8") == D8:
        plan["waves"] = WAVES
        base.save(ROOT / "plan.json", plan)
        return [list(wave) for wave in WAVES]
    plan["arms"]["D8"] = D8
    plan["waves"] = WAVES
    plan["d8_removed_tools"] = REMOVED
    old_code = ROOT / "code/D"
    d8_code = ROOT / "code/D8"
    copytree(old_code, d8_code, ignore=ignore_patterns("__pycache__", "*.pyc"), dirs_exist_ok=True)
    services = d8_code / "experiments/skill_services_r49.py"
    source = services.read_text(encoding="utf-8")
    source = source.replace("request_archive='inline_original_images_semantic_restart_r49'",
                            "request_archive=protocol['request_archive']")
    install(services, source)
    for dataset in DATASETS:
        source = ROOT / "manifests" / "D" / f"{dataset}.json"
        m = base.read(source)
        m["arm"] = D8
        m["implementation_revision"] = D8 + "-full848"
        m["protocol"]["experiment_id"] = ROOT.name + "-D8"
        m["protocol"]["request_archive"] = "image_base64_content_addressed_v1"
        m["ablation"] = {"parent_arm": plan["arms"]["D"], "disabled_tools": REMOVED}
        runtime = m["runtime"]
        for name in REMOVED:
            del runtime["tools"][name]
        for spec in runtime["arms"].values():
            spec["tools"] = [name for name in spec["tools"] if name not in REMOVED]
        assert len(runtime["tools"]) == 8
        assert all(set(spec["tools"]) == set(runtime["tools"]) for spec in runtime["arms"].values())
        assert runtime["tools"]["chest_xray_expert"]["revision"] == plan["revision"]
        base.save(ROOT / "manifests" / "D8" / source.name, m)

    path = ROOT / "run_r55_full848_dataset.py"
    runner = path.read_text(encoding="utf-8")
    lines = runner.splitlines(keepends=True)
    arms = next(line for line in lines if line.startswith("ARMS = "))
    runner = runner.replace(arms, f"ARMS = {plan['arms']!r}\n", 1)
    runner = runner.replace("and len(tools) == 11", "and len(tools) == (8 if arm == 'D8' else 11)")
    runner = runner.replace("if arm == 'D':", "if arm in ('D', 'D8'):")
    install(path, runner)

    scratch = Path("/dev/shm") / ("medrax-" + ROOT.name)
    scratch.mkdir(mode=0o700, exist_ok=True)
    for arm in ("E", "D8"):
        output = ROOT / "generation" / arm
        target = scratch / arm
        if not output.exists():
            target.mkdir(mode=0o700, exist_ok=True)
            output.symlink_to(target, target_is_directory=True)
        elif output.is_dir() and not any(output.iterdir()) and not output.is_symlink():
            output.rmdir()
            target.mkdir(mode=0o700, exist_ok=True)
            output.symlink_to(target, target_is_directory=True)
    plan["second_wave_output"] = {arm: str((ROOT / "generation" / arm).resolve()) for arm in ("E", "D8")}
    base.save(ROOT / "plan.json", plan)
    return [list(wave) for wave in WAVES]


def existing_attempt(arm, dataset):
    _, job, _ = base.dataset_paths(arm, dataset)
    attempts = sorted(job.glob("attempt-*"))
    return attempts[-1] if attempts else None


def runner(arm, dataset):
    attempt = existing_attempt(arm, dataset)
    return base.live(base.read(attempt / "runner.started.json")) if attempt else None


def signal_owned(receipt, sig, program):
    current = base.live(receipt)
    if not current or not current["alive"]:
        return False
    cmd = (Path("/proc") / str(receipt["pid"]) / "cmdline").read_bytes().split(b"\0")
    if os.fsencode(program) not in cmd:
        raise RuntimeError("Process identity changed during the laboratory handoff")
    os.kill(receipt["pid"], sig)
    return True


def safe_to_release(out, proc):
    pid = proc["pid"]
    if base.native(pid)["state"] != "T":
        return False
    children = (Path("/proc") / str(pid) / "task" / str(pid) / "children").read_text().strip()
    if children:
        return False
    services = out / "services"
    for marker in (services / "calls").glob("*/*/*/started.json"):
        folder = marker.parent
        if not (folder / "result.json").is_file():
            return False
        terminal = (folder / "response.json").is_file()
        disposition = any((folder / name).is_file() for name in (
            "unavailable.top4.json", "unavailable.continue60.json", "unavailable.recovery001.json",
            "timeout.json",
        ))
        if not (terminal or disposition):
            return False
    for marker in (services / "tool_cache").glob("*/started.json"):
        if not (marker.parent / "result.json").is_file():
            return False
    return True


def release_d_slake():
    out, _, _ = base.dataset_paths("D", "slake")
    program = ROOT / "run_r55_full848_dataset.py"
    for _ in range(55):
        proc = runner("D", "slake")
        if not proc or not proc["alive"]:
            return {"state": "finished_or_not_started"}
        if not signal_owned(proc, signal.SIGSTOP, program):
            return {"state": "finished_or_not_started"}
        try:
            for _ in range(20):
                if base.native(proc["pid"])["state"] in ("T", "Z", None):
                    break
                time.sleep(0.025)
            if safe_to_release(out, proc):
                n = sum(1 for _ in (out / "predictions" / "R55-D-11tools-CheXagent8B").glob("*.json"))
                signal_owned(proc, signal.SIGKILL, program)
                return {"state": "saved_prefix", "predictions": n, "runner": proc["pid"]}
        finally:
            # If still paused, allow the current request or tool to finish.
            if base.native(proc["pid"])["state"] == "T":
                signal_owned(proc, signal.SIGCONT, program)
        time.sleep(1.5)
    return {"state": "let_inflight_dataset_finish"}


def handoff(old):
    if not old or not old["alive"]:
        return
    program = ROOT / "queue_r55_11tools_lab.py"
    signal_owned(old, signal.SIGSTOP, program)
    for _ in range(30):
        if base.native(old["pid"])["state"] == "T":
            break
        time.sleep(0.05)
    release = None
    try:
        gpu0 = runner("D", "chexbench")
        release = release_d_slake()
        base.save(HANDOFF, {"previous_dispatcher": old["pid"], "D_chexbench": gpu0,
                            "D_slake": release, "epoch": time.time()})
        signal_owned(old, signal.SIGTERM, program)
    finally:
        signal_owned(old, signal.SIGCONT, program)
    for _ in range(80):
        if not base.live(old)["alive"]:
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("The original laboratory dispatcher did not exit")
    if release["state"] == "saved_prefix":
        out, job, _ = base.dataset_paths("D", "slake")
        base.save(job / "paused_for_m5.json", release)
        # An unfinished run has no successful generation marker.
        if not (out / "complete.json").is_file():
            (out / "generation.exitcode").write_text("75\n", encoding="utf-8")


def checkpoint_inherited(plan, arm, ds, receipt):
    """Record a cleanly finished orphan before running the regular scorer."""
    out, _, _ = base.dataset_paths(arm, ds)
    attempt = existing_attempt(arm, ds)
    done = base.read(out / "complete.json")
    if not done or (done.get("arm"), done.get("questions")) != (plan["arms"][arm], plan["counts"][ds]):
        raise RuntimeError(f"Inherited runner exited before completing {arm}/{ds}. See {attempt}")
    stdout = attempt / "runner.stdout.log"
    with stdout.open("rb") as stream:
        stream.seek(max(0, stdout.stat().st_size - 8192))
        terminal = json.loads(stream.read().splitlines()[-1])
    if terminal.get("arm") not in (arm, plan["arms"][arm]) or (
            terminal.get("dataset"), terminal.get("questions")) != (ds, plan["counts"][ds]):
        raise RuntimeError(f"Missing successful terminal result for inherited {arm}/{ds}. See {stdout}")
    base.save(attempt / "runner.exit.json", {"returncode": 0, "pid": receipt["pid"],
                                             "epoch": time.time(), "completion": "terminal_runner_output"})
    (out / "generation.exitcode").write_text("0\n", encoding="utf-8")


def save_arm(plan, arm):
    scores = {ds: base.official(plan, arm, ds) for ds in DATASETS}
    if not all(scores.values()):
        return False
    questions = sum(score["questions"] for score in scores.values())
    correct = sum(score["correct"] for score in scores.values())
    base.save(JOBS / arm / "complete.json", dict(arm=plan["arms"][arm], correct=correct, questions=questions,
              accuracy_pct=100 * correct / questions, datasets=scores))
    return True


def run_wave(plan, wave, keys):
    active, failed = {}, {}
    for arm in wave:
        for ds in DATASETS:
            proc = runner(arm, ds)
            if proc and proc["alive"]:
                active[proc["gpu"]] = (arm, ds, None, proc)
    snapshot = base.read(HANDOFF) or {}
    inherited = snapshot.get("D_chexbench")
    if "D" in wave and inherited and not base.live(inherited)["alive"] and not base.official(plan, "D", "chexbench"):
        out, _, _ = base.dataset_paths("D", "chexbench")
        if (out / "complete.json").is_file() and not (out / "generation.exitcode").exists():
            checkpoint_inherited(plan, "D", "chexbench", inherited)
    waiting = [(arm, ds) for arm in wave for ds in DATASETS
               if not base.official(plan, arm, ds) and not any(a[:2] == (arm, ds) for a in active.values())]
    with ThreadPoolExecutor(max_workers=2) as pool:
        while waiting or active:
            for gpu, (arm, ds, future, proc) in list(active.items()):
                if future is not None and not future.done():
                    continue
                if proc is not None and base.live(proc)["alive"]:
                    continue
                try:
                    if proc is not None:
                        checkpoint_inherited(plan, arm, ds, proc)
                        waiting.insert(0, (arm, ds))
                    elif result := future.result():
                        failed[f"{arm}/{ds}"] = result
                except Exception as error:
                    failed[f"{arm}/{ds}"] = str(error)
                del active[gpu]
            if waiting:
                for gpu, info in base.gpu_status().items():
                    if gpu not in plan["gpus"] or gpu in active or info["pids"] or info["used_mib"] >= 1024:
                        continue
                    active_arms = {info[0] for info in active.values()}
                    preferred = next((arm for arm in wave if arm not in active_arms
                                      and any(a == arm for a, _ in waiting)), None)
                    chosen = next((i for i, (a, _) in enumerate(waiting) if a == preferred), 0)
                    if waiting:
                        arm, ds = waiting.pop(chosen)
                        active[gpu] = (arm, ds, pool.submit(base.run_dataset, plan, arm, ds, gpu, keys), None)
            for arm in wave:
                if not (JOBS / arm / "complete.json").is_file():
                    save_arm(plan, arm)
            base.save(JOBS / "queue.state.json", dict(
                arm="+".join(wave), wave=list(wave),
                gpus={gpu: {"arm": a, "dataset": d} for gpu, (a, d, _, _) in active.items()},
                waiting=[f"{a}/{d}" for a,d in waiting], failed=failed, epoch=time.time()))
            if waiting or active:
                time.sleep(4)
    return failed


def run():
    keys = sys.stdin.buffer.read().splitlines()
    if len(keys) != 4 or not all(keys):
        raise RuntimeError("Existing main, embedding, writer and memory credentials required")
    with (JOBS / "queue.run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = base.read(ROOT / "plan.json")
        (JOBS / "queue.finished.json").unlink(missing_ok=True)
        for wave in WAVES:
            failures = run_wave(plan, wave, keys)
            if failures:
                base.save(JOBS / "queue.finished.json", {"returncode": 1, "wave": wave, "failed": failures})
                return 1
        base.save(JOBS / "queue.finished.json", {"returncode": 0, "completed": ARM_ORDER})
    return 0


def score_inherited(dataset):
    out, job, _ = base.dataset_paths("D", dataset)
    plan = base.read(ROOT / "plan.json")
    proc = runner("D", dataset)
    if not proc or proc["alive"]:
        raise RuntimeError(f"Inherited D/{dataset} runner has not exited")
    attempt = existing_attempt("D", dataset)
    if not base.official(plan, "D", dataset):
        if not (attempt / "runner.exit.json").is_file():
            checkpoint_inherited(plan, "D", dataset, proc)
        if (out / "generation.exitcode").read_text().strip() != "0":
            raise RuntimeError(f"Inherited D/{dataset} generation did not complete")
        # The generation success marker makes this a scorer-only operation.
        rc = base.run_dataset(plan, "D", dataset, proc["gpu"], (b"", b"", b"", b""))
        if rc:
            raise RuntimeError(f"D/{dataset} scorer exited {rc}, see {job}")
    return base.official(plan, "D", dataset)


def launch():
    keys = sys.stdin.buffer.read()
    if len(keys.splitlines()) != 4 or not all(keys.splitlines()):
        raise RuntimeError("Existing laboratory credentials missing")
    with (JOBS / "queue.launch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        stage()
        current = base.live(base.read(JOBS / "queue.started.json"))
        script = Path(__file__).resolve()
        if current and current["alive"]:
            if current.get("program") == script.name:
                return current
            handoff(current)
        if (base.read(JOBS / "queue.finished.json") or {}).get("completed") == list(ARM_ORDER):
            return {"complete": True}
        with (JOBS / "queue.parallel.stdout.log").open("ab") as out, \
                (JOBS / "queue.parallel.stderr.log").open("ab") as err:
            process = subprocess.Popen([sys.executable, "-B", "-u", str(script), "run"],
                                       stdin=subprocess.PIPE, stdout=out, stderr=err, start_new_session=True)
            process.stdin.write(keys)
            process.stdin.close()
        receipt = dict(base.native(process.pid), program=script.name, epoch=time.time())
        base.save(JOBS / "queue.started.json", receipt)
        return receipt


def status():
    base.ORDER = ARM_ORDER
    report = base.status()
    report["handoff"] = base.read(HANDOFF)
    report["waves"] = WAVES
    report["second_wave_free"] = disk_usage("/dev/shm").free
    if report["process"] and not report["process"]["alive"]:
        report["queue_error"] = base.tail(JOBS / "queue.parallel.stderr.log")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("stage", "launch", "run", "status", "score_inherited"))
    parser.add_argument("dataset", choices=DATASETS, nargs="?")
    args = parser.parse_args()
    phase = args.phase
    if phase == "run":
        raise SystemExit(run())
    if phase == "score_inherited":
        if not args.dataset:
            parser.error("score_inherited requires a dataset")
        result = score_inherited(args.dataset)
    else:
        result = globals()[phase]()
    print(json.dumps(result, ensure_ascii=True))
