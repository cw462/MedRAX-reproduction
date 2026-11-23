"""Run the six AutoDL Qwen R55 eight-tool arms and record native cohort exits."""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import r55_deepseek_rerun_runtime as guards


ROOT, JOBS = guards.ROOT, guards.JOBS
MODELS = {"flash": "qwen3.6-flash", "plus": "qwen3.7-plus"}
COUNTS = {"slake": 114, "vqarad": 116, "chexbench": 618}
ARMS = ("ReAct", "M5", "M2")
MEMORY = {"M5": "cerebra_fusion_memory", "M2": "expel"}
TOOLS = ("chest_xray_expert", "llava_med_qa", "medgemma", "llava_rad", "medvlm_r1",
         "maira2_grounded_report", "xray_phrase_grounding", "roi_crop")
CREDENTIALS = Path("/root/.config/medrax-autodl-r55/memory_resume.keys")
MIB = 1024**2
FLOOR = 320 * MIB
CHEXBENCH_WORK_SPACE = 1050 * MIB
QUEUE = [(model, arm, dataset) for dataset in COUNTS for arm in ARMS for model in MODELS]


def credentials():
    if CREDENTIALS.stat().st_mode & 0o077:
        raise RuntimeError("The existing AutoDL credential file must be private")
    qwen, memory = CREDENTIALS.read_bytes().splitlines()
    if not qwen.startswith(b"sk-sp-") or not memory.startswith(b"sk-") or memory.startswith((b"sk-sp-", b"sk-ws-")):
        raise RuntimeError("The existing credential slots do not match the two configured routes")
    return qwen, memory


def paths(model, arm, dataset):
    run = ROOT / model
    if arm in MEMORY:
        return run / "generation" / arm / dataset, None
    return run / "flash_react/react" / dataset, run / "flash_react/api" / dataset


def job_path(model, arm, dataset):
    return JOBS / "cohorts" / model / arm / dataset


def summary_path(model, arm, dataset):
    out, _ = paths(model, arm, dataset)
    return out / ("analysis/summary.json" if arm in MEMORY else "summary.json")


def command(model, arm, dataset, phase):
    root = ROOT / model
    python = str(root / "env/modern/bin/python")
    if arm in MEMORY:
        return [python, "-B", "-u", str(root / "bin/run_qwen8_memory.py"), phase, str(root), arm,
                "--dataset", dataset]
    args = [python, "-B", "-u", str(root / "flash_react/code/run_qwen_baselines.py"), str(root),
            str(root / "flash_react"), "react", "--dataset", dataset, "--r55-8-tools", "--workers", "3"]
    if phase == "verify":
        args.append("--prepare")
    return args


def environment(model, arm):
    plan = guards.read(ROOT / "plan.json")
    return dict(os.environ, CUDA_VISIBLE_DEVICES="0", R55_MEMEVOLVE_GPU="0",
                R55_CHEXAGENT8_SNAPSHOT=plan["chexagent8_snapshot"], R55_REQUIRE_CHEXAGENT8="1",
                R55_QWEN8_ARM=f"{model}/{arm}", OMP_NUM_THREADS="2", MKL_NUM_THREADS="2",
                PYTHONDONTWRITEBYTECODE="1", LANGCHAIN_TRACING_V2="false", LANGSMITH_TRACING="false")


def wait_for_case():
    arm = os.environ["R55_QWEN8_ARM"]
    while shutil.disk_usage(ROOT).free < FLOOR:
        time.sleep(4)
    guards.wait_for_arm(ROOT, arm)


