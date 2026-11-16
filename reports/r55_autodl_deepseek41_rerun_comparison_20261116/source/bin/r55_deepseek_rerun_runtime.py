"""Admission, recovery and cohort supervision for the DeepSeek R55 rerun."""

import fcntl
import json
import os
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile


ROOT = Path(__file__).resolve().parents[1]
JOBS = ROOT / "jobs"
PLAN = ROOT / "plan.json"
PYTHON = ROOT / "env/modern/bin/python"
RESIDENT_ROOT = Path("/root/autodl-tmp/medrax_r55_top4_full848_chexagent8_20261114")
GPU_LOCK = RESIDENT_ROOT / "jobs/gpu-worker.0.lock"
MIN_FREE_MIB = 6144
SAMPLE_SECONDS = 4
COOLDOWN_SECONDS = 30
MEMORY_ARMS = {"M2", "M5"}
OOM = re.compile(r"cuda (?:error: )?out of memory|outofmemoryerror|cublas_status_alloc_failed", re.I)
TRANSIENT = {"Request timed out.", "Connection error."}


def read(path):
    try:
        return json.loads(path.read_bytes())
    except FileNotFoundError:
        return {}


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as temp:
        json.dump(data, temp, ensure_ascii=False, indent=2)
        temp.write("\n")
    Path(temp.name).replace(path)


