from __future__ import annotations
import copy
import csv
import json
import os
import shutil
import sys
from pathlib import Path
from collections import Counter
from .common import (ExperimentError, canonical, file_hash, object_hash, read_json, relative_path,
                     require, resolve_path, write_once, write_text_once)
from .cohort import build_cohort, laterality_signature, validate_inputs, validate_order

PKG = Path(__file__).resolve().parents[1]
TOOLS = {"chest_xray_expert", "llava_med_qa", "medgemma", "llava_rad", "medvlm_r1",
         "maira2_grounded_report", "xray_phrase_grounding", "roi_crop", "medret", "reflect", "verify"}
NATIVE_FILES = ("run_r55_11tools_m5.py", "run_r55_full848_dataset.py",
                "score_r55_full848_dataset.py", "r55_memevolve_driver003.py", "r55_memory_token_plan.py")
CODE_FILES = ("run_online_skill_r54.py", "skill_services_r55.py", "skill_services_r54.py",
              "skill_services_r49.py", "toolsets_r54.py", "online_memory_r49.py",
              "cxr_online_primitives_r49.py", "r54_author_metrics.py", "report_skill_r54.py")
PATH_FIELDS = ("native_root", "code_root", "template_manifest", "data_root", "references_root",
               "memory_runtime", "work_dir", "prompt_file")

def new_config(native_root: Path, work: Path) -> dict:
    """Read the LOCAL production plan. A GitHub report is not a complete runtime."""
    root = native_root.resolve()
    plan_path = root / "plan.json"
    require(plan_path.is_file(), f"Missing local execution plan: {plan_path}")
    plan = read_json(plan_path)
    require(isinstance(plan.get("data"), dict) and "chexbench" in plan["data"], "plan.data.chexbench missing")
    def rp(v): return str(resolve_path(v, root))
    return {
        "schema": "openi60_config_v1", "native_root": str(root),
        "code_root": str(root / "code" / "M5"),
        "template_manifest": str(root / "manifests" / "M5" / "chexbench.json"),
        "data_root": rp(plan["data"]["chexbench"]),
        "references_root": rp(plan["references"]["chexbench"]),
        "memory_runtime": rp(plan["memory_runtime"]), "work_dir": str(work.resolve()),
        "prompt_file": str(PKG / "prompts" / "L1_zh.txt"),
        "n": 60, "seed": 20261121, "expected_pool": 293,
        "expected_main_model": "qwen3.7-plus", "gpu": "0",
        "main_key_env": "OPENI60_MAIN_API_KEY", "memory_key_env": "OPENI60_MEMORY_API_KEY",
        "execution_order": ["B0", "L1"],
    }

def load_config(path: Path) -> dict:
    cfg = read_json(path)
    require(cfg.get("schema") == "openi60_config_v1", "Unsupported configuration schema")
    for field in PATH_FIELDS:
        require(isinstance(cfg.get(field), str), f"Missing path: {field}")
        cfg[field] = str(resolve_path(cfg[field], path.resolve().parent))
    require(type(cfg.get("n")) is int and cfg["n"] > 0, "n must be a positive integer")
    require(type(cfg.get("seed")) is int, "seed must be an integer")
    require(cfg.get("execution_order") in (["B0", "L1"], ["L1", "B0"]), "Must run each arm once")
    require(str(cfg.get("gpu")) in ("0", "1"), "The verified native runner supports GPU index 0 or 1")
    cfg["gpu"] = str(cfg["gpu"])
    for key in ("main_key_env", "memory_key_env"):
        require(isinstance(cfg.get(key), str) and cfg[key].isidentifier(), f"Invalid env name: {key}")
    require(cfg.get("expected_main_model") == "qwen3.7-plus", "This package targets the supplied Qwen3.7-Plus experiment")
    return cfg

