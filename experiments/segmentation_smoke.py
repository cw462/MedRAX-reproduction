"""Offline official MedRAX/XRV 1.3.5 PSPNet smoke; never ground-truth labels.

Requires a previously downloaded official checkpoint and its pre-recorded SHA256.
No model downloads or upstream inference-parameter changes are permitted. Output
must be a new directory; its visualization contains the source image and is ignored
by Git. The upstream 0.2 mm pixel spacing is an assumption, not a calibration.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import numbers
import os
from pathlib import Path
import platform
import re
import socket
import subprocess
import sys
import time
from unittest.mock import patch

TOOL_RELATIVE = "medrax/tools/segmentation.py"
XRV_VERSION = "1.3.5"
XRV_REFERENCE_COMMIT = "6fa28a2fbfb1b30fcb5f8f501626d91177ef593c"
XRV_WRAPPER_SHA256 = "b33a193de990cc1bf00b3611d86f6f79de9c3556faa1009daceb697fee788c47"
CHECKPOINT_NAME = "pspnet_chestxray_best_model_4.pth"
CHECKPOINT_BYTES = 272988989
CHECKPOINT_URL = "https://github.com/mlmed/torchxrayvision/releases/download/v1/" + CHECKPOINT_NAME
ORGANS = ("Left Clavicle", "Right Clavicle", "Left Scapula", "Right Scapula", "Left Lung",
          "Right Lung", "Left Hilus Pulmonis", "Right Hilus Pulmonis", "Heart", "Aorta",
          "Facies Diaphragmatica", "Mediastinum", "Weasand", "Spine")
MODULES = {"torch": "torch", "torchvision": "torchvision", "torchxrayvision": "torchxrayvision",
           "numpy": "numpy", "scikit-image": "skimage", "matplotlib": "matplotlib",
           "Pillow": "PIL", "pandas": "pandas", "requests": "requests", "tqdm": "tqdm",
           "imageio": "imageio", "langchain-core": "langchain_core", "pydantic": "pydantic"}
METRIC_FIELDS = {"area_pixels", "area_cm2", "centroid", "bbox", "width", "height", "aspect_ratio",
                 "relative_position", "mean_intensity", "std_intensity", "confidence_score"}


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def environment():
    result = {"python": platform.python_version(), "os": platform.system(),
              "os_release": platform.release(), "machine": platform.machine()}
    for package in MODULES:
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = None
    return result


def imported_versions(distributions, modules=None):
    modules = sys.modules if modules is None else modules
    result = {}
    for package, name in MODULES.items():
        module = modules.get(name)
        value = vars(module).get("__version__") if module is not None else None
        value = str(value) if value is not None else None
        metadata = distributions.get(package)
        result[package] = {"module": name, "imported": module is not None, "version": value,
                           "matches_distribution_metadata": value == metadata
                           if value is not None and metadata is not None else None}
    return result


def source_provenance(repo):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args],
                                       stderr=subprocess.DEVNULL, text=True).strip()
    if Path(git("rev-parse", "--show-toplevel")).resolve() != repo:
        raise ValueError("repo must be the official checkout root")
    return {"commit": git("rev-parse", "HEAD"), "working_tree_dirty": bool(git("status", "--porcelain")),
            "tool_sha256": sha256_file(repo / TOOL_RELATIVE), "runner_sha256": sha256_file(__file__)}


def validate_checkpoint(path, expected_sha256, *, expected_bytes=CHECKPOINT_BYTES):
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("A pre-recorded SHA256 is mandatory")
    if not path.is_file() or path.name != CHECKPOINT_NAME or path.stat().st_size != expected_bytes:
        raise ValueError("Checkpoint filename/size differs from the official release asset")
    actual = sha256_file(path)
    if actual != expected_sha256.lower():
        raise ValueError("Checkpoint SHA256 does not match the caller's pre-recorded digest")
    return {"filename": CHECKPOINT_NAME, "bytes": path.stat().st_size, "sha256": actual,
            "source_url": CHECKPOINT_URL, "upstream_digest_available": False,
            "digest_provenance": "caller_pinned_local_download_sha256"}


def offline_load_recorder(original, checkpoint, records):
    def load(source, *args, **kwargs):
        if not isinstance(source, (str, os.PathLike)) or Path(source).resolve() != checkpoint.resolve():
            raise ValueError("Unexpected checkpoint load denied")
        value = original(source, *args, **kwargs)
        records.append({"filename": CHECKPOINT_NAME, "provenance": "observed_successful_torch_load"})
        return value
    return load


def deny_network(*args, **kwargs):
    raise RuntimeError("Network/download operation forbidden by offline segmentation smoke")


def safe_tool_status(result):
    if not isinstance(result, (list, tuple)) or len(result) != 2 or not isinstance(result[1], dict):
        return {"analysis_status": "invalid_return", "error_details_omitted": True}
    status = result[1].get("analysis_status")
    return {"analysis_status": status if status in ("completed", "failed") else "invalid_status",
            "error_metadata_present": any(key in result[1] for key in ("error", "error_traceback", "error_details")),
            "error_details_omitted": True}


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(value):
        raise ValueError("Metric must be a finite real number")
    return float(value)


def _positive_integer(value):
    if isinstance(value, bool) or not isinstance(value, numbers.Integral) or value < 1:
        raise ValueError("Metric must be a positive integer")
    return int(value)


def _close(actual, expected):
    if not math.isclose(actual, expected, rel_tol=1e-5, abs_tol=1e-6):
        raise ValueError("Returned metric does not reconcile with the official metric contract")


def validate_metrics(raw, image_shape):
    if not isinstance(raw, dict) or set(raw) != METRIC_FIELDS:
        raise ValueError("Unexpected organ metric fields")
    image_h, image_w = image_shape
    area = _positive_integer(raw["area_pixels"])
    width, height = _positive_integer(raw["width"]), _positive_integer(raw["height"])
    bbox = raw["bbox"]
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4 or any(
            isinstance(x, bool) or not isinstance(x, numbers.Integral) for x in bbox):
        raise ValueError("Invalid organ bounding box")
    y0, x0, y1, x1 = map(int, bbox)
    if not (0 <= y0 < y1 <= image_h and 0 <= x0 < x1 <= image_w and
            width == x1 - x0 and height == y1 - y0 and area <= width * height):
        raise ValueError("Organ area/bounding box lies outside the source image")
    centroid = raw["centroid"]
    if not isinstance(centroid, (list, tuple)) or len(centroid) != 2:
        raise ValueError("Invalid organ centroid")
    cy, cx = map(_finite, centroid)
    if not (y0 <= cy < y1 and x0 <= cx < x1):
        raise ValueError("Centroid is outside the organ bounding box")
    relative = raw["relative_position"]
    if not isinstance(relative, dict) or set(relative) != {"top", "left", "center_dist"}:
        raise ValueError("Invalid relative position")
    relative = {key: _finite(value) for key, value in relative.items()}
    _close(relative["top"], cy / image_h)
    _close(relative["left"], cx / image_w)
    _close(relative["center_dist"], math.hypot(cy / image_h - 0.5, cx / image_w - 0.5))
    area_cm2, aspect = _finite(raw["area_cm2"]), _finite(raw["aspect_ratio"])
    _close(area_cm2, area * (0.2 / 10) ** 2)
    _close(aspect, height / width)
    mean, std, confidence = (_finite(raw[key]) for key in ("mean_intensity", "std_intensity", "confidence_score"))
    if not (0 <= mean <= 255 and 0 <= std <= 255 and 0 <= confidence <= 1):
        raise ValueError("Intensity/probability summary is out of range")
    return {"area_pixels": area, "area_cm2": area_cm2, "centroid": [cy, cx], "bbox": [y0, x0, y1, x1],
            "width": width, "height": height, "aspect_ratio": aspect, "relative_position": relative,
            "mean_intensity": mean, "std_intensity": std, "confidence_score": confidence}


def validate_result(result, image_shape, artifact_dir, prediction):
    if safe_tool_status(result)["analysis_status"] != "completed":
        raise ValueError("Official tool did not report completed")
    output, metadata = result
    if not isinstance(output, dict) or set(output) != {"segmentation_image_path", "metrics"}:
        raise ValueError("Unexpected segmentation return fields")
    if metadata.get("requested_organs") != list(ORGANS):
        raise ValueError("All 14 official structures must be requested in their original order")
    if list(metadata.get("original_size", ())) != list(image_shape) or list(metadata.get("model_size", ())) != [512, 512]:
        raise ValueError("Unexpected original/model geometry")
    _close(_finite(metadata.get("pixel_spacing_mm")), 0.2)
    if prediction.get("output_shape") != [1, 14, 512, 512] or not prediction.get("all_logits_finite"):
        raise ValueError("Expected one finite 14-channel model prediction")
    counts, probabilities = prediction.get("positive_pixels", []), prediction.get("mean_probabilities", [])
    if len(counts) != 14 or len(probabilities) != 14 or any(
            type(count) is not int or not 0 <= count <= 512 * 512 for count in counts):
        raise ValueError("Invalid 14-channel mask audit")
    if any(not 0 <= _finite(value) <= 1 for value in probabilities):
        raise ValueError("Invalid 14-channel probability audit")
    metrics = output["metrics"]
    if not isinstance(metrics, dict) or any(name not in ORGANS for name in metrics):
        raise ValueError("Unexpected organ name")
    if list(metrics) != [name for name in ORGANS if name in metrics] or metadata.get("processed_organs") != list(metrics):
        raise ValueError("Processed-organ metadata differs from returned metrics")
    clean, structures = {}, []
    for index, name in enumerate(ORGANS):
        if name in metrics:
            if counts[index] == 0:
                raise ValueError("Empty model mask cannot produce organ metrics")
            clean[name] = validate_metrics(metrics[name], image_shape)
            _close(clean[name]["confidence_score"], probabilities[index])
            status = "metrics_returned"
        else:
            status = "empty_model_mask" if counts[index] == 0 else "no_metrics_after_alignment"
        structures.append({"name": name, "channel": index, "status": status,
                           "positive_pixels_model_grid": counts[index]})
    path = Path(output["segmentation_image_path"]).resolve()
    if (Path(metadata.get("segmentation_image_path", "")).resolve() != path or
            not path.is_relative_to(artifact_dir.resolve()) or not path.is_file() or
            not re.fullmatch(r"segmentation_[0-9a-f]{8}\.png", path.name)):
        raise ValueError("Visualization is missing or outside the new output artifact directory")
    return {"tool_analysis_status": "completed", "model_channel_count": 14,
            "requested_structure_count": 14, "metrics_returned_count": len(clean),
            "all_structures_empty": not any(counts), "structures": structures, "metrics": clean}, path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "image", "output", "checkpoint"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--checkpoint-sha256", required=True, help="Digest fixed before this run; never auto-derived as an expected value")
    parser.add_argument("--device", required=True, help="cpu, cuda, or cuda:N; no automatic CPU fallback")
    args = parser.parse_args(argv)
    repo, image, output, checkpoint = (path.expanduser().resolve() for path in
                                      (args.repo, args.image, args.output, args.checkpoint))
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError:
        print("Output directory unavailable or already exists; nothing overwritten.", file=sys.stderr)
        return 2
    (output / ".gitignore").write_text("*\n", encoding="utf-8")
    artifact_dir = output / "artifacts"
    began = time.monotonic()
    summary = {"schema_version": 1, "kind": "real_segmentation_tool_smoke", "status": "running",
               "offline_only": True, "upstream_inference_parameters_unchanged": True,
               "clinical_correctness_evaluated": False, "segmentation_is_reference_label": False,
               "physical_area_calibrated": False, "pixel_spacing_mm_assumed": 0.2,
               "pixel_spacing_source": "upstream_default_not_measured", "publishable_by_default": False,
               "started_utc": datetime.now(timezone.utc).isoformat(), "environment": environment(),
               "device_requested": args.device, "checkpoint": None, "checkpoint_loads": [],
               "forward_observations": [], "tool_return_metadata": None, "output_checks": None,
               "visualization": None, "init_seconds": None, "inference_seconds": None,
               "peak_cuda_allocated_bytes": None, "peak_cuda_reserved_bytes": None}
    stage, torch, device, cuda_ready = "input_validation", None, None, False
    try:
        if not (repo / TOOL_RELATIVE).is_file() or not image.is_file() or image.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            raise FileNotFoundError("Official source and an existing JPEG/PNG are required")
        summary["image"] = {"sha256": sha256_file(image), "bytes": image.stat().st_size}
        stage = "source_provenance"
        summary["source"] = source_provenance(repo)
        stage = "checkpoint_validation"
        summary["checkpoint"] = validate_checkpoint(checkpoint, args.checkpoint_sha256)
        with ExitStack() as offline:
            offline.enter_context(patch.object(socket.socket, "connect", side_effect=deny_network))
            offline.enter_context(patch.object(socket, "create_connection", side_effect=deny_network))
            offline.enter_context(patch.dict(os.environ, {"MPLBACKEND": "Agg"}))
            sink = offline.enter_context(open(os.devnull, "w"))
            offline.enter_context(redirect_stdout(sink)); offline.enter_context(redirect_stderr(sink))
            stage = "dependency_import"
            import torch
            import numpy as np
            import skimage.io
            import torchxrayvision as xrv
            import matplotlib
            from PIL import Image
            matplotlib.use("Agg")
            stage = "xrv_source_validation"
            if xrv.__version__ != XRV_VERSION:
                raise ValueError("This audited smoke requires TorchXRayVision 1.3.5")
            xrv_root = Path(xrv.__file__).resolve().parent
            source_files = ("__init__.py", "_version.py", "datasets.py", "utils.py",
                            "baseline_models/chestx_det/__init__.py",
                            "baseline_models/chestx_det/ptsemseg/pspnet.py",
                            "baseline_models/chestx_det/ptsemseg/utils.py")
            summary["xrv_source"] = {name: sha256_file(xrv_root / name) for name in source_files}
            summary["xrv_source"]["reference_commit"] = XRV_REFERENCE_COMMIT
            if summary["xrv_source"]["baseline_models/chestx_det/__init__.py"] != XRV_WRAPPER_SHA256:
                raise ValueError("Installed PSPNet wrapper differs from audited 1.3.5 source")
            stage = "image_validation"
            pixels = skimage.io.imread(image)
            if pixels.dtype != np.uint8 or pixels.ndim not in (2, 3) or min(pixels.shape[:2]) < 2:
                raise ValueError("Use an 8-bit grayscale/RGB JPEG/PNG for upstream normalization")
            if pixels.ndim == 3 and pixels.shape[2] not in (1, 3, 4):
                raise ValueError("Unsupported image channels")
            image_shape = list(pixels.shape[:2])
            summary["image"].update(shape=list(pixels.shape), dtype=str(pixels.dtype))
            del pixels
            stage = "device_validation"
            device = torch.device(args.device)
            if device.type not in ("cpu", "cuda"):
                raise ValueError("Only CPU/CUDA are supported")
            if device.type == "cuda":
                if not torch.cuda.is_available():
                    raise RuntimeError("Requested CUDA is unavailable")
                index = torch.cuda.current_device() if device.index is None else device.index
                torch.cuda.set_device(index); device = torch.device("cuda", index)
                torch.cuda.synchronize(device); torch.cuda.reset_peak_memory_stats(device)
                cuda_ready = True
                free, total = torch.cuda.mem_get_info(device)
                summary["gpu"] = {"index": index, "name": torch.cuda.get_device_name(index),
                                  "total_memory_bytes": total, "free_memory_before_init_bytes": free,
                                  "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES")}
            summary["environment"].update(torch_cuda_build=torch.version.cuda,
                                          cudnn_version=torch.backends.cudnn.version(), matplotlib_backend=matplotlib.get_backend())
            stage = "tool_import"
            name = "_medrax_segmentation_smoke"
            spec = importlib.util.spec_from_file_location(name, repo / TOOL_RELATIVE)
            module = importlib.util.module_from_spec(spec); sys.modules[name] = module
            spec.loader.exec_module(module)
            stage = "model_initialization"
            tick = time.monotonic()
            with patch.object(xrv.utils, "get_cache_dir", return_value=str(checkpoint.parent)), \
                    patch.object(xrv.utils, "download", side_effect=deny_network), \
                    patch.object(torch, "load", side_effect=offline_load_recorder(torch.load, checkpoint, summary["checkpoint_loads"])):
                tool = module.ChestXRaySegmentationTool(device=str(device), temp_dir=artifact_dir)
            if cuda_ready:
                torch.cuda.synchronize(device)
            summary["init_seconds"] = time.monotonic() - tick
            if len(summary["checkpoint_loads"]) != 1 or sha256_file(checkpoint) != summary["checkpoint"]["sha256"]:
                raise ValueError("Expected one unchanged verified checkpoint load")
            if tool.organ_map != dict(zip(ORGANS, range(14))) or list(tool.model.targets) != list(ORGANS):
                raise ValueError("Unexpected model/organ channel mapping")
            _close(_finite(tool.pixel_spacing_mm), 0.2)
            summary["upstream_parameters"] = {"organs": None, "center_crop": True,
                                               "resize": [512, 512], "sigmoid_threshold": 0.5,
                                               "pixel_spacing_mm": float(tool.pixel_spacing_mm)}

            def observe_forward(model, inputs, logits):
                shape = list(logits.shape)
                finite = bool(torch.isfinite(logits).all().item())
                if shape != [1, 14, 512, 512] or not finite:
                    raise ValueError("Unexpected/nonfinite PSPNet prediction")
                probabilities = torch.sigmoid(logits.detach())
                summary["forward_observations"].append({
                    "output_shape": shape, "all_logits_finite": finite,
                    "positive_pixels": (probabilities > 0.5).sum(dim=(2, 3))[0].cpu().tolist(),
                    "mean_probabilities": probabilities.mean(dim=(2, 3))[0].cpu().tolist(),
                    "confidence_is_calibrated": False,
                })

            stage = "inference"
            hook = tool.model.register_forward_hook(observe_forward)
            tick = time.monotonic()
            try:
                result = tool.invoke({"image_path": str(image)})
            finally:
                hook.remove()
            if cuda_ready:
                torch.cuda.synchronize(device)
            summary["inference_seconds"] = time.monotonic() - tick
            summary["tool_return_metadata"] = safe_tool_status(result)
            stage = "output_validation"
            if len(summary["forward_observations"]) != 1:
                raise ValueError("Expected exactly one real model forward")
            checks, visualization = validate_result(result, image_shape, artifact_dir, summary["forward_observations"][0])
            with Image.open(visualization) as saved:
                if saved.format != "PNG":
                    raise ValueError("Expected a valid PNG visualization")
                visual_size = list(saved.size); saved.verify()
            summary["output_checks"] = checks
            summary["visualization"] = {"filename": "artifacts/" + visualization.name,
                                         "sha256": sha256_file(visualization), "bytes": visualization.stat().st_size,
                                         "size": visual_size, "contains_source_image": True,
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
            name for name, item in runtime.items() if item["matches_distribution_metadata"] is False]
        summary["environment_sha256"] = json_hash(summary["environment"])
        summary["elapsed_seconds"] = time.monotonic() - began
        summary["finished_utc"] = datetime.now(timezone.utc).isoformat()
        with (output / "summary.json").open("x", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, indent=2, allow_nan=False); handle.write("\n")
    print(json.dumps({"status": summary["status"], "stage": summary.get("failed_stage"), "summary_file": "summary.json"}))
    return 0 if summary["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
