"""Explicit local MedRAX tool variants; import does not load ML dependencies.

Factories return (real BaseTool, path-free provenance). Initialize serially before
starting any API requests: the temporary offline loader patches are process-wide.
Only the tool's original return is sent to the Agent. validate_observation returns
logging-safe checks, never a replacement medical result or a clinical label.

The first multi-tool experiment should use report mode='original'. 'eos_only' is
an explicit separate factor; it changes decoder EOS only, not beam selection.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from unittest.mock import patch

if __package__:
    from . import classifier_smoke as classifier_audit
    from . import report_smoke as report_audit
    from . import segmentation_smoke as segmentation_audit
else:
    import classifier_smoke as classifier_audit
    import report_smoke as report_audit
    import segmentation_smoke as segmentation_audit

UPSTREAM_COMMIT = "dae30e2f136ef0b2a40885a4c335386e9ffad052"
SOURCE_SHA256 = {
    "classification": "0abc52339ecfccb969e94eaefb49324c3760a71b7421f0c8c5e91c0a83f1c7f0",
    "report": "fdffbcb2e4b5500ea2f72480d5870cf87b783c3285ac47ca50023b6d4726ea59",
    "segmentation": "db54e63e6a5f244998fd76f307f17d13f72b777a3315aca538a783a61965d857",
}
SOURCE_RELATIVE = {"classification": "medrax/tools/classification.py",
                   "report": "medrax/tools/report_generation.py",
                   "segmentation": "medrax/tools/segmentation.py"}
SEGMENTATION_WEIGHT_SHA256 = "019b167eac6b729fc1bb92bbbc185fc1730aaa65819f4e3fe718186cadc044fc"
CLASSIFIER_FILENAME = "nih-pc-chex-mimic_ch-google-openi-kaggle-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt"
CLASSIFIER_WEIGHT_SHA256 = "56524913dd16a906422e8d8b66a7a5c46be1d82eb7ac012d8103776f1aa68899"
CLASSIFIER_WEIGHT_BYTES = 28382008
XRV_MODELS_SHA256 = "554f5b57a2c41e7e35d0b1d4d87ad0b4fa1414818dd87ee86adb21ff225f4984"
CLASSIFIER_LABELS = (
    "Atelectasis", "Consolidation", "Infiltration", "Pneumothorax", "Edema", "Emphysema",
    "Fibrosis", "Effusion", "Pneumonia", "Pleural_Thickening", "Cardiomegaly", "Nodule",
    "Mass", "Hernia", "Lung Lesion", "Fracture", "Lung Opacity", "Enlarged Cardiomediastinum",
)
REPORT_ASSET_MANIFESTS = {
    "findings": "96ba168355d03b7630738e9a710666c73edc91c8880cd0c4b5218d422254bbe6",
    "impression": "a162629bb4e434ec7fc2edbaaf32665701bdbcedb5e04978801364c8560202bf",
}
ORIGINAL_GENERATION_ARGS = {"num_return_sequences": 1, "max_length": 128,
                            "use_cache": True, "beam_width": 2}
CLASSIFIER_DESCRIPTION = (
    "A tool that analyzes a chest X-ray image and returns 18 image-level pathology scores. "
    "Input is the path to a JPG or PNG chest X-ray image. Scores range from 0 to 1 and use "
    "TorchXRayVision op_norm operating-point normalization: each class's operating threshold "
    "maps to 0.5. These values are not direct disease probabilities for this image or population. "
    "The output provides no lesion locations, laterality, bounding boxes, or relationships. "
    "Conditions: Atelectasis, Consolidation, Infiltration, Pneumothorax, Edema, Emphysema, "
    "Fibrosis, Effusion, Pneumonia, Pleural Thickening, Cardiomegaly, Nodule, Mass, Hernia, "
    "Lung Lesion, Fracture, Lung Opacity, and Enlarged Cardiomediastinum."
)
CLASSIFIER_NOTE = (
    "These are image-level op_norm operating-point scores in [0,1], not direct disease "
    "probabilities. Each class's operating threshold maps to 0.5. No location, laterality, "
    "bounding box, or lesion-relationship output is provided; clinical evidence is unverified."
)


def _hash_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _mode(mode, choices):
    if mode not in choices:
        raise ValueError("Unknown explicit tool variant")


def _source(repo, kind):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args],
                                       text=True, stderr=subprocess.DEVNULL).strip()
    if Path(git("rev-parse", "--show-toplevel")).resolve() != repo:
        raise ValueError("Use the upstream checkout root")
    commit, dirty = git("rev-parse", "HEAD"), bool(git("status", "--porcelain"))
    raw = (repo / SOURCE_RELATIVE[kind]).read_bytes()
    canonical = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    return {"commit": commit, "working_tree_dirty": dirty, "relative_file": SOURCE_RELATIVE[kind],
            "tool_sha256": hashlib.sha256(raw).hexdigest(), "tool_lf_sha256": canonical,
            "variant_module_sha256": classifier_audit.sha256_file(Path(__file__)),
            "hash_policy": "record_only"}


def _module(repo, kind):
    name = "_medrax_fixed_variant_" + kind
    spec = importlib.util.spec_from_file_location(name, repo / SOURCE_RELATIVE[kind])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _deny_network(*args, **kwargs):
    raise RuntimeError("Tool initialization requires complete local assets")


@contextmanager
def _offline_initialization():
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                                                    "HF_HUB_DISABLE_TELEMETRY": "1"}))
        stack.enter_context(patch.object(socket.socket, "connect", side_effect=_deny_network))
        stack.enter_context(patch.object(socket, "create_connection", side_effect=_deny_network))
        sink = stack.enter_context(open(os.devnull, "w"))
        stack.enter_context(redirect_stdout(sink)); stack.enter_context(redirect_stderr(sink))
        yield


def _device(torch, device):
    result = torch.device(device)
    if result.type not in ("cpu", "cuda") or (result.type == "cuda" and not torch.cuda.is_available()):
        raise ValueError("Requested CPU/CUDA device is unavailable; no automatic fallback")
    return str(result)


def _schema_hash(tool):
    schema = tool.args_schema
    return _hash_json(schema.model_json_schema() if hasattr(schema, "model_json_schema") else schema.schema())


def _provenance(tool, kind, mode, source, assets, loads, environment):
    return {"kind": kind, "mode": mode, "tool_name": tool.name,
            "description_sha256": hashlib.sha256(tool.description.encode()).hexdigest(),
            "args_schema_sha256": _schema_hash(tool), "source": source,
            "assets_recorded": assets, "hash_policy": "record_only",
            "checksum_verification": "skipped_by_user", "loads_observed": deepcopy(loads),
            "environment": environment, "offline_initialization": True,
            "clinical_evidence": "unknown", "clinical_correctness_evaluated": False,
            "step_credit": None}


def classifier_variant_class(base, mode):
    """Return the unchanged class or a description/note-only explicit subclass."""
    _mode(mode, ("original", "operating_point"))
    if mode == "original":
        return base

    class OperatingPointClassifier(base):
        description: str = CLASSIFIER_DESCRIPTION

        def _run(self, *args, **kwargs):
            result = super()._run(*args, **kwargs)
            if (not isinstance(result, (tuple, list)) or len(result) != 2 or
                    not isinstance(result[1], dict) or result[1].get("analysis_status") != "completed"):
                return result
            values, metadata = result
            # Preserve the same numeric object and every other metadata field.
            changed = dict(metadata, note=CLASSIFIER_NOTE)
            return (values, changed) if isinstance(result, tuple) else [values, changed]

    return OperatingPointClassifier


def _checkpoint_asset(checkpoint, *, expected_bytes=None):
    if not checkpoint.is_file() or checkpoint.stat().st_size <= 0:
        raise FileNotFoundError("A nonempty local checkpoint is required")
    if expected_bytes is not None and checkpoint.stat().st_size != expected_bytes:
        raise ValueError("Local checkpoint download is incomplete")
    return {"filename": checkpoint.name, "bytes": checkpoint.stat().st_size,
            "sha256": None, "checksum_verification": "skipped_by_user"}


def _classifier_asset(checkpoint):
    asset = _checkpoint_asset(checkpoint, expected_bytes=CLASSIFIER_WEIGHT_BYTES)
    asset.update(model_name=classifier_audit.MODEL_NAME)
    return asset


def create_classifier_tool(repo, *, checkpoint, device, mode="original"):
    """Load one fixed local classifier. No call to its image-inference method."""
    _mode(mode, ("original", "operating_point"))
    repo, checkpoint = Path(repo).resolve(), Path(checkpoint).expanduser().resolve()
    source = _source(repo, "classification")
    asset = _classifier_asset(checkpoint)
    loads = []
    with _offline_initialization():
        import torch
        import torchxrayvision as xrv
        target = _device(torch, device)
        xrv_source = Path(xrv.__file__).resolve().parent / "models.py"
        if xrv.__version__ != "1.3.5":
            raise ValueError("The score-semantics variant requires the audited XRV 1.3.5 source")
        module = _module(repo, "classification")
        cls = classifier_variant_class(module.ChestXRayClassifierTool, mode)
        original_load = torch.load

        def load(path, *args, **kwargs):
            if not isinstance(path, (str, os.PathLike)) or Path(path).resolve() != checkpoint:
                raise ValueError("Unexpected classifier checkpoint load")
            value = original_load(path, *args, **kwargs)
            loads.append({"loader": "torch.load", "filename": CLASSIFIER_FILENAME})
            return value

        with patch.object(xrv.utils, "get_cache_dir", return_value=str(checkpoint.parent)), \
                patch.object(xrv.utils, "download", side_effect=_deny_network), \
                patch.object(torch, "load", side_effect=load):
            tool = cls(model_name=classifier_audit.MODEL_NAME, device=target)
        if len(loads) != 1:
            raise ValueError("Expected exactly one classifier load")
        if (tool.name != "chest_xray_classifier" or tuple(tool.model.pathologies) != CLASSIFIER_LABELS or
                tuple(xrv.datasets.default_pathologies) != CLASSIFIER_LABELS):
            raise ValueError("Classifier name or 18-output mapping differs from the fixed model")
    environment = classifier_audit.versions()
    environment["imported_runtime_versions"] = classifier_audit.loaded_module_versions()
    provenance = _provenance(tool, "classification", mode, source, [asset], loads, environment)
    provenance.update(xrv_models_sha256=classifier_audit.sha256_file(xrv_source),
                      factory_overrides_numeric_model_or_preprocessing=False,
                      changed_fields=[] if mode == "original" else ["description", "returned_metadata.note"])
    return tool, provenance


def report_generation_parameters(generation_args, model, tokenizer, mode):
    """Same original parameters, with only explicit decoder EOS substitution."""
    _mode(mode, ("original", "eos_only"))
    if generation_args != ORIGINAL_GENERATION_ARGS:
        raise ValueError("Report generation arguments differ from the fixed upstream defaults")
    params = {**generation_args, "bos_token_id": model.config.bos_token_id,
              "eos_token_id": model.config.eos_token_id, "pad_token_id": model.config.pad_token_id,
              "decoder_start_token_id": tokenizer.cls_token_id}
    if mode == "eos_only":
        eos = model.config.decoder.eos_token_id
        if type(eos) is not int or eos < 0 or eos != tokenizer.sep_token_id:
            raise ValueError("Decoder EOS must be a nonnegative integer matching tokenizer SEP")
        params["eos_token_id"] = eos
    return params


def report_variant_class(base, generation_config_class, mode):
    _mode(mode, ("original", "eos_only"))
    if mode == "original":
        return base

    class EosOnlyReport(base):
        def _generate_report_section(self, pixel_values, model, tokenizer):
            params = report_generation_parameters(self.generation_args, model, tokenizer, "eos_only")
            config = generation_config_class(**params)
            generated = model.generate(pixel_values, generation_config=config)
            return tokenizer.batch_decode(generated, skip_special_tokens=True)[0]

    return EosOnlyReport


def _report_assets(cache_dir):
    snapshots, manifests = {}, []
    for role, spec in report_audit.MODEL_SPECS.items():
        snapshot = (Path(cache_dir) / ("models--" + spec["repo_id"].replace("/", "--")) /
                    "snapshots" / spec["revision"])
        if any(not (snapshot / name).is_file() for name in report_audit.REQUIRED_FILES):
            raise FileNotFoundError("Required report snapshot is incomplete")
        artifacts = []
        for name in report_audit.AUDITED_FILES:
            path = snapshot / name
            if path.is_file():
                weight = name == "model.safetensors"
                if weight and path.stat().st_size != spec["weight_bytes"]:
                    raise ValueError("Report checkpoint download is incomplete")
                artifacts.append({"filename": name, "bytes": path.stat().st_size,
                    "sha256": None if weight else classifier_audit.sha256_file(path)})
        manifest = {"repo_id": spec["repo_id"], "revision": spec["revision"],
                    "files": artifacts, "checksum_verification": "skipped_by_user"}
        manifest["manifest_sha256"] = _hash_json(manifest)
        snapshots[spec["repo_id"]] = (role, snapshot)
        manifests.append({"role": role, **manifest})
    return snapshots, manifests


def create_report_tool(repo, *, cache_dir, device, mode="original"):
    """Load the fixed two-model report tool offline; original is the default."""
    _mode(mode, ("original", "eos_only"))
    repo, cache_dir = Path(repo).resolve(), Path(cache_dir).expanduser().resolve()
    source = _source(repo, "report")
    snapshots, assets = _report_assets(cache_dir)
    loads = []
    with _offline_initialization():
        import torch
        import transformers
        target = _device(torch, device)
        if transformers.__version__ != "4.45.2":
            raise ValueError("Use the report runtime version verified by the fixed smoke")
        module = _module(repo, "report")
        cls = report_variant_class(module.ChestXRayReportGeneratorTool, module.GenerationConfig, mode)
        with ExitStack() as stack:
            for loader_class, kind in ((module.VisionEncoderDecoderModel, "model"),
                                       (module.BertTokenizer, "tokenizer"),
                                       (module.ViTImageProcessor, "processor")):
                wrapper = report_audit.local_loader(loader_class.from_pretrained, kind, snapshots, loads)
                stack.enter_context(patch.object(loader_class, "from_pretrained", side_effect=wrapper))
            tool = cls(cache_dir=str(cache_dir), device=target)
        expected = {(role, kind) for role in report_audit.MODEL_SPECS for kind in ("model", "tokenizer", "processor")}
        if len(loads) != 6 or {(entry["role"], entry["loader"]) for entry in loads} != expected:
            raise ValueError("Expected all six fixed report asset loads")
        if tool.name != "chest_xray_report_generator":
            raise ValueError("Report tool name differs from upstream")
        effective = {}
        for role in report_audit.MODEL_SPECS:
            model, tokenizer = getattr(tool, role + "_model"), getattr(tool, role + "_tokenizer")
            params = report_generation_parameters(tool.generation_args, model, tokenizer, mode)
            config = module.GenerationConfig(**params)
            effective[role] = {key: getattr(config, key, None) for key in
                               ("num_return_sequences", "max_length", "num_beams", "beam_width",
                                "use_cache", "do_sample", "bos_token_id", "eos_token_id",
                                "pad_token_id", "decoder_start_token_id")}
            if str(model.dtype) != "torch.float32":
                raise ValueError("Report weights must retain the original FP32 inference dtype")
    for entry in loads:
        entry["provenance"] = "successful_from_pretrained_local_snapshot"
    environment = report_audit.versions()
    environment["imported_runtime_versions"] = report_audit.imported_versions(environment)
    # Transformers is a lazy module: getattr resolves its version when vars alone does not.
    environment["actual_transformers_version"] = transformers.__version__
    provenance = _provenance(tool, "report", mode, source, assets, loads, environment)
    provenance.update(generation_args=dict(tool.generation_args), effective_generation_config=effective,
                      changed_fields=[] if mode == "original" else ["GenerationConfig.eos_token_id"],
                      semantic_completeness_evaluated=False)
    return tool, provenance


def create_segmentation_tool(repo, *, checkpoint, device, temp_dir):
    """Load the unchanged official PSPNet tool; put private overlays in a new dir.

    The caller supplies an existing parent directory and a never-used temp_dir.
    No inference happens here. Weight checksums are skipped; file completeness
    and actual model loading determine readiness.
    """
    repo, checkpoint, temp_dir = (Path(path).expanduser().resolve() for path in (repo, checkpoint, temp_dir))
    source = _source(repo, "segmentation")
    asset = _checkpoint_asset(checkpoint, expected_bytes=segmentation_audit.CHECKPOINT_BYTES)
    temp_dir.mkdir(exist_ok=False)
    (temp_dir / ".gitignore").write_text("*\n", encoding="utf-8")
    loads = []
    with _offline_initialization(), patch.dict(os.environ, {"MPLBACKEND": "Agg"}):
        import torch
        import torchxrayvision as xrv
        import matplotlib
        matplotlib.use("Agg")
        target = _device(torch, device)
        wrapper = Path(xrv.__file__).resolve().parent / "baseline_models/chestx_det/__init__.py"
        if xrv.__version__ != segmentation_audit.XRV_VERSION:
            raise ValueError("Use the previously audited XRV 1.3.5 PSPNet wrapper")
        module = _module(repo, "segmentation")
        with patch.object(xrv.utils, "get_cache_dir", return_value=str(checkpoint.parent)), \
                patch.object(xrv.utils, "download", side_effect=_deny_network), \
                patch.object(torch, "load", side_effect=segmentation_audit.offline_load_recorder(torch.load, checkpoint, loads)):
            tool = module.ChestXRaySegmentationTool(device=target, temp_dir=temp_dir)
        if len(loads) != 1:
            raise ValueError("Expected one PSPNet checkpoint load")
        if (tool.name != "chest_xray_segmentation" or
                tool.organ_map != dict(zip(segmentation_audit.ORGANS, range(14))) or
                list(tool.model.targets) != list(segmentation_audit.ORGANS)):
            raise ValueError("Official segmentation name or 14-channel mapping changed")
        segmentation_audit._close(segmentation_audit._finite(tool.pixel_spacing_mm), 0.2)
    env = segmentation_audit.environment()
    env["imported_runtime_versions"] = segmentation_audit.imported_versions(env)
    provenance = _provenance(tool, "segmentation", "original", source, [asset], loads, env)
    provenance.update(changed_fields=[], model_channel_count=14,
                      xrv_wrapper_sha256=segmentation_audit.sha256_file(wrapper),
                      pixel_spacing_mm_assumed=0.2, physical_area_calibrated=False,
                      segmentation_is_reference_label=False, private_overlay_contains_source_image=True,
                      factory_did_inference=False)
    return tool, provenance


def _segmentation_observation(result, artifact_dir):
    if artifact_dir is None:
        raise ValueError("A private overlay directory is required for segmentation validation")
    output, metadata = result
    if not isinstance(output, dict) or set(output) != {"metrics", "segmentation_image_path"}:
        raise ValueError("Invalid segmentation output fields")
    if metadata.get("analysis_status") != "completed":
        raise ValueError("Segmentation did not complete")
    size = metadata.get("original_size")
    if (not isinstance(size, (tuple, list)) or len(size) != 2 or
            any(type(value) is not int or value < 1 for value in size) or
            list(metadata.get("model_size", ())) != [512, 512]):
        raise ValueError("Invalid segmentation geometry")
    segmentation_audit._close(segmentation_audit._finite(metadata.get("pixel_spacing_mm")), 0.2)
    requested, metrics = metadata.get("requested_organs"), output["metrics"]
    if (not isinstance(requested, list) or not requested or
            any(not isinstance(name, str) or name not in segmentation_audit.ORGANS for name in requested) or
            not isinstance(metrics, dict) or any(name not in requested for name in metrics)):
        raise ValueError("Invalid requested/returned organ names")
    ordered = list(dict.fromkeys(name for name in requested if name in metrics))
    if list(metrics) != ordered or metadata.get("processed_organs") != ordered:
        raise ValueError("Returned organ mapping disagrees with metadata")
    clean = {name: segmentation_audit.validate_metrics(raw, size) for name, raw in metrics.items()}
    raw_path = output["segmentation_image_path"]
    if not isinstance(raw_path, (str, os.PathLike)) or not isinstance(metadata.get("segmentation_image_path"), (str, os.PathLike)):
        raise ValueError("Missing overlay path")
    path, directory = Path(raw_path).resolve(), Path(artifact_dir).resolve()
    if (not path.is_relative_to(directory) or not path.is_file() or
            Path(metadata["segmentation_image_path"]).resolve() != path or
            not re.fullmatch(r"segmentation_[0-9a-f]{8}\.png", path.name)):
        raise ValueError("Overlay is missing or outside the private artifact directory")
    with path.open("rb") as handle:
        if handle.read(8) != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Overlay has no PNG signature")
    return {"configured_model_channel_count": 14, "forward_prediction_audited": False,
            "requested_organs": list(requested), "requested_structure_count": len(set(requested)),
            "processed_organs": ordered, "metrics_returned_count": len(clean), "metrics_sha256": _hash_json(clean),
            "omission_reason_verified": False, "pixel_spacing_mm_assumed": 0.2,
            "physical_area_calibrated": False, "confidence_is_calibrated": False,
            "segmentation_is_reference_label": False,
            "overlay": {"bytes": path.stat().st_size, "sha256": segmentation_audit.sha256_file(path),
                        "png_signature_checked": True, "contains_source_image": True,
                        "publishable_by_default": False}}


def validate_observation(kind, result, *, artifact_dir=None):
    """Return only safe execution/format details; never report text or paths.

    A valid return means schema checks passed. Medical correctness is always
    unknown. Failure metadata is preserved only as a whitelisted status enum.
    """
    kind = "classification" if kind == "classifier" else kind
    _mode(kind, ("classification", "report", "segmentation"))
    metadata = result[1] if isinstance(result, (tuple, list)) and len(result) == 2 else None
    status = metadata.get("analysis_status") if isinstance(metadata, dict) else None
    details = {"kind": kind, "valid": False, "tool_analysis_status":
               status if status in ("completed", "failed") else "invalid",
               "clinical_evidence": "unknown", "clinical_correctness_evaluated": False,
               "step_credit": None, "raw_content_logged": False}
    if status == "failed":
        details["validation_status"] = "tool_reported_failure"
        return details
    try:
        if kind == "classification":
            scores = classifier_audit.validate_scores(result, CLASSIFIER_LABELS)
            details.update(scores=scores, score_count=18, scores_sha256=_hash_json(scores),
                           probability_calibration_evaluated=False,
                           localization_or_laterality_provided=False)
        elif kind == "report":
            details.update(report_audit.validate_report(result))
        else:
            details.update(_segmentation_observation(result, artifact_dir))
        details.update(valid=True, validation_status="output_contract_passed")
    except (ValueError, TypeError, OverflowError, KeyError, OSError):
        details["validation_status"] = "invalid_output_contract"
    return details
