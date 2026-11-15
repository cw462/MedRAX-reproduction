"""Run the laboratory's two Flash memory arms, sharing the free RTX 3090."""
from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
from shutil import disk_usage
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "r55_full848_11tools_chexagent8b001"
CODE = LAB / "code/M5"
EXP = CODE / "experiments"
PROVIDERS = {"M12": "evolver", "M9": "generative"}
LABELS = {arm: f"R55-LAB-FLASH-{arm}-11tools-CheXagent8B" for arm in PROVIDERS}
COUNTS = {"slake": 114, "vqarad": 116, "chexbench": 618}
GPU = os.environ.get("R55_LAB_ASSIGNED_GPU", "0")
FLASH = "qwen3.6-flash"
sys.path.append(str(LAB))


def read(path):
    try:
        return json.loads(path.read_bytes())
    except FileNotFoundError:
        return {}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def identity(pid):
    try:
        stat = (Path("/proc") / str(pid) / "stat").read_text().rsplit(") ", 1)[1].split()
    except FileNotFoundError:
        return None
    return int(stat[19]) if stat[0] not in ("X", "Z") else None


def is_alive(receipt):
    pid, start = receipt.get("pid"), receipt.get("start_ticks")
    return bool(pid and start is not None and identity(pid) == start)


def run_dataset(arm, dataset, verify=False):
    sys.path.insert(0, str(EXP))
    import r55_memevolve_driver_official as bridge
    import run_online_skill_r54 as engine
    from cxr_online_primitives_r49 import rows
    from flash_same_image import context
    from online_memory_r49 import ReferenceVault, save_once
    from run_cxr_vqa_toolsets import exclusive_lock
    from r55_verifier_official import DeepSeekVerifier
    from skill_services_r55 import Services, Tools

    bridge.PROVIDERS.update(PROVIDERS)
    manifest = read(ROOT / "manifests" / arm / f"{dataset}.json")
    plan = read(ROOT / "plan.json")
    work = ROOT / ("verification" if verify else "generation") / arm / dataset
    work.mkdir(mode=0o700, parents=True, exist_ok=True)
    inputs, order = manifest["inputs"], manifest["order"]
    ids = [r["question_id"] for r in inputs]
    data = Path(plan["data"][dataset])
    assert rows(data / "inputs.jsonl") == inputs and [r["question_id"] for r in order] == ids
    assert len(ids) == len(set(ids)) == COUNTS[dataset] and set(ids) == set(manifest["reference_files"])
    assert manifest["arm"] == LABELS[arm] and manifest["memory_source"] == bridge.SOURCE
    assert manifest["memory_provider"] == PROVIDERS[arm] and not manifest["skill_enabled"]
    assert manifest["config"]["model"] == manifest["protocol"]["model"] == FLASH
    assert GPU in ("0", "1") and os.environ["CUDA_VISIBLE_DEVICES"] == os.environ["R55_MEMEVOLVE_GPU"] == GPU
    runtime_tools = deepcopy(manifest["runtime"])
    for spec in runtime_tools["tools"].values():
        if spec.get("gpu"):
            spec["gpu"] = GPU
    tools = manifest["runtime"]["arms"]["M"]["tools"]
    assert len(tools) == len(set(tools)) == 11 and set(tools) == set(manifest["runtime"]["tools"])
    save_once(work / "manifest.json", manifest)
    engine.ARM = LABELS[arm]
    engine.context = context

    class FirstAnswer(Exception):
        pass

    class BoundaryService(Services):
        def call(self, row, slot, ordinal, messages):
            assert row == inputs[0] and slot == "R49-AGENT" and ordinal == 1 and messages
            raise FirstAnswer

    class ClosedVault:
        def after_prediction(self, *_):
            raise AssertionError("Validation attempted to access the reference")

    def fixture(_):
        raise AssertionError("Empty memory requested a model completion before the first answer")

    if verify:
        main_key = deepseek_key = "offline-validation"
        service_class = BoundaryService
        vault = ClosedVault()
    else:
        main_key, deepseek_key = [sys.stdin.readline().strip() for _ in range(2)]
        assert main_key and deepseek_key
        service_class = Services
        vault = ReferenceVault(Path(plan["references"][dataset]), manifest["reference_files"])

    class SharedTools(Tools):
        def observe(self, name, spec, args, image, item, folder, saved):
            if saved.is_file() or not spec.get("gpu"):
                return super().observe(name, spec, args, image, item, folder, saved)
            assert spec["gpu"] == GPU
            with (ROOT / f"jobs/gpu{GPU}-tool.lock").open("a") as lease:
                fcntl.flock(lease, fcntl.LOCK_EX)
                return super().observe(name, spec, args, image, item, folder, saved)

    class Memory(bridge.Memory):
        def retrieve(self, row):
            if disk_usage(work).free < 256 * 1024**2:
                raise RuntimeError("Insufficient space to archive the next question")
            return super().retrieve(row)

    service = service_class(manifest["config"], manifest["protocol"], runtime_tools,
                            work / "services", main_key, manifest["embedding_model"],
                            manifest["embedding_base_url"])
    verifier = DeepSeekVerifier(work / "services", deepseek_key)
    service.verifier = verifier
    service.tools = SharedTools(runtime_tools, data, work / "services", service.call, verifier)
    runtime = Path(plan["memory_runtime"])
    bridge.load_runtime(runtime, work)
    with exclusive_lock(work / ".online.lock"):
        memory = Memory(arm, runtime, work / "external_memory", deepseek_key,
                        fixture if verify else None, use_official=not verify)
        try:
            engine.run_stream(inputs, order, data, work, service, vault, tools,
                              evolver=engine.disabled_evolve, external_memory=memory)
        except FirstAnswer:
            assert verify and memory.model.calls == 0 and not (work / "predictions").exists()
            assert not list((work / "services").rglob("started.json"))
            proof = {"arm": arm, "dataset": dataset, "provider": PROVIDERS[arm], "bound_questions": len(ids),
                     "first_answer_boundary": ids[0], "new_external_requests": 0}
            save_once(work / "verified.json", proof)
            return proof
    assert not verify and read(work / "complete.json")["questions"] == len(ids)
    for result in ("retrieval.json", "ingest.json"):
        assert {p.parent.name for p in (work / "external_memory/episodes").glob(f"*/{result}")} == set(ids)
    final = {"arm": LABELS[arm], "provider": PROVIDERS[arm], "questions": len(ids), "model_calls": memory.model.calls}
    save_once(work / "memory.completed.json", final)
    return final


