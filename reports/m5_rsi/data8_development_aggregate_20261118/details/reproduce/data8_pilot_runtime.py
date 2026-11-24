"""Run a separate Qwen3.7-Plus M5 eight-tool 300-question pilot on Linux."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
HOME = ROOT / "artifacts"
CONTROL = HOME / "control/data8_pilot"
NATIVE = ROOT / "experiments/m5_rsi/native.py"
TEMPLATE = HOME / "native_templates/plus.json"
BINDING = HOME / "native_bindings/plus.json"
MODEL = "qwen3.7-plus"
TOOLS = ("chest_xray_expert", "llava_med_qa", "medgemma", "llava_rad", "medvlm_r1",
         "maira2_grounded_report", "xray_phrase_grounding", "roi_crop")
EXTRA = ("medret", "reflect", "verify")
COUNTS = {"chexbench": 219, "slake": 40, "vqarad": 41}
MEMBERS = {"train_new": 300, **{f"eval_848/{name}": size for name, size in COUNTS.items()}}


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def replace(path, content):
    pending = path.with_name(path.name + ".pending")
    pending.write_bytes(content)
    pending.replace(path)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    replace(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def scoped_paths():
    old = Path("/root/autodl-tmp/medrax_m5_data_rsi_v2_20261117_plus").resolve()
    if ROOT == old or old in ROOT.parents:
        raise ValueError("Pilot must use an independent project root")
    for path in (HOME, CONTROL, NATIVE, TEMPLATE, BINDING, HOME / "manifests", HOME / "pilot_data8"):
        if path.resolve() != path or ROOT not in path.parents:
            raise ValueError(f"Pilot write path is redirected: {path}")


@contextmanager
def lock():
    CONTROL.mkdir(parents=True, exist_ok=True)
    with (CONTROL / "controller.lock").open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def input_identity():
    train_groups = train_pixels = train_files = set()
    records = {}
    for member, count in MEMBERS.items():
        folder = HOME / "manifests" / member
        inputs, labels = folder / "inputs.json", folder / "labels.json"
        payload, references = read(inputs), read(labels)
        rows, order = payload["inputs"], payload["order"]
        ids = [row["question_id"] for row in rows]
        order_ids = [item["question_id"] if isinstance(item, dict) else item for item in order]
        if (len(ids) != count or len(set(ids)) != count or ids != order_ids
                or len(references) != count or set(ids) != {row["question_id"] for row in references}):
            raise ValueError(f"Invalid frozen denominator, order or references for {member}")
        groups = {row["group_id"] for row in rows}
        hashes = [item for row in rows for item in row["image_hashes"]]
        pixels = {item["pixel_sha256"] for item in hashes}
        files = {item["file_sha256"] for item in hashes}
        if member == "train_new":
            train_groups, train_pixels, train_files = groups, pixels, files
        elif train_groups & groups or train_pixels & pixels or train_files & files:
            raise ValueError(f"Training overlaps pilot evaluation for {member}")
        records[member] = {"count": count, "inputs_sha256": sha(inputs), "labels_sha256": sha(labels)}
    return records


def protocol(binding, inputs):
    from experiments.m5_rsi.policy import P0
    from experiments.m5_rsi.search import Candidate

    sources = {
        "native_engine": Path(binding["experiment_sources"]) / "run_online_skill_r54.py",
        "native_broker": Path(binding["experiment_sources"]) / "online_memory_r49.py",
        "native_tools": Path(binding["experiment_sources"]) / "skill_services_r55.py",
        "native_scorer": Path(binding["experiment_sources"]) / "cxr_author_alignment.py",
        "memory_driver": Path(binding["memory_driver_sources"]) / "r55_memevolve_driver_official.py",
        "memory_provider": Path(binding["memory_runtime"]) / "EvolveLab/providers/cerebra_fusion_memory_provider.py",
        "pilot": Path(__file__).resolve(),
        "config": ROOT / "configs/m5_rsi.yaml",
        "binding": BINDING,
        "template": TEMPLATE,
    }
    sources.update({f"rsi/{path.name}": path for path in sorted(NATIVE.parent.glob("*.py"))})
    return {"model": MODEL, "arm": "DATA", "tools": list(TOOLS), "candidate": Candidate(P0).wire(),
            "sources": {key: sha(path) for key, path in sources.items()}, "inputs": inputs}


def binding_for_root():
    binding = read(BINDING)
    from experiments.m5_rsi.workflow import config_file

    config = config_file(ROOT / "configs/m5_rsi.yaml")
    if (config["models"] != {"plus": MODEL} or config["project_root"] != str(ROOT)
            or config["artifacts"] != str(HOME) or config["native_bindings"] != str(BINDING.parent)):
        raise ValueError("Pilot config must isolate only Qwen3.7-Plus")
    if (binding["model"], binding["assets"], binding["manifests"], binding["template"]) != (
            MODEL, str(HOME), str(HOME / "manifests"), str(TEMPLATE)):
        raise ValueError("Pilot native binding must address isolated assets, manifests and template")
    return binding, config


def prepare():
    binding, _ = binding_for_root()
    inputs = input_identity()
    saved = CONTROL / "protocol.json"
    if saved.is_file():
        if read(saved) != protocol(binding, inputs):
            raise ValueError("Prepared pilot protocol changed")
        return
    template = read(TEMPLATE)
    runtime = template["runtime"]
    roster = tuple(runtime["arms"]["M"]["tools"])
    if (roster not in (TOOLS + EXTRA, TOOLS) or set(runtime["tools"]) != set(roster)
            or template["protocol"]["model"] != MODEL or template["skill_enabled"]
            or template["memory_provider"] != "cerebra_fusion_memory"):
        raise ValueError("Pilot template does not contain the expected M5 baseline")
    if roster != TOOLS and sha(TEMPLATE) != binding["template_sha256"]:
        raise ValueError("The source M5 template digest changed")
    old = ', "roi_crop", "medret", "reflect", "verify",'
    new = ', "roi_crop",'
    source = NATIVE.read_text(encoding="utf-8")
    if source.count(old) == 1:
        updated = source.replace(old, new, 1)
        compile(updated, str(NATIVE), "exec")
        replace(NATIVE, updated.encode())
    elif source.count(new) != 1:
        raise ValueError("Cannot find the exact isolated native tool roster")
    for arm in runtime["arms"].values():
        arm["tools"] = [name for name in arm["tools"] if name in TOOLS]
    runtime["tools"] = {name: runtime["tools"][name] for name in TOOLS}
    write(TEMPLATE, template)
    binding["template_sha256"] = sha(TEMPLATE)
    write(BINDING, binding)
    write(saved, protocol(binding, inputs))


def execute(resume):
    from experiments.m5_rsi.native import NATIVE_TOOLS, NativeRunner
    from experiments.m5_rsi.run_plus import bind_runtime, credentials, launcher_environment
    from experiments.m5_rsi.search import Candidate

    binding, config = binding_for_root()
    claim = read(CONTROL / "protocol.json")
    if claim != protocol(binding, input_identity()) or NATIVE_TOOLS != TOOLS:
        raise ValueError("The prepared eight-tool protocol changed")
    state_path = CONTROL / "controller.json"
    prior = read(state_path) if state_path.is_file() else None
    if prior and prior["status"] == "complete":
        return read(HOME / "pilot_data8/results.json")
    if prior and not resume:
        raise ValueError("Inspect the previous attempt and pass --resume to continue")
    state = {"status": "running", "pid": os.getpid(), "started_at": now(), "phase": "preflight"}
    write(state_path, state)
    try:
        env = launcher_environment()
        env.update(credentials(env))
        bind_runtime(config, env)
        os.environ.update(env)
        runner = NativeRunner(binding, config.get("native_python") or sys.executable, ROOT)
        candidate = Candidate(**claim["candidate"])
        root = HOME / "pilot_data8"
        snapshot = root / "train/warm_snapshot"
        scores = {}
        for member, expected in MEMBERS.items():
            training = member == "train_new"
            stage = "train" if training else member.split("/")[1]
            out = root / ("train" if training else f"evaluation/{stage}")
            state.update(phase=stage, updated_at=now())
            write(state_path, state)
            values = runner.invoke(candidate, member, out, None if training else snapshot,
                                   "warmup" if training else "evaluate")["scores"]
            if len(values) != expected or any(type(value) not in (int, float) or value not in (0, 1)
                                               for value in values):
                raise ValueError(f"Incomplete native receipt for {stage}")
            if training and sha(snapshot / "graph.json") != read(snapshot / "snapshot.json")["sha256"]:
                raise ValueError("Native training did not seal a matching memory graph")
            scores[stage] = {"correct": int(sum(values)), "n": expected}
            write(CONTROL / "completed" / f"{stage}.json", {"phase": stage, "ended_at": now(), **scores[stage]})
        scores.pop("train")
        correct = sum(row["correct"] for row in scores.values())
        result = {"model": MODEL, "arm": "DATA", "tools": list(TOOLS), "training": 300,
                  "evaluation": scores, "correct": correct, "n": 300, "accuracy": correct / 300,
                  "protocol_sha256": sha(CONTROL / "protocol.json"), "finished_at": now()}
        write(root / "results.json", result)
        write(state_path, {**state, "status": "complete", "phase": "report", "updated_at": now()})
        return result
    except (Exception, KeyboardInterrupt) as error:
        extra = {"returncode": error.returncode} if isinstance(error, subprocess.CalledProcessError) else {}
        write(state_path, {**state, **extra, "status": "failed", "error": type(error).__name__, "updated_at": now()})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "status"))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    scoped_paths()
    if args.action == "status":
        live = False
        try:
            with lock():
                pass
        except BlockingIOError:
            live = True
        path = CONTROL / "controller.json"
        state = read(path) if path.is_file() else {"status": "not_started"}
        if state["status"] == "running" and not live:
            state["status"] = "interrupted"
        value = {**state, "lock_active": live, "completed": sorted(p.stem for p in (CONTROL / "completed").glob("*.json"))}
    else:
        with lock():
            if args.action == "prepare":
                prepare()
                value = {"status": "prepared", "tools": list(TOOLS), "evaluation_counts": COUNTS}
            else:
                value = execute(args.resume)
    print(json.dumps(value, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
