"""Offline, synchronous smoke/factory of unchanged MedRAX MAIRA-2 grounding.

Only use assets obtained under the user's accepted model access conditions.
This script never reads credentials, accepts a gate, downloads or calls an API.
Custom model code is pinned and loaded only from the reviewed local snapshot.
Initialize in a fresh single-GPU worker before unrelated network/API activity.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from unittest.mock import patch

if __package__:
    from . import llava_smoke as audit
else:
    import llava_smoke as audit

REPO_ID = "microsoft/maira-2"
REVISION = "795a2b1cd4a310624b4e3d14b5a23e41fd273deb"
UPSTREAM_COMMIT = audit.UPSTREAM_COMMIT
TOOL_RELATIVE = "medrax/tools/grounding.py"
TOOL_LF_SHA256 = "85f5ed3aa1fdc1f99803c57b1b555006f5a0133f0987885115e5e24830d8f3f0"
TRANSFORMERS_VERSION = "4.51.3"
MAX_NEW_TOKENS = 300
MODEL_SPEC = {"repo_id": REPO_ID, "revision": REVISION, "files": {
    "LICENSE": (10615, "de02ceff33401253712fb08972715c3a33763444f6d6f3f03551f9aa4410df55"),
    "README.md": (14138, "9c27ea4c930e3ff88ea90c9762c0cfc9eaa1547751ef10a0a97c17438c028273"),
    "added_tokens.json": (3723, "c90f72c5037e99a4359da5692148f5dbf9894cc24ecfe03b571910b450058b5a"),
    "chat_template.json": (611, "b595af7fc19045198a91efdcc722d4dd08af31a93492d05d42037b3783ac397a"),
    "config.json": (2401, "dbfdaf64818f638de41522b7bcadaf7607e7f8828356e554191a8d05d6862fc8"),
    "configuration_maira2.py": (1061, "d4af0f69f658d87283d9447668531da9c5389c33f014ee8fad7541b77ec13922"),
    "generation_config.json": (179, "e7a230ce62c6c2d73f0fe3beb08a22becda01b3726017398cf3c39fbb69520d5"),
    "model.safetensors.index.json": (49835, "744f8349aaed9c254c9c86a987df31888129dbdfd97754578376264740035bb9"),
    "modeling_maira2.py": (4747, "b275182782505a5b0bdad1d66890bb0be236e3417edc0fb713171fe5b8e78bb2"),
    "preprocessor_config.json": (560, "f3331f81e0f86fcee8d2867fc706f82109093a0ce982dc4c9d5459659b2cc0fa"),
    "processing_maira2.py": (27708, "aae26529eedf242191ed1d9492fae28236bbf397824d44782e1f840dc7d6fe11"),
    "processor_config.json": (405, "22702ddac06f4a4b66767b8b64dff5a54a658064e8f40d8c967ddc75f9afebfb"),
    "special_tokens_map.json": (552, "4859e5dbde90e059988a0a2136d8df3f2773d4d2fc4c4543690028f0b2166e7f"),
    "tokenizer.json": (3656334, "3ecf4a877bb11bb1ff5318f0bc2d32c8eb072fa06e73b648de0c2e088aec3253"),
    "tokenizer.model": (499723, "9e556afd44213b6bd1be2b850ebbbd98f5481437a8021afaf58ee7fb1818d347"),
    "tokenizer_config.json": (37032, "40d92170570d7304ab47f9bbfebf5179d365ec62093bc24f1f9ab4d4d30bb150"),
    "model-00001-of-00006.safetensors": (4955289768, "e899381d0b4def093d86a599663831282240a57676bd0f6b9646c37c83dce682"),
    "model-00002-of-00006.safetensors": (4857207664, "1309c85392505e2fc421c741b7f3b56f4146f24662e26837220f32d53401aa80"),
    "model-00003-of-00006.safetensors": (4857207704, "95ef725a26f95751c4e181fa44230b5793a297fc84928532797b0c51947e29e7"),
    "model-00004-of-00006.safetensors": (4857207704, "735d55ba903a0a5733af227fea50da1588588a9bf6512b3747acda91184a96df"),
    "model-00005-of-00006.safetensors": (4857207704, "38a7879c501f697864a36ca338866be4d45dfb2fc9b8d4f995d65cc0e984bac5"),
    "model-00006-of-00006.safetensors": (3136688192, "9131ce3ccd96fb1c2654048ba8fb8e4bb9eb131b4395d06c5c1330d0d608fb72"),
}}
CUSTOM_CLASSES = {"model": ("Maira2ForConditionalGeneration", "modeling_maira2.py"),
                  "processor": ("Maira2Processor", "processing_maira2.py"),
                  "config": ("Maira2Config", "configuration_maira2.py")}


def source_provenance(repo):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    if (Path(git("rev-parse", "--show-toplevel")).resolve() != repo or
            git("rev-parse", "HEAD") != UPSTREAM_COMMIT or git("status", "--porcelain")):
        raise ValueError("Use the fixed clean official MedRAX checkout")
    raw = (repo / TOOL_RELATIVE).read_bytes()
    if hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() != TOOL_LF_SHA256:
        raise ValueError("Official grounding tool source differs")
    return {"commit": UPSTREAM_COMMIT, "working_tree_dirty": False, "filename": TOOL_RELATIVE,
            "sha256": hashlib.sha256(raw).hexdigest(), "lf_sha256": TOOL_LF_SHA256,
            "runner_sha256": audit.sha256_file(__file__), "shared_audit_sha256": audit.sha256_file(audit.__file__)}


def local_loader(original, *, kind, snapshot, loads):
    snapshot = Path(snapshot).resolve()

    def load(source, *args, **kwargs):
        if not isinstance(source, (str, os.PathLike)) or not (
                str(source) == REPO_ID or Path(source).resolve() == snapshot):
            raise ValueError("Unexpected MAIRA pretrained source")
        if kwargs.get("revision") not in (None, REVISION) or kwargs.get("code_revision") not in (None, REVISION):
            raise ValueError("Unexpected MAIRA model/code revision")
        if kwargs.get("trust_remote_code") is not True:
            raise ValueError("The original tool must explicitly request the reviewed custom classes")
        changed = dict(kwargs, local_files_only=True)
        for key in ("revision", "code_revision", "cache_dir"):
            changed.pop(key, None)
        if kind == "model":
            changed["use_safetensors"] = True
        value = original(str(snapshot), *args, **changed)
        loads.append({"loader": kind, "local_files_only": True, "reviewed_custom_code_only": True,
                      "completed": True})
        return value
    return load


def loaded_custom_code(tool, dynamic_cache):
    details = []
    for role, obj in (("model", tool.model), ("processor", tool.processor), ("config", tool.model.config)):
        class_name, filename = CUSTOM_CLASSES[role]
        cls = type(obj)
        path = Path(inspect.getfile(cls)).resolve()
        if (cls.__name__ != class_name or path.name != filename or
                not path.is_relative_to(dynamic_cache.resolve()) or
                audit.sha256_file(path) != MODEL_SPEC["files"][filename][1]):
            raise ValueError("Loaded custom class differs from the freshly cached reviewed source")
        details.append({"role": role, "class": class_name, "filename": filename,
                        "sha256": MODEL_SPEC["files"][filename][1]})
    return details


def _module(repo):
    name = "_medrax_fixed_maira_smoke"
    spec = importlib.util.spec_from_file_location(name, repo / TOOL_RELATIVE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def create_maira_tool(repo, *, cache_dir, temp_dir, device="cuda:0"):
    """Load the original 8-bit tool in a fresh worker, without doing inference.

    temp_dir must be new; overlays go in temp_dir/overlays. Reviewed dynamic
    Python files are copied by HF into temp_dir/hf_modules, never fetched.
    Only synchronous invoke is supported by this audited use of the tool.
    """
    repo, cache_dir, temp_dir = (Path(value).expanduser().resolve() for value in (repo, cache_dir, temp_dir))
    source = source_provenance(repo)
    snapshot, asset, states = audit.inspect_snapshot(cache_dir, MODEL_SPEC)
    if any(name.startswith("transformers_modules." + REVISION) for name in sys.modules):
        raise ValueError("Use a fresh worker; a MAIRA dynamic module is already imported")
    temp_dir.mkdir(exist_ok=False)
    (temp_dir / ".gitignore").write_text("*\n", encoding="utf-8")
    dynamic_cache, overlays = temp_dir / "hf_modules", temp_dir / "overlays"
    loads = []
    with audit.offline_context(), patch.dict(os.environ, {"MPLBACKEND": "Agg", "HF_MODULES_CACHE": str(dynamic_cache)}):
        import torch
        import transformers
        import transformers.dynamic_module_utils as dynamic
        import matplotlib
        matplotlib.use("Agg")
        target = audit._device(torch, device)
        if transformers.__version__ != TRANSFORMERS_VERSION:
            raise ValueError("Use the isolated fixed MAIRA Transformers 4.51.3 runtime")
        module = _module(repo)
        with ExitStack() as stack:
            stack.enter_context(patch.object(dynamic, "HF_MODULES_CACHE", str(dynamic_cache)))
            for loader_class, kind in ((module.AutoModelForCausalLM, "model"), (module.AutoProcessor, "processor")):
                wrapper = local_loader(loader_class.from_pretrained, kind=kind, snapshot=snapshot, loads=loads)
                stack.enter_context(patch.object(loader_class, "from_pretrained", side_effect=wrapper))
            # The complete reviewed checkpoint is safetensors; no pickle fallback.
            stack.enter_context(patch.object(torch, "load", side_effect=RuntimeError("Unexpected pickle checkpoint load")))
            tool = module.XRayPhraseGroundingTool(model_path=REPO_ID, cache_dir=str(cache_dir),
                temp_dir=str(overlays), load_in_4bit=False, load_in_8bit=True, device=target)
        audit.assert_files_unchanged(snapshot, states)
        if len(loads) != 2 or {item["loader"] for item in loads} != {"model", "processor"}:
            raise ValueError("Expected exactly two completed local MAIRA loaders")
        if (tool.name != "xray_phrase_grounding" or not getattr(tool.model, "is_loaded_in_8bit", False)
                or getattr(tool.model, "is_loaded_in_4bit", False) or str(tool.model.device) != target):
            raise ValueError("Official tool identity, 8-bit quantization or device mismatch")
        custom = loaded_custom_code(tool, dynamic_cache)
        model_state = {"dtype": str(tool.model.dtype), "device": str(tool.model.device),
                       "is_loaded_in_8bit": True, "vision_dtype": str(next(tool.model.vision_tower.parameters()).dtype),
                       "generation_config": {key: getattr(tool.model.generation_config, key, None) for key in
                           ("do_sample", "num_beams", "max_new_tokens", "max_length", "eos_token_id", "pad_token_id")},
                       "configured_image_seq_length": tool.model.config.image_seq_length}
    provenance = {"kind": "maira", "mode": "original", "tool_name": tool.name, "source": source,
                  "assets": [asset], "asset_loads": loads, "loaded_custom_code": custom,
                  "environment": audit.environment(), "model_state": model_state,
                  "offline_initialization": True, "post_load_asset_check": "size_and_mtime_only",
                  "description_sha256": hashlib.sha256(tool.description.encode()).hexdigest(),
                  "args_schema_sha256": audit.json_hash(tool.args_schema.model_json_schema()),
                  "changed_fields": [], "invocation": "synchronous_only", "factory_did_inference": False,
                  "clinical_evidence": "unknown", "clinical_correctness_evaluated": False,
                  "bounding_boxes_are_reference_labels": False, "private_overlay_subdirectory": "overlays"}
    return tool, provenance


def validate_image(path):
    """Reject the upstream processor's divide-by-zero input without changing it."""
    from PIL import Image
    path = Path(path)
    if not path.is_file() or path.suffix.lower() not in (".png", ".jpg", ".jpeg"):
        raise ValueError("An existing JPEG/PNG is required")
    with Image.open(path) as image:
        if image.format not in ("JPEG", "PNG") or min(image.size) < 2:
            raise ValueError("Invalid image format or dimensions")
        gray = image.convert("L")
        low, high = gray.getextrema()
        if high <= low:
            raise ValueError("Constant grayscale image makes the original processor normalization undefined")
        details = {"sha256": audit.sha256_file(path), "bytes": path.stat().st_size,
                   "size": list(image.size), "format": image.format, "grayscale_nonconstant": True}
        # convert('L') has already decoded the image. PNG.verify() after decode
        # is invalid in Pillow and would reject otherwise valid inputs.
    return details


