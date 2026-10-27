"""Label-free audit of frozen splits and a pinned ChestAgentBench image archive.

Outputs are PRIVATE data artifacts: never commit image/QID mappings or inputs.
No label files or raw metadata are opened; existing split assignments are retained.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import zipfile

import numpy as np
from PIL import Image

REVISION = "921e60440927f9893228d843c0206b755744252a"
ARCHIVE_BYTES = 822949819
ARCHIVE_SHA256 = "8d5ac156c267046aadf54f20d961896c6e73d31ec59b8f635d1b208fa1444226"
SPLITS = ("memory_train", "validation", "heldout_test")
PHASH_METHOD = "grayscale_Lanczos32_DCT_low8_median_excluding_DC_v1"
PIXEL_METHOD = "decoded_RGBA_no_resize_no_EXIF_transform_width_height_prefix_v1"


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)+"\n").encode("utf-8")


def sha(data): return hashlib.sha256(data).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4*1024*1024), b""): h.update(block)
    return h.hexdigest()


def unique_pairs(values):
    result = {}
    for key, value in values:
        if key in result: raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def decode(text): return json.loads(text, object_pairs_hook=unique_pairs)
def read_json(path): return decode(Path(path).read_text(encoding="utf-8-sig"))
def read_jsonl(path): return [decode(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_json(path, value):
    with Path(path).open("xb") as stream: stream.write(canonical(value))


def write_jsonl(path, rows):
    with Path(path).open("xb") as stream:
        for row in rows: stream.write(canonical(row))


def load_splits(directory):
    root = Path(directory)
    manifest = read_json(root/"manifest.json")
    hashes = manifest["artifact_sha256"]
    paths = ["audit_index.jsonl"]+[split+".inputs.jsonl" for split in SPLITS]
    for name in paths:
        if file_sha(root/name) != hashes[name]: raise ValueError("Frozen split artifact hash mismatch")
    index, case_splits = {}, defaultdict(set)
    for row in read_jsonl(root/"audit_index.jsonl"):
        if set(row) != {"question_id", "case_hash", "split"} or row["split"] not in SPLITS:
            raise ValueError("Unexpected audit schema")
        if row["question_id"] in index: raise ValueError("Duplicate audit question")
        index[row["question_id"]] = row
        case_splits[row["case_hash"]].add(row["split"])
    if any(len(values) != 1 for values in case_splits.values()): raise ValueError("Case ID assigned across frozen splits")
    rows, seen = {}, set()
    for split in SPLITS:
        rows[split] = read_jsonl(root/(split+".inputs.jsonl"))
        for row in rows[split]:
            if set(row) != {"question_id", "question", "images"}: raise ValueError("Inference fields must be exact")
            qid = row["question_id"]
            if qid in seen or qid not in index or index[qid]["split"] != split: raise ValueError("Input/index mismatch")
            if type(row["question"]) is not str or type(row["images"]) is not list or any(type(x) is not str for x in row["images"]):
                raise ValueError("Invalid inference types")
            for path in row["images"]:
                relative = PurePosixPath(path)
                if relative.is_absolute() or ".." in relative.parts or "\\" in path: raise ValueError("Unsafe archive member path")
            seen.add(qid)
    if seen != set(index): raise ValueError("Audit not fully covered by inference inputs")
    provenance = {"split_manifest_sha256": file_sha(root/"manifest.json"),
                  "artifact_sha256": {name: hashes[name] for name in paths}, "source_metadata_sha256": manifest["source_sha256"],
                  "split_seed": manifest["seed"], "labels_read": False}
    return rows, index, provenance


def phash(image):
    pixels = np.asarray(image.convert("L").resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float64)
    transform = np.cos(np.pi*(2*np.arange(32)+1)[None, :]*np.arange(8)[:, None]/64)
    transform[0] /= np.sqrt(2)
    low = transform @ pixels @ transform.T
    median = np.median(low.reshape(-1)[1:])
    bits = (low.reshape(-1) > median); bits[0] = False
    value = 0
    for bit in bits: value = (value << 1) | int(bit)
    return f"{value:016x}", float(pixels.std())


def inspect_image(data):
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        rgba = image.convert("RGBA")
        pixel_bytes = canonical({"width": image.width, "height": image.height, "mode": "RGBA"})+rgba.tobytes()
        perceptual, deviation = phash(image)
        result = {"width": image.width, "height": image.height, "mode": image.mode, "format": image.format,
                  "canonical_pixel_sha256": sha(pixel_bytes), "phash": perceptual,
                  "phash_grayscale_std": deviation, "low_information_candidate": deviation < 5.0}
    with Image.open(io.BytesIO(data)) as image: image.verify()
    return result


def duplicate_groups(records, field):
    grouped = defaultdict(list)
    for row in records:
        if row.get(field): grouped[row[field]].append(row)
    output = []
    for value, group in sorted(grouped.items()):
        cases = sorted({case for row in group for case in row["case_hashes"]})
        splits = sorted({split for row in group for split in row["splits"]})
        if len(group) > 1 or len(cases) > 1:
            output.append({field: value, "image_paths": [row["dataset_image_path"] for row in group],
                           "case_hashes": cases, "splits": splits, "cross_case": len(cases) > 1,
                           "cross_split": len(splits) > 1,
                           "question_ids": sorted({qid for row in group for qid in row["question_ids"]})})
    return output


def exact_case_components(records):
    """Union whole cases through exact bytes OR exact canonical pixels only."""
    parent = {case: case for row in records for case in row["case_hashes"]}
    def find(case):
        while parent[case] != case:
            parent[case] = parent[parent[case]]; case = parent[case]
        return case
    def union(left, right):
        left, right = find(left), find(right)
        if left != right: parent[max(left, right)] = min(left, right)
    evidence = duplicate_groups(records, "sha256")+duplicate_groups(records, "canonical_pixel_sha256")
    for group in evidence:
        for case in group["case_hashes"][1:]: union(group["case_hashes"][0], case)
    grouped = defaultdict(set)
    for case in parent: grouped[find(case)].add(case)
    return [sorted(group) for group in grouped.values() if len(group) > 1], evidence


def derive_exclusions(rows, index, records, audit_hash, output, development_audit=None):
    components, evidence = exact_case_components(records)
    by_case = defaultdict(list)
    for qid, entry in index.items(): by_case[entry["case_hash"]].append(qid)
    split_by_case = {entry["case_hash"]: entry["split"] for entry in index.values()}
    risks = []
    for component in components:
        splits = sorted({split_by_case[case] for case in component})
        if len(splits) > 1:
            risks.append({"case_hashes": component, "splits": splits,
                          "question_ids_by_split": {split: sorted(qid for case in component if split_by_case[case] == split for qid in by_case[case]) for split in splits},
                          "evidence": [item for item in evidence if set(item["case_hashes"]) <= set(component) and len(item["case_hashes"]) > 1]})
    blocked_cases = {split: sorted({case for component in risks for case in component["case_hashes"] if split_by_case[case] == split}) for split in SPLITS}
    excluded_questions = {split: sorted(qid for case in blocked_cases[split] for qid in by_case[case]) for split in SPLITS}
    eligible_train = [row for row in rows["memory_train"] if index[row["question_id"]]["case_hash"] not in blocked_cases["memory_train"]]
    clean_test = [row for row in rows["heldout_test"] if index[row["question_id"]]["case_hash"] not in blocked_cases["heldout_test"]]
    write_jsonl(output/"memory_train_new_pool_eligible.inputs.jsonl", eligible_train)
    write_jsonl(output/"heldout_clean.inputs.jsonl", clean_test)
    old_overlap = None
    if development_audit is not None:
        old = read_json(development_audit)
        old_records = old["records"]
        affected = [row["question_id"] for row in old_records if row.get("case_hash", row.get("case_hash_audit_only")) in blocked_cases["memory_train"]]
        old_overlap = {"source_audit_sha256": file_sha(development_audit), "question_count": len(old_records),
                       "affected_question_count": len(affected), "affected_question_ids": affected}
    manifest = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
                "rule": "Connect entire cases using exact byte SHA256 or exact canonical RGBA-pixel SHA256. Any component spanning frozen splits is flagged. Exclude its memory_train cases from NEW memory pools and its heldout cases from an additional clean evaluation input. Original splits and full heldout remain unchanged.",
                "canonical_pixel_definition": PIXEL_METHOD, "phash_used_for_exclusion": False,
                "heldout_labels_or_outputs_used": False, "source_image_audit_sha256": audit_hash,
                "risk_components": risks, "excluded_case_hashes_by_split": blocked_cases,
                "excluded_question_ids_by_split": excluded_questions,
                "original_counts": {split: {"questions": len(rows[split]), "cases": len({entry["case_hash"] for entry in index.values() if entry["split"] == split})} for split in SPLITS},
                "new_memory_pool_eligible": {"questions": len(eligible_train), "cases": len({index[row["question_id"]]["case_hash"] for row in eligible_train})},
                "heldout_clean": {"questions": len(clean_test), "cases": len({index[row["question_id"]]["case_hash"] for row in clean_test})},
                "derived_artifact_sha256": {name: file_sha(output/name) for name in ["memory_train_new_pool_eligible.inputs.jsonl", "heldout_clean.inputs.jsonl"]},
                "existing_development_overlap": old_overlap,
                "limitations": ["Full original heldout and derived clean heldout require separate transparent denominators.", "Near-pHash matches are review candidates only and never excluded automatically.", "Case grouping and exact image checks do not establish patient independence.", "Validation cases in risk components are flagged; no original validation membership is changed."]}
    write_json(output/"leakage_exclusion_manifest.json", manifest)
    return manifest


def audit_archive(archive_path, split_directory, output, *, expected_sha256=ARCHIVE_SHA256,
                  expected_bytes=ARCHIVE_BYTES, phash_distance=4, verify_all_crc=True, development_audit=None):
    if not 0 <= phash_distance <= 16: raise ValueError("pHash review threshold must be 0..16")
    archive_path, output = Path(archive_path), Path(output)
    archive_hash = file_sha(archive_path)
    if archive_hash != expected_sha256 or archive_path.stat().st_size != expected_bytes:
        raise ValueError("Archive differs from the expected pinned official artifact")
    rows, index, provenance = load_splits(split_directory)
    references = defaultdict(list)
    for split in SPLITS:
        for row in rows[split]:
            for image in row["images"]: references[image].append(index[row["question_id"]])
    output.mkdir(parents=True, exist_ok=True)
    if (output/"summary.json").exists() or (output/"image_audit.jsonl").exists(): raise FileExistsError("Audit output already exists")
    records = []
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist(); counts = Counter(info.filename for info in infos)
        duplicates = sorted(path for path, count in counts.items() if count > 1)
        bad_crc = archive.testzip() if verify_all_crc else None
        for number, (path, refs) in enumerate(sorted(references.items()), 1):
            row = {"dataset_image_path": path, "question_ids": sorted({item["question_id"] for item in refs}),
                   "case_hashes": sorted({item["case_hash"] for item in refs}), "splits": sorted({item["split"] for item in refs}), "status": "pending"}
            if path not in counts: row["status"] = "missing"
            elif counts[path] != 1: row["status"] = "ambiguous_archive_member"
            else:
                try:
                    info = archive.getinfo(path); data = archive.read(path)
                    row.update(status="readable", sha256=sha(data), bytes=len(data), zip_crc32=f"{info.CRC:08x}", **inspect_image(data))
                    expected_extension = {"JPEG": {".jpg", ".jpeg"}, "PNG": {".png"}}.get(row["format"], set())
                    row["filename_extension_matches_encoding"] = PurePosixPath(path).suffix.lower() in expected_extension
                except (ValueError, OSError, zipfile.BadZipFile) as error:
                    row.update(status="unreadable", error_type=type(error).__name__)
            records.append(row)
            if number % 250 == 0: print(json.dumps({"images_inspected": number, "referenced_images": len(references)}), flush=True)
    write_jsonl(output/"image_audit.jsonl", records)
    byte_groups, pixel_groups = duplicate_groups(records, "sha256"), duplicate_groups(records, "canonical_pixel_sha256")
    write_json(output/"exact_byte_duplicates.json", byte_groups); write_json(output/"exact_pixel_duplicates.json", pixel_groups)
    print(json.dumps({"cross_split_exact_byte_groups": sum(item["cross_split"] for item in byte_groups),
                      "cross_split_exact_pixel_groups": sum(item["cross_split"] for item in pixel_groups)}), flush=True)
    exclusions = derive_exclusions(rows, index, records, file_sha(output/"image_audit.jsonl"), output, development_audit)
    near, valid = [], [row for row in records if row["status"] == "readable"]
    for left_index, left in enumerate(valid):
        for right in valid[left_index+1:]:
            if left["sha256"] == right["sha256"] or left["canonical_pixel_sha256"] == right["canonical_pixel_sha256"]: continue
            distance = (int(left["phash"], 16)^int(right["phash"], 16)).bit_count()
            if distance <= phash_distance:
                splits = sorted(set(left["splits"])|set(right["splits"]))
                cases = sorted(set(left["case_hashes"])|set(right["case_hashes"]))
                near.append({"left_image": left["dataset_image_path"], "right_image": right["dataset_image_path"],
                             "hamming_distance": distance, "splits": splits, "case_hashes": cases,
                             "cross_split": len(splits) > 1, "cross_case": len(cases) > 1,
                             "low_information_candidate": left["low_information_candidate"] or right["low_information_candidate"],
                             "status": "unreviewed_similarity_candidate_not_patient_identity_or_proven_leakage"})
    write_jsonl(output/"phash_review_candidates.jsonl", near)
    by_path = {row["dataset_image_path"]: row for row in records}
    question_audit, per_split = [], {}
    for split in SPLITS:
        for row in rows[split]:
            bad = [path for path in row["images"] if by_path[path]["status"] != "readable"]
            question_audit.append({"question_id": row["question_id"], "split": split, "case_hash": index[row["question_id"]]["case_hash"],
                                   "image_count": len(row["images"]), "all_images_readable": bool(row["images"]) and not bad,
                                   "unavailable_image_paths": bad, "no_images": not row["images"]})
        subset = [row for row in question_audit if row["split"] == split]
        per_split[split] = {"questions": len(subset), "cases": len({row["case_hash"] for row in subset}),
                            "image_count_distribution": dict(sorted(Counter(row["image_count"] for row in subset).items())),
                            "all_images_readable_questions": sum(row["all_images_readable"] for row in subset),
                            "zero_image_questions": [row["question_id"] for row in subset if row["no_images"]]}
    write_jsonl(output/"question_image_audit.jsonl", question_audit)
    summary = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(), "dataset_revision": REVISION,
               "archive_sha256": archive_hash, "archive_bytes": archive_path.stat().st_size, "archive_size_hash_verified": True,
               "archive_members": len(infos), "archive_files": sum(not info.is_dir() for info in infos),
               "archive_duplicate_member_names": duplicates, "all_member_crc_checked": verify_all_crc, "first_bad_crc_member": bad_crc,
               "split_provenance": provenance, "split_summary": per_split,
               "total_questions": len(question_audit), "total_cases": len({row["case_hash"] for row in question_audit}),
               "unique_referenced_images": len(records), "referenced_image_status_counts": dict(Counter(row["status"] for row in records)),
               "referenced_image_formats": dict(Counter(row.get("format", "unknown") for row in records)),
               "referenced_image_modes": dict(Counter(row.get("mode", "unknown") for row in records)),
               "extension_encoding_mismatches": sum(row.get("filename_extension_matches_encoding") is False for row in records),
               "canonical_pixel_method": PIXEL_METHOD, "phash_method": PHASH_METHOD, "phash_distance_threshold": phash_distance,
               "exact_byte_duplicate_groups": len(byte_groups), "cross_split_exact_byte_groups": sum(row["cross_split"] for row in byte_groups),
               "exact_pixel_duplicate_groups": len(pixel_groups), "cross_split_exact_pixel_groups": sum(row["cross_split"] for row in pixel_groups),
               "phash_review_candidate_pairs": len(near), "cross_split_phash_candidate_pairs": sum(row["cross_split"] for row in near),
               "exclusion_manifest_sha256": file_sha(output/"leakage_exclusion_manifest.json"),
               "new_memory_pool_eligible": exclusions["new_memory_pool_eligible"], "heldout_clean": exclusions["heldout_clean"],
               "labels_read": False, "original_splits_changed": False,
               "limitations": ["Image decoding/pixel/pHash audit covers every benchmark-referenced image, not all unreferenced archive files; archive CRC covers all members when enabled.",
                               "Near-pHash similarity is a review candidate only, not identity or leakage proof.",
                               "609 metadata case IDs versus 675 described source cases remains a provenance discrepancy; this audit does not invent a reconciliation.",
                               "No patient independence or medical correctness is established."]}
    write_json(output/"summary.json", summary)
    print(json.dumps({key: summary[key] for key in ["total_questions", "total_cases", "unique_referenced_images", "referenced_image_status_counts", "cross_split_exact_byte_groups", "cross_split_exact_pixel_groups", "cross_split_phash_candidate_pairs", "new_memory_pool_eligible", "heldout_clean"]}), flush=True)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("archive", "split-directory", "output"): parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--expected-sha256", default=ARCHIVE_SHA256); parser.add_argument("--expected-bytes", type=int, default=ARCHIVE_BYTES)
    parser.add_argument("--phash-distance", type=int, default=4); parser.add_argument("--skip-all-member-crc", action="store_true")
    parser.add_argument("--development-audit", type=Path)
    args = parser.parse_args(argv)
    audit_archive(args.archive, args.split_directory, args.output, expected_sha256=args.expected_sha256,
                  expected_bytes=args.expected_bytes, phash_distance=args.phash_distance,
                  verify_all_crc=not args.skip_all_member_crc, development_audit=args.development_audit)


if __name__ == "__main__": main()
