"""Prepare, freeze, or execute a single configuration of the M5 RSI matrix."""

import csv
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml

from .data import EVAL_COUNTS, TARGETS, digest, read, write
from .native import DEEPSEEK_KEY, NATIVE_TOOLS, QWEN_KEY, NativeRunner, native_paths
from .search import ARMS, GEPA_RELEASE, RSI_COMMIT, Candidate, Replay, bind_dependencies, search_arm
from .policy import P0


FROZEN_FILES = ("inputs.json", "labels.json")
MODEL_IDS = {"plus": "qwen3.7-plus", "flash": "qwen3.6-flash"}
NEXT_PHASES = ("smoke", "search", "warmup", "evaluate")


def config_file(path):
    result = yaml.safe_load(path.read_text(encoding="utf-8"))
    models = result["models"]
    if (not isinstance(models, dict) or not models
            or any(name not in MODEL_IDS or MODEL_IDS[name] != model for name, model in models.items())
            or result["seed"] != 42):
        raise ValueError("Experiment model IDs or pilot seed changed")
    return result


def counts_from_data(home):
    root = home / "manifests"
    report = read(root / "sampling_report.json")
    if report["status"] != "frozen" or report["targets"] != TARGETS or report["seed"] != 42:
        raise ValueError("v2 development splits are not frozen")
    split_paths = {
        "train": [root / "train_new"],
        "validation": [root / "val_new"],
        "eval": [root / "eval_848" / name for name in EVAL_COUNTS],
    }
    split_ids = {}
    counts = {}
    for name, paths in split_paths.items():
        rows = []
        for folder in paths:
            record = report["manifest_sha256"][name]
            if name == "eval":
                record = record[folder.name]
            if any(digest(folder / leaf) != record[leaf] for leaf in FROZEN_FILES):
                raise ValueError(f"Frozen {name} manifests changed")
            rows.extend(read(folder / "inputs.json")["inputs"])
        split_ids[name] = (
            {r["group_id"] for r in rows},
            {i["pixel_sha256"] for r in rows for i in r["image_hashes"]},
            {i["file_sha256"] for r in rows for i in r["image_hashes"]},
        )
        counts[name] = len(rows)
    for left, right in (("train", "validation"), ("train", "eval"), ("validation", "eval")):
        if any(a & b for a, b in zip(split_ids[left], split_ids[right], strict=True)):
            raise ValueError(f"Overlap between {left} and {right}")
    if counts != {"train": 300, "validation": 100, "eval": 848}:
        raise ValueError("One or more protocol denominators changed")
    return counts


def dry_run(config):
    home = Path(config["artifacts"])
    models = config["models"]
    counts = counts_from_data(home)
    n_train, n_val, n_eval = (counts[key] for key in ("train", "validation", "eval"))
    search = {arm: (1 + sum(n for _, n in stages)) * (n_train + n_val) for arm, stages in ARMS.items()}
    return {"counts": counts, "backbones": models, "arms": {arm: list(stages) for arm, stages in ARMS.items()},
            "max_development_rollouts_per_backbone": search,
            "final_train_per_configuration": n_train, "final_evaluation_per_configuration": n_eval,
            "max_total_rollouts": len(models) * (sum(search.values()) + len(ARMS) * (n_train + n_eval)),
            "authorization": "no fee ceiling confirmation per user; no launch is performed by preflight",
            "evaluation_reset": "new clone of the arm's fresh training snapshot per dataset",
            "upstream": {"rsi": RSI_COMMIT, "official_gepa": GEPA_RELEASE}}


def enabled_model(config, backbone):
    if backbone not in config["models"]:
        raise ValueError(f"Backbone {backbone} is disabled in the active configuration")
    return config["models"][backbone]


def native_binding(config, backbone):
    model = enabled_model(config, backbone)
    binding_file = Path(config["native_bindings"]) / f"{backbone}.json"
    binding = read(binding_file)
    if binding.get("model") != model:
        raise ValueError("Native binding contains a different M5 backbone")
    for key in ("assets", "manifests"):
        if not Path(binding[key]).is_dir():
            raise FileNotFoundError(f"Staged native {key} not available")
    return binding