def _box(value):
    if not isinstance(value, (list, tuple)) or len(value) != 4 or any(
            isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in value):
        raise ValueError("Invalid bounding box numbers")
    x0, y0, x1, y1 = map(float, value)
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError("Bounding box must have positive area within the normalized image")
    return [x0, y0, x1, y1]


def adjusted_box(box, size):
    width, height = size
    crop = min(width, height)
    dx, dy = (width - crop) // 2, (height - crop) // 2
    return [int(box[0] * crop + dx) / width, int(box[1] * crop + dy) / height,
            int(box[2] * crop + dx) / width, int(box[3] * crop + dy) / height]


def validate_observation(result, *, artifact_dir, image_size):
    """Validate execution/geometry only; preserve the actual result for the Agent."""
    safe = {"kind": "maira", "valid": False, "tool_analysis_status": "invalid",
            "clinical_evidence": "unknown", "clinical_correctness_evaluated": False,
            "bounding_boxes_are_reference_labels": False, "step_credit": None, "raw_content_logged": False}
    try:
        if not isinstance(result, (tuple, list)) or len(result) != 2 or not isinstance(result[1], dict):
            raise ValueError("Invalid return structure")
        output, metadata = result
        status = metadata.get("analysis_status")
        if status in ("completed", "completed_no_finding", "failed"):
            safe["tool_analysis_status"] = status
        if status == "failed":
            safe["validation_status"] = "tool_reported_failure"
            return safe
        if status not in ("completed", "completed_no_finding"):
            raise ValueError("Invalid tool status")
        if (len(image_size) != 2 or any(type(n) is not int or n < 2 for n in image_size) or
                list(metadata.get("original_size", ())) != list(image_size) or
                list(metadata.get("model_input_size", ())) != [518, 518]):
            raise ValueError("Unexpected source/model geometry")
        if not isinstance(output, dict) or set(output) != {"predictions", "visualization_path"}:
            raise ValueError("Invalid output fields")
        predictions = output["predictions"]
        if not isinstance(predictions, list):
            raise ValueError("Invalid prediction list")
        if status == "completed_no_finding":
            if predictions or output["visualization_path"] is not None:
                raise ValueError("No-finding contract disagrees with actual output")
            safe.update(valid=True, validation_status="output_contract_passed", prediction_count=0,
                        box_count=0, no_finding_is_verified_negative=False, overlay=None)
            return safe
        if not predictions:
            raise ValueError("Completed grounding requires a nonempty grounded prediction")
        hashes, total = [], 0
        for item in predictions:
            if not isinstance(item, dict) or set(item) != {"phrase", "bounding_boxes"} or not isinstance(item["phrase"], str) or not item["phrase"].strip():
                raise ValueError("Invalid grounded phrase")
            mapping = item["bounding_boxes"]
            if not isinstance(mapping, dict) or set(mapping) != {"model_coordinates", "image_coordinates"}:
                raise ValueError("Invalid coordinate fields")
            model, original = mapping["model_coordinates"], mapping["image_coordinates"]
            if not isinstance(model, list) or not isinstance(original, list) or not model or len(model) != len(original):
                raise ValueError("Model/source box counts differ")
            for raw, aligned in zip(model, original):
                raw, aligned = _box(raw), _box(aligned)
                if any(not math.isclose(a, b, abs_tol=1e-8, rel_tol=1e-8)
                       for a, b in zip(adjusted_box(raw, image_size), aligned)):
                    raise ValueError("Source coordinates disagree with original center-crop adjustment")
            total += len(model)
            hashes.append({"phrase_sha256": hashlib.sha256(item["phrase"].encode()).hexdigest(),
                           "phrase_characters": len(item["phrase"]), "box_count": len(model)})
        raw_path = output["visualization_path"]
        if not isinstance(raw_path, (str, os.PathLike)):
            raise ValueError("Missing grounding visualization")
        path = Path(raw_path).resolve()
        if (not path.is_file() or not path.is_relative_to(Path(artifact_dir).resolve()) or
                not re.fullmatch(r"grounding_[0-9a-f]{8}\.png", path.name)):
            raise ValueError("Overlay missing or outside the private artifact directory")
        with path.open("rb") as handle:
            if handle.read(8) != b"\x89PNG\r\n\x1a\n":
                raise ValueError("Overlay has no PNG signature")
        safe.update(valid=True, validation_status="output_contract_passed", prediction_count=len(predictions),
                    box_count=total, predictions_sha256=audit.json_hash(predictions), phrases=hashes,
                    overlay={"bytes": path.stat().st_size, "sha256": audit.sha256_file(path),
                             "contains_source_image": True, "publishable_by_default": False,
                             "png_signature_checked": True})
    except (ValueError, TypeError, KeyError, OSError, UnicodeError):
        safe["validation_status"] = "invalid_output_contract"
    return safe


