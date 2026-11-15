"""Run one real official MedRAX classifier call; not an Agent benchmark.

No reference labels are read. Model initialization may download public weights.
Generated output is intentionally excluded from Git by its own .gitignore.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from unittest.mock import patch

MODEL_NAME = "densenet121-res224-all"
CLASSIFIER_RELATIVE = "medrax/tools/classification.py"
PACKAGES = ("torch", "torchvision", "torchxrayvision", "numpy", "scikit-image",
            "langchain-core", "pydantic")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def versions() -> dict:
    result = {"python": platform.python_version(), "os": platform.system(),
              "os_release": platform.release(), "machine": platform.machine()}
    for package in PACKAGES:
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = None
    return result


def loaded_module_versions() -> dict:
    """Record imported code separately from potentially duplicate dist metadata."""
    names = ("torch", "torchvision", "torchxrayvision", "numpy", "skimage",
             "langchain_core", "pydantic", "transformers")
    return {name: getattr(sys.modules[name], "__version__", None)
            for name in names if name in sys.modules}


def git_info(repo: Path) -> dict:
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args],
                                       stderr=subprocess.DEVNULL, text=True).strip()
    if Path(git("rev-parse", "--show-toplevel")).resolve() != repo:
        raise ValueError("repo must be the checkout root")
    return {"commit": git("rev-parse", "HEAD"),
            "working_tree_dirty": bool(git("status", "--porcelain")),
            "classifier_sha256": sha256_file(repo / CLASSIFIER_RELATIVE)}


def validate_scores(result, expected_labels):
    if not isinstance(result, (tuple, list)) or len(result) != 2:
        raise ValueError("Unexpected tool return structure")
    scores, metadata = result
    if not isinstance(metadata, dict) or metadata.get("analysis_status") != "completed":
        raise ValueError("Tool did not report completed")
    if not isinstance(scores, dict) or len(scores) != 18:
        raise ValueError("Expected exactly 18 outputs")
    expected_labels = list(expected_labels)
    if len(expected_labels) != 18 or list(scores) != expected_labels:
        raise ValueError("Output labels differ from loaded model labels")
    if any(isinstance(value, (bool, str)) for value in scores.values()):
        raise ValueError("Scores must be numeric")
    clean = {name: float(value) for name, value in scores.items()}
    if not all(math.isfinite(value) and 0 <= value <= 1 for value in clean.values()):
        raise ValueError("Scores must be finite and between zero and one")
    # Never forward metadata: the original tool includes the image path and errors.
    return clean


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path,
                        help="New output directory; existing directories are rejected")
    parser.add_argument("--device", required=True, help="cpu, cuda, or cuda:N")
    args = parser.parse_args(argv)
    repo, image, output = (p.resolve() for p in (args.repo, args.image, args.output))
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError:
        print("Output directory unavailable or already exists; nothing overwritten.", file=sys.stderr)
        return 2
    (output / ".gitignore").write_text("*\n", encoding="utf-8")
    began = time.monotonic()
    report = {"schema_version": 1, "status": "running", "kind": "real_tool_smoke",
              "not_an_agent_or_accuracy_benchmark": True,
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "model_name": MODEL_NAME, "environment": versions(),
              "device_requested": args.device, "checkpoints_loaded": [],
              "scores": None, "init_seconds": None, "inference_seconds": None,
              "peak_cuda_allocated_bytes": None, "peak_cuda_reserved_bytes": None}
    stage = "input_validation"
    torch = None
    device = None
    try:
        if not repo.is_dir() or not (repo / CLASSIFIER_RELATIVE).is_file():
            raise FileNotFoundError("Official classifier source unavailable")
        if not image.is_file() or image.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            raise FileNotFoundError("An existing PNG or JPEG is required")
        report["image"] = {"sha256": sha256_file(image), "bytes": image.stat().st_size}
        stage = "source_provenance"
        report["source"] = git_info(repo)
        stage = "dependency_import"
        import torch
        import skimage.io
        import numpy as np
        stage = "image_validation"
        pixels = skimage.io.imread(image)
        if pixels.dtype != np.uint8 or pixels.ndim not in (2, 3):
            raise ValueError("Use an 8-bit grayscale or RGB PNG/JPEG for the official preprocessing")
        if pixels.ndim == 3 and pixels.shape[2] not in (1, 3, 4):
            raise ValueError("Unsupported channel count")
        if min(pixels.shape[:2]) < 2:
            raise ValueError("Invalid image dimensions")
        report["image"].update(shape=list(pixels.shape), dtype=str(pixels.dtype))
        del pixels
        stage = "device_validation"
        device = torch.device(args.device)
        if device.type not in ("cpu", "cuda"):
            raise ValueError("Only CPU and CUDA are supported by this smoke runner")
        if device.type == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA was requested but is unavailable")
            index = torch.cuda.current_device() if device.index is None else device.index
            torch.cuda.set_device(index)
            device = torch.device("cuda", index)
            torch.cuda.synchronize(device)
            torch.cuda.reset_peak_memory_stats(device)
            report["gpu"] = {"index": index, "name": torch.cuda.get_device_name(index),
                             "total_memory_bytes": torch.cuda.get_device_properties(index).total_memory}
        report["environment"].update(torch_cuda_build=torch.version.cuda,
                                     cudnn_version=torch.backends.cudnn.version())
        stage = "classifier_import"
        name = "_medrax_classifier_smoke"
        spec = importlib.util.spec_from_file_location(name, repo / CLASSIFIER_RELATIVE)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        # Import by file avoids medrax.tools.__init__, which imports every tool.
        spec.loader.exec_module(module)
        stage = "model_initialization"
        original_load = torch.load
        loaded_paths = []

        def record_load(source, *positional, **keyword):
            value = original_load(source, *positional, **keyword)
            candidate = source if isinstance(source, (str, os.PathLike)) else getattr(source, "name", None)
            if isinstance(candidate, (str, os.PathLike)) and Path(candidate).is_file():
                loaded_paths.append(Path(candidate).resolve())
            return value

        with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
            started = time.monotonic()
            with patch.object(torch, "load", side_effect=record_load):
                tool = module.ChestXRayClassifierTool(model_name=MODEL_NAME, device=str(device))
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            report["init_seconds"] = time.monotonic() - started
            stage = "checkpoint_provenance"
            if not loaded_paths:
                raise RuntimeError("No checkpoint load observed; cannot verify loaded weights")
            for checkpoint in dict.fromkeys(loaded_paths):
                report["checkpoints_loaded"].append({"filename": checkpoint.name,
                    "sha256": sha256_file(checkpoint), "bytes": checkpoint.stat().st_size,
                    "provenance": "observed_successful_torch_load"})
            stage = "inference"
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            started = time.monotonic()
            result = tool.invoke({"image_path": str(image)})
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            report["inference_seconds"] = time.monotonic() - started
            stage = "output_validation"
            report["scores"] = validate_scores(result, tool.model.pathologies)
        report["status"] = "completed"
        report["output_checks"] = {"count": 18, "labels_match_model": True,
                                   "finite": True, "range_0_1": True,
                                   "tool_analysis_status": "completed"}
    except Exception as exc:
        report.update(status="failed", failed_stage=stage, error_type=type(exc).__name__)
        # Messages and tracebacks can contain identifying paths; do not publish them.
    finally:
        report["loaded_module_versions"] = loaded_module_versions()
        if torch is not None and device is not None and device.type == "cuda" and torch.cuda.is_available():
            try:
                report["peak_cuda_allocated_bytes"] = torch.cuda.max_memory_allocated(device)
                report["peak_cuda_reserved_bytes"] = torch.cuda.max_memory_reserved(device)
            except Exception:
                pass
        report["elapsed_seconds"] = time.monotonic() - began
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        with (output / "summary.json").open("x", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
    print(json.dumps({"status": report["status"], "stage": report.get("failed_stage"),
                      "summary_file": "summary.json"}))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
