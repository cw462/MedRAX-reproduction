"""Pack the selected data and reconstruct native launch templates from R55 receipts."""

from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import subprocess
import tarfile

import yaml

from .data import EVAL_COUNTS, archived_manifest, digest, read, write
from .native import NATIVE_TOOLS
from .search import GEPA_RELEASE, GEPA_WHEEL_HASH, RSI_COMMIT
from .workflow import MODEL_IDS, counts_from_data


AUTODL_BASE = "/root/autodl-tmp/medrax_r55_top4_full848"
DEFAULT_TARGET = "/root/autodl-tmp/medrax_m5_data_rsi_v2_20261117"
PLUS_TARGET = DEFAULT_TARGET + "_plus"
PLUS_OUTPUT = Path.home() / "MedRAX_Experiment_Artifacts/m5_data_rsi_v2_20261117_plus"


def archived_models(home, models):
    prior = home.parent
    archives = {
        **{dataset: (prior / "r55_autodl_four_20261115_001/dataset-archives/M5" / dataset / "evidence.tar.gz")
           for dataset in EVAL_COUNTS},
    }
    if "plus" in models:
        archives["plus"] = prior / "r55_lab_11tools_chexagent8b001/M5/evidence.tar.gz"
    with ThreadPoolExecutor(max_workers=3) as pool:
        manifests = dict(zip(archives, pool.map(archived_manifest, archives.values()), strict=True))
    for label, data in manifests.items():
        model = MODEL_IDS["plus" if label == "plus" else "flash"]
        if (data["protocol"]["model"] != model or tuple(data["runtime"]["arms"]["M"]["tools"]) != NATIVE_TOOLS
                or data.get("memory_provider") != "cerebra_fusion_memory" or data.get("skill_enabled")):
            raise ValueError(f"Historical M5 configuration does not match {label}")
    return manifests, archives


def inherited_views(home, manifests):
    views = {}
    for dataset in EVAL_COUNTS:
        historical = manifests[dataset]
        official = read(home / "manifests/eval_848" / dataset / "inputs.json")
        view_source = historical["runtime"]["backend_config"]["r54_image_views_by_path"]
        if historical["order"] != official["order"]:
            raise ValueError(f"Archived 11-tool evaluation order differs from the frozen {dataset} order")
        for original, public in zip(historical["inputs"], official["inputs"], strict=True):
            if original["question_id"] != public["question_id"] or original["question"] != public["question"]:
                raise ValueError(f"Archived 11-tool inputs differ for {dataset}")
            keys = [item["asset"] for item in public["image_hashes"]]
            for image, asset in zip(original["images"], keys, strict=True):
                matches = [v for path, v in view_source.items() if path.endswith("/" + image)]
                if not matches or any(v != matches[0] for v in matches[1:]):
                    raise ValueError(f"No unique frozen modality/view for {dataset}/{image}")
                view = {k: matches[0][k] for k in ("source", "modality", "view")}
                if asset in views and views[asset] != view:
                    if (views[asset]["modality"], views[asset]["view"]) != (view["modality"], view["view"]):
                        raise ValueError(f"Conflicting historical modality/view for {asset}")
                    continue
                views[asset] = view
    return views


def prepare_templates(home, stage, target, models):
    manifests, archives = archived_models(home, models)
    views = inherited_views(home, manifests)
    flash = manifests["chexbench"]
    common_runtime = copy.deepcopy(flash["runtime"])
    # Rebind the original image metadata for this run in native.execute.
    common_runtime["backend_config"]["r54_image_views_by_path"] = {}
    common_runtime["tools"] = {name: common_runtime["tools"][name] for name in NATIVE_TOOLS}
    paths = {
        "experiment_sources": AUTODL_BASE + "/r55_autodl_four_20261115_001/code/experiments",
        "memory_driver_sources": AUTODL_BASE + "/r55_autodl_qwen_8tools_20261116_001/bin",
        "memory_runtime": AUTODL_BASE + "/r55_autodl_four_20261115_001/runtime/five",
    }
    identity = {}
    model_files = []
    for name, model_id in models.items():
        label = "plus" if name == "plus" else "chexbench"
        source = manifests[label]
        cfg, protocol = copy.deepcopy(source["config"]), copy.deepcopy(source["protocol"])
        experiment_id = f"m5-data-rsi-v2-{name}"
        cfg["experiment_id"] = protocol["experiment_id"] = experiment_id
        template = {"runtime": common_runtime, "config": cfg, "protocol": protocol,
                    "embedding_model": flash["embedding_model"], "embedding_base_url": flash.get("embedding_base_url"),
                    "skill_enabled": False, "memory_provider": flash["memory_provider"], "memory_source": flash["memory_source"]}
        file = stage / "native_templates" / f"{name}.json"
        write(file, template)
        binding = {**paths, "template": f"{target}/artifacts/native_templates/{name}.json",
                   "template_sha256": digest(file), "model": model_id, "eval_views": views,
                   "manifests": f"{target}/artifacts/manifests", "assets": f"{target}/artifacts"}
        binding_file = stage / "native_bindings" / f"{name}.json"
        write(binding_file, binding)
        model_files.extend((file, binding_file))
        identity[name] = {"request_model_id": model_id, "role": "solver",
                          "profile": {k: cfg["profile"][k] for k in ("base_url", "credential_slot")},
                          "params": {k: protocol.get(k) for k in
                                     ("temperature", "top_p", "max_output_tokens", "enable_thinking",
                                      "main_call_limits", "tool_call_limits")},
                          "native_archive": str(archives[label])}
    identity["proposer"] = {"request_model_id": MODEL_IDS["plus"], "same_route_for_all_search_arms": True}
    identity["memory"] = {"provider": "CerebraFusionMemory", "checkpoint_source": flash["memory_source"],
                          "request_model_id": "deepseek-flash", "endpoint": "https://api.deepseek.com/chat/completions"}
    identity["embedding"] = {"request_model_id": flash["embedding_model"],
                             "graph_encoder": "native CerebraFusionMemory SentenceTransformer"}
    write(stage / "model_mapping.json", identity)
    return len(views), model_files


