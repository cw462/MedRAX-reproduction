"""Bind the archived MedRAX splits to the native v4 runtime in place."""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
import random

from .data import prepare
from .dev100_metrics import sample_dev100
from .io import ProtocolError, read_json, write_once

NATIVE_FIELDS = ("question_id", "question", "options", "images", "image_id", "source")
IDENTITY_FIELDS = ("question_id", "case_id", "group_id", "study_id", "image_id", "image_path")


def load_pool(path, dataset=None):
    public = read_json(path / "inputs.json")
    by_id = {row["question_id"]: row for row in public["inputs"]}
    ordered_ids = [
        item["question_id"] if isinstance(item, dict) else item
        for item in public["order"]
    ]
    if (len(by_id) != len(public["inputs"]) or len(set(ordered_ids)) != len(ordered_ids)
            or set(ordered_ids) != set(by_id)):
        raise ProtocolError(f"Invalid frozen question order in {path}")
    return [
        {**by_id[qid], "dataset": dataset or by_id[qid].get("dataset") or by_id[qid]["source"]}
        for qid in ordered_ids
    ]


def identities(row):
    result = {(field, str(row[field])) for field in IDENTITY_FIELDS if row.get(field)}
    # Source-relative paths are unique inside the shared archive asset directory.
    result.update(("image_path", name) for name in row["images"])
    return result


def index_identities(rows):
    return {identity for row in rows for identity in identities(row)}


def exclude_conflicts(rows, other):
    allowed, removed = [], []
    for row in rows:
        if identities(row) & other:
            removed.append(row["question_id"])
        else:
            allowed.append(row)
    return allowed, removed


def counts(rows):
    return dict(Counter(row["dataset"] for row in rows))


def select_validation(rows, expected, seed):
    rng = random.Random(seed)
    keep = set()
    for dataset, n in expected.items():
        candidates = [row["question_id"] for row in rows if row["dataset"] == dataset]
        if len(candidates) < n:
            raise ProtocolError(
                f"Validation source cannot replace excluded {dataset} cases: {len(candidates)}/{n}"
            )
        keep.update(rng.sample(candidates, n) if len(candidates) > n else candidates)
    return [row for row in rows if row["question_id"] in keep]


def select_splits(task, train_pool, val_pool, target_rows):
    config = task["data"]
    if counts(train_pool) != config["dev_pool_counts"]:
        raise ProtocolError("Archived train_new composition differs from the task")
    target = index_identities(target_rows)
    val_pool, removed_val = exclude_conflicts(val_pool, target)
    validation = select_validation(val_pool, config["val_counts"], task["seed"])
    train_pool, removed_train = exclude_conflicts(train_pool, target | index_identities(validation))
    candidates = [{"dataset": row["dataset"], "qid": row["question_id"]} for row in train_pool]
    order = sample_dev100(candidates, task["seed"])
    if counts(order[:50]) != config["dev_prefix50_counts"] or counts(order) != config["dev_total_counts"]:
        raise ProtocolError("Seeded developer split composition differs from the task")
    train_by_id = {row["question_id"]: row for row in train_pool}
    return order, train_by_id, validation, {
        "identity_fields": list(IDENTITY_FIELDS),
        "removed_development_qids": removed_train,
        "removed_validation_qids": removed_val,
        "patient_metadata_available": all(row.get("patient_id") for row in (
            train_pool + validation + target_rows
        )),
    }


def write_records(path, rows):
    # Preparation may restart before the bindings are committed. Each file is
    # rewritten from the same fixed order, with labels kept in a private directory.
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    path.chmod(0o600)


