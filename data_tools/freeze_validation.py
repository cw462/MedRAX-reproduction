"""Freeze a private, label-free validation subset with complete image bundles.

Selection uses only frozen validation inputs, case audit IDs and readable-image
metadata. Task tags are approximate question-stem tags, not ground truth labels.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import random
import re
from pathlib import Path
import zipfile

try:
    from . import audit_figures as audit
except ImportError:
    import audit_figures as audit

TAG_RULES = {
    "diagnosis": r"\b(?:diagnos\w*|differential|disease|etiolog\w*|cause)\b",
    "detection": r"\b(?:detect\w*|abnormal\w*|finding\w*|present|presence|identify|identif\w*)\b",
    "localization": r"\b(?:locat\w*|where|side|lobe|zone|region|anatomic\w*)\b",
    "comparison_temporal": r"\b(?:compar\w*|chang\w*|prior|previous|follow[- ]?up|progress\w*|worsen\w*|improv\w*)\b",
    "characterization": r"\b(?:character\w*|appear\w*|pattern|shape|size|density|feature\w*|describe\w*)\b",
    "relationship": r"\b(?:relationship|relat\w*|associat\w*|correlat\w*)\b",
    "classification": r"\b(?:classif\w*|category|type|grade|severity|stage)\b",
}
SELECTION_RULE = (
    "Use frozen validation only; exclude zero-image questions explicitly; retain "
    "one question per case and all its images. Set single/multiple-image quotas "
    "as close to half as feasible. Greedily maximize previously uncovered "
    "question-stem regex tags while preserving quota feasibility, breaking ties "
    "by seeded shuffled question IDs. This is a coverage-oriented convenience "
    "subset, not representative stratified sampling. No labels or model outputs."
)


def task_tags(question):
    # Remove choices before deriving tags; otherwise option content changes tags.
    stem = re.split(r"(?m)^\s*[A-F][.):]\s+", question, maxsplit=1)[0]
    tags = sorted(name for name, pattern in TAG_RULES.items() if re.search(pattern, stem, re.I))
    return tags or ["unspecified"]


def feasible(candidates, used, single, multiple):
    if single < 0 or multiple < 0:
        return False
    by_kind = {kind: {row["case_hash"] for row in candidates if row["kind"] == kind and row["case_hash"] not in used}
               for kind in ("single", "multiple")}
    return (len(by_kind["single"]) >= single and len(by_kind["multiple"]) >= multiple
            and len(by_kind["single"] | by_kind["multiple"]) >= single + multiple)


def select_questions(rows, index, *, count=30, seed=20261027):
    if type(count) is not int or count < 1:
        raise ValueError("Requested count must be positive")
    candidates, skipped = [], []
    for row in rows:
        qid = row["question_id"]
        if index[qid]["split"] != "validation":
            raise ValueError("Only validation cases may be selected")
        if not row["images"]:
            skipped.append(qid)
            continue
        candidates.append({"row": row, "case_hash": index[qid]["case_hash"],
                           "kind": "single" if len(row["images"]) == 1 else "multiple",
                           "task_tags": task_tags(row["question"])})
    candidates.sort(key=lambda row: row["row"]["question_id"])
    random.Random(seed).shuffle(candidates)
    ranks = {row["row"]["question_id"]: rank for rank, row in enumerate(candidates)}
    total = min(count, len({row["case_hash"] for row in candidates}))
    if not total:
        raise ValueError("No nonzero-image validation cases")
    quotas = [single for single in range(total + 1) if feasible(candidates, set(), single, total-single)]
    single = min(quotas, key=lambda number: (abs(number-total/2), -number))
    target = {"single": single, "multiple": total-single}
    remaining = dict(target)
    used, covered, selected = set(), set(), []
    while len(selected) < total:
        options = []
        for row in candidates:
            if row["case_hash"] in used or remaining[row["kind"]] == 0:
                continue
            after = dict(remaining); after[row["kind"]] -= 1
            if feasible(candidates, used | {row["case_hash"]}, after["single"], after["multiple"]):
                options.append(row)
        if not options:
            raise RuntimeError("Selection cannot fulfill its precomputed quotas")
        chosen = max(options, key=lambda row: (len(set(row["task_tags"])-covered), -ranks[row["row"]["question_id"]]))
        selected.append(chosen); used.add(chosen["case_hash"])
        covered.update(chosen["task_tags"]); remaining[chosen["kind"]] -= 1
    metadata = {"requested_question_count": count, "selected_question_count": total,
                "eligible_question_count": len(candidates),
                "eligible_distinct_case_count": len({row["case_hash"] for row in candidates}),
                "skipped_zero_image_question_ids": sorted(skipped), "target_image_count_quotas": target,
                "actual_image_count_quotas": dict(Counter(row["kind"] for row in selected)),
                "query_visible_task_tag_counts": dict(sorted(Counter(tag for row in selected for tag in row["task_tags"]).items())),
                "query_visible_task_tags_available": sorted({tag for row in candidates for tag in row["task_tags"]}),
                "query_visible_task_tags_uncovered": sorted({tag for row in candidates for tag in row["task_tags"]}-covered)}
    return selected, metadata


def freeze(archive_path, split_directory, image_audit_directory, output, *, count=30, seed=20261027):
    archive_path, image_audit_directory, output = Path(archive_path), Path(image_audit_directory), Path(output)
    if output.exists():
        raise FileExistsError("Refusing to replace an existing frozen validation output")
    rows, index, provenance = audit.load_splits(split_directory)
    summary = audit.read_json(image_audit_directory/"summary.json")
    exclusions = audit.read_json(image_audit_directory/"leakage_exclusion_manifest.json")
    if summary["exclusion_manifest_sha256"] != audit.file_sha(image_audit_directory/"leakage_exclusion_manifest.json"):
        raise ValueError("Exclusion manifest hash mismatch")
    if summary["split_provenance"] != provenance:
        raise ValueError("Image audit belongs to different split inputs")
    image_file = image_audit_directory/"image_audit.jsonl"
    if audit.file_sha(image_file) != exclusions["source_image_audit_sha256"]:
        raise ValueError("Image audit hash mismatch")
    if (archive_path.stat().st_size != summary["archive_bytes"]
            or audit.file_sha(archive_path) != summary["archive_sha256"]):
        raise ValueError("Archive differs from the audited artifact")
    if not summary["archive_size_hash_verified"] or not summary["all_member_crc_checked"] or summary["first_bad_crc_member"] is not None:
        raise ValueError("Full archive integrity audit must pass before freezing")
    images = {row["dataset_image_path"]: row for row in audit.read_jsonl(image_file)}
    # Fail if a nonzero-image validation question is unavailable, rather than
    # silently introducing image-quality exclusions into the sampling frame.
    for row in rows["validation"]:
        if any(images[path]["status"] != "readable" for path in row["images"]):
            raise ValueError("Validation contains unavailable images; resolve before selection")
    selected, selection_info = select_questions(rows["validation"], index, count=count, seed=seed)
    blocked = set(exclusions["excluded_case_hashes_by_split"]["validation"])
    selection_plan = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
                      "seed": seed, "rule": SELECTION_RULE, "split": "validation", **selection_info,
                      "question_ids": [row["row"]["question_id"] for row in selected],
                      "case_hashes_audit_only": [row["case_hash"] for row in selected],
                      "query_visible_task_tag_patterns": TAG_RULES,
                      "exact_overlap_case_hashes_audit_only": sorted(blocked & {row["case_hash"] for row in selected}),
                      "source_provenance": provenance, "source_image_audit_sha256": audit.file_sha(image_file),
                      "source_image_audit_summary_sha256": audit.file_sha(image_audit_directory/"summary.json"),
                      "leakage_exclusion_manifest_sha256": audit.file_sha(image_audit_directory/"leakage_exclusion_manifest.json"),
                      "source_archive_sha256": summary["archive_sha256"], "source_archive_bytes": summary["archive_bytes"],
                      "dataset_revision": summary["dataset_revision"],
                      "labels_or_outputs_read": False, "original_splits_changed": False}
    output.mkdir(parents=True)
    (output/"images").mkdir()
    # Freeze the question IDs before image extraction or any downstream outputs.
    audit.write_json(output/"selection_plan.json", selection_plan)
    inference, records = [], []
    with zipfile.ZipFile(archive_path) as archive:
        for number, chosen in enumerate(selected, 1):
            source = chosen["row"]; local_images, mappings = [], []
            for image_number, path in enumerate(source["images"], 1):
                metadata = images[path]
                extension = {"JPEG": ".jpg", "PNG": ".png", "GIF": ".gif"}.get(metadata["format"])
                if extension is None:
                    raise ValueError("Unsupported audited image encoding")
                name = f"val_{number:02d}_image_{image_number:02d}{extension}"
                data = archive.read(path)
                if audit.sha(data) != metadata["sha256"]:
                    raise ValueError("Extracted image differs from audited original bytes")
                with (output/"images"/name).open("xb") as stream:
                    stream.write(data)
                local_images.append(name)
                mappings.append({"dataset_image_path": path, "inference_image_path": name,
                                 **{key: metadata[key] for key in ("sha256", "bytes", "width", "height", "mode", "format", "canonical_pixel_sha256")}})
            inference.append({"question_id": source["question_id"], "question": source["question"], "images": local_images})
            records.append({"question_id": source["question_id"], "split": "validation", "case_hash_audit_only": chosen["case_hash"],
                            "image_count": len(local_images), "query_visible_task_tags": chosen["task_tags"],
                            "exact_cross_split_overlap_flag": chosen["case_hash"] in blocked, "images": mappings})
    audit.write_jsonl(output/"inference.jsonl", inference)
    audit.write_json(output/"audit_manifest.json", {"schema_version": 1, "split": "validation", "records": records,
                     "selection_plan_sha256": audit.file_sha(output/"selection_plan.json"),
                     "source_archive_sha256": summary["archive_sha256"], "dataset_revision": summary["dataset_revision"],
                     "inference_sha256": audit.file_sha(output/"inference.jsonl"), "labels_or_outputs_read": False})
    manifest = {"schema_version": 1, "status": "frozen_ready_for_validation", "split": "validation",
                "question_count": len(inference), "distinct_case_count": len({row["case_hash_audit_only"] for row in records}),
                "image_file_count": sum(len(row["images"]) for row in inference),
                "image_bytes": sum(image["bytes"] for row in records for image in row["images"]),
                "image_count_distribution": dict(sorted(Counter(row["image_count"] for row in records).items())),
                "query_visible_task_tag_counts": selection_info["query_visible_task_tag_counts"],
                "image_root": "images", "images_are_complete_original_bytes": True,
                "artifact_sha256": {name: audit.file_sha(output/name) for name in ("selection_plan.json", "audit_manifest.json", "inference.jsonl")},
                "labels_or_outputs_read": False, "original_splits_changed": False,
                "limitations": ["Coverage-oriented development validation subset, not a representative accuracy estimate.",
                                "Task tags come from question stems only and are approximate; labels and official answer metadata were not read.",
                                "Distinct case IDs and exact-image audit do not establish patient independence.",
                                "Original heldout and derived clean heldout remain separate and unused by this selection."]}
    audit.write_json(output/"manifest.json", manifest)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("archive", "split-directory", "image-audit-directory", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20261027)
    args = parser.parse_args(argv)
    result = freeze(args.archive, args.split_directory, args.image_audit_directory, args.output, count=args.count, seed=args.seed)
    print(audit.canonical(result).decode("utf-8"))


if __name__ == "__main__":
    main()