def score(arm, dataset):
    from run_r55_full848_dataset import ARMS
    from score_r55_full848_dataset import score_dataset
    ARMS.update(LABELS)
    work = ROOT / "generation" / arm / dataset
    events = work / "external_memory/model_calls"
    issued = {f.parent for f in events.glob("*/*/*/started.json")}
    closed = {f.parent for f in events.glob("*/*/*/result.json")}
    assert issued == closed and len(closed) == read(work / "memory.completed.json")["model_calls"]
    result = score_dataset(CODE, work)
    assert result["arm"] == LABELS[arm] and result["questions"] == COUNTS[dataset]
    return result


def child(phase, arm, dataset, attempt, keys):
    command = [sys.executable, "-B", "-u", __file__, phase, arm, dataset]
    with (attempt / (phase + ".stdout.log")).open("xb") as out, \
         (attempt / (phase + ".stderr.log")).open("xb") as err:
        proc = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.PIPE, stdout=out, stderr=err)
        save(attempt / (phase + ".started.json"),
             {"pid": proc.pid, "start_ticks": identity(proc.pid), "gpu": GPU, "epoch": time.time()})
        proc.communicate(keys)
    result = {"pid": proc.pid, "exit": proc.returncode, "epoch": time.time()}
    save(attempt / (phase + ".exit.json"), result)
    return result


def controller(arm):
    job = ROOT / "jobs" / arm
    keys = sys.stdin.buffer.read()
    assert len(keys.splitlines()) == 2 and all(keys.splitlines())
    scores = {}
    with (job / "controller.lock").open("a") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            for dataset, count in COUNTS.items():
                done = read(job / dataset / "complete.json")
                if done:
                    scores[dataset] = done["score"]
                    continue
                attempt = job / dataset / f"attempt-{time.time_ns()}"
                attempt.mkdir(mode=0o700, parents=True)
                work = ROOT / "generation" / arm / dataset
                generation_exit = work / "generation.exitcode"
                if not generation_exit.is_file() or generation_exit.read_text().strip() != "0":
                    result = child("dataset", arm, dataset, attempt, keys)
                    if work.is_dir():
                        generation_exit.write_text(str(result["exit"]) + "\n")
                    if result["exit"]:
                        raise RuntimeError(f"{dataset} generation exit {result['exit']}: {attempt.name}")
                result = child("score", arm, dataset, attempt, b"")
                if result["exit"]:
                    raise RuntimeError(f"{dataset} scoring exit {result['exit']}: {attempt.name}")
                result_score = read(work / "analysis/summary.json")
                assert result_score["questions"] == count
                scores[dataset] = result_score
                save(job / dataset / "complete.json", {"score": result_score, "epoch": time.time()})
        except Exception as error:
            save(job / "terminal.json", {"exit": 1, "error": str(error), "epoch": time.time()})
            raise
        save(job / "terminal.json", {"exit": 0, "arm": LABELS[arm], "datasets": scores,
            "correct": sum(r["correct"] for r in scores.values()), "questions": sum(COUNTS.values()),
            "epoch": time.time()})


