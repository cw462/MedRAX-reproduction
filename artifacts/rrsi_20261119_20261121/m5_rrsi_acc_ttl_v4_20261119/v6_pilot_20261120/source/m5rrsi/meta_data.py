"""Freeze independent confirmation blocks for the v6 improver trials."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random

from .dev100_data import identities, load_pool, materialize
from .io import ProtocolError, read_json, write_once


def case_keys(row):
    keys = identities(row)
    for image in row["image_hashes"]:
        for field in ("file_sha256", "pixel_sha256"):
            if image.get(field):
                keys.add((field, image[field]))
    return keys


def select_confirmation_blocks(train, excluded, seed):
    """Take four 7 Rad-ReStruct / 3 SLAKE blocks from remaining cases."""
    rng = random.Random(seed)
    blocked = {key for row in excluded for key in case_keys(row)}
    candidates = {}
    for dataset in ("rad_restruct", "slake"):
        queue = sorted((row for row in train if row["dataset"] == dataset),
                       key=lambda row: row["question_id"])
        rng.shuffle(queue)
        candidates[dataset] = iter(queue)

    blocks = []
    for _ in range(4):
        block = []
        for dataset, quota in (("rad_restruct", 7), ("slake", 3)):
            selected = 0
            for row in candidates[dataset]:
                keys = case_keys(row)
                if keys & blocked:
                    continue
                blocked.update(keys)
                block.append(row)
                selected += 1
                if selected == quota:
                    break
            if selected != quota:
                raise ProtocolError(f"Not enough isolated {dataset} cases for the confirmation pool")
        rng.shuffle(block)
        blocks.append(block)
    return blocks


def frozen_split(binding, archive_rows, count, split):
    manifest = read_json(binding["manifest"])
    by_qid = {row["question_id"]: row for row in archive_rows}
    ids = [case["id"] for case in manifest["cases"]]
    if len(ids) != count or len(set(ids)) != count or not set(ids) <= by_qid.keys():
        raise ProtocolError(f"The frozen {split} manifest cannot be bound to its archive")
    return [by_qid[qid] for qid in ids]


def prepare_confirmation(v5_run: Path, output: Path) -> dict:
    """Bind the frozen v5 splits with the original archive, then materialize v6 only."""
    v5_run, output = Path(v5_run).resolve(), Path(output).resolve()
    if output.is_relative_to(v5_run):
        raise ProtocolError("V6 confirmation data must be written outside the v5 run")
    resolved = read_json(v5_run / "resolved_config.json")
    task, datasets = resolved["task"], resolved["datasets"]
    if task["data"]["dev_size"] != 50:
        raise ProtocolError("V6 must use the fixed 50-question development stream")

    plus_root = Path(resolved["v4_root"]).parent / "medrax_m5_data_rsi_v2_20261117_plus"
    archive = read_json(plus_root / "artifacts/native_bindings/plus.json")
    manifests, assets = Path(archive["manifests"]), Path(archive["assets"])
    train_path = manifests / task["data"]["dev_split"]
    train = load_pool(train_path)
    val = load_pool(manifests / task["data"]["val_split"])
    test = [row for dataset in ("slake", "vqarad", "chexbench")
            for row in load_pool(manifests / "eval_848" / dataset, dataset)]
    dev50 = frozen_split(datasets["dev"], train, 50, "development")
    dev100 = read_json(datasets["dev100_order"])
    if [row["question_id"] for row in dev50] != [row["qid"] for row in dev100[:50]]:
        raise ProtocolError("Frozen development order differs from the v5 dev50 prefix")
    val100 = frozen_split(datasets["val"], val, 100, "validation")
    test848 = frozen_split(datasets["test"], test, 848, "target test")

    seed = task["seed"]
    blocks = select_confirmation_blocks(train, dev50 + val100 + test848, seed)
    selection = {
        "seed": seed,
        "v5_run": str(v5_run),
        "dev50_ids": [row["question_id"] for row in dev50],
        "blocks": [[row["question_id"] for row in block] for block in blocks],
    }
    write_once(output / "selection.json", selection)
    binding_path = output / "confirmation_bindings.json"
    if binding_path.exists():
        saved = read_json(binding_path)
        for block in saved["blocks"]:
            if not all(Path(block[key]).is_file() for key in ("manifest", "references", "case_metadata")):
                raise ProtocolError("A frozen confirmation input is missing")
        return saved

    result = {"selection": str(output / "selection.json"), "blocks": []}
    for number, block in enumerate(blocks, 1):
        artifact = materialize(output / f"block_{number:02d}", block, assets,
                               train_path / "labels.json")
        result["blocks"].append({"block": number, **artifact})
    write_once(binding_path, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v5-run", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    options = parser.parse_args()
    binding = prepare_confirmation(options.v5_run, options.output)
    print(json.dumps({"selection": binding["selection"], "counts": [
        block["dataset_counts"] for block in binding["blocks"]
    ]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