def verify_local(cfg: dict) -> dict:
    root, code = Path(cfg["native_root"]), Path(cfg["code_root"])
    for name in NATIVE_FILES:
        require((root / name).is_file(), f"Missing native runtime file: {root / name}")
    for name in CODE_FILES:
        require((code / "experiments" / name).is_file(), f"Missing deployed source: {code / 'experiments' / name}")
    runtime = Path(cfg["memory_runtime"])
    for name in ("EvolveLab", "models", "deps"):
        require((runtime / name).is_dir(), f"Missing memory runtime directory: {runtime / name}")
    require(Path(cfg["prompt_file"]).is_file(), "Prompt file missing")
    require(Path(cfg["data_root"]).is_dir() and Path(cfg["references_root"]).is_dir(), "Data/reference roots missing")
    require(Path(cfg["work_dir"]) not in (root, code, runtime, Path(cfg["data_root"])), "Work dir must be new and separate")
    m = read_json(Path(cfg["template_manifest"]))
    require(m.get("dataset") == "chexbench", "Use the original CheXBench native manifest")
    require(m.get("arm") == "R55-M5-11tools-CheXagent8B", "Wrong native M5 arm")
    require(m.get("skill_enabled") is False and m.get("cerebra_generated_tools") is False,
            "Skill/dynamic tools must remain disabled")
    require(m.get("memory_provider") == "cerebra_fusion_memory", "Not the M5 memory provider")
    require(m.get("memory_source") == "078e18cb6153fdc5b888308349cb6771eb7bde8f", "Different MemEvolve source")
    tools = m["runtime"]["arms"]["M"]["tools"]
    require(len(tools) == 11 and set(tools) == TOOLS, "Native 11-tool catalog does not match")
    require(set(m["runtime"]["tools"]) == TOOLS, "Unexpected extra/removed registered tools")
    require(m["protocol"].get("model") == cfg["expected_main_model"], "Wrong main model in protocol")
    require(m.get("continuation", {}).get("historical_predictions", 0) >= 0, "Invalid continuation metadata")
    validate_inputs(m["inputs"]); validate_order(m["inputs"], m["order"])
    require(set(m["reference_files"]) == {r["question_id"] for r in m["inputs"]}, "Reference index mismatch")
    require(all(v.get("file") == q + ".json" for q, v in m["reference_files"].items()), "Unsupported reference filenames")
    return m

def map_paths(value, old: Path, new: Path):
    """Relocate copied original-image bindings; leave all other model/tool paths untouched."""
    def remap(s):
        if isinstance(s, str) and (s == str(old) or s.startswith(str(old) + os.sep)):
            return str(new) + s[len(str(old)):]
        return s
    if isinstance(value, dict):
        return {remap(k): map_paths(v, old, new) for k, v in value.items()}
    if isinstance(value, list):
        return [map_paths(v, old, new) for v in value]
    return remap(value)

def source_inventory(cfg: dict) -> dict[str, str]:
    files = set()
    root = Path(cfg["native_root"])
    files.update(root.glob("*.py"))
    for base in (Path(cfg["code_root"]), Path(cfg["memory_runtime"]) / "EvolveLab", PKG / "openi60"):
        files.update(p for p in base.rglob("*.py") if not any(
            part in {"__pycache__", ".git", ".venv", "venv", "node_modules"} for part in p.parts))
    files.update([PKG / "openi60_cli.py", PKG / "native_worker.py"])
    route = root / "jobs" / "memory-writer-token-plan.json"
    if route.is_file():
        files.add(route)
    resident = cfg.get("autodl_residents")
    if resident is not None:
        files.update(Path(resident[key]) for key in ("model_module", "dispatch_module"))
    return {str(p.resolve()): file_hash(p) for p in sorted(files)}