def preflight(config):
    home = Path(config["artifacts"])
    output = dry_run(config)
    bind_dependencies(home)
    import gepa
    errors = []
    assert callable(gepa.optimize)
    try:
        from rsi.gepa.reflection import ReflectionProposer
        from rsi.metaharness.loop import MetaHarnessLoop

        assert callable(ReflectionProposer.propose) and callable(MetaHarnessLoop.run)
        output["rsi_import"] = "passed"
    except ModuleNotFoundError as exc:
        if os.name != "nt" or exc.name != "resource":
            raise
        output["rsi_import"] = "native Linux resource module required by upstream"
    output["native_inspections"] = {}
    for key, model in config["models"].items():
        try:
            binding = native_binding(config, key)
            paths = native_paths(binding)
            template = read(paths["template"])
            if tuple(template["runtime"]["arms"]["M"]["tools"]) != NATIVE_TOOLS:
                raise ValueError("Native tools differ from the audited 11-tool baseline")
            if template["protocol"]["model"] != model or template["skill_enabled"]:
                raise ValueError("Native protocol must use the selected model with Skill disabled")
            output["native_inspections"][key] = {
                "model": template["protocol"]["model"], "locked_template": binding["template_sha256"],
                "tools": list(NATIVE_TOOLS),
            }
        except (FileNotFoundError, KeyError, ValueError) as exc:
            errors.append(f"{key}: {exc}")
    if os.name != "posix":
        errors.append("The original native tool execution and file locking require the staged Linux GPU host")
    if not os.environ.get(QWEN_KEY) or not os.environ.get(DEEPSEEK_KEY):
        errors.append("Native key slots must be loaded on the execution host")
    output["blockers"] = errors
    output["status"] = "blocked_native_runtime" if errors else "preflight_passed_awaiting_live_smoke"
    write(home / "preflight.json", output)
    return output


def source_lock(config):
    home = Path(config["artifacts"])
    filenames = sorted(Path(__file__).parent.glob("*.py"))
    sources = {path.name: digest(path) for path in filenames}
    bound = {}
    for name in config["models"]:
        binding = native_binding(config, name)
        paths = native_paths(binding)
        locations = {
            "event_loop": paths["experiment_sources"] / "run_online_skill_r54.py",
            "broker": paths["experiment_sources"] / "online_memory_r49.py",
            "tools": paths["experiment_sources"] / "skill_services_r55.py",
            "scorer": paths["experiment_sources"] / "cxr_author_alignment.py",
            "memory_driver": paths["memory_driver_sources"] / "r55_memevolve_driver_official.py",
            "memory_provider": paths["memory_runtime"] / "EvolveLab/providers/cerebra_fusion_memory_provider.py",
        }
        bound[name] = {"binding": binding, "native_sources": {slot: digest(file) for slot, file in locations.items()}}
    return {"m5_rsi_sources": sources, "r55_bindings": bound, "config": config,
            "data_lock": digest(home / "manifests" / "sampling_report.json")}


def lock_protocol(config):
    path = Path(config["artifacts"]) / "protocol_lock.json"
    value = source_lock(config)
    if path.is_file() and read(path) != value:
        raise ValueError("Protocol sources or data changed after the first run")
    if not path.is_file():
        write(path, value)
    return digest(path)


def make_proposer(config, out, label):
    from rsi.core.llm import LLM, LLMResponse, Usage

    settings = config["proposer"]
    model = settings["model"]
    endpoint = settings["base_url"].rstrip("/")
    if model != MODEL_IDS["plus"] or endpoint != "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1":
        raise ValueError("All search arms must use the frozen Qwen3.7-Plus proposer")
    key = os.environ[QWEN_KEY]

    class QwenProposal(LLM):
        name = model

        def _complete(self, prompt, *, system, max_tokens, seed):
            # Provider seed support has not been attested for this route.
            calls = out / "proposer_api"
            index = len(list(calls.glob("*.json"))) + 1
            if index > 120:
                raise RuntimeError("Search arm exhausted its proposer call allotment")
            record = calls / f"{index:03d}.json"
            request = {
                "model": model,
                "messages": (([{"role": "system", "content": system}] if system else []) +
                             [{"role": "user", "content": prompt}]),
                "max_tokens": min(max_tokens or settings["max_tokens"], settings["max_tokens"]),
                "temperature": settings["temperature"], "top_p": settings["top_p"],
                "enable_thinking": False, "stream": False,
            }
            write(record, {"status": "started", "model": model, "configuration": label, "seed_logical": seed})
            t0 = time.monotonic()
            try:
                req = Request(endpoint + "/chat/completions", data=json.dumps(request).encode("utf-8"),
                              headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                              method="POST")
                with urlopen(req, timeout=180) as stream:
                    response = json.load(stream)
                choice = response["choices"][0]
                text = choice["message"]["content"]
                if not isinstance(text, str):
                    raise ValueError("Proposer returned no text")
                usage = response.get("usage") or {}
            except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as exc:
                error = type(exc).__name__
                info = {"status": "failed", "error": error, "http_status": getattr(exc, "code", None)}
                write(record, {**read(record), **info})
                return LLMResponse("", Usage(calls=1), model, error=error)
            duration = time.monotonic() - t0
            write(record, {**read(record), "status": "complete", "usage": usage, "returned_model": response.get("model"),
                           "latency_seconds": duration, "usd": None, "finish_reason": choice["finish_reason"]})
            return LLMResponse(text, Usage(calls=1, input_tokens=usage.get("prompt_tokens", 0),
                                            output_tokens=usage.get("completion_tokens", 0), latency_s=duration),
                               response.get("model", model), raw={"finish_reason": choice["finish_reason"]})

    return QwenProposal()


