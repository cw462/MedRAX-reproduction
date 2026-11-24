"""Run one Qwen3.7-Plus eight-tool development arm on the frozen 300/100 split."""

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

import data8_pilot_runtime as pilot


ARMS = ("DATA", "GEPA", "META", "GEPA_META")
VALIDATION_COUNT = 100
VALIDATION_SHA = {
    "inputs.json": "6b5e428dc04ce7fa0ba31e309f620d92373ba6482cf182fafa856e2d38a95563",
    "labels.json": "4fd9e8a708f328e78a5c63331985819402093991f2fb3688315ad691e4d0dff0",
}


@contextmanager
def lock(control):
    control.mkdir(parents=True, exist_ok=True)
    with (control / "controller.lock").open("a+b") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def status(control):
    live = False
    try:
        with lock(control):
            pass
    except BlockingIOError:
        live = True
    path = control / "controller.json"
    state = pilot.read(path) if path.is_file() else {"status": "not_started"}
    if state["status"] == "running" and not live:
        state["status"] = "interrupted"
    return {**state, "lock_active": live, "completed": sorted(p.stem for p in (control / "completed").glob("*.json"))}


def validate_inputs(binding):
    base_path = pilot.CONTROL / "protocol.json"
    base = pilot.read(base_path)
    if base != pilot.protocol(binding, base["inputs"]):
        raise ValueError("The frozen DATA pilot protocol changed")
    manifests = pilot.HOME / "manifests"
    train = base["inputs"]["train_new"]
    if (train["count"] != 300 or any(pilot.sha(manifests / "train_new" / filename) != train[field]
                                     for filename, field in (("inputs.json", "inputs_sha256"),
                                                             ("labels.json", "labels_sha256")))):
        raise ValueError("Optimizer training data must be the frozen 300-question split")
    if any(pilot.sha(manifests / "val_new" / filename) != expected for filename, expected in VALIDATION_SHA.items()):
        raise ValueError("Optimizer validation data must be the original frozen 100-question split")
    return pilot.sha(base_path)


def protocol(arm, stages, base_hash):
    upstream = pilot.HOME / "upstream"
    dependencies = {}
    if stages:
        dependencies = {"rsi_source_sha256": pilot.sha(upstream / "rsi_source.json"),
                        "gepa_wheel_sha256": pilot.sha(upstream / "gepa-0.1.4-py3-none-any.whl")}
    return {"arm": arm, "dataset_protocol": base_hash, "model": pilot.MODEL, "tools": list(pilot.TOOLS),
            "script_sha256": pilot.sha(Path(__file__).resolve()),
            "optimizer_slots": [[method, limit] for method, limit in stages],
            "validation": {"count": VALIDATION_COUNT, "sha256": VALIDATION_SHA},
            "dependencies": dependencies}


