"""Offline smoke of the official MedRAX report tool; never a clinical validation.

Requires both fixed snapshots in --cache-dir. No model downloads are permitted.
The complete generated report stays in an ignored output directory; summary.json
contains hashes and lengths, not report text, image content, or identifying paths.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from unittest.mock import patch

TOOL_RELATIVE = "medrax/tools/report_generation.py"
MODEL_SPECS = {
    "findings": {
        "repo_id": "IAMJB/chexpert-mimic-cxr-findings-baseline",
        "revision": "5bed2b551d7cadfe08f0757d29cc054dc1adb60d",
        "weight_bytes": 245236624,
        "weight_sha256": "99aac033cad7e158ad63bb4bcfc5736f7bc7c38eb65019c0781d6c6d4d7d1864",
    },
    "impression": {
        "repo_id": "IAMJB/chexpert-mimic-cxr-impression-baseline",
        "revision": "dd9e8a79659426980e8197657c81d2b9d443ddd0",
        "weight_bytes": 271078124,
        "weight_sha256": "75f68f7f4cc05d61d8fb68dff8c944c6ba89e6c35da8531963eebdd52c68407e",
    },
}
REQUIRED_FILES = ("config.json", "model.safetensors", "preprocessor_config.json",
                  "tokenizer_config.json", "vocab.txt")
AUDITED_FILES = (*REQUIRED_FILES, "generation_config.json", "special_tokens_map.json",
                 "added_tokens.json", "tokenizer.json", "README.md")
PACKAGES = ("torch", "torchvision", "transformers", "huggingface-hub", "tokenizers",
            "safetensors", "Pillow", "numpy", "langchain-core", "pydantic")
RUNTIME_MODULES = dict(zip(PACKAGES, ("torch", "torchvision", "transformers", "huggingface_hub",
                                    "tokenizers", "safetensors", "PIL", "numpy",
                                    "langchain_core", "pydantic")))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_hash(value) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def versions() -> dict:
    result = {"python": platform.python_version(), "os": platform.system(),
              "os_release": platform.release(), "machine": platform.machine()}
    for package in PACKAGES:
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = None
    # Multiple site-packages locations can expose conflicting dist-info records.
    # Keep candidate versions without publishing their filesystem paths.
    candidates = {name.lower().replace("_", "-"): [] for name in PACKAGES}
    try:
        for distribution in importlib.metadata.distributions():
            name = (distribution.metadata.get("Name") or "").lower().replace("_", "-")
            if name in candidates:
                candidates[name].append(distribution.version)
        result["distribution_candidates"] = {
            name: sorted(candidates[name.lower().replace("_", "-")]) for name in PACKAGES
        }
    except Exception as exc:
        result["distribution_candidates_error_type"] = type(exc).__name__
    return result


def imported_versions(distribution_versions: dict, modules=None) -> dict:
    """Inspect already imported modules; do not import extra packages for auditing."""
    modules = sys.modules if modules is None else modules
    result = {}
    for package, name in RUNTIME_MODULES.items():
        module = modules.get(name)
        raw = vars(module).get("__version__") if module is not None else None
        runtime = str(raw) if raw is not None else None
        metadata = distribution_versions.get(package)
        result[package] = {"module": name, "imported": module is not None,
                           "version": runtime, "matches_distribution_metadata":
                           runtime == metadata if runtime is not None and metadata is not None else None}
    return result


def source_provenance(repo: Path) -> dict:
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args],
                                       stderr=subprocess.DEVNULL, text=True).strip()
    if Path(git("rev-parse", "--show-toplevel")).resolve() != repo:
        raise ValueError("repo must be the checkout root")
    return {"commit": git("rev-parse", "HEAD"),
            "working_tree_dirty": bool(git("status", "--porcelain")),
            "tool_sha256": sha256_file(repo / TOOL_RELATIVE),
            "runner_sha256": sha256_file(Path(__file__))}


def inspect_snapshot(cache_dir: Path, spec: dict):
    """Resolve an immutable standard HF snapshot without importing Hub/network code."""
    snapshot = cache_dir / ("models--" + spec["repo_id"].replace("/", "--"))
    snapshot = snapshot / "snapshots" / spec["revision"]
    if not snapshot.is_dir() or any(not (snapshot / name).is_file() for name in REQUIRED_FILES):
        raise FileNotFoundError("Required local snapshot is incomplete")
    artifacts = []
    for name in AUDITED_FILES:
        path = snapshot / name
        if path.is_file():
            artifacts.append({"filename": name, "bytes": path.stat().st_size,
                              "sha256": sha256_file(path)})
    weight = next(item for item in artifacts if item["filename"] == "model.safetensors")
    if weight["bytes"] != spec["weight_bytes"] or weight["sha256"] != spec["weight_sha256"]:
        raise ValueError("Checkpoint differs from the pinned official artifact")
    manifest = {"repo_id": spec["repo_id"], "revision": spec["revision"],
                "weight_matches_official_sha256": True, "files": artifacts}
    manifest["manifest_sha256"] = json_hash(manifest)
    return snapshot, manifest


def validate_report(result) -> dict:
    if not isinstance(result, (tuple, list)) or len(result) != 2:
        raise ValueError("Unexpected tool return structure")
    text, metadata = result
    if not isinstance(metadata, dict) or metadata.get("analysis_status") != "completed":
        raise ValueError("Tool did not report completed")
    if metadata.get("sections_generated") != ["findings", "impression"]:
        raise ValueError("Expected both report sections")
    if not isinstance(text, str) or "\x00" in text:
        raise ValueError("Expected a complete report string")
    prefix = "CHEST X-RAY REPORT\n\nFINDINGS:\n"
    separator = "\n\nIMPRESSION:\n"
    if not text.startswith(prefix) or text.count(separator) != 1:
        raise ValueError("Unexpected official report layout")
    findings, impression = text[len(prefix):].split(separator)
    if not findings.strip() or not impression.strip():
        raise ValueError("Generated report section is empty")
    return {"tool_analysis_status": "completed", "full_string": True,
            "string_format_only": True, "semantic_completeness_evaluated": False,
            "nonempty_sections": ["findings", "impression"],
            "report_chars": len(text), "findings_chars": len(findings),
            "impression_chars": len(impression),
            "report_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def local_loader(original, kind, snapshots, observed):
    """Preserve the official loader, replacing only its source with verified local assets."""
    def load(source, *args, **kwargs):
        if str(source) not in snapshots:
            raise ValueError("Unexpected model source; network loading is forbidden")
        role, path = snapshots[str(source)]
        kwargs.pop("cache_dir", None)
        kwargs.update(local_files_only=True, trust_remote_code=False)
        if kind == "model":
            kwargs["use_safetensors"] = True
        value = original(str(path), *args, **kwargs)
        observed.append({"role": role, "loader": kind,
                         "provenance": "successful_from_pretrained_verified_local_snapshot"})
        return value
    return load


def generation_recorder(original, role, calls):
    def generate(*args, **kwargs):
        config = kwargs.get("generation_config")
        observed_config = {key: getattr(config, key, None) for key in
                           ("max_length", "num_beams", "beam_width", "do_sample", "use_cache",
                            "eos_token_id", "pad_token_id")}
        generated = original(*args, **kwargs)
        shape = list(generated.shape)
        if len(shape) != 2 or shape[0] != 1 or shape[1] < 1:
            raise ValueError("Unexpected generated token shape")
        # Read tokens only in memory for the audit; never include them in output.
        sequence = generated.detach().cpu().tolist()[0]
        eos = observed_config["eos_token_id"]
        eos_ids = [eos] if isinstance(eos, int) else eos
        contains_eos = any(token in eos_ids for token in sequence) if eos_ids else None
        maximum = observed_config["max_length"]
        reached_limit = shape[1] >= maximum if isinstance(maximum, int) and maximum > 0 else None
        calls.append({"role": role, "output_shape": shape, "generation_config": observed_config,
                      "sequence_contains_eos": contains_eos, "reached_max_length": reached_limit,
                      "termination_reason_inferred": False, "semantic_completeness_evaluated": False})
        # EOS may coincide with the length boundary or occur in a decoder prefix;
        # these observations alone do not prove why generation stopped.
        return generated
    return generate


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "image", "output", "cache-dir"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--device", required=True, help="cpu, cuda, or cuda:N")
    args = parser.parse_args(argv)
    repo, image, output, cache_dir = (path.resolve() for path in
                                    (args.repo, args.image, args.output, args.cache_dir))
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError:
        print("Output directory unavailable or already exists; nothing overwritten.", file=sys.stderr)
        return 2
    (output / ".gitignore").write_text("*\n", encoding="utf-8")
    started = time.monotonic()
    summary = {"schema_version": 2, "kind": "real_report_tool_smoke", "status": "running",
               "clinical_correctness_evaluated": False, "not_an_agent_or_accuracy_benchmark": True,
               "semantic_completeness_evaluated": False,
               "offline_only": True, "upstream_generation_arguments_unchanged": True,
               "started_utc": datetime.now(timezone.utc).isoformat(), "environment": versions(),
               "device_requested": args.device, "assets_verified": [], "loads_observed": [],
               "generation_calls": [], "report_artifact": None, "init_seconds": None,
               "inference_seconds": None, "peak_cuda_allocated_bytes": None,
               "peak_cuda_reserved_bytes": None}
    stage = "input_validation"
    torch = device = None
    cuda_ready = False
    try:
        if not (repo / TOOL_RELATIVE).is_file():
            raise FileNotFoundError("Official report tool source unavailable")
        if not image.is_file() or image.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            raise FileNotFoundError("An existing PNG or JPEG is required")
        summary["image"] = {"sha256": sha256_file(image), "bytes": image.stat().st_size}
        stage = "source_provenance"
        summary["source"] = source_provenance(repo)
        stage = "offline_asset_validation"
        snapshots = {}
        for role, spec in MODEL_SPECS.items():
            snapshot, manifest = inspect_snapshot(cache_dir, spec)
            snapshots[spec["repo_id"]] = (role, snapshot)
            summary["assets_verified"].append({"role": role, **manifest})
        with patch.dict(os.environ, {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                                    "HF_HUB_DISABLE_TELEMETRY": "1"}):
            with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
                stage = "dependency_import"
                import torch
                from PIL import Image
                stage = "image_validation"
                with Image.open(image) as opened:
                    if opened.format not in ("PNG", "JPEG") or min(opened.size) < 2:
                        raise ValueError("Invalid image format or dimensions")
                    summary["image"].update(size=list(opened.size), mode=opened.mode)
                    opened.verify()
                stage = "device_validation"
                device = torch.device(args.device)
                if device.type not in ("cpu", "cuda"):
                    raise ValueError("Only CPU and CUDA are supported")
                if device.type == "cuda":
                    if not torch.cuda.is_available():
                        raise RuntimeError("Requested CUDA is unavailable")
                    index = torch.cuda.current_device() if device.index is None else device.index
                    torch.cuda.set_device(index)
                    device = torch.device("cuda", index)
                    torch.cuda.synchronize(device)
                    torch.cuda.reset_peak_memory_stats(device)
                    cuda_ready = True
                    summary["gpu"] = {"index": index, "name": torch.cuda.get_device_name(index),
                                      "total_memory_bytes": torch.cuda.get_device_properties(index).total_memory}
                summary["environment"].update(torch_cuda_build=torch.version.cuda,
                                              cudnn_version=torch.backends.cudnn.version())
                stage = "report_tool_import"
                name = "_medrax_report_smoke"
                spec = importlib.util.spec_from_file_location(name, repo / TOOL_RELATIVE)
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)
                stage = "model_initialization"
                tick = time.monotonic()
                with ExitStack() as stack:
                    for cls, kind in ((module.VisionEncoderDecoderModel, "model"),
                                      (module.BertTokenizer, "tokenizer"),
                                      (module.ViTImageProcessor, "processor")):
                        wrapped = local_loader(cls.from_pretrained, kind, snapshots,
                                               summary["loads_observed"])
                        stack.enter_context(patch.object(cls, "from_pretrained", side_effect=wrapped))
                    tool = module.ChestXRayReportGeneratorTool(cache_dir=str(cache_dir), device=str(device))
                if cuda_ready:
                    torch.cuda.synchronize(device)
                summary["init_seconds"] = time.monotonic() - tick
                expected_loads = {(role, kind) for role in MODEL_SPECS
                                  for kind in ("model", "tokenizer", "processor")}
                if len(summary["loads_observed"]) != 6 or {
                    (item["role"], item["loader"]) for item in summary["loads_observed"]
                } != expected_loads:
                    raise RuntimeError("Both complete model assets were not loaded")
                summary["upstream_generation_args"] = dict(tool.generation_args)
                summary["model_dtypes"] = {role: str(getattr(tool, role + "_model").dtype)
                                           for role in MODEL_SPECS}
                stage = "inference"
                tick = time.monotonic()
                with ExitStack() as stack:
                    for role in MODEL_SPECS:
                        model = getattr(tool, role + "_model")
                        wrapped = generation_recorder(model.generate, role, summary["generation_calls"])
                        stack.enter_context(patch.object(model, "generate", side_effect=wrapped))
                    result = tool.invoke({"image_path": str(image)})
                if cuda_ready:
                    torch.cuda.synchronize(device)
                summary["inference_seconds"] = time.monotonic() - tick
                stage = "output_validation"
                checks = validate_report(result)
                if [item["role"] for item in summary["generation_calls"]] != ["findings", "impression"]:
                    raise ValueError("Expected two successful real generation calls")
                summary["output_checks"] = checks
                stage = "save_local_report"
                raw = result[0].encode("utf-8")
                with (output / "report.txt").open("xb") as handle:
                    handle.write(raw)
                summary["report_artifact"] = {"filename": "report.txt", "bytes": len(raw),
                                               "sha256": checks["report_sha256"],
                                               "publishable_by_default": False}
                summary["status"] = "completed"
    except (Exception, KeyboardInterrupt) as exc:
        summary.update(status="failed", failed_stage=stage, error_type=type(exc).__name__)
    finally:
        if cuda_ready:
            try:
                summary["peak_cuda_allocated_bytes"] = torch.cuda.max_memory_allocated(device)
                summary["peak_cuda_reserved_bytes"] = torch.cuda.max_memory_reserved(device)
            except Exception:
                pass
        runtime = imported_versions(summary["environment"])
        summary["environment"]["imported_runtime_versions"] = runtime
        summary["environment"]["runtime_distribution_mismatches"] = [
            name for name, item in runtime.items() if item["matches_distribution_metadata"] is False
        ]
        summary["environment_sha256"] = json_hash(summary["environment"])
        summary["elapsed_seconds"] = time.monotonic() - started
        summary["finished_utc"] = datetime.now(timezone.utc).isoformat()
        with (output / "summary.json").open("x", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
    print(json.dumps({"status": summary["status"], "stage": summary.get("failed_stage"),
                      "summary_file": "summary.json"}))
    return 0 if summary["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