def generation_recorder(original, model, observations):
    def generate(*args, **kwargs):
        if args or kwargs.get("max_new_tokens") != MAX_NEW_TOKENS or kwargs.get("use_cache") is not True:
            raise ValueError("Official grounding generation arguments changed")
        if set(kwargs) - {"input_ids", "attention_mask", "pixel_values", "max_new_tokens", "use_cache"}:
            raise ValueError("Unexpected grounding model input")
        ids, pixels = kwargs["input_ids"], kwargs["pixel_values"]
        if len(ids.shape) != 2 or ids.shape[0] != 1 or list(pixels.shape) != [1, 3, 518, 518]:
            raise ValueError("Unexpected input tensor geometry")
        prefix = ids.shape[1]
        eos = audit._token_ids(model.generation_config.eos_token_id)
        image_count = int((ids == model.config.image_token_index).sum().item())
        item = {"status": "started", "input_token_shape": list(ids.shape), "pixel_shape": list(pixels.shape),
                "image_token_count": image_count, "parameters": {"max_new_tokens": MAX_NEW_TOKENS, "use_cache": True},
                "eos_token_ids": eos, "pad_token_ids": audit._token_ids(model.generation_config.pad_token_id),
                "do_sample": model.generation_config.do_sample, "num_beams": model.generation_config.num_beams,
                "raw_tokens_logged": False}
        observations.append(item)
        try:
            output = original(**kwargs)
            if len(output.shape) != 2 or output.shape[0] != 1 or not prefix < output.shape[1] <= prefix + MAX_NEW_TOKENS:
                raise ValueError("Invalid generated sequence length")
            rows, inputs = output.detach().cpu().tolist()[0], ids.detach().cpu().tolist()[0]
            if rows[:prefix] != inputs:
                raise ValueError("Generated sequence does not preserve the input prefix")
            new = rows[prefix:]
            item.update(status="completed", output_shape=list(output.shape), new_token_count=len(new),
                        prefix_preserved=True, eos_in_new_tokens=any(token in eos for token in new),
                        last_token_is_eos=new[-1] in eos, reached_new_token_cap=len(new) == MAX_NEW_TOKENS,
                        termination_flags_are_not_semantic_completeness=True)
            return output
        except Exception as exc:
            item.update(status="failed", error_type=type(exc).__name__)
            raise
    return generate