def prepare(cfg: dict) -> dict:
    m = verify_local(cfg)
    sample, order, cohort = build_cohort(m, cfg["n"], cfg["seed"], cfg.get("expected_pool"))
    work = Path(cfg["work_dir"])
    require(not work.exists(), f"Refusing existing work directory: {work}. Never overwrite old runs.")
    # Validate original image boundaries & view annotations BEFORE creating the work dir.
    original_data = Path(cfg["data_root"])
    views = m["runtime"].get("backend_config", {}).get("r54_image_views_by_path", {})
    require(isinstance(views, dict) and views, "Missing original input-only image view map")
    image_files = {}
    for row in sample:
        for name in row["images"]:
            src = (original_data / relative_path(name)).resolve()
            require(src.is_relative_to(original_data), f"Original image escaped data root: {src}")
            require(src.is_file(), f"Original image missing: {src}")
            require(str(src) in views, f"Missing input-only view binding: {src}")
            image_files[name] = src
        require((Path(cfg["references_root"]) / (row["question_id"] + ".json")).is_file(), "Missing reference file")
    patch = Path(cfg["prompt_file"]).read_text(encoding="utf-8").strip()
    require(bool(patch), "L1 prompt is empty")
    from .hook import BEGIN, END
    require(BEGIN not in patch and END not in patch, "Prompt must not contain internal wrapper markers")
    inventory = source_inventory(cfg)
    work.mkdir(parents=True)
    data = work / "data"; data.mkdir()
    image_hashes = {}
    for name, src in sorted(image_files.items()):
        dst = data / relative_path(name); dst.parent.mkdir(parents=True, exist_ok=True)
        # COPY bytes, not symlink: the native sender rejects paths resolving outside data_root.
        shutil.copy2(src, dst)
        image_hashes[name] = file_hash(dst)
        require(image_hashes[name] == file_hash(src), "Image copy changed bytes")
    write_text_once(data / "inputs.jsonl", "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in sample))
    base = copy.deepcopy(m)
    base["inputs"], base["order"] = sample, order
    base["reference_files"] = {r["question_id"]: copy.deepcopy(m["reference_files"][r["question_id"]]) for r in sample}
    base.pop("continuation", None)  # A NEW stream, never inherit historical predictions or memory.
    for k in ("saved_prefix_questions", "historical_predictions"):
        base.pop(k, None)
    base["runtime"] = map_paths(base["runtime"], original_data, data)
    # Other absolute tool/model paths and all provider/temperature/budget fields remain unchanged.
    base["protocol"]["experiment_id"] = "openi60-" + object_hash({"seed": cfg["seed"], "ids": cohort["selected_ids"]})[:12]
    base["openi60"] = {"sample_sha256": object_hash(sample), "order_sha256": object_hash(order),
                       "cold_start": True, "subset_count_override": cfg["n"],
                       "historical_source": str(Path(cfg["template_manifest"]))}
    base["view_counts_image_occurrences"] = dict(Counter(
        str(views[str((original_data / name).resolve())].get("modality")) + "/" +
        str(views[str((original_data / name).resolve())].get("view"))
        for row in sample for name in row["images"]))
    for arm in ("B0", "L1"):
        out = work / arm; out.mkdir()
        arm_manifest = copy.deepcopy(base)
        # Distinct protocol bookkeeping IDs; native budget/ledger policies remain unchanged.
        arm_manifest["protocol"]["experiment_id"] += "-" + arm
        arm_manifest["openi60"]["experiment_arm"] = arm
        write_once(out / "manifest.json", arm_manifest)
        write_text_once(out / "solver_suffix.txt", (patch + "\n") if arm == "L1" else "")
    route = Path(cfg["native_root"]) / "jobs" / "memory-writer-token-plan.json"
    frozen = {
        "schema": "openi60_frozen_v1", "config": cfg, "cohort": cohort,
        "source_files": inventory, "source_inventory_sha256": object_hash(inventory),
        "native_template_sha256": file_hash(Path(cfg["template_manifest"])),
        "data_inputs_sha256": file_hash(data / "inputs.jsonl"),
        "image_sha256": image_hashes,
        "manifest_sha256": {a: file_hash(work / a / "manifest.json") for a in ("B0", "L1")},
        "suffix_sha256": {a: file_hash(work / a / "solver_suffix.txt") for a in ("B0", "L1")},
        "memory_route_marker": {"path": str(route), "exists": route.is_file(),
                                "sha256": file_hash(route) if route.is_file() else None},
        "references_root": cfg["references_root"],
        "references_not_parsed_at_sampling": True,
        "all_counts_are_first_answer_episodes_not_API_calls": True,
        "paid_inference_executed_by_preparation": False,
    }
    write_once(work / "frozen.json", frozen)
    write_once(work / "cohort.json", cohort)
    with (work / "selected_questions.csv").open("x", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ordinal", "question_id", "group", "question", "options", "images"])
        writer.writeheader()
        for i, row in enumerate(sample, 1):
            writer.writerow({"ordinal": i, "question_id": row["question_id"],
                "group": cohort["selected_groups"][row["question_id"]], "question": row["question"],
                "options": json.dumps(row["options"], ensure_ascii=False), "images": json.dumps(row["images"])})
    return {"work_dir": str(work), "questions_per_arm": cfg["n"], "first_answer_episodes_total": cfg["n"] * 2,
            "eligible_pool": cohort["pool_size"], "candidate_case_disjoint_remaining": len(cohort["remaining_case_disjoint_candidate_ids"]),
            "phase": "prepared_only", "model_calls": 0}

def verify_frozen(work: Path, *, include_images: bool = True) -> dict:
    work = work.resolve()
    frozen = read_json(work / "frozen.json")
    require(frozen.get("schema") == "openi60_frozen_v1", "Wrong frozen schema")
    require(frozen["config"]["work_dir"] == str(work), "Work directory moved after preparation")
    for name, expected in frozen["source_files"].items():
        p = Path(name)
        require(p.is_file() and file_hash(p) == expected, f"Frozen source changed/missing: {p}")
    for arm in ("B0", "L1"):
        for filename, section in (("manifest.json", "manifest_sha256"), ("solver_suffix.txt", "suffix_sha256")):
            require(file_hash(work / arm / filename) == frozen[section][arm], f"Frozen {arm}/{filename} changed")
    require(file_hash(work / "data" / "inputs.jsonl") == frozen["data_inputs_sha256"], "Subset inputs changed")
    route = frozen["memory_route_marker"]
    p = Path(route["path"])
    require(p.is_file() == route["exists"], "Memory transport route marker changed existence")
    if route["exists"]:
        require(file_hash(p) == route["sha256"], "Memory transport route changed")
    if include_images:
        for name, expected in frozen["image_sha256"].items():
            p = work / "data" / relative_path(name)
            require(p.is_file() and not p.is_symlink() and file_hash(p) == expected, f"Frozen image changed: {name}")
    return frozen