def chexbench_capacity(free):
    return min(4, max(0, (free - FLOOR) // CHEXBENCH_WORK_SPACE))


def working_budget(identity):
    return CHEXBENCH_WORK_SPACE if identity[-1] == "chexbench" else 240 * MIB


def available_for(active, identity, free):
    pending = [item for item, (phase, _) in active.items() if phase == "dataset"] + [identity]
    budget = sum(working_budget(item) for item in pending)
    if free >= FLOOR + budget:
        return True
    if free <= FLOOR:
        return False
    remaining = 0
    for item in pending:
        existing = [str(path) for path in paths(*item) if path is not None and path.is_dir()]
        used = 0
        if existing:
            measured = subprocess.run(["du", "-s", "-B1", "--", *existing], capture_output=True, text=True, timeout=12)
            if measured.returncode == 0:
                used = sum(int(line.split()[0]) for line in measured.stdout.splitlines())
        remaining += max(0, working_budget(item) - used)
    return free >= FLOOR + remaining


def launch(identity, phase, keys):
    model, arm, dataset = identity
    job = job_path(*identity)
    job.mkdir(parents=True, exist_ok=True)
    with (job / f"{phase}.stdout.log").open("ab") as out, (job / f"{phase}.stderr.log").open("ab") as err:
        child = subprocess.Popen(command(*identity, phase), cwd=ROOT / model, env=environment(model, arm),
                                 stdin=subprocess.PIPE if keys else subprocess.DEVNULL, stdout=out, stderr=err)
    guards.save(job / f"{phase}.started.json", {"pid": child.pid, "start_ticks": guards.native(child.pid),
                                               "epoch": time.time()})
    if keys:
        with child.stdin:
            child.stdin.write(b"\n".join(keys if arm in MEMORY else keys[:1]) + b"\n")
    return child


def finish(identity):
    model, arm, dataset = identity
    out, _ = paths(*identity)
    summary = guards.read(summary_path(*identity))
    label = f"R55-{arm}" if arm in MEMORY else "react"
    n = COUNTS[dataset]
    if (summary["arm"], summary["dataset"], summary["questions"]) != (label, dataset, n):
        raise RuntimeError(f"Mismatched native score for {identity}")
    predictions = list((out / "predictions").rglob("*.json"))
    if len(predictions) != n:
        raise RuntimeError(f"Incomplete prediction set for {identity}")
    if arm in MEMORY and len(list((out / "external_memory/episodes").glob("*/ingest.json"))) != n:
        raise RuntimeError(f"Incomplete memory writes for {identity}")
    guards.save(job_path(*identity) / "complete.json", {"epoch": time.time(), "correct": summary["correct"],
                                                       "questions": n, "model": MODELS[model]})


def supervise(keys):
    active = {}
    healthy_samples = 0
    scope = {tuple(pair) for pair in guards.read(JOBS / "scope.json").get("selected", [])}
    queue = [identity for identity in QUEUE if not scope or identity[:2] in scope]
    max_active = guards.read(ROOT / "plan.json").get("max_active_cohorts", 2)
    with guards.lease(JOBS / "supervisor.lock"):
        while True:
            gpu = guards.gpu_sample()
            healthy_samples = healthy_samples + 1 if gpu["healthy"] else 0
            guards.save(JOBS / "gpu.json", dict(gpu, healthy_samples=healthy_samples))
            for identity, (phase, child) in list(active.items()):
                code = child.poll()
                if code is None:
                    continue
                del active[identity]
                job = job_path(*identity)
                guards.save(job / f"{phase}.exit.json", {"epoch": time.time(), "exit": code})
                if code:
                    guards.save(job / "failed.json", {"epoch": time.time(), "phase": phase, "exit": code,
                                                      "error": guards.safe_error(job, phase)})
                elif identity[1] in MEMORY and phase == "dataset":
                    active[identity] = ("score", launch(identity, "score", ()))
                else:
                    finish(identity)

            closed = {item for item in queue if (job_path(*item) / "complete.json").is_file()}
            failed = {item for item in queue if (job_path(*item) / "failed.json").is_file()}
            if len(closed | failed) == len(queue):
                receipt = "needs-attention.json" if failed else "complete.json"
                guards.save(JOBS / receipt, {"epoch": time.time(), "completed": len(closed), "failed": sorted(failed)})
                return
            free = shutil.disk_usage(ROOT).free
            waiting = [item for item in queue if item not in closed and item not in failed and item not in active]
            for _ in range(max_active - len(active)):
                busy = {item[:2] for item in active}
                for identity in sorted(waiting, key=lambda item: (item[-1] != "chexbench", item[:2] in busy)):
                    model, arm, dataset = identity
                    if not guards.allowed(ROOT, f"{model}/{arm}") or not available_for(active, identity, free):
                        continue
                    active[identity] = ("dataset", launch(identity, "dataset", keys))
                    waiting.remove(identity)
                    break
            time.sleep(4)


def status():
    initial = guards.read(JOBS / "supervisor.started.json")
    holding = guards.read(JOBS / "gpu-hold.json")
    now = time.time()
    rows = []
    for identity in QUEUE:
        model, arm, dataset = identity
        job = job_path(*identity)
        out, _ = paths(*identity)
        start = guards.read(job / "dataset.started.json")
        complete, fail = (guards.read(job / name) for name in ("complete.json", "failed.json"))
        active = bool(start and guards.native(start["pid"]) == start["start_ticks"])
        state = "scored" if complete else "failed" if fail else "running" if active else "queued"
        preds = list((out / "predictions").rglob("*.json"))
        if complete and (job / "archive.json").is_file():
            saved = complete["questions"]
        else:
            saved = len(preds)
        rows.append({"model": MODELS[model], "variant": model, "arm": arm, "dataset": dataset,
                     "state": state, "saved": saved, "expected": COUNTS[dataset], "score": complete.get("correct"),
                     "pid": start.get("pid"), "started": start.get("epoch"), "finished": complete.get("epoch"),
                     "last_prediction": max((p.stat().st_mtime for p in preds), default=None),
                     "archived": (job / "archive.json").is_file(), "error": fail.get("error")})
    free = shutil.disk_usage(ROOT).free
    return {"epoch": now, "root": str(ROOT), "free_mib": free // MIB,
            "chexbench_capacity": chexbench_capacity(free),
            "gpu": guards.read(JOBS / "gpu.json"), "gpu_hold": holding,
            "live": bool(initial and guards.native(initial["pid"]) == initial["start_ticks"]),
            "supervisor": initial, "completed": guards.read(JOBS / "complete.json") or None, "cohorts": rows}


if __name__ == "__main__":
    os.umask(0o077)
    if sys.argv[1:] != ["supervise"]:
        raise SystemExit("Expected supervise")
    supervise(credentials())
