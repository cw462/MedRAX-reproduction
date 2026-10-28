"""Offline smoke/factory for the local MedRAX LLaVA-Med tool.

Use a standard HF cache with both fixed snapshots below. No downloads, CPU
fallback, clinical validation, or Agent benchmark are performed by this script.
Initialize serially before API activity: loader/network patches are process-wide.
The original main.py 8-bit setting, tool description and generation args remain.
Requires one visible CUDA GPU because the upstream tool uses bare .cuda().
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import time
from unittest.mock import patch

UPSTREAM_COMMIT = "dae30e2f136ef0b2a40885a4c335386e9ffad052"
TOOL_RELATIVE = "medrax/tools/llava_med.py"
TRANSFORMERS_VERSION = "4.45.2"
SOURCE_SHA256 = {
    TOOL_RELATIVE: "4c432a4bc9916b291e13ed232dfc5c056ad797c6256ec753d0dce26b6b297729",
    "medrax/llava/model/builder.py": "dc9bcecc082c0fb5171475fed2f776a0a9090d3dad99f13fdaae8ea6d1d93afa",
    "medrax/llava/model/language_model/llava_mistral.py": "7f4467b1112d0fb391858ca1e35212f237da87bf32325ccd192922686d0c430c",
    "medrax/llava/model/llava_arch.py": "7440e9f94b578bb29476803f2fdfe4bc817e9888058230904b3465139e285ccf",
    "medrax/llava/model/multimodal_encoder/clip_encoder.py": "836eec65502494c39e9726b10a49c82a3b906bd6b5e216dda7552fc94c45da67",
    "medrax/llava/model/multimodal_encoder/builder.py": "05bdb9ead8befee9b11efc84a98e11df387cb3ca1a95665aeb6eb173266ca64b",
    "medrax/llava/model/multimodal_projector/builder.py": "58652888186802efcf3d7e52745703395d614df16ef3a998e0ccbd6df0b804da",
    "medrax/llava/mm_utils.py": "417851d49f0e3b8d38320e3cc199feb9aa16d86bc1b42b00cacad43200ec78cd",
    "medrax/llava/conversation.py": "fade6632c9e171e597e21952274c5f71a313cad82369bbc2f9fe3c5f4058cf87",
    "medrax/llava/constants.py": "05caa532060f61b30cada5ba23da0f4bf640c898298913f768653583482e5901",
}
# Weight digests are the official Hub LFS SHA256 values at the fixed revisions.
# Small-file digests were independently computed from those revision URLs.
MODEL_SPECS = {
    "llava": {
        "repo_id": "microsoft/llava-med-v1.5-mistral-7b",
        "revision": "91bb16c122001ddc9cf1fd36ce1dae09448943a2",
        "files": {
            "config.json": (1407, "f6ae889c5488ef86895e78f641339062962dd6b434666019fa119ab09d2bd8b3"),
            "generation_config.json": (111, "741acba7f5e235dac0e6865ecc212bbadb1ab1d6d853de7d759268cb62aaf2b4"),
            "model.safetensors.index.json": (73152, "d5ecec60dba218c6621cfa524d739de942b4552bcbb25efe63848c18a731b2f6"),
            "special_tokens_map.json": (438, "719833ff26ac897a3ec8ed946028a135de2a351470af59b4008744ab1f0ee9b7"),
            "tokenizer_config.json": (1463, "5b219f9212f7263269898c799cc9d9be2326e853bf1e497f1c412f3a274d0597"),
            "tokenizer.model": (493443, "dadfd56d766715c61d2ef780a525ab43b8e6da4de6865bda3d95fdef5e134055"),
            "model-00001-of-00004.safetensors": (4943162336, "ef2190dc6c2a940e60f03f5fdb4dddb2320eb87801aeca5c40b0a28ce8aa420e"),
            "model-00002-of-00004.safetensors": (4999819336, "2b229607fecd98b8111320178e5bf3e2c527b05a942c85d65b5b507c76c1ed00"),
            "model-00003-of-00004.safetensors": (4927408360, "12b18ecdf8924d5fe28ada797fe6697fa60e62cba630759fbeb52975b261c4e2"),
            "model-00004-of-00004.safetensors": (262144128, "1d2063fcd429d3f0f0a8a091b0522f0e02f2d85fe0e5b0eeb4ae168183a603bc"),
        },
    },
    "clip": {
        "repo_id": "openai/clip-vit-large-patch14-336",
        "revision": "ce19dc912ca5cd21c8a653c79e251e808ccabcd1",
        "files": {
            "config.json": (4757, "51b1c14aabcdf639c4a0370eeda1010b773bbe1df78319c7d0f5882c22ac0ac0"),
            "preprocessor_config.json": (316, "d253881f65322dc546df59cf925a408e5538b8ecb5a1b496cdd36af9992686d4"),
            "pytorch_model.bin": (1711974081, "c6032c2e0caae3dc2d4fba35535fa6307dbb49df59c7e182b1bc4b3329b81801"),
        },
    },
}
GENERATION_ARGS = {"do_sample": False, "temperature": 0.2, "max_new_tokens": 500, "use_cache": True}
PACKAGES = {"torch": "torch", "torchvision": "torchvision", "transformers": "transformers",
            "huggingface-hub": "huggingface_hub", "tokenizers": "tokenizers",
            "safetensors": "safetensors", "accelerate": "accelerate", "bitsandbytes": "bitsandbytes",
            "sentencepiece": "sentencepiece", "protobuf": "google.protobuf", "numpy": "numpy",
            "Pillow": "PIL", "langchain-core": "langchain_core", "pydantic": "pydantic"}


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def environment():
    result = {"python": platform.python_version(), "os": platform.system(), "machine": platform.machine()}
    runtime = {}
    for package, module_name in PACKAGES.items():
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = None
        module = sys.modules.get(module_name)
        raw = getattr(module, "__version__", None) if module is not None else None
        version = str(raw) if raw is not None else None
        runtime[package] = {"imported": module is not None, "version": version,
                            "matches_distribution_metadata": version == result[package]
                            if version is not None and result[package] is not None else None}
    result["imported_runtime_versions"] = runtime
    return result


def source_provenance(repo):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    if Path(git("rev-parse", "--show-toplevel")).resolve() != repo:
        raise ValueError("Use the fixed official checkout root")
    files = []
    for name, expected in SOURCE_SHA256.items():
        raw = (repo / name).read_bytes()
        canonical = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
        files.append({"filename": name, "sha256": hashlib.sha256(raw).hexdigest(), "lf_sha256": canonical})
    return {"commit": git("rev-parse", "HEAD"), "working_tree_dirty": bool(git("status", "--porcelain")), "files": files,
            "hash_policy": "record_only",
            "runner_sha256": sha256_file(Path(__file__))}


def inspect_snapshot(cache_dir, spec):
    """Require complete local weights and configs; hashes never gate loading."""
    snapshot = (Path(cache_dir) / ("models--" + spec["repo_id"].replace("/", "--")) /
                "snapshots" / spec["revision"])
    if not snapshot.is_dir():
        raise FileNotFoundError("Fixed local snapshot is unavailable")
    allowed = set(spec["files"]) | {"README.md", "LICENSE", "LICENSE.txt", ".gitattributes"}
    if any(path.name not in allowed or not path.is_file() for path in snapshot.iterdir()):
        raise ValueError("Snapshot contains unverified additional runtime artifacts")
    artifacts, states = [], {}
    for name, (size, expected) in spec["files"].items():
        path = snapshot / name
        if not path.is_file():
            raise FileNotFoundError("Fixed snapshot is incomplete")
        before = path.stat()
        weight = name.endswith((".safetensors", ".bin"))
        if before.st_size <= 0 or (weight and before.st_size != size):
            raise ValueError("Local artifact download is incomplete")
        after = path.stat()
        states[name] = (after.st_size, after.st_mtime_ns)
        artifacts.append({"filename": name, "bytes": after.st_size,
                          "sha256": None if weight else sha256_file(path)})
    if "model.safetensors.index.json" in spec["files"]:
        index = json.loads((snapshot / "model.safetensors.index.json").read_text(encoding="utf-8"))
        shards = {name for name in spec["files"] if name.endswith(".safetensors")}
        if not index.get("weight_map") or set(index["weight_map"].values()) != shards:
            raise ValueError("Weight index does not describe exactly the fixed shards")
    manifest = {"repo_id": spec["repo_id"], "revision": spec["revision"], "files": artifacts,
                "reference_weight_digest_source": "official_hub_lfs_sha256_at_reference_revision",
                "small_file_digest_source": "actual_local_bytes",
                "all_required_artifacts_verified": False, "checksum_verification": "skipped_by_user",
                "hash_policy": "record_only"}
    manifest["manifest_sha256"] = json_hash(manifest)
    return snapshot.resolve(), manifest, states


def assert_files_unchanged(snapshot, states):
    """Return whether stat metadata changed; changes no longer abort a run."""
    return all((path.stat().st_size, path.stat().st_mtime_ns) == before
               for name, before in states.items() for path in [snapshot / name])


def deny_network(*args, **kwargs):
    raise RuntimeError("This tool requires complete fixed local assets; network is disabled")


@contextmanager
def offline_context():
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                                                    "HF_HUB_DISABLE_TELEMETRY": "1"}))
        stack.enter_context(patch.object(socket.socket, "connect", side_effect=deny_network))
        stack.enter_context(patch.object(socket, "create_connection", side_effect=deny_network))
        sink = stack.enter_context(open(os.devnull, "w"))
        stack.enter_context(redirect_stdout(sink)); stack.enter_context(redirect_stderr(sink))
        yield


def local_loader(original, *, role, kind, snapshot, loads):
    """Map only an exact repository ID or its local path; preserve kwargs."""
    snapshot = Path(snapshot).resolve()
    repo_id = MODEL_SPECS[role]["repo_id"]
    revision = MODEL_SPECS[role]["revision"]

    def load(source, *args, **kwargs):
        if not isinstance(source, (str, os.PathLike)) or not (
            str(source) == repo_id or Path(source).resolve() == snapshot
        ):
            raise ValueError("Unexpected pretrained source")
        if kwargs.get("revision") not in (None, revision):
            raise ValueError("Unexpected pretrained revision")
        if kwargs.get("trust_remote_code") not in (None, False):
            raise ValueError("Unreviewed remote model code is disallowed")
        kwargs = dict(kwargs)
        kwargs.update(local_files_only=True, trust_remote_code=False)
        kwargs.pop("revision", None)
        kwargs.pop("cache_dir", None)
        if kind == "model":
            # These are the only formats in the verified pinned snapshots.
            kwargs["use_safetensors"] = role == "llava"
        value = original(str(snapshot), *args, **kwargs)
        loads.append({"role": role, "loader": kind, "local_files_only": True, "completed": True})
        return value

    return load


def _torch_loader(original, allowed, loads):
    def load(path, *args, **kwargs):
        if not isinstance(path, (str, os.PathLike)) or Path(path).resolve() != allowed:
            raise ValueError("Unexpected pickle checkpoint load")
        value = original(path, *args, **kwargs)
        loads.append({"role": "clip", "loader": "torch.load", "completed": True})
        return value
    return load


def _device(torch, device):
    if device not in ("cuda", "cuda:0") or not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise ValueError("Expose exactly one CUDA GPU and request cuda:0; upstream uses bare .cuda()")
    torch.cuda.set_device(0)
    return "cuda:0"


def _module(repo):
    # Absolute medrax.llava imports must all come from the same pinned checkout.
    for name, module in list(sys.modules.items()):
        if name == "medrax" or name.startswith("medrax."):
            raw = getattr(module, "__file__", None)
            if raw is None or not Path(raw).resolve().is_relative_to(repo):
                raise ValueError("An imported MedRAX package comes from a different source tree")
    name = "_medrax_fixed_llava_smoke"
    spec = importlib.util.spec_from_file_location(name, repo / TOOL_RELATIVE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def create_llava_tool(repo, *, cache_dir, device="cuda:0"):
    """Return the original real tool and safe provenance; perform no inference.

    Both model snapshots must already exist. This pins Transformers 4.45.2 as
    the initial isolated-runtime candidate; actual compatibility requires the
    real smoke. It does not claim that imports or inference have passed.
    """
    repo, cache_dir = Path(repo).resolve(), Path(cache_dir).expanduser().resolve()
    source = source_provenance(repo)
    assets, snapshots, states = [], {}, {}
    for role, spec in MODEL_SPECS.items():
        snapshot, manifest, state = inspect_snapshot(cache_dir, spec)
        snapshots[role], states[role] = snapshot, state
        assets.append({"role": role, **manifest})
    loads = []
    with offline_context(), patch.object(sys, "path", [str(repo), *sys.path]):
        import torch
        import transformers
        target = _device(torch, device)
        if transformers.__version__ != TRANSFORMERS_VERSION:
            raise ValueError("Use the explicitly pinned LLaVA Transformers runtime")
        module = _module(repo)
        builder = importlib.import_module("medrax.llava.model.builder")
        clip = importlib.import_module("medrax.llava.model.multimodal_encoder.clip_encoder")
        with ExitStack() as stack:
            for loader_class, role, kind in (
                (builder.AutoTokenizer, "llava", "tokenizer"),
                (builder.LlavaMistralForCausalLM, "llava", "model"),
                (clip.CLIPVisionConfig, "clip", "config"),
                (clip.CLIPImageProcessor, "clip", "processor"),
                (clip.CLIPVisionModel, "clip", "model"),
            ):
                wrapper = local_loader(loader_class.from_pretrained, role=role, kind=kind,
                                       snapshot=snapshots[role], loads=loads)
                stack.enter_context(patch.object(loader_class, "from_pretrained", side_effect=wrapper))
            stack.enter_context(patch.object(torch, "load", side_effect=_torch_loader(
                torch.load, (snapshots["clip"] / "pytorch_model.bin").resolve(), loads)))
            # Keep repository ID for builder's llava/mistral string branch.
            tool = module.LlavaMedTool(model_path=MODEL_SPECS["llava"]["repo_id"], cache_dir=str(cache_dir),
                                       device=target, torch_dtype=torch.bfloat16, low_cpu_mem_usage=True,
                                       load_in_4bit=False, load_in_8bit=True)
        for role in MODEL_SPECS:
            assert_files_unchanged(snapshots[role], states[role])
        expected = {("llava", "tokenizer"), ("llava", "model"), ("clip", "config"),
                    ("clip", "processor"), ("clip", "model"), ("clip", "torch.load")}
        if {(entry["role"], entry["loader"]) for entry in loads} != expected:
            raise ValueError("Required fixed LLaVA/CLIP loads were not all observed")
        if (tool.name != "llava_med_qa" or not getattr(tool.model, "is_loaded_in_8bit", False)
                or getattr(tool.model, "is_loaded_in_4bit", False)):
            raise ValueError("Tool name or original main.py 8-bit quantization setting differs")
        if str(tool.model.device) != target or not tool.model.get_vision_tower().is_loaded:
            raise ValueError("Both real language and vision models must be loaded on the requested device")
        model_state = {"dtype": str(tool.model.dtype), "device": str(tool.model.device),
                       "is_loaded_in_8bit": True, "context_len": int(tool.context_len),
                       "vision_dtype": str(tool.model.get_vision_tower().dtype),
                       "vision_device": str(tool.model.get_vision_tower().device)}
    provenance = {"tool_name": tool.name, "mode": "original", "source": source, "assets": assets,
                  "asset_loads": loads, "environment": environment(), "model_state": model_state,
                  "offline_initialization": True, "post_load_asset_check": "size_and_mtime_only",
                  "generation_args": dict(GENERATION_ARGS), "conversation_template": "vicuna_v1",
                  "description_sha256": hashlib.sha256(tool.description.encode()).hexdigest(),
                  "args_schema_sha256": json_hash(tool.args_schema.model_json_schema()),
                  "changed_fields": [], "clinical_evidence": "unknown",
                  "clinical_correctness_evaluated": False, "factory_did_inference": False}
    return tool, provenance


def validate_observation(result):
    """A valid complete string is a return-contract check, never medical truth."""
    details = {"kind": "llava", "valid": False, "tool_analysis_status": "invalid",
               "clinical_evidence": "unknown", "clinical_correctness_evaluated": False,
               "semantic_completeness_evaluated": False, "step_credit": None, "raw_content_logged": False}
    if not isinstance(result, (tuple, list)) or len(result) != 2 or not isinstance(result[1], dict):
        details["validation_status"] = "invalid_output_contract"
        return details
    answer, metadata = result
    status = metadata.get("analysis_status")
    if status in ("completed", "failed"):
        details["tool_analysis_status"] = status
    if status == "failed":
        details["validation_status"] = "tool_reported_failure"
        return details
    if status != "completed" or not isinstance(answer, str) or not answer.strip() or "\x00" in answer:
        details["validation_status"] = "invalid_output_contract"
        return details
    raw = answer.encode("utf-8")
    details.update(valid=True, validation_status="output_contract_passed", answer_characters=len(answer),
                   answer_utf8_bytes=len(raw), answer_sha256=hashlib.sha256(raw).hexdigest())
    return details


def _token_ids(value):
    if value is None:
        return []
    values = value if isinstance(value, (tuple, list)) else [value]
    if any(type(item) is not int or item < 0 for item in values):
        raise ValueError("Invalid configured token ID")
    return list(values)


def generation_recorder(original, model, observations):
    def generate(*args, **kwargs):
        if set(kwargs) != {*GENERATION_ARGS, "images"} or any(kwargs[key] != val for key, val in GENERATION_ARGS.items()):
            raise ValueError("Official generation parameters changed")
        config = model.generation_config
        eos = _token_ids(config.eos_token_id)
        pad = _token_ids(config.pad_token_id)
        item = {"parameters": dict(GENERATION_ARGS), "num_beams": getattr(config, "num_beams", None),
                "eos_token_ids": eos, "pad_token_ids": pad, "status": "started",
                "input_token_shape": list(args[0].shape) if args else None,
                "image_tensor_shape": list(kwargs["images"].shape), "raw_tokens_logged": False}
        observations.append(item)
        try:
            result = original(*args, **kwargs)
            shape = list(result.shape)
            if len(shape) != 2 or shape[0] != 1 or shape[1] < 1:
                raise ValueError("Unexpected generated sequence shape")
            tokens = result.detach().cpu().tolist()[0]
            item.update(status="completed", output_shape=shape,
                        eos_present=any(token in eos for token in tokens),
                        last_token_is_eos=tokens[-1] in eos,
                        returned_sequence_length_at_least_max_new_tokens=shape[1] >= GENERATION_ARGS["max_new_tokens"],
                        length_flag_is_not_semantic_completeness=True)
            return result
        except Exception as exc:
            item.update(status="failed", error_type=type(exc).__name__)
            raise
    return generate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "cache-dir", "image", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--question", required=True, help="Inference question only; no reference label or explanation")
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args(argv)
    output = args.output.expanduser().resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError:
        print("Output directory already exists or cannot be created; nothing overwritten.", file=sys.stderr)
        return 2
    (output / ".gitignore").write_text("*\n", encoding="utf-8")
    began = time.monotonic()
    summary = {"schema_version": 1, "kind": "real_official_llava_smoke", "status": "running",
               "started_utc": datetime.now(timezone.utc).isoformat(), "offline_only": True,
               "publishable_by_default": False, "clinical_correctness_evaluated": False,
               "clinical_evidence": "unknown", "semantic_completeness_evaluated": False,
               "upstream_generation_parameters_unchanged": True, "generation_observations": [],
               "init_seconds": None, "inference_seconds": None, "output_checks": None}
    stage, torch, cuda_ready = "input_validation", None, False
    try:
        image = args.image.expanduser().resolve()
        if (not image.is_file() or image.suffix.lower() not in (".png", ".jpg", ".jpeg")
                or not args.question.strip() or "\x00" in args.question):
            raise ValueError("An existing JPEG/PNG and a nonempty question are required")
        summary["image"] = {"sha256": sha256_file(image), "bytes": image.stat().st_size}
        summary["question"] = {"sha256": hashlib.sha256(args.question.encode()).hexdigest(),
                               "characters": len(args.question)}
        with offline_context():
            stage = "image_validation"
            from PIL import Image
            with Image.open(image) as pixels:
                if pixels.format not in ("JPEG", "PNG") or min(pixels.size) < 2:
                    raise ValueError("Invalid image format or dimensions")
                summary["image"].update(format=pixels.format, size=list(pixels.size), mode=pixels.mode)
                pixels.verify()
            stage = "device_validation"
            import torch
            target = _device(torch, args.device)
            torch.cuda.synchronize(0); torch.cuda.reset_peak_memory_stats(0)
            cuda_ready = True
            free, total = torch.cuda.mem_get_info(0)
            summary["gpu"] = {"logical_device": target, "name": torch.cuda.get_device_name(0),
                              "visible_device_count": 1, "free_before_init_bytes": free, "total_bytes": total,
                              "torch_cuda_build": torch.version.cuda}
            stage = "model_initialization"
            tick = time.monotonic()
            tool, provenance = create_llava_tool(args.repo, cache_dir=args.cache_dir, device=target)
            torch.cuda.synchronize(0)
            summary["init_seconds"] = time.monotonic() - tick
            summary["provenance"] = provenance
            stage = "inference"
            wrapper = generation_recorder(tool.model.generate, tool.model, summary["generation_observations"])
            tick = time.monotonic()
            with patch.object(tool.model, "generate", side_effect=wrapper):
                result = tool.invoke({"question": args.question, "image_path": str(image)})
            torch.cuda.synchronize(0)
            summary["inference_seconds"] = time.monotonic() - tick
            stage = "output_validation"
            summary["output_checks"] = validate_observation(result)
            if (not summary["output_checks"]["valid"] or len(summary["generation_observations"]) != 1
                    or summary["generation_observations"][0]["status"] != "completed"):
                raise ValueError("The real tool output/generation contract did not pass")
            with (output / "answer.txt").open("x", encoding="utf-8") as handle:
                handle.write(result[0])
            summary["private_answer_file"] = "answer.txt"
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
        summary["environment"] = environment()
        summary["environment_sha256"] = json_hash(summary["environment"])
        summary["elapsed_seconds"] = time.monotonic() - began
        summary["finished_utc"] = datetime.now(timezone.utc).isoformat()
        with (output / "summary.json").open("x", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, indent=2, allow_nan=False); handle.write("\n")
    print(json.dumps({"status": summary["status"], "stage": summary.get("failed_stage"), "summary_file": "summary.json"}))
    return 0 if summary["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
