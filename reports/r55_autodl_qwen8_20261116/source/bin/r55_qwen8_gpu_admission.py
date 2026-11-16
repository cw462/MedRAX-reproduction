"""Share the resident GPU across the four Qwen runs and contain tool OOMs."""

from contextlib import contextmanager
import fcntl
import re
import time

import r55_deepseek_rerun_runtime as guards


SLOTS = (guards.GPU_LOCK, guards.GPU_LOCK.with_name("gpu-worker.1.lock"))
PARALLEL_FREE_MIB = 12 * 1024
FAMILIES = {
    "chest_xray_expert": "chexagent", "maira2_grounded_report": "maira", "xray_phrase_grounding": "maira",
    "llava_med_qa": "llava-med", "llava_rad": "llava-rad", "medgemma": "medgemma", "medvlm_r1": "medvlm-r1",
}
OOM = re.compile(r"cuda[ _]*(?:error[ _:]*)?out[ _]+of[ _]+memory|outofmemoryerror|"
                 r"cublas_status_alloc_failed|cudnn_status_alloc_failed", re.I)


def admission_lock(root):
    return root / "jobs/gpu-admission.lock"


def lock_if_free(path):
    stream = path.open("a")
    try:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        stream.close()
        return None
    return stream


@contextmanager
def gpu_slot(root, arm):
    chosen = None
    while chosen is None:
        guards.wait_for_arm(root, arm)
        with guards.lease(admission_lock(root)):
            if not guards.allowed(root, arm):
                continue
            free = [lock for path in SLOTS if (lock := lock_if_free(path)) is not None]
            if len(free) == 2:
                chosen = free.pop(0)
            elif free:
                plan = guards.read(root / "plan.json")
                can_overlap = (plan.get("gpu_slots", 1) == 2 and not (root / "jobs/gpu-single-slot.json").is_file())
                if can_overlap and guards.gpu_sample().get("free_mib", 0) >= PARALLEL_FREE_MIB:
                    chosen = free.pop()
            for lock in free:
                lock.close()
        if chosen is None:
            time.sleep(0.3)
    with chosen:
        yield


def oom_result(result, folder):
    if OOM.search(f"{result.get('error_type', '')} {result.get('error', '')}"):
        return True
    if result.get("status") == "completed":
        return False
    for path in (folder / "backend.stderr.log", folder / "artifacts/backend.stderr.log"):
        if path.is_file():
            with path.open("rb") as stream:
                stream.seek(max(0, path.stat().st_size - 16384))
                if OOM.search(stream.read().decode(errors="replace")):
                    return True
    return False


def outcome(observe, folder):
    try:
        result, hit = observe()
    except Exception as error:
        if not OOM.search(f"{type(error).__name__} {error}"):
            raise
        problem = {"status": "failed", "error_type": type(error).__name__, "error": str(error)[:400]}
        guards.save(folder / "gpu-exception.json", problem)
        return problem, False, "cuda_oom"
    if oom_result(result, folder):
        return result, hit, "cuda_oom"
    if not (folder / "backend_route.json").is_file():
        return result, hit, "resident_tool_unavailable"
    return result, hit, None


def archive_failure(root, arm, name, folder, kind, attempt):
    jobs = root / "jobs"
    hold = jobs / "gpu-hold.json"
    record = {"id": str(time.time_ns()), "epoch": time.time(), "kind": kind, "arm": arm, "tool": name,
              "attempt": attempt, "tool_cache": str(folder.relative_to(root)), "gpu": guards.read(jobs / "gpu.json")}
    evidence = jobs / "gpu-incidents" / record["id"]
    retry = kind == "cuda_oom" and attempt == 1
    with guards.lease(admission_lock(root)):
        current = guards.read(hold)
        if kind == "cuda_oom":
            guards.save(jobs / "gpu-single-slot.json", record)
        replaceable = current.get("mode") in (None, "cooldown") or current.get("kind") == "gpu_recovery_pending"
        if replaceable:
            guards.save(hold, dict(record, mode="blocked", kind="gpu_recovery_pending" if retry else kind))
        guards.save(evidence / "incident.json", dict(record, action="retry_with_one_tool" if retry else "hold"))
        if retry:
            guards.save(evidence / "awaiting_retry.json", {"epoch": time.time()})
        folder.rename(evidence / "original-tool-attempt")
    return evidence


def recover(root, arm, name, folder, observe, evidence):
    jobs = root / "jobs"
    hold = jobs / "gpu-hold.json"
    with guards.lease(jobs / "gpu-recovery.lock"), guards.lease(SLOTS[0]), guards.lease(SLOTS[1]):
        if guards.read(hold).get("kind") != "gpu_recovery_pending":
            raise RuntimeError(f"GPU recovery is held, incident {evidence.name}")
        for _ in range(8):
            if guards.gpu_sample().get("healthy"):
                time.sleep(4)
                if guards.gpu_sample().get("healthy"):
                    break
            time.sleep(4)
        else:
            raise RuntimeError(f"GPU memory remained below the retry limit, incident {evidence.name}")
        if guards.read(hold).get("kind") != "gpu_recovery_pending":
            raise RuntimeError(f"GPU recovery is held, incident {evidence.name}")
        result, hit, kind = outcome(observe, folder)
        if kind:
            next_incident = archive_failure(root, arm, name, folder, kind, 2)
            raise RuntimeError(f"GPU safety hold after {kind}, incident {next_incident.name}")
        with guards.lease(admission_lock(root)):
            guards.save(evidence / "recovered.json", {"epoch": time.time(), "new_status": result["status"]})
            (evidence / "awaiting_retry.json").unlink(missing_ok=True)
            if (guards.read(hold).get("kind") == "gpu_recovery_pending"
                    and not any((jobs / "gpu-incidents").glob("*/awaiting_retry.json"))):
                guards.save(hold, {"mode": "cooldown", "id": evidence.name, "after": time.time() + 12})
        return result, hit


def guarded_tool(root, arm, name, folder, saved, observe):
    key_lock = folder.parent / ".leases" / (folder.name + ".lock")
    family = root / "jobs/gpu-families" / (FAMILIES[name] + ".lock")
    with guards.lease(key_lock), guards.lease(family):
        if saved.is_file() and not oom_result(guards.read(saved), folder):
            return observe()
        with gpu_slot(root, arm):
            result, hit, kind = outcome(observe, folder)
            if not kind:
                return result, hit
            evidence = archive_failure(root, arm, name, folder, kind, 1)
        if kind != "cuda_oom":
            raise RuntimeError(f"GPU safety hold after {kind}, incident {evidence.name}")
        return recover(root, arm, name, folder, observe, evidence)