def materialize(out, rows, assets, label_file):
    private = out / "private"
    trusted = out / "trusted"
    private.mkdir(parents=True, exist_ok=True, mode=0o700)
    trusted.mkdir(exist_ok=True, mode=0o700)
    label_rows = read_json(label_file)
    labels = {row["question_id"]: row for row in label_rows}
    if len(labels) != len(label_rows):
        raise ProtocolError(f"Duplicate reference IDs in {label_file}")

    public_cases, reference_rows, metadata, expected = [], [], {}, {}
    previous = defaultdict(list)
    for ordinal, row in enumerate(rows, 1):
        qid = row["question_id"]
        options = row.get("options") or {}
        original_digests = [image["file_sha256"] for image in row["image_hashes"]]
        if len(original_digests) != len(row["images"]):
            raise ProtocolError(f"Missing original image binding for {qid}")
        expected[qid] = original_digests
        key = row["dataset"] + ":" + "|".join(original_digests)
        public_cases.append({
            "id": qid,
            "dataset": row["dataset"],
            "question": row["question"],
            "options": [{"label": label, "text": text} for label, text in options.items()],
            "images": [str((assets / name).resolve(strict=True)) for name in row["images"]],
            "group_keys": [key],
        })
        label = labels.get(qid)
        if label is None or "answer" not in label:
            raise ProtocolError(f"Missing real reference for {qid}")
        reference_rows.append({
            "id": qid,
            "reference": {field: label[field] for field in ("answer", "answer_text") if field in label},
        })
        annotation = {field: row[field] for field in ("modality", "view") if field in row}
        annotation["source"] = str(row["source"])
        native_row = {field: row[field] for field in NATIVE_FIELDS if field in row}
        native_row["options"] = options
        metadata[qid] = {
            "native_row": native_row,
            "order_item": {"question_id": qid, "image_key": key, "previous_ids": previous[key].copy()},
            "ordinal": ordinal,
            "image_annotations": [dict(annotation) for _ in row["images"]],
        }
        previous[key].append(qid)

    files = {
        "manifest": str(out / "stream.json"),
        "references": str(private / "references.jsonl"),
        "case_metadata": str(trusted / "native_cases.json"),
    }
    public_file = out / "public_cases.jsonl"
    write_records(public_file, public_cases)
    write_records(Path(files["references"]), reference_rows)
    native_cases = Path(files["case_metadata"])
    # Native M5 consumes the options dict in insertion order.
    native_cases.write_text(json.dumps(metadata, ensure_ascii=False) + "\n", encoding="utf-8")
    native_cases.chmod(0o600)
    manifest = prepare(public_file, files["manifest"])
    for case in manifest["cases"]:
        if [image["sha256"] for image in case["images"]] != expected[case["id"]]:
            raise ProtocolError(f"Archived original image bytes differ for {case['id']}")
    return {**files, "questions": manifest["n"], "dataset_counts": counts(rows)}


def prepare_data(task, v4_root: Path, out: Path) -> dict:
    v4_root, out = v4_root.resolve(), out.resolve()
    data_config = task["data"]
    dev_size = data_config["dev_size"]
    if dev_size not in (50, 100):
        raise ProtocolError("dev_size must be the fixed 50- or 100-question prefix")
    identity = {"v4_root": str(v4_root), "seed": task["seed"], "data": data_config}
    bindings = out / "data_bindings.json"
    if bindings.is_file():
        saved = read_json(bindings)
        if saved["identity"] != identity:
            raise ProtocolError("Saved data binding differs from the requested experiment")
        for stage in ("dev", "val", "test"):
            for key in ("manifest", "references", "case_metadata"):
                if not Path(saved[stage][key]).is_file():
                    raise ProtocolError(f"Saved {stage} input is missing: {key}")
        return saved

    old_root = v4_root.parent / "medrax_m5_data_rsi_v2_20261117_plus"
    binding = read_json(old_root / "artifacts/native_bindings/plus.json")
    manifests, assets = Path(binding["manifests"]), Path(binding["assets"])
    train_source = manifests / data_config["dev_split"]
    val_source = manifests / data_config["val_split"]
    train, val = load_pool(train_source), load_pool(val_source)

    # The test stream references the existing immutable v4 preparation. Use the
    # archived source IDs only for cross-split checks and to verify order.
    test = {
        "manifest": str(v4_root / "prepared/stream.json"),
        "references": str(v4_root / "prepared/private/references.jsonl"),
        "case_metadata": str(v4_root / "prepared/trusted/native_cases.json"),
        "source": str(manifests / "eval_848"),
    }
    test_order = ("slake", "vqarad", "chexbench")
    target_rows = [
        row for dataset in test_order
        for row in load_pool(manifests / "eval_848" / dataset, dataset)
    ]
    target = read_json(test["manifest"])
    expected_ids = [(row["dataset"], row["question_id"]) for row in target_rows]
    if (counts(target_rows) != data_config["test_counts"]
            or [(row["dataset"], row["id"]) for row in target["cases"]] != expected_ids
            or not Path(test["references"]).is_file()
            or not Path(test["case_metadata"]).is_file()):
        raise ProtocolError("The prepared R55 test stream differs from the frozen source")
    test.update(questions=target["n"], dataset_counts=counts(target_rows))

    order, train_by_id, validation, overlap = select_splits(task, train, val, target_rows)
    order_file = out / "dev100_order.json"
    write_once(order_file, order)
    dev = materialize(out / "dev", [train_by_id[item["qid"]] for item in order[:dev_size]],
                      assets, train_source / "labels.json")
    val = materialize(out / "val", validation, assets, val_source / "labels.json")
    result = {
        "identity": identity,
        "dev100_order": str(order_file),
        "overlap": overlap,
        "dev": {**dev, "source": str(train_source)},
        "val": {**val, "source": str(val_source)},
        "test": test,
    }
    write_once(bindings, result)
    return result
