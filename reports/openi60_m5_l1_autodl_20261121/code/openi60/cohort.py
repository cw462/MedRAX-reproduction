"""Label-blind sampling; consumes the ORIGINAL execution manifest, not result logs."""
from __future__ import annotations
import copy
import random
import re
from collections import Counter
from typing import Any
from pathlib import Path
from .common import require, safe_qid, object_hash, relative_path

INPUT_KEYS = {"question_id", "question", "options", "images", "image_id", "source"}
FORBIDDEN = {"answer", "answer_text", "reference", "reference_annotation", "label", "labels",
             "ground_truth", "correct", "prediction", "predictions", "comparison", "decisions",
             "reward", "feedback", "source_label", "terminal_raw"}
SIDE = re.compile(r"\b(left|right)\b", re.I)

def no_labels(value: Any, path: str = "input") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            require(str(key).lower() not in FORBIDDEN, f"Label/outcome field not allowed: {path}.{key}")
            no_labels(child, f"{path}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            no_labels(child, f"{path}[{i}]")

def validate_inputs(inputs: list[dict]) -> None:
    require(bool(inputs) and isinstance(inputs, list), "inputs must be a nonempty list")
    ids = []
    for row in inputs:
        require(isinstance(row, dict) and not set(row) - INPUT_KEYS,
                "Use the native execution manifest, not published scored JSONL")
        no_labels(row)
        ids.append(safe_qid(row["question_id"]))
        require(isinstance(row.get("question"), str) and row["question"].strip(), "Missing question")
        require(isinstance(row.get("images"), list) and row["images"], "Missing original images")
        for image in row["images"]:
            relative_path(image)
        require(isinstance(row.get("options"), dict) and row["options"], "This pilot requires options")
        require(all(isinstance(k, str) and isinstance(v, str) for k, v in row["options"].items()),
                "Options must map original labels to strings")
    require(len(ids) == len(set(ids)), "Duplicate question id")

def laterality_signature(row: dict) -> str | None:
    """Exactly two options; same text except one opposite whole-word left/right.

    This conservative rule intentionally does not treat two unrelated findings,
    bilateral-vs-unilateral questions, or upper/lower as left-right questions.
    """
    source = row.get("source") or {}
    if not (row["question_id"].lower().startswith("chexbench_openi_") or
            str(source.get("subset", "")).lower() == "openi"):
        return None
    options = row.get("options", {})
    if len(options) != 2:
        return None
    values = [" ".join(v.lower().strip().split()) for v in options.values()]
    matches = [SIDE.findall(v) for v in values]
    if any(len(m) != 1 for m in matches) or {m[0] for m in matches} != {"left", "right"}:
        return None
    bodies = [SIDE.sub("<SIDE>", v) for v in values]
    return bodies[0] if bodies[0] == bodies[1] else None

def validate_order(inputs: list[dict], order: list[dict]) -> dict[str, dict]:
    require([r["question_id"] for r in inputs] == [r["question_id"] for r in order],
            "Native input/order mismatch")
    seen: dict[str, list[str]] = {}
    by_id = {}
    for item in order:
        key = item.get("image_key")
        require(isinstance(key, str) and key, "Missing image_key in native order")
        prior = seen.setdefault(key, [])
        require(item.get("previous_ids") == prior, "Native previous_ids is not the chronological prefix")
        by_id[item["question_id"]] = item
        prior.append(item["question_id"])
    return by_id

def case_groups(inputs: list[dict], by_id: dict[str, dict]) -> dict[str, str]:
    """Union known study/image identifiers. This does NOT establish patient identity."""
    parent = {r["question_id"]: r["question_id"] for r in inputs}
    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(a: str, b: str) -> None:
        a, b = find(a), find(b)
        if a != b:
            parent[max(a, b)] = min(a, b)
    owners: dict[str, str] = {}
    for row in inputs:
        qid = row["question_id"]
        tokens = ["native-image:" + by_id[qid]["image_key"]]
        if row.get("image_id"):
            tokens.append("image-id:" + str(row["image_id"]))
        source = row.get("source") or {}
        for key in ("case_id", "study_id", "patient_id"):
            for scope in (row, source):
                if scope.get(key) is not None:
                    tokens.append(key + ":" + str(scope[key]))
        for pixel in source.get("image_pixel_ids", []):
            tokens.append("pixel-id:" + str(pixel))
        for image in row["images"]:
            tokens.append("image-path:" + str(relative_path(image)))
            # OpenI CXR<n> is a STUDY identifier, not proof of patient independence.
            m = re.match(r"(CXR\d+)(?:_|\b)", Path(image).name, flags=re.I)
            if m:
                tokens.append("openi-study:" + m.group(1).upper())
        for token in tokens:
            if token in owners:
                union(qid, owners[token])
            else:
                owners[token] = qid
    groups = {}
    for qid in parent:
        groups[qid] = "case_" + object_hash(find(qid))[:16]
    return groups

def build_cohort(manifest: dict, n: int, seed: int, expected_pool: int | None) -> tuple[list, list, dict]:
    inputs = manifest["inputs"]
    validate_inputs(inputs)
    by_id = validate_order(inputs, manifest["order"])
    candidates = [r for r in inputs if laterality_signature(r) is not None]
    if expected_pool is not None:
        require(len(candidates) == expected_pool,
                f"Laterality pool={len(candidates)}, expected={expected_pool}. "
                "Inspect the pool; do not silently change the question filter.")
    require(type(n) is int and 1 <= n <= len(candidates), "Invalid sample size")
    # Selection sees only qids/options, NEVER correctness, references, or prior answers.
    selected = set(random.Random(seed).sample(sorted(r["question_id"] for r in candidates), n))
    # Preserve relative original stream order in BOTH arms; seed controls sample only.
    sample = [copy.deepcopy(r) for r in inputs if r["question_id"] in selected]
    seen: dict[str, list] = {}
    order = []
    for row in sample:
        key = by_id[row["question_id"]]["image_key"]
        prev = seen.setdefault(key, [])
        order.append({"question_id": row["question_id"], "image_key": key, "previous_ids": list(prev)})
        prev.append(row["question_id"])
    groups = case_groups(inputs, by_id)
    selected_groups = {groups[q] for q in selected}
    remaining = [r["question_id"] for r in candidates if groups[r["question_id"]] not in selected_groups]
    related = [r["question_id"] for r in candidates
               if r["question_id"] not in selected and groups[r["question_id"]] in selected_groups]
    report = {
        "schema": "openi60_cohort_v1", "seed": seed, "n": n,
        "selection": "uniform_question_sample_without_outcomes",
        "order": "relative_order_of_original_manifest",
        "pool_size": len(candidates), "population_correctness_not_read": True,
        "selected_ids": [r["question_id"] for r in sample],
        "selected_groups": {r["question_id"]: groups[r["question_id"]] for r in sample},
        "remaining_case_disjoint_candidate_ids": remaining,
        "excluded_related_ids": related,
        "grouping_warning": "Known study/image identifiers only; not independent patient verification.",
        "selected_option_skeleton_counts": dict(Counter(laterality_signature(r) for r in sample)),
        "pool_option_skeleton_counts": dict(Counter(laterality_signature(r) for r in candidates)),
        "same_image_followups_in_sample": sum(bool(r["previous_ids"]) for r in order),
        "historical_exposure": "Development/regression pilot, not a new held-out test.",
    }
    return sample, order, report