def gpu_environment(gpu=GPU):
    return dict(os.environ, R55_LAB_ASSIGNED_GPU=gpu, CUDA_VISIBLE_DEVICES=gpu, R55_MEMEVOLVE_GPU=gpu,
                OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", PYTHONDONTWRITEBYTECODE="1",
                LANGCHAIN_TRACING_V2="false", LANGSMITH_TRACING="false")


def launch():
    keys = sys.stdin.buffer.read()
    assert len(keys.splitlines()) == 2 and all(keys.splitlines())
    with (ROOT / "jobs/launch.lock").open("a") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        existing = read(ROOT / "jobs/launch.json")
        if existing:
            return existing
        for arm in PROVIDERS:
            proof = read(ROOT / "verification" / arm / "slake/verified.json")
            assert proof["provider"] == PROVIDERS[arm] and proof["new_external_requests"] == 0
            assert not (ROOT / "jobs" / arm / "controller.started.json").is_file()
        physical = subprocess.check_output(
            ["nvidia-smi", "-i", GPU, "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True).strip()
        if int(physical) >= 1024:
            raise RuntimeError("The selected laboratory GPU is no longer free")
        launched = {}
        for arm in PROVIDERS:
            job = ROOT / "jobs" / arm
            job.mkdir(parents=True, exist_ok=True)
            with (job / "controller.log").open("ab") as log:
                proc = subprocess.Popen([sys.executable, "-B", "-u", __file__, "controller", arm],
                    cwd=ROOT, env=gpu_environment(), stdin=subprocess.PIPE, stdout=log,
                    stderr=subprocess.STDOUT, start_new_session=True)
                receipt = {"pid": proc.pid, "start_ticks": identity(proc.pid), "gpu": GPU, "epoch": time.time()}
                save(job / "controller.started.json", receipt)
                proc.stdin.write(keys)
                proc.stdin.close()
                launched[arm] = receipt
        save(ROOT / "jobs/launch.json", launched)
        return launched


def status():
    out = {"root": str(ROOT), "epoch": time.time(), "arms": {}}
    for arm in PROVIDERS:
        job = ROOT / "jobs" / arm
        started = read(job / "controller.started.json")
        terminal = read(job / "terminal.json")
        datasets = {}
        for dataset in COUNTS:
            work = ROOT / "generation" / arm / dataset
            preds = sorted(p.stat().st_mtime for p in (work / "predictions" / LABELS[arm]).glob("*.json"))
            model_files = list((work / "services/calls/R49-AGENT").glob("*/*/result.json"))
            memory_files = sorted((work / "external_memory/model_calls").glob("*/*/*/result.json"),
                                  key=lambda p: p.stat().st_mtime, reverse=True)[:10]
            writer = next((r.get("model_returned") for p in memory_files if (r := read(p)).get("response_received")), None)
            main = next((r.get("model_returned") for p in model_files if (r := read(p)).get("response_received")), None)
            finished = read(job / dataset / "complete.json")
            attempts = sorted((job / dataset).glob("attempt-*"))
            data = {"saved": len(preds), "last": preds[-1] if preds else None,
                    "recent_5m": sum(p >= out["epoch"] - 300 for p in preds),
                    "memory_commits": len(list((work / "external_memory/episodes").glob("*/ingest.json"))),
                    "score": finished.get("score", {}).get("correct"),
                    "main": main, "memory": writer}
            if attempts:
                data["runner"] = read(attempts[-1] / "dataset.started.json").get("pid")
                data["runner_exit"] = read(attempts[-1] / "dataset.exit.json").get("exit")
            datasets[dataset] = data
        out["arms"][arm] = {"controller": started.get("pid"), "gpu": started.get("gpu"),
                            "launch_epoch": started.get("epoch"), "alive": is_alive(started),
                            "exit": terminal.get("exit"), "error": terminal.get("error"),
                            "total": terminal.get("correct"), "datasets": datasets}
    return out


if __name__ == "__main__":
    os.umask(0o077)
    phase, *pos = sys.argv[1:]
    if phase == "controller":
        controller(*pos)
    else:
        phases = {"dataset": run_dataset, "verify": lambda arm, ds: run_dataset(arm, ds, True),
                  "score": score, "launch": launch, "status": status}
        print(json.dumps(phases[phase](*pos), ensure_ascii=False))