def arm_root(config, backbone, arm):
    return Path(config["artifacts"]) / "runs" / backbone / arm / str(config["seed"])


def execute_arm(config, command, backbone, arm):
    model = enabled_model(config, backbone)
    home = Path(config["artifacts"])
    counts = counts_from_data(home)
    bind_dependencies(home)
    protocol = lock_protocol(config)
    binding = native_binding(config, backbone)
    workspace = Path(config["project_root"])
    worker = config.get("native_python") or sys.executable
    output = arm_root(config, backbone, arm)
    if command == "smoke":
        out = home / "live_smoke" / backbone
        runner = NativeRunner(binding, worker, workspace, phase="smoke", limits={"train": 12, "val": 8})
        replay = Replay(out / "replays", {"protocol": protocol, "model": model, "smoke": True},
                        12, 8, runner)
        result = replay.get(Candidate(P0), "val")
        write(out / "smoke.completed.json", {"status": "complete", "train": 12, "validation": 8,
                                             "validation_correct": sum(result["scores"]), "protocol": protocol})
        return {"status": "live_smoke_complete", "path": str(out / "smoke.completed.json")}
    if command == "search":
        smoke = read(home / "live_smoke" / backbone / "smoke.completed.json")
        if smoke["protocol"] != protocol:
            raise ValueError("Live smoke must use the locked native protocol")
        proposer = make_proposer(config, output, f"{backbone}/{arm}")
        runner = NativeRunner(binding, worker, workspace)
        replay = Replay(output / "development", {"protocol": protocol, "model": model, "arm": arm},
                        counts["train"], counts["validation"], runner,
                        maximum=1 + sum(n for _, n in ARMS[arm]))
        search_arm(replay, proposer, arm, output, seed=config["seed"])
        return {"status": "selection_complete", "path": str(output / "selected_candidate.json")}
    freeze = read(home / "freeze_manifest.json")
    candidate_file = output / "selected_candidate.json"
    if (freeze["protocol"] != protocol or digest(candidate_file) != freeze["candidates"][f"{backbone}/{arm}"]):
        raise ValueError("Candidates must remain frozen for the entire evaluation")
    candidate = Candidate(**read(candidate_file))
    runner = NativeRunner(binding, worker, workspace)
    if command == "warmup":
        runner.invoke(candidate, "train_new", output / "final_train", None, "warmup")
        return {"status": "fresh_training_complete", "path": str(output / "final_train" / "warm_snapshot")}
    if command == "evaluate":
        snapshot = output / "final_train" / "warm_snapshot"
        read(snapshot / "snapshot.json")
        for dataset in EVAL_COUNTS:
            runner.invoke(candidate, f"eval_848/{dataset}", output / "evaluation" / dataset, snapshot, "evaluate")
        return {"status": "evaluation_complete", "path": str(output / "evaluation")}
    raise ValueError(f"Unknown execution command {command}")


def freeze_all(config):
    home = Path(config["artifacts"])
    protocol = lock_protocol(config)
    files = {}
    for backbone in config["models"]:
        for arm in ARMS:
            p = arm_root(config, backbone, arm) / "selected_candidate.json"
            Candidate(**read(p))
            files[f"{backbone}/{arm}"] = digest(p)
    path = home / "freeze_manifest.json"
    value = {"protocol": protocol, "candidates": files, "seed": config["seed"]}
    if path.is_file() and read(path) != value:
        raise ValueError("A different final evaluation matrix is already frozen")
    write(path, value)
    return {"status": "all_configurations_frozen", "configurations": len(files), "path": str(path)}


def report(config):
    home = Path(config["artifacts"])
    rows, paired = [], []
    for backbone, model in config["models"].items():
        all_scores = {}
        for arm in ARMS:
            path = arm_root(config, backbone, arm) / "evaluation"
            scores = {d: read(path / d / "native.completed.json")["scores"] for d in EVAL_COUNTS}
            if any(len(values) != EVAL_COUNTS[d] for d, values in scores.items()):
                raise ValueError("Cannot report a subset as an 848-question run")
            all_scores[arm] = scores
            facts = {d: sum(scores[d]) for d in EVAL_COUNTS}
            rows.append({"model": model, "arm": arm, **facts, "total_correct": sum(facts.values()),
                         "n": 848, "micro": sum(facts.values()) / 848,
                         "macro": sum(facts[d] / EVAL_COUNTS[d] for d in facts) / len(facts)})
            if arm == "DATA":
                continue
            for d in EVAL_COUNTS:
                flips = list(zip(all_scores["DATA"][d], scores[d], strict=True))
                gain, harm = flips.count((0, 1)), flips.count((1, 0))
                paired.append({"model": model, "arm": arm, "dataset": d,
                               "gain": gain, "harm": harm, "net": gain - harm})
    root = home / "results"
    root.mkdir(exist_ok=True)
    for name, records in (("results_summary.csv", rows), ("paired_differences.csv", paired)):
        with (root / name).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    return {"status": "results_complete", "path": str(root)}
