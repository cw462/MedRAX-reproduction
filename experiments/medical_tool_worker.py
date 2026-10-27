"""One isolated official medical tool behind a private JSONL stdio protocol.

Use worker_bridge.WorkerPool. No network/API, generic command execution or
medical fallback output is implemented. Child stderr/private artifacts must
never be passed to the Agent or published as ordinary experiment summaries.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, redirect_stdout
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import time
import traceback
from unittest.mock import patch

if __package__:
    from . import worker_bridge as bridge
else:
    import worker_bridge as bridge


def emit(stream, value):
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    if len(raw) > bridge.MAX_LINE: raise ValueError("Response exceeds the fixed transport size")
    stream.write(raw); stream.flush()


def describe(spec):
    """Import official class metadata without constructing/downloading a model."""
    if spec.kind == "llava":
        import llava_smoke as smoke
        source = smoke.source_provenance(Path(spec.repo).resolve())
        import transformers
        if transformers.__version__ != smoke.TRANSFORMERS_VERSION:
            raise ValueError("Wrong LLaVA Transformers runtime")
        with patch.object(sys, "path", [spec.repo, *sys.path]):
            module = smoke._module(Path(spec.repo).resolve())
        cls = module.LlavaMedTool
    elif spec.kind == "maira":
        import maira_smoke as smoke
        source = smoke.source_provenance(Path(spec.repo).resolve())
        import transformers
        if transformers.__version__ != smoke.TRANSFORMERS_VERSION:
            raise ValueError("Wrong MAIRA Transformers runtime")
        cls = smoke._module(Path(spec.repo).resolve()).XRayPhraseGroundingTool
    else:
        import chexagent_smoke as smoke
        import transformers
        if transformers.__version__ != "4.40.0": raise ValueError("Wrong CheXagent Transformers runtime")
        if (bridge.file_digest(Path(spec.repo) / smoke.TOOL_RELATIVE) != smoke.TOOL_SHA256 or
                bridge.file_digest(spec.asset_manifest) != smoke.APPROVED_MANIFEST_SHA256):
            raise ValueError("CheXagent source/review manifest changed")
        module_spec = importlib.util.spec_from_file_location("_worker_official_chexagent", Path(spec.repo) / smoke.TOOL_RELATIVE)
        module = importlib.util.module_from_spec(module_spec); sys.modules[module_spec.name] = module
        module_spec.loader.exec_module(module)
        cls = module.XRayVQATool
        source = {"filename": smoke.TOOL_RELATIVE, "sha256": smoke.TOOL_SHA256,
                  "review_manifest_sha256": smoke.APPROVED_MANIFEST_SHA256}
    fields = cls.model_fields
    schema = fields["args_schema"].default.model_json_schema()
    return {"name": fields["name"].default, "description": fields["description"].default,
            "parameters": schema, "schema_sha256": bridge.digest(schema),
            "return_direct": fields["return_direct"].default, "source": source,
            "model_loaded": False, "metadata_only_import": True,
            "required_transformers": transformers.__version__}


def deny_network(*args, **kwargs):
    raise RuntimeError("Network is disabled in this real local tool worker")


def invoke_real(spec, tool, provenance, params, images, root, *, first_call, image_hashes):
    import torch
    from PIL import Image
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise ValueError("A worker requires exactly one visible GPU")
    torch.cuda.set_device(0); torch.cuda.synchronize(0); torch.cuda.reset_peak_memory_stats(0)
    started = time.monotonic()
    audit = {"kind": spec.kind, "model_reused": not first_call, "initialization_seconds": 0.0,
             "generation_observations": [], "feature_observations": [], "conversion_observations": [],
             "clinical_evidence": "unknown", "clinical_correctness_evaluated": False,
             "raw_content_logged": False}
    original_open = Image.open
    allowed = {Path(image).resolve() for image in images}
    def image_open(path, *args, **kwargs):
        if (not isinstance(path, (str, os.PathLike)) or Path(path).resolve() not in allowed or
                bridge.file_digest(Path(path).resolve()) != image_hashes[str(Path(path).resolve())]):
            raise ValueError("Image open outside the current explicit path fields")
        return original_open(path, *args, **kwargs)
    if spec.kind == "chexagent":
        import chexagent_smoke as smoke
        smoke.validate_request(images[0], params["prompt"], params.get("max_new_tokens", 512))
        tick = time.monotonic()
        smoke.verify_assets(Path(spec.snapshot), Path(spec.vision_snapshot), Path(spec.asset_manifest), Path(spec.repo))
        audit["asset_verification_seconds"] = time.monotonic() - tick
        measured = {"loader_calls": [], "generate_calls": 0, "visual_forward_calls": 0}
        with patch.object(Image, "open", image_open):
            result = smoke.execute_tool(Path(spec.repo), Path(spec.snapshot), Path(spec.vision_snapshot),
                Path(images[0]), params["prompt"], params.get("max_new_tokens", 512), "cuda:0", measured)
        audit.update(measured, model_reused=False, reloads_each_invocation=True)
        try:
            checks = {"valid": True, **smoke.validate_result(result, measured)}
        except (ValueError, TypeError, KeyError):
            checks = {"valid": False, "clinical_correctness_verified": False}
        audit["output_contract"] = checks
    else:
        if spec.kind == "llava":
            import llava_smoke as smoke
        else:
            import maira_smoke as smoke
            # Validate each request before loading or using the original tool.
            image_info = smoke.validate_image(images[0])
        if tool is None:
            tick = time.monotonic()
            if spec.kind == "llava":
                tool, provenance = smoke.create_llava_tool(spec.repo, cache_dir=spec.cache_dir, device="cuda:0")
            else:
                tool, provenance = smoke.create_maira_tool(spec.repo, cache_dir=spec.cache_dir,
                                                         temp_dir=root / "model_runtime", device="cuda:0")
            torch.cuda.synchronize(0)
            audit["initialization_seconds"] = time.monotonic() - tick
        tick = time.monotonic()
        with ExitStack() as stack:
            stack.enter_context(patch.object(Image, "open", image_open))
            stack.enter_context(patch.object(tool.model, "generate", side_effect=smoke.generation_recorder(
                tool.model.generate, tool.model, audit["generation_observations"])))
            if spec.kind == "maira":
                stack.enter_context(patch.object(tool.model, "get_image_features", side_effect=smoke.feature_recorder(
                    tool.model.get_image_features, audit["feature_observations"])))
                stack.enter_context(patch.object(tool.processor, "convert_output_to_plaintext_or_grounded_sequence",
                    side_effect=smoke.conversion_recorder(tool.processor.convert_output_to_plaintext_or_grounded_sequence,
                                                         audit["conversion_observations"])))
            result = tool.invoke(params)
        torch.cuda.synchronize(0)
        audit["inference_seconds"] = time.monotonic() - tick
        checks = (smoke.validate_observation(result) if spec.kind == "llava" else smoke.validate_observation(
            result, artifact_dir=root / "model_runtime" / "overlays", image_size=image_info["size"]))
        actual = len(audit["generation_observations"]) == 1 and audit["generation_observations"][0]["status"] == "completed"
        if spec.kind == "maira":
            actual = actual and bool(audit["feature_observations"]) and audit["generation_observations"][0]["image_token_count"] == 1369
        audit["output_contract"] = dict(checks, real_generation_observed=actual)
        audit["provenance_sha256"] = bridge.digest(provenance)
        # Source/assets/env are private reviewable evidence; path-free, but large.
        if first_call: audit["initialization_provenance"] = provenance
    audit["total_worker_seconds"] = time.monotonic() - started
    audit["peak_cuda_allocated_bytes"] = torch.cuda.max_memory_allocated(0)
    audit["peak_cuda_reserved_bytes"] = torch.cuda.max_memory_reserved(0)
    return result, audit, tool, provenance


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--describe", action="store_true")
    args = parser.parse_args(argv)
    protocol_out = sys.stdout.buffer
    request = None
    try:
        if bridge.file_digest(args.config) != args.config_sha256: raise ValueError("Private config digest mismatch")
        config = bridge.parse_json(args.config.read_text(encoding="utf-8"))
        if (config.get("protocol") != bridge.PROTOCOL or config.get("worker_script_sha256") != bridge.file_digest(__file__) or
                config.get("bridge_sha256") != bridge.file_digest(bridge.__file__)):
            raise ValueError("Frozen worker/bridge source mismatch")
        spec = bridge.WorkerSpec(**config["spec"]); spec.validate()
        cases = bridge.validate_cases(config["cases"])
        if bridge.digest(cases) != config["cases_sha256"]: raise ValueError("Frozen case-image allowlist mismatch")
        root = Path(config["private_root"]).resolve()
        if root != args.config.resolve().parent: raise ValueError("Private root mismatch")
        with ExitStack() as stack:
            stack.enter_context(redirect_stdout(sys.stderr))
            stack.enter_context(patch.object(socket.socket, "connect", side_effect=deny_network))
            stack.enter_context(patch.object(socket.socket, "connect_ex", side_effect=deny_network))
            stack.enter_context(patch.object(socket, "create_connection", side_effect=deny_network))
            descriptor = describe(spec)
            emit(protocol_out, {"protocol": bridge.PROTOCOL, "event": "ready", "tool_name": bridge.KINDS[spec.kind],
                "descriptor": descriptor, "worker_script_sha256": config["worker_script_sha256"],
                "cases_sha256": config["cases_sha256"]})
            if args.describe: return 0
            tool, provenance, first_call = None, None, True
            while True:
                raw = sys.stdin.buffer.readline(bridge.MAX_LINE + 1)
                if not raw: return 0
                if len(raw) > bridge.MAX_LINE or not raw.endswith(b"\n"): raise ValueError("Invalid request framing")
                request = bridge.parse_json(raw.decode("utf-8"))
                if type(request) is not dict or request.get("protocol") != bridge.PROTOCOL:
                    raise ValueError("Invalid request protocol")
                if request.get("op") == "shutdown": return 0
                required = {"protocol", "op", "request_id", "case_id", "tool_name", "params", "params_sha256", "case_images_sha256"}
                if set(request) != required or request["op"] != "invoke" or request["tool_name"] != descriptor["name"]:
                    raise ValueError("Invalid request envelope")
                rid = request["request_id"]
                if type(rid) is not str or not bridge.REQUEST_ID.fullmatch(rid) or request["case_id"] not in cases:
                    raise ValueError("Invalid request identity")
                allowed = cases[request["case_id"]]
                if request["case_images_sha256"] != bridge.digest(allowed) or request["params_sha256"] != bridge.digest(request["params"]):
                    raise ValueError("Request image/parameter digest mismatch")
                params, images = bridge.validate_request(spec.kind, request["params"], allowed)
                bridge.write_private(root / ("accepted_" + rid + ".private.json"), request)
                result, measured, tool, provenance = invoke_real(spec, tool, provenance, params, images, root,
                                                                 first_call=first_call, image_hashes=allowed)
                # Detect concurrent file replacement even if decoding succeeded.
                bridge.validate_request(spec.kind, params, allowed)
                first_call = False
                tree = bridge.encode_value(result)
                response = {"protocol": bridge.PROTOCOL, "event": "result", "request_id": rid,
                    "tool_name": descriptor["name"], "params_sha256": request["params_sha256"],
                    "result_tree": tree, "result_sha256": bridge.digest(tree), "audit": measured}
                bridge.write_private(root / ("completed_" + rid + ".private.json"), response)
                emit(protocol_out, response)
                if spec.kind == "chexagent": return 0
    except (Exception, KeyboardInterrupt) as exc:
        traceback.print_exc(file=sys.stderr)
        reply = {"protocol": bridge.PROTOCOL, "event": "error", "error_type": type(exc).__name__}
        if type(request) is dict:
            reply.update({key: request.get(key) for key in ("request_id", "tool_name", "params_sha256")})
        try: emit(protocol_out, reply)
        except Exception: pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