@contextmanager
def lease(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def native(pid):
    try:
        stats = (Path("/proc") / str(pid) / "stat").read_text().rsplit(") ", 1)[1].split()
        return int(stats[19]) if stats[0] not in ("X", "Z") else None
    except FileNotFoundError:
        return None


def gpu_sample():
    sampled = time.time()
    try:
        proc = subprocess.run(
            ["nvidia-smi", "-i", "0", "--query-gpu=memory.total,memory.used,memory.free",
             "--format=csv,noheader,nounits"],
            check=True, capture_output=True, text=True, timeout=5,
        )
        total, used, free = map(int, proc.stdout.strip().split(","))
    except (OSError, subprocess.SubprocessError, ValueError):
        return {"epoch": sampled, "error": "gpu_telemetry_unavailable", "healthy": False}
    return {"epoch": sampled, "total_mib": total, "used_mib": used, "free_mib": free,
            "healthy": free >= MIN_FREE_MIB}


def allowed(root, arm, now=None, recovery_key=None):
    now = time.time() if now is None else now
    telemetry = read(root / "jobs/gpu.json")
    hold = read(root / "jobs/gpu-hold.json")
    if not telemetry.get("healthy") or now - telemetry.get("epoch", 0) > 15:
        return False
    mode = hold.get("mode")
    if mode == "blocked":
        return False
    if mode == "recovering":
        return (arm == hold["arm"] and recovery_key == hold["tool_cache"]
                and telemetry["epoch"] >= hold["after"]
                and telemetry.get("healthy_samples", 0) >= 2)
    return mode != "cooldown" or now >= hold["after"]


def wait_for_arm(root, arm, recovery_key=None):
    while not allowed(root, arm, recovery_key=recovery_key):
        time.sleep(1)


def tool_incident(root, arm, name, folder, kind, attempt):
    now = time.time()
    record = {"id": str(time.time_ns()), "epoch": now, "kind": kind, "arm": arm, "tool": name,
              "attempt": attempt, "tool_cache": str(folder.relative_to(root)),
              "gpu": read(root / "jobs/gpu.json")}
    evidence = root / "jobs/gpu-incidents" / record["id"]
    mode = "recovering" if kind == "cuda_oom" and attempt == 1 else "blocked"
    hold = dict(record, mode=mode, after=now + 12)
    save(root / "jobs/gpu-hold.json", hold)
    save(evidence / "incident.json", dict(record, action=mode))
    folder.rename(evidence / "original-tool-attempt")
    return evidence


def oom_result(result):
    return bool(OOM.search(f"{result.get('error_type', '')} {result.get('error', '')}"))


def guarded_tool(root, arm, name, folder, saved, observe):
    # Keep the lock outside the cache entry so a failed attempt can be archived
    # without exposing its result to a second case using that cache key.
    key_lock = folder.parent / ".leases" / (folder.name + ".lock")
    with lease(key_lock):
        if saved.is_file():
            return observe()
        incident = None
        for attempt in (1, 2):
            recovery_key = str(folder.relative_to(root)) if attempt == 2 else None
            while True:
                wait_for_arm(root, arm, recovery_key)
                with lease(GPU_LOCK):
                    if not allowed(root, arm, recovery_key=recovery_key):
                        continue
                    result, cache_hit = observe()
                    routed = (folder / "backend_route.json").is_file()
                    if not oom_result(result) and routed:
                        if incident:
                            save(incident / "recovered.json", {"epoch": time.time(), "new_status": result["status"]})
                            save(root / "jobs/gpu-hold.json", {
                                "mode": "cooldown", "id": incident.name, "after": time.time() + COOLDOWN_SECONDS,
                            })
                        return result, cache_hit
                    kind = "cuda_oom" if oom_result(result) else "resident_tool_unavailable"
                    incident = tool_incident(root, arm, name, folder, kind, attempt)
                    if kind != "cuda_oom" or attempt == 2:
                        raise RuntimeError(f"GPU safety hold after {kind}, incident {incident.name}")
                    break


def call_main(root, service, send, row, role, ordinal, messages):
    if role != "R49-AGENT":
        return send(row, role, ordinal, messages)
    folder = service.out / "calls" / role / row["question_id"] / str(ordinal)
    for attempt in range(3):
        try:
            return send(row, role, ordinal, messages)
        except Exception:
            result = read(folder / "result.json")
            if (attempt == 2 or result.get("error") not in TRANSIENT
                    or result.get("response_received") is not False
                    or (folder / "response.json").exists() or not (folder / "request.json").is_file()):
                raise
            archive = root / "jobs/main-transport-retries" / str(time.time_ns())
            save(archive / "retry.json", {"request": str(folder.relative_to(root)),
                                          "original_error": result["error"], "attempt": attempt + 1})
            original_request = (folder / "request.json").read_bytes()
            folder.rename(archive / "original-request")
            folder.mkdir()
            (folder / "request.json").write_bytes(original_request)
            time.sleep(4 * (attempt + 1))


def output_path(arm, dataset):
    if arm in MEMORY_ARMS:
        return ROOT / "generation" / arm / dataset
    return ROOT / "flash_react" / arm.lower() / dataset


def summary_path(arm, dataset):
    return output_path(arm, dataset) / ("analysis/summary.json" if arm in MEMORY_ARMS else "summary.json")


def job_path(arm, dataset):
    return JOBS / "cohorts" / arm / dataset


def command_for(arm, dataset, phase="dataset"):
    if arm in MEMORY_ARMS:
        return [str(ROOT / "bin/run_top4_flash_memory_official.py"), phase, str(ROOT), arm,
                "--dataset", dataset]
    args = [str(ROOT / "flash_react/code_official/run_qwen_baselines.py"), str(ROOT),
            str(ROOT / "flash_react"), arm.lower(), "--dataset", dataset, "--r55-11-tools", "--workers", "3"]
    if arm == "Reflexion":
        args.append("--wait-for-react")
    return args


def job_env(plan, arm):
    return dict(os.environ, CUDA_VISIBLE_DEVICES="0", R55_MEMEVOLVE_GPU="0",
                R55_RERUN_ARM=arm, R55_CHEXAGENT8_SNAPSHOT=plan["chexagent8_snapshot"],
                R55_REQUIRE_CHEXAGENT8="1", R55_BASELINE_SHARED_GPU_ROOT=str(ROOT),
                OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", PYTHONDONTWRITEBYTECODE="1",
                LANGCHAIN_TRACING_V2="false", LANGSMITH_TRACING="false")


def run_child(arm, dataset, phase, key, plan):
    job = job_path(arm, dataset)
    job.mkdir(parents=True, exist_ok=True)
    epoch = time.time()
    with (job / f"{phase}.stdout.log").open("ab") as out, (job / f"{phase}.stderr.log").open("ab") as err:
        proc = subprocess.Popen([str(PYTHON), "-B", "-u", *command_for(arm, dataset, phase)],
                                cwd=ROOT, env=job_env(plan, arm),
                                stdin=subprocess.PIPE if key else subprocess.DEVNULL, stdout=out, stderr=err)
        save(job / f"{phase}.started.json", {"pid": proc.pid, "start_ticks": native(proc.pid), "epoch": epoch})
        if key:
            with proc.stdin:
                proc.stdin.write((key + b"\n") * 2)
    return proc


def safe_error(job, phase):
    lines = (job / f"{phase}.stderr.log").read_text(encoding="utf-8", errors="replace").splitlines()
    safe = [line[:200] for line in lines if line.startswith(("AssertionError", "RuntimeError", "ValueError",
                                                             "openai.", "FileNotFoundError", "OSError"))
            and not any(secret in line.lower() for secret in ("sk-", "bearer", "authorization", "base64"))]
    return safe[-1] if safe else f"{phase} failed"


def finish_cohort(arm, dataset, count):
    summary = read(summary_path(arm, dataset))
    expected_arm = f"R55-{arm}" if arm in MEMORY_ARMS else arm.lower()
    assert (summary["arm"], summary["dataset"], summary["questions"]) == (expected_arm, dataset, count)
    if arm in MEMORY_ARMS:
        commits = list((output_path(arm, dataset) / "external_memory/episodes").glob("*/ingest.json"))
        assert len(commits) == count
    save(job_path(arm, dataset) / "complete.json",
         {"epoch": time.time(), "correct": summary["correct"], "questions": count})


def supervise(key):
    assert key and len(key.splitlines()) == 1
    plan = read(PLAN)
    queue = [(j["arm"], j["dataset"], j["questions"], {tuple(dep) for dep in j["depends_on"]})
             for j in plan["queue"]]
    active = {}
    healthy_samples = 0
    with lease(JOBS / "supervisor.lock"):
        while True:
            gpu = gpu_sample()
            healthy_samples = healthy_samples + 1 if gpu["healthy"] else 0
            save(JOBS / "gpu.json", dict(gpu, healthy_samples=healthy_samples))
            closed = set()
            failed = set()
            for arm, dataset, n, needs in queue:
                job = job_path(arm, dataset)
                ident = (arm, dataset)
                if (job / "complete.json").is_file():
                    closed.add(ident)
                    continue
                if (job / "failed.json").is_file():
                    failed.add(ident)
                    continue
                if ident not in active:
                    continue
                phase, child = active[ident]
                code = child.poll()
                if code is None:
                    continue
                del active[ident]
                save(job / f"{phase}.exit.json", {"epoch": time.time(), "exit": code})
                if code:
                    save(job / "failed.json", {"epoch": time.time(), "phase": phase, "exit": code,
                                               "error": safe_error(job, phase)})
                    failed.add(ident)
                elif arm in MEMORY_ARMS and phase == "dataset":
                    active[ident] = ("score", run_child(arm, dataset, "score", b"", plan))
                else:
                    finish_cohort(arm, dataset, n)
                    closed.add(ident)
            if len(closed) == len(queue):
                save(JOBS / "complete.json", {"epoch": time.time(), "cohorts": len(closed)})
                return
            for arm, dataset, n, needs in queue:
                ident = arm, dataset
                if len(active) >= plan["max_active_cohorts"]:
                    break
                if ident in closed or ident in failed or ident in active or not needs <= closed:
                    continue
                if not allowed(ROOT, arm) or read(JOBS / "gpu-hold.json").get("mode") == "recovering":
                    continue
                active[ident] = ("dataset", run_child(arm, dataset, "dataset", key, plan))
            unavailable = set(failed)
            for arm, dataset, _, needs in queue:
                if needs & unavailable:
                    unavailable.add((arm, dataset))
            if not active and len(closed | unavailable) == len(queue):
                save(JOBS / "needs-attention.json",
                     {"epoch": time.time(), "failed_or_dependent": sorted(unavailable)})
                return
            time.sleep(SAMPLE_SECONDS)


def status():
    plan = read(PLAN)
    initial = read(JOBS / "supervisor.started.json")
    hold = read(JOBS / "gpu-hold.json")
    now = time.time()
    incident = []
    for f in sorted((JOBS / "gpu-incidents").glob("*/incident.json")):
        incident.append(dict(read(f), recovered=read(f.with_name("recovered.json")) or None))
    rows = []
    for spec in plan.get("queue", []):
        arm, dataset = spec["arm"], spec["dataset"]
        job = job_path(arm, dataset)
        base = output_path(arm, dataset)
        times = [f.stat().st_mtime for f in (base / "predictions").rglob("*.json")]
        start = read(job / "dataset.started.json")
        complete, failed = read(job / "complete.json"), read(job / "failed.json")
        if complete:
            state = "scored"
        elif failed:
            state = "failed"
        elif start:
            state = "running" if allowed(ROOT, arm, now) else "waiting_for_gpu"
        elif any((job_path(*dep) / "failed.json").exists() for dep in spec["depends_on"]):
            state = "blocked_dependency"
        else:
            state = "queued"
        rows.append(dict(spec, state=state, saved=len(times), score=complete.get("correct"),
                         finished=complete.get("epoch"), started=start.get("epoch"),
                         pid=start.get("pid"), error=failed.get("error"),
                         recent_5m=sum(t >= now - 300 for t in times),
                         recent_10m=sum(t >= now - 600 for t in times)))
    return {"epoch": now, "root": str(ROOT), "gpu": read(JOBS / "gpu.json"), "gpu_hold": hold,
            "supervisor_live": bool(initial and native(initial["pid"]) == initial["start_ticks"]),
            "completed": read(JOBS / "complete.json") or None, "cohorts": rows, "incidents": incident}


if __name__ == "__main__":
    os.umask(0o077)
    if sys.argv[1] == "supervise":
        supervise(sys.stdin.buffer.read().strip())
    elif sys.argv[1] == "status":
        print(json.dumps(status()))
    else:
        raise SystemExit("Expected supervise or status")
