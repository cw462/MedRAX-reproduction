"""Server preflight: no API calls, verifies data, imports and tool provenance.

Run from the project root with the project venv:
  HOME=<root>/models/home CUDA_VISIBLE_DEVICES=0 .venv/bin/python code/preflight_memory.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
sys.path[:0] = [str(CODE), str(CODE / "experiments")]

from memory_pipeline.core import Boundary, file_hash  # noqa: E402
import memory_pipeline.injection  # noqa: E402,F401
import provider_ledger  # noqa: E402,F401
import provider_profile  # noqa: E402,F401
import score_memory_runs  # noqa: E402,F401


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    prepared = ROOT / "data/prepared_v2"
    exclusions = ROOT / "data/audit_v3/leakage_exclusion_manifest.json"
    subset = ROOT / "data/memory_v1"
    boundary = Boundary.from_split_directory(prepared, exclusions,
                                             expected_exclusions_sha256=file_hash(exclusions))
    payload = boundary.payload()
    print(json.dumps({"boundary_entries": len(payload["entries"]),
                      "split_manifest_sha256": payload["registry"]["split_manifest_sha256"],
                      "exclusions_sha256": payload["exclusions_sha256"]}))

    checked = 0
    for name, split in (("memory_train_subset_v1.jsonl", "memory_train"),
                        ("validation_subset_v1.jsonl", "validation")):
        rows = [json.loads(line) for line in (subset / "inputs" / name).read_text().splitlines() if line.strip()]
        for row in rows:
            entry = boundary.lookup(row["question_id"])
            assert entry["split"] == split, (row["question_id"], entry["split"])
            assert entry["image_count"] == len(row["images"])
            hashes = [sha256_file(subset / "images" / rel) for rel in row["images"]]
            assert hashes == entry["image_sha256"], row["question_id"]
            checked += 1
    print(json.dumps({"subset_questions_verified": checked}))

    from types import SimpleNamespace
    import tool_variants as variants
    args = SimpleNamespace(
        repo=ROOT / "source/MedRAX", device="cuda:0",
        classifier_checkpoint=ROOT / "models/home/.torchxrayvision/models_data/"
            "nih-pc-chex-mimic_ch-google-openi-kaggle-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt",
        report_cache=ROOT / "models/hf_report",
        segmentation_checkpoint=ROOT / "models/home/.torchxrayvision/models_data/pspnet_chestxray_best_model_4.pth")
    print(json.dumps({"classifier_exists": args.classifier_checkpoint.is_file(),
                      "report_cache_exists": args.report_cache.is_dir(),
                      "segmentation_exists": args.segmentation_checkpoint.is_file()}))

    with open(os.devnull, "w") as sink:
        import contextlib
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            tools_a = variants.create_classifier_tool(args.repo, checkpoint=args.classifier_checkpoint,
                                                      device=args.device, mode="original")
            report_a = variants.create_report_tool(args.repo, cache_dir=args.report_cache,
                                                   device=args.device, mode="original")
            tools_b = variants.create_classifier_tool(args.repo, checkpoint=args.classifier_checkpoint,
                                                      device=args.device, mode="original")
            report_b = variants.create_report_tool(args.repo, cache_dir=args.report_cache,
                                                   device=args.device, mode="original")
    import diagnostic_eval as diag
    stable = {
        "classifier": diag.hash_value(tools_a[1]) == diag.hash_value(tools_b[1]),
        "report": diag.hash_value(report_a[1]) == diag.hash_value(report_b[1]),
        "classifier_version": diag.hash_value(tools_a[1]),
        "report_version": diag.hash_value(report_a[1]),
    }
    print(json.dumps(stable))
    if not (stable["classifier"] and stable["report"]):
        raise SystemExit("Tool provenance is not deterministic across initializations")
    print("PREFLIGHT_OK")


if __name__ == "__main__":
    main()