def feature_recorder(original, observations):
    def features(*args, **kwargs):
        output = original(*args, **kwargs)
        shape = list(output.shape)
        if shape != [1, 1369, 4096]:
            raise ValueError("Unexpected actual MAIRA projected image feature shape")
        observations.append({"projected_image_features_shape": shape, "raw_features_logged": False})
        return output
    return features


def conversion_recorder(original, observations):
    def convert(text, *args, **kwargs):
        item = {"decoded_sha256": hashlib.sha256(text.encode()).hexdigest(), "decoded_characters": len(text),
                "raw_text_logged": False, "status": "started"}
        observations.append(item)
        try:
            result = original(text, *args, **kwargs)
            item.update(status="completed", returned_type=type(result).__name__)
            if isinstance(result, list):
                item["returned_items"] = len(result)
            return result
        except Exception as exc:
            item.update(status="failed", error_type=type(exc).__name__)
            raise
    return convert


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "cache-dir", "image", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--phrase", required=True, help="Inference phrase only, never a reference answer")
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args(argv)
    output = args.output.expanduser().resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError:
        print("Output directory already exists or is unavailable; nothing overwritten.", file=sys.stderr)
        return 2
    (output / ".gitignore").write_text("*\n", encoding="utf-8")
    began = time.monotonic()
    summary = {"schema_version": 1, "kind": "real_official_maira_grounding_smoke", "status": "running",
               "started_utc": datetime.now(timezone.utc).isoformat(), "offline_only": True,
               "publishable_by_default": False, "clinical_evidence": "unknown", "clinical_correctness_evaluated": False,
               "bounding_boxes_are_reference_labels": False, "upstream_parameters_unchanged": True,
               "generation_observations": [], "feature_observations": [], "conversion_observations": [],
               "init_seconds": None, "inference_seconds": None, "output_checks": None}
    stage, torch, cuda_ready = "input_validation", None, False
    try:
        if not args.phrase.strip() or "\x00" in args.phrase:
            raise ValueError("A nonempty inference phrase is required")
        image = args.image.expanduser().resolve()
        summary["phrase"] = {"sha256": hashlib.sha256(args.phrase.encode()).hexdigest(), "characters": len(args.phrase)}
        with audit.offline_context():
            summary["image"] = validate_image(image)
            stage = "device_validation"
            import torch
            device = audit._device(torch, args.device)
            torch.cuda.synchronize(0); torch.cuda.reset_peak_memory_stats(0)
            cuda_ready = True
            free, total = torch.cuda.mem_get_info(0)
            summary["gpu"] = {"logical_device": device, "name": torch.cuda.get_device_name(0),
                              "free_before_init_bytes": free, "total_bytes": total, "torch_cuda_build": torch.version.cuda}
            stage = "model_initialization"
            tick = time.monotonic()
            tool, provenance = create_maira_tool(args.repo, cache_dir=args.cache_dir, temp_dir=output / "worker", device=device)
            torch.cuda.synchronize(0)
            summary["init_seconds"] = time.monotonic() - tick
            summary["provenance"] = provenance
            stage = "inference"
            tick = time.monotonic()
            with ExitStack() as stack:
                stack.enter_context(patch.object(tool.model, "generate", side_effect=generation_recorder(
                    tool.model.generate, tool.model, summary["generation_observations"])))
                stack.enter_context(patch.object(tool.model, "get_image_features", side_effect=feature_recorder(
                    tool.model.get_image_features, summary["feature_observations"])))
                stack.enter_context(patch.object(tool.processor, "convert_output_to_plaintext_or_grounded_sequence",
                    side_effect=conversion_recorder(tool.processor.convert_output_to_plaintext_or_grounded_sequence,
                                                    summary["conversion_observations"])))
                result = tool.invoke({"image_path": str(image), "phrase": args.phrase, "max_new_tokens": MAX_NEW_TOKENS})
            torch.cuda.synchronize(0)
            summary["inference_seconds"] = time.monotonic() - tick
            # Preserve both successful and failed original tool returns privately.
            with (output / "tool_result.private.json").open("x", encoding="utf-8") as handle:
                json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
            summary["private_tool_result_file"] = "tool_result.private.json"
            stage = "output_validation"
            checks = validate_observation(result, artifact_dir=output / "worker" / "overlays",
                                          image_size=summary["image"]["size"])
            summary["output_checks"] = checks
            generated, features = summary["generation_observations"], summary["feature_observations"]
            if (not checks["valid"] or len(generated) != 1 or generated[0]["status"] != "completed" or
                    not features or generated[0]["image_token_count"] != 1369 or
                    len(summary["conversion_observations"]) != 1 or summary["conversion_observations"][0]["status"] != "completed"):
                raise ValueError("Real generation/image/grounding return contract did not pass")
            summary["status"] = "completed"
    except (Exception, KeyboardInterrupt) as exc:
        summary.update(status="failed", failed_stage=stage, error_type=type(exc).__name__)
    finally:
        if cuda_ready:
            try:
                summary["peak_cuda_allocated_bytes"] = torch.cuda.max_memory_allocated(0)
                summary["peak_cuda_reserved_bytes"] = torch.cuda.max_memory_reserved(0)
            except Exception:
                pass
        summary["environment"] = audit.environment()
        summary["environment_sha256"] = audit.json_hash(summary["environment"])
        summary["elapsed_seconds"] = time.monotonic() - began
        summary["finished_utc"] = datetime.now(timezone.utc).isoformat()
        with (output / "summary.json").open("x", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, indent=2, allow_nan=False); handle.write("\n")
    print(json.dumps({"status": summary["status"], "stage": summary.get("failed_stage"), "summary_file": "summary.json"}))
    return 0 if summary["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
