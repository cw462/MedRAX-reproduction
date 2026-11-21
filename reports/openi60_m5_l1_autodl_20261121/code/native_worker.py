#!/usr/bin/env python3
"""Subprocess adapter to the existing, verified R55 runner and scorer.

No model implementation, fake answers, replacement scorer, or new retrieval logic.
Credentials are read by the native runner from stdin exactly as before.
"""
from __future__ import annotations
import argparse
import importlib
import importlib.util
import inspect
import json
import os
import sys
from pathlib import Path
from openi60.common import require, read_json, write_once, object_hash
from openi60.setup import verify_frozen
from openi60.hook import make_services

def load_native(cfg):
    root, code = Path(cfg["native_root"]), Path(cfg["code_root"])
    sys.path[:0] = [str(root), str(code / "experiments"), str(code)]
    runner = importlib.import_module("run_r55_11tools_m5")
    counts = importlib.import_module("run_r55_full848_dataset")
    services = importlib.import_module("skill_services_r55")
    require(Path(runner.__file__).resolve() == root / "run_r55_11tools_m5.py", "Native runner shadowed")
    require(Path(counts.__file__).resolve() == root / "run_r55_full848_dataset.py", "Native counts module shadowed")
    require(Path(services.__file__).resolve() == code / "experiments" / "skill_services_r55.py", "Services shadowed")
    require(list(inspect.signature(runner.run_dataset).parameters) == ["code", "out", "data", "references", "runtime"],
            "Unsupported native run_dataset signature")
    require(runner.COUNTS is counts.COUNTS, "Unexpected native count binding")
    require(counts.ARMS["M5"] == "R55-M5-11tools-CheXagent8B", "Native arm changed")
    require(counts.COUNTS["chexbench"] == 618, "Original dataset count unexpectedly modified")
    return runner, counts, services

def install_resident_tools(cfg, services):
    route = cfg.get("autodl_residents")
    if route is None:
        return
    modules = {}
    for name, filename in (("r55_resident_tools", route["model_module"]),
                           ("openi60_autodl_resident_pool", route["dispatch_module"])):
        path = Path(filename).resolve()
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        modules[name] = module
    require(list(inspect.signature(services.Tools.observe).parameters) ==
            ["self", "name", "spec", "args", "image", "identity", "folder", "saved"],
            "Unsupported native tool observation interface")
    services.Tools = modules["openi60_autodl_resident_pool"].tools_factory(
        services.Tools, {"resident_control": route["resident_control"],
                         "run_root": cfg["work_dir"]})

def seed_semantics(value):
    """Exclude runtime IDs and clocks, preserve initial rule payloads and statistics."""
    excluded = {"id", "node_id", "uuid", "created", "updated", "timestamp", "last_accessed",
                "last_access", "last_used", "last_updated", "creation_time", "modified_time"}
    if isinstance(value, dict):
        return {k: seed_semantics(v) for k, v in value.items()
                if k not in excluded and not k.endswith(("_at", "_timestamp", "_time"))}
    if isinstance(value, list):
        return [seed_semantics(v) for v in value]
    return value

def install_memory_audit(runner, work, arm):
    original = runner.CheckpointMemory
    class SeedAuditedMemory(original):
        def __init__(self, runtime, out, key, inputs, fixture=None):
            super().__init__(runtime, out, key, inputs, fixture)
            if self.prefix:
                require((work / arm / "initial_memory.json").is_file(), "Resume lacks original seed audit")
                return
            nodes = json.loads(json.dumps([vars(n) for n in self.provider.nodes.values()], default=runner.bridge.plain))
            require(len(nodes) == 7, "Native seven-pattern initialization changed")
            semantic = sorted((seed_semantics(n) for n in nodes), key=lambda n: json.dumps(n, sort_keys=True))
            fingerprint = object_hash(semantic)
            value = {"nodes": nodes, "semantic_nodes": semantic, "semantic_sha256": fingerprint,
                     "node_count": len(nodes), "tool_memory_enabled": self.provider.enable_tool_memory,
                     "memory_use_token_plan": self.model.use_token_plan}
            # Persist before any retrieve/ingest, so initial states can be inspected.
            seed_path = work / arm / "initial_memory.json"
            if seed_path.is_file():
                prior = read_json(seed_path)
                require(prior["semantic_sha256"] == fingerprint
                        and prior["memory_use_token_plan"] == self.model.use_token_plan,
                        "Initial seed/route changed on restart")
            else:
                write_once(seed_path, value)
            other = work / ("L1" if arm == "B0" else "B0") / "initial_memory.json"
            if other.is_file():
                prev = read_json(other)
                require(prev["semantic_sha256"] == fingerprint,
                        "The two initial memory payloads differ. Inspect nodes; do NOT bypass silently.")
                require(prev["memory_use_token_plan"] == self.model.use_token_plan, "Memory transport differs")
    runner.CheckpointMemory = SeedAuditedMemory

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=("check", "generate", "score"))
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--arm", choices=("B0", "L1"), default="B0")
    a = p.parse_args()
    require(not sys.flags.optimize, "Do not use python -O; native protocol assertions must remain active")
    work = a.work.resolve()
    frozen = verify_frozen(work)
    cfg = frozen["config"]
    runner, native, services = load_native(cfg)
    install_resident_tools(cfg, services)
    qids = set(frozen["cohort"]["selected_ids"])
    suffix = (work / a.arm / "solver_suffix.txt").read_text(encoding="utf-8").strip()
    replacement = make_services(services.Services, suffix, a.arm, qids)
    if a.phase == "check":
        # Also load the original scorer; no service/model is instantiated.
        scorer = importlib.import_module("score_r55_full848_dataset")
        require(callable(scorer.score_dataset), "Native scorer unavailable")
        print(json.dumps({"status": "native_imports_ok", "model_calls": 0,
                          "runner": str(Path(runner.__file__).resolve()),
                          "solver_call_signature": str(inspect.signature(services.Services.call))}))
        return
    # Only adapt the EXPECTED COHORT SIZE in this child process, not score logic.
    native.COUNTS["chexbench"] = cfg["n"]
    if a.phase == "score":
        module = importlib.import_module("score_r55_full848_dataset")
        require(module.COUNTS is native.COUNTS, "Scorer count binding unexpectedly changed")
        result = module.score_dataset(Path(cfg["code_root"]), work / a.arm)
    else:
        require(os.environ.get("CUDA_VISIBLE_DEVICES") == cfg["gpu"]
                and os.environ.get("R55_MEMEVOLVE_GPU") == cfg["gpu"], "GPU binding inconsistent")
        services.Services = replacement
        install_memory_audit(runner, work, a.arm)
        result = runner.run_dataset(
            Path(cfg["code_root"]), work / a.arm, work / "data",
            Path(cfg["references_root"]), Path(cfg["memory_runtime"]))
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