def execute(arm, control, output, resume):
    from experiments.m5_rsi.native import NATIVE_TOOLS, NativeRunner
    from experiments.m5_rsi.run_plus import bind_runtime, credentials, launcher_environment
    from experiments.m5_rsi.search import ARMS as stages_by_arm, Candidate, Replay, bind_dependencies, key_for, search_arm
    from experiments.m5_rsi.workflow import make_proposer

    state_path = control / "controller.json"
    result_path = output / "results.json"
    prior = pilot.read(state_path) if state_path.is_file() else None
    binding, config = pilot.binding_for_root()
    base_hash = validate_inputs(binding)
    stages = stages_by_arm[arm]
    claim = protocol(arm, stages, base_hash)
    frozen_protocol = control / "protocol.json"
    if NATIVE_TOOLS != pilot.TOOLS or (frozen_protocol.is_file() and pilot.read(frozen_protocol) != claim):
        raise ValueError("Optimizer source, eight-tool binding or frozen protocol changed")
    if prior and prior["status"] == "complete":
        return pilot.read(result_path)
    if prior and not resume:
        raise ValueError("Inspect the prior attempt and pass --resume to continue")
    if not frozen_protocol.is_file():
        pilot.write(frozen_protocol, claim)
    protocol_hash = pilot.sha(frozen_protocol)

    state = {"arm": arm, "status": "running", "pid": os.getpid(), "started_at": pilot.now()}

    def stage(phase, **fields):
        state.update(phase=phase, updated_at=pilot.now(), **fields)
        pilot.write(state_path, state)

    def complete(phase, **fields):
        receipt = control / "completed" / f"{phase}.json"
        if receipt.is_file():
            check = pilot.read(receipt)
            if any(check[key] != val for key, val in fields.items()):
                raise ValueError(f"Durable receipt changed: {phase}")
        else:
            pilot.write(receipt, {"phase": phase, "ended_at": pilot.now(), **fields})

    stage("preflight")
    try:
        if stages:
            bind_dependencies(pilot.HOME)
        env = launcher_environment()
        env.update(credentials(env))
        bind_runtime(config, env)
        os.environ.update(env)
        executable = config.get("native_python") or sys.executable
        selected = output / "selected_candidate.json"
        frozen_candidate = control / "candidate.frozen.json"
        development = output / "development"
        track = {"protocol_sha256": protocol_hash, "model": pilot.MODEL, "arm": arm}
        if not frozen_candidate.is_file():
            stage("search" if stages else "development")
            proposer = make_proposer(config, output, f"plus/{arm}/eight-tool-development") if stages else None
            runner = NativeRunner(binding, executable, pilot.ROOT)
            budget = 1 + sum(limit for _, limit in stages)
            replays = Replay(development, track, pilot.MEMBERS["train_new"],
                             VALIDATION_COUNT, runner, maximum=budget)
            search_arm(replays, proposer, arm, output, seed=config["seed"])
            stage("freeze")
            pilot.write(frozen_candidate, {"sha256": pilot.sha(selected), "protocol_sha256": protocol_hash})
        selection = pilot.sha(selected)
        if pilot.read(frozen_candidate) != {"sha256": selection, "protocol_sha256": protocol_hash}:
            raise ValueError("The chosen development candidate changed after freezing")
        complete("search" if stages else "development", candidate_sha256=selection)
        complete("freeze", candidate_sha256=selection)

        candidate = Candidate(**pilot.read(selected))
        identity = key_for({"candidate": candidate.wire(), "protocol": track})
        replay = development / identity
        training_receipt = replay / "train/replay.completed.json"
        validation_receipt = replay / "val/replay.completed.json"
        scores = pilot.read(validation_receipt)["scores"]
        if (len(pilot.read(training_receipt)["scores"]) != 300 or len(scores) != VALIDATION_COUNT
                or any(type(value) not in (int, float) or value not in (0, 1) for value in scores)):
            raise ValueError("Selected candidate has incomplete development evidence")
        correct = int(sum(scores))
        complete("validation", correct=correct, n=VALIDATION_COUNT, receipt_sha256=pilot.sha(validation_receipt))
        result = {"model": pilot.MODEL, "arm": arm, "tools": list(pilot.TOOLS), "training": 300,
                  "split": "development_validation", "validation_used_for_selection": bool(stages),
                  "correct": correct, "n": VALIDATION_COUNT, "accuracy": correct / VALIDATION_COUNT,
                  "candidate_sha256": selection, "protocol_sha256": protocol_hash,
                  "validation_receipt": str(validation_receipt.relative_to(pilot.ROOT)),
                  "dataset_protocol_sha256": base_hash, "finished_at": pilot.now()}
        pilot.write(result_path, result)
        stage("report", status="complete")
        return result
    except (Exception, KeyboardInterrupt) as error:
        extra = {"returncode": error.returncode} if isinstance(error, subprocess.CalledProcessError) else {}
        stage(state["phase"], status="failed", error=type(error).__name__, **extra)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "status"))
    parser.add_argument("--arm", choices=ARMS, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    pilot.scoped_paths()
    control = pilot.HOME / "control/optimization_data8" / args.arm
    output = pilot.HOME / "optimization_data8" / args.arm
    if control.resolve() != control or output.resolve() != output:
        raise ValueError("Optimizer write path is redirected outside its isolated arm")
    if args.action == "status":
        value = status(control)
    else:
        with lock(control):
            value = execute(args.arm, control, output, args.resume)
    print(json.dumps(value, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