def staged_rsi(home, stage):
    checkout = home / "upstream" / "RSI"
    revision = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    if revision != RSI_COMMIT:
        raise ValueError("RSI checkout is not the selected commit")
    files = subprocess.check_output(["git", "-C", str(checkout), "ls-files", "-z", "--", "rsi", "LICENSE"])
    files = [name.decode("utf-8") for name in files.split(b"\0") if name]
    snapshot = {name: digest(checkout / name) for name in files}
    status = subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(checkout), "status", "--porcelain", "--", "rsi", "LICENSE"]
    )
    if status:
        raise ValueError("RSI source checkout changed after pinning")
    write(stage / "rsi_source.json", {"commit": revision, "sha256": snapshot})
    return [checkout / name for name in files]


def make_bundle(config, *, target=None, output=None):
    home = Path(config["artifacts"])
    workspace = Path(config["project_root"])
    models = config["models"]
    if not models or any(MODEL_IDS.get(name) != model_id for name, model_id in models.items()):
        raise ValueError("Unknown native model in deployment configuration")
    plus_only = models == {"plus": MODEL_IDS["plus"]}
    if target is None:
        target = PLUS_TARGET if plus_only else DEFAULT_TARGET
    if output is None:
        output = PLUS_OUTPUT if plus_only else home
    output = Path(output).resolve()
    counts_from_data(home)
    stage = output / "deployment"
    view_count, model_files = prepare_templates(home, stage, target, models)
    rsi_files = staged_rsi(home, stage)
    wheel = home / "upstream" / f"gepa-{GEPA_RELEASE}-py3-none-any.whl"
    if digest(wheel) != GEPA_WHEEL_HASH:
        raise ValueError("GEPA wheel checksum changed")
    main = copy.deepcopy(config)
    main.update(project_root=target, artifacts=f"{target}/artifacts",
                native_bindings=f"{target}/artifacts/native_bindings",
                native_python=AUTODL_BASE + "/env/modern/bin/python")
    port = stage / "autodl.m5_rsi.yaml"
    port.write_text(yaml.safe_dump(main, sort_keys=False), encoding="utf-8")
    with (stage / "editable_allowlist.json").open("w", encoding="utf-8") as file:
        json.dump({"gepa": ["solver_instruction", "memory_write", "advice_synthesis"],
                   "meta": {"file": "policy.py",
                            "settings": ["top_k", "semantic_weight", "max_neighbors"],
                            "functions": ["rank", "keep"]}}, file, indent=2)
    data = home / "manifests"
    image_paths = sorted({path for p in data.rglob("inputs.json") for row in read(p)["inputs"] for path in row["images"]})
    checkout = home / "upstream/RSI"
    bundle = output / "m5_rsi_autodl.bundle.tar.gz"
    pending = bundle.with_suffix(".part")
    with tarfile.open(pending, "w:gz", compresslevel=1) as archive:
        archive.add(port, "configs/m5_rsi.yaml")
        for path in sorted((workspace / "experiments/m5_rsi").glob("*.py")):
            archive.add(path, f"experiments/m5_rsi/{path.name}")
        for path in sorted(data.rglob("*.json")):
            archive.add(path, "artifacts/manifests/" + path.relative_to(data).as_posix())
        for image in image_paths:
            archive.add(home / image, f"artifacts/{image}")
        for p in (*model_files, stage / "model_mapping.json", stage / "editable_allowlist.json"):
            archive.add(p, "artifacts/" + p.relative_to(stage).as_posix())
        for path in rsi_files:
            archive.add(path, "artifacts/upstream/RSI/" + path.relative_to(checkout).as_posix())
        archive.add(stage / "rsi_source.json", "artifacts/upstream/rsi_source.json")
        archive.add(wheel, "artifacts/upstream/" + wheel.name)
    pending.replace(bundle)
    result = {"status": "staged_locally_awaiting_gpu_host", "archive": str(bundle), "sha256": digest(bundle),
              "bytes": bundle.stat().st_size, "solver_images": len(image_paths), "inherited_views": view_count,
              "target": target, "models": models, "new_model_requests": 0}
    write(stage / "bundle.completed.json", result)
    return result
