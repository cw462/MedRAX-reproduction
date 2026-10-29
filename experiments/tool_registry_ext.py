"""Full MedRAX tool registry for the memory runs.

Adds the tools the earlier restricted runs did not have (CheXagent VQA, LLaVA-Med,
utilities) and keeps a provenance record per tool. Weights come from the local HF
cache; nothing is fetched at run time.

GPU placement on 2x RTX 3090 (24 GB each):
  cuda:0  classifier + report + segmentation + LLaVA-Med   (~16.5 GB)
  cuda:1  CheXagent VQA                                    (~7 GB)
  cpu     image visualizer / DICOM processor               (no weights)

LLaVA-Med's upstream code calls `.cuda()` with no index, so it must live on the
visible device 0.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import os
from pathlib import Path
import sys

DEFAULT_TOOLS = ["chest_xray_classifier", "chest_xray_report_generator",
                 "chest_xray_segmentation", "chest_xray_expert", "llava_med_qa",
                 "xray_phrase_grounding", "image_visualizer", "dicom_processor"]

KINDS = {
    "chest_xray_classifier": "classification",
    "chest_xray_report_generator": "report",
    "chest_xray_segmentation": "segmentation",
    "chest_xray_expert": "vqa",
    "llava_med_qa": "llava",
    "xray_phrase_grounding": "grounding",
    "image_visualizer": "utility",
    "dicom_processor": "utility",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _versions() -> dict:
    out = {}
    for package in ("torch", "transformers", "torchxrayvision", "numpy", "accelerate"):
        try:
            out[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            out[package] = None
    return out


def _provenance(tool, kind, repo, source_file, model_id, snapshot, dtype, device):
    module_path = Path(repo) / "medrax" / "tools" / source_file
    return {
        "kind": kind,
        "mode": "original",
        "tool_name": tool.name,
        "description_sha256": hashlib.sha256(tool.description.encode()).hexdigest(),
        "args_schema_sha256": hashlib.sha256(
            str(tool.args_schema.model_json_schema() if hasattr(tool.args_schema, "model_json_schema")
                else tool.args_schema.schema()).encode()).hexdigest(),
        "source": {"file": source_file, "sha256": _sha(module_path)},
        "model": {"model_id": model_id,
                  "snapshot": Path(snapshot).name if snapshot else None},
        "assets_verified": [],
        "environment": {**_versions(), "dtype": dtype, "device": device},
        "offline_initialization": True,
        "clinical_evidence": "unknown",
        "clinical_correctness_evaluated": False,
        "step_credit": None,
    }


def _snapshot(cache_dir: Path, repo_id: str) -> str:
    from huggingface_hub import snapshot_download
    cache = Path(cache_dir)
    # The models were downloaded with HF_HOME=<cache_dir>, which stores them under
    # <cache_dir>/hub. Pass that subdirectory explicitly; env changes after import
    # do not affect huggingface_hub's resolved constants.
    for candidate in (cache / "hub", cache):
        try:
            return snapshot_download(repo_id, cache_dir=str(candidate), local_files_only=True)
        except Exception:
            continue
    raise RuntimeError(f"Local snapshot not found for {repo_id} under {cache}")


def build_tools(repo: Path, *, cache_dir: Path, classifier_checkpoint: Path,
                report_cache: Path, segmentation_checkpoint: Path | None,
                temp_dir: Path, tools=None,
                device_main: str = "cuda:0", device_vqa: str = "cuda:1",
                device_grounding: str = "cuda:1"):
    """Return (tools, provenance) for the requested subset of DEFAULT_TOOLS."""
    repo = Path(repo).resolve()
    cache_dir = Path(cache_dir).resolve()
    temp_dir = Path(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(cache_dir))
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    sys.path.insert(0, str(repo))

    import torch
    import tool_variants as variants

    wanted = list(tools or DEFAULT_TOOLS)
    unknown = set(wanted) - set(DEFAULT_TOOLS)
    if unknown:
        raise ValueError(f"Unknown tools: {sorted(unknown)}")

    built, provenance = {}, {}
    if "chest_xray_classifier" in wanted:
        tool, prov = variants.create_classifier_tool(repo, checkpoint=classifier_checkpoint,
                                                     device=device_main, mode="original")
        built[tool.name], provenance[tool.name] = tool, prov
    if "chest_xray_report_generator" in wanted:
        tool, prov = variants.create_report_tool(repo, cache_dir=report_cache,
                                                 device=device_main, mode="original")
        built[tool.name], provenance[tool.name] = tool, prov
    if "chest_xray_segmentation" in wanted:
        if segmentation_checkpoint is None:
            raise ValueError("Segmentation requested without a checkpoint")
        tool, prov = variants.create_segmentation_tool(repo, checkpoint=segmentation_checkpoint,
                                                       device=device_main,
                                                       temp_dir=temp_dir / "segmentation")
        built[tool.name], provenance[tool.name] = tool, prov

    if "chest_xray_expert" in wanted:
        from medrax.tools.xray_vqa import XRayVQATool
        snap = _snapshot(cache_dir, "StanfordAIMI/CheXagent-2-3b")
        tool = XRayVQATool(model_name=snap, cache_dir=str(cache_dir / "hub"),
                           device=device_vqa, dtype=torch.bfloat16)
        built[tool.name] = tool
        provenance[tool.name] = _provenance(tool, "vqa", repo, "xray_vqa.py",
                                            "StanfordAIMI/CheXagent-2-3b", snap,
                                            "bfloat16", device_vqa)

    if "llava_med_qa" in wanted:
        from medrax.tools.llava_med import LlavaMedTool
        snap = _snapshot(cache_dir, "microsoft/llava-med-v1.5-mistral-7b")
        tool = LlavaMedTool(model_path=snap, cache_dir=str(cache_dir / "hub"),
                            device=device_main, torch_dtype=torch.bfloat16)
        built[tool.name] = tool
        provenance[tool.name] = _provenance(tool, "llava", repo, "llava_med.py",
                                            "microsoft/llava-med-v1.5-mistral-7b", snap,
                                            "bfloat16", device_main)

    if "xray_phrase_grounding" in wanted:
        # MAIRA-2 needs transformers>=4.46 while the main environment is pinned to
        # 4.45.2 for the report tool, and it must load in bf16 (fp32 needs ~31 GB).
        # So the model runs in its own interpreter behind a JSONL worker; the Agent
        # only ever sees the official tool name, description and argument schema.
        import importlib.util
        import json

        from langchain_core.tools import StructuredTool

        import maira_client as maira

        source = repo / "medrax" / "tools" / "grounding.py"
        spec = importlib.util.spec_from_file_location("_grounding_schema_only", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        snapshot = _snapshot(cache_dir, "microsoft/maira-2")
        executable = os.environ.get(
            "MEDRAX_MAIRA_PYTHON",
            str(repo.parent.parent / ".venv-maira" / "bin" / "python"))
        if not Path(executable).exists():
            raise ValueError(f"MAIRA worker interpreter not found: {executable}")
        client = maira.MairaClient(
            python_executable=executable, repo=repo, model_path=snapshot,
            cache_dir=cache_dir / "hub", temp_dir=temp_dir / "maira",
            device=device_grounding, log_path=temp_dir / "maira_worker.log")
        client.start()
        audit_path = temp_dir / "grounding_audit.jsonl"

        def _ground(image_path: str, phrase: str, max_new_tokens: int = 300):
            # The upstream tool returns (output, metadata) and the runner's
            # observe() contract reads metadata["analysis_status"]; returning a
            # JSON string here made every grounding call count as a failed return
            # and still consume the per-case tool budget.
            result = client.ground(image_path, phrase, max_new_tokens)
            with open(audit_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(result, ensure_ascii=False) + "\n")
            boxes = result.get("predictions", [])
            output = {"predictions": [{"phrase": b["phrase"],
                                       "bounding_boxes": {"model_coordinates": [b["model"]],
                                                          "image_coordinates": [b["image"]]}}
                                      for b in boxes],
                      "visualization_path": None}
            metadata = {"image_path": image_path,
                        "analysis_status": result["analysis_status"],
                        "phrase": result["phrase"],
                        "n_boxes": len(boxes),
                        "tool_version": result.get("tool_version"),
                        "clinical_evidence": "unknown",
                        "step_credit": None}
            return output, metadata

        tool = StructuredTool.from_function(
            func=_ground, name="xray_phrase_grounding",
            description=module.XRayPhraseGroundingTool.model_fields["description"].default,
            args_schema=module.XRayPhraseGroundingInput)
        built[tool.name] = tool
        provenance[tool.name] = _provenance(tool, "grounding", repo, "grounding.py",
                                            "microsoft/maira-2", snapshot,
                                            "bfloat16", device_grounding)
        provenance[tool.name]["worker"] = client.describe()

    if "image_visualizer" in wanted:
        from medrax.tools.utils import ImageVisualizerTool
        tool = ImageVisualizerTool()
        built[tool.name] = tool
        provenance[tool.name] = _provenance(tool, "utility", repo, "utils.py",
                                            None, None, "n/a", "cpu")

    if "dicom_processor" in wanted:
        from medrax.tools.dicom import DicomProcessorTool
        tool = DicomProcessorTool(temp_dir=str(temp_dir / "dicom"))
        built[tool.name] = tool
        provenance[tool.name] = _provenance(tool, "utility", repo, "dicom.py",
                                            None, None, "n/a", "cpu")

    if set(built) != set(wanted):
        raise RuntimeError(f"Initialized {sorted(built)} but requested {sorted(wanted)}")
    return built, provenance
