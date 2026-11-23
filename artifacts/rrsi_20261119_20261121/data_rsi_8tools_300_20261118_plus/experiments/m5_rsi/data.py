"""Build the v2 development splits against the immutable R55 evaluation inputs."""

from collections import Counter, defaultdict
import hashlib
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import random
import re
import subprocess
import tarfile
import zipfile

from PIL import Image, ImageOps
import numpy as np
from scipy.fft import dctn


RAD_SHA = "b293158f0c5c1c5fa27dd615c28005eb54d7b1de"
SLAKE_SHA = "a9083ce6c34ac3ffb17671a605962924d8a8f9e9"
SLAKE_HASHES = {
    "train.json": "7a9fb81f9d7bb145c3d7e9bc8d3b9016ba18b6539ea5031a53bae8fd3cd991c3",
    "validation.json": "32b016440b0c3be11056a78a18eeab46333268407fbb6e6b32f9f4c2debc50f6",
    "imgs.zip": "44eb7d9214e1ac5b7946e237b669401866df9114fd9a3618c5a84fbffcded0b0",
}
OPENI_URL = "https://openi-vip.nlm.nih.gov/imgs/collections/NLMCXR_png.tgz"
OPENI_BYTES = 1_360_814_128
R55_REPORT = "39c598862713f730c0710054e4f74e842b263531"
EVAL_COUNTS = {"chexbench": 618, "slake": 114, "vqarad": 116}
TARGETS = {"train": {"rad_restruct": 220, "slake": 80},
           "validation": {"rad_restruct": 70, "slake": 30}}
CAP = 3
PHASH_RADIUS = 5
DHASH_RADIUS = 8
OPENI_CASE = re.compile(r"^CXR(\d+)(?:_|$)", re.IGNORECASE)
SLAKE_IMAGE = re.compile(r"xmlab(\d+)", re.IGNORECASE)


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".pending")
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pending.replace(path)


def write_bytes(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".pending")
    pending.write_bytes(content)
    pending.replace(path)


def source_asset(family, path):
    parts = PurePosixPath(path).parts
    if family == "slake":
        if len(parts) < 2 or not SLAKE_IMAGE.fullmatch(parts[-2]) or parts[-1] != "source.jpg":
            raise ValueError(f"Unexpected SLAKE original {path}")
        return f"slake/{parts[-2].lower()}/source.jpg"
    name = parts[-1]
    if family == "openi" and not re.fullmatch(r"[A-Za-z0-9_-]+\.png", name, flags=re.I):
        raise ValueError(f"Unexpected OpenI filename {path}")
    if family == "vqarad" and not re.fullmatch(r"[A-Za-z0-9_.-]+\.(?:jpe?g|png)", name, flags=re.I):
        raise ValueError(f"Unexpected VQA-RAD filename {path}")
    return f"{family}/{name}"


def collect_rad(root):
    mapping = read(root / "id_to_img_mapping_frontal_reports.json")
    stats = {}
    all_rows = []
    for split, directory in (("train", "train_qa_pairs"), ("validation", "val_qa_pairs")):
        counts = Counter()
        for path in sorted((root / directory).glob("*.json")):
            counts["source_reports"] += 1
            for index, row in enumerate(read(path)):
                counts["source_questions"] += 1
                if not isinstance(row, list) or len(row) != 4:
                    raise ValueError(f"Unexpected author QA structure in {path.name}:{index}")
                question, answers, history, meta = row
                if not isinstance(question, str) or not isinstance(answers, list) or not isinstance(history, list):
                    raise ValueError(f"Invalid author fields in {path.name}:{index}")
                options = meta["options"]
                if history or meta["answer_type"] != "single_choice" or len(answers) != 1:
                    continue
                if not isinstance(options, list) or answers[0] not in options or len(set(options)) != len(options):
                    continue
                counts["eligible_qa"] += 1
                mapped = mapping.get(path.stem)
                if not mapped:
                    counts["missing_image_mapping"] += 1
                    continue
                labels = {chr(65 + i): value for i, value in enumerate(options)}
                if len(labels) > 26:
                    raise ValueError("Choice set does not fit the native output alphabet")
                images = sorted({source_asset("openi", x + ".png") for x in mapped}, key=str.casefold)
                answer = next(letter for letter, value in labels.items() if value == answers[0])
                all_rows.append({
                    "question_id": f"m5rsi_rad_{path.stem}_{index:04d}", "source": "rad_restruct",
                    "source_version": RAD_SHA, "original_split": split, "source_file": f"{directory}/{path.name}",
                    "source_index": index, "patient_id": None, "study_id": f"openi:{path.stem}",
                    "question_type": "single_choice", "question": question, "options": labels,
                    "answer": answer, "answer_text": answers[0], "all_assets": images,
                    "modality": "X-Ray", "view": "frontal", "anatomy": meta["path"].split("_", 1)[0],
                    "access": "Rad-ReStruct author annotations / NLM OpenI Indiana University originals",
                })
        stats[split] = counts
    return all_rows, stats


def collect_slake(root):
    rows = []
    stats = {}
    for split in ("train", "validation"):
        source_rows = read(root / f"{split}.json")
        counts = Counter(source_questions=len(source_rows))
        for i, row in enumerate(source_rows):
            if row["q_lang"] != "en":
                continue
            counts["english_questions"] += 1
            asset = source_asset("slake", row["img_name"])
            assert int(row["img_id"]) == int(SLAKE_IMAGE.search(asset).group(1))
            answer = row["answer"]
            if not isinstance(answer, str) or not answer.strip():
                counts["empty_reference"] += 1
                continue
            counts["eligible_qa"] += 1
            rows.append({
                "question_id": f"m5rsi_slake_{row['qid']}", "source": "slake",
                "source_version": SLAKE_SHA, "original_split": split, "source_file": f"{split}.json",
                "source_index": i, "source_qid": row["qid"], "patient_id": None,
                "study_id": f"slake:{row['img_id']}", "question_type": row["answer_type"],
                "question": row["question"], "answer": answer, "answer_text": answer,
                "all_assets": [asset], "modality": row["modality"], "view": "unknown",
                "anatomy": row["location"], "access": "BoKelvin/SLAKE dataset card CC-BY-4.0",
            })
        stats[split] = counts
    return rows, stats


def archived_manifest(path):
    with tarfile.open(path, "r|gz") as archive:
        for member in archive:
            if member.isfile() and member.name.endswith("/manifest.json"):
                value = json.load(archive.extractfile(member))
                if "inputs" in value and "order" in value:
                    return value
    raise ValueError(f"Missing original R55 dataset manifest: {path}")


def collect_eval(workspace, prior):
    all_rows = []
    original_order = {}
    for dataset, count in EVAL_COUNTS.items():
        archive = prior / "dataset-archives" / "plus" / "M5" / dataset / "evidence.tar.gz"
        manifest = archived_manifest(archive)
        order = manifest["order"]
        inputs = manifest["inputs"]
        base = f"reports/r55_autodl_qwen8_20261116/plus/m5/{dataset}.jsonl"
        listing = subprocess.check_output(["git", "show", f"{R55_REPORT}:{base}"], cwd=workspace)
        official = {r["question_id"]: r for r in map(json.loads, listing.splitlines())}
        assert len(inputs) == len(order) == len(official) == count
        assert [x["question_id"] for x in order] == [x["question_id"] for x in inputs]
        assert set(official) == set(manifest["reference_files"])
        original_order[dataset] = order
        for row in inputs:
            qid = row["question_id"]
            ref = official[qid]
            assert row["question"] == ref["question"] and (row.get("options") or {}) == (ref.get("options") or {})
            origin = row["source"]
            if dataset == "chexbench":
                family = "slake" if origin["subset"] == "SLAKE" else "openi"
                paths = origin["official_image_paths"]
            elif dataset == "slake":
                family, paths = "slake", [origin["original_image"]]
            else:
                family, paths = "vqarad", row["images"]
            assets = [source_asset(family, path) for path in paths]
            cases = {m.group(1) for a in assets if family == "openi"
                     and (m := OPENI_CASE.search(PurePosixPath(a).stem))}
            source_study = origin.get("official_study_id")
            study = f"{family}:{source_study}" if source_study is not None else None
            if len(cases) == 1:
                study = "openi:" + next(iter(cases))
            elif family == "slake":
                study = "slake:" + SLAKE_IMAGE.search(assets[0]).group(1)
            all_rows.append({
                **row, "source": origin, "source_version": origin.get("revision", R55_REPORT),
                "dataset": dataset, "original_split": "eval", "patient_id": origin.get("official_patient_id"),
                "study_id": study, "all_assets": assets, "answer": ref["reference"],
                "answer_text": (row.get("options") or {}).get(ref["reference"], ref["reference"]),
                "question_type": "single_choice" if row.get("options") else "short_answer",
                "access": "existing frozen and approved R55 evaluation originals",
            })
    return all_rows, original_order


def image_record(content):
    with Image.open(BytesIO(content)) as image:
        rgb = ImageOps.exif_transpose(image).convert("RGB")
        pixels = hashlib.sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()
        light = rgb.convert("L")
        block = dctn(np.asarray(light.resize((32, 32), Image.Resampling.LANCZOS), dtype=float),
                     norm="ortho")[:8, :8].flatten()
        edge = np.asarray(light.resize((9, 8), Image.Resampling.LANCZOS))
        p = np.packbits(block > np.median(block[1:])).tobytes()
        d = np.packbits(edge[:, 1:] > edge[:, :-1]).tobytes()
        return {
            "file_sha256": hashlib.sha256(content).hexdigest(), "pixel_sha256": pixels,
            "phash": p.hex(), "dhash": d.hex(), "width": rgb.width, "height": rgb.height,
        }


def originals(root, archive, slake, vqarad, needed):
    """Read only original image members. Annotation and mask files are excluded."""
    keys = set(needed)
    index = {}

    def save(key, content):
        if key in index:
            raise ValueError(f"Multiple originals map to {key}")
        index[key] = image_record(content)
        path = root / "images" / key
        if not path.is_file() or digest(path) != index[key]["file_sha256"]:
            write_bytes(path, content)

    with tarfile.open(archive, "r|gz") as tar:
        for item in tar:
            key = "openi/" + PurePosixPath(item.name).name
            if item.isfile() and key in keys:
                save(key, tar.extractfile(item).read())
    with zipfile.ZipFile(slake / "imgs.zip") as zf:
        for entry in zf.infolist():
            key = "slake/" + "/".join(PurePosixPath(entry.filename).parts[-2:])
            if not entry.is_dir() and key in keys:
                save(key, zf.read(entry))
    for key in sorted(x for x in keys if x.startswith("vqarad/")):
        path = vqarad / "images" / PurePosixPath(key).name
        if path.is_file():
            save(key, path.read_bytes())
    return index


class Groups:
    """Join all the original images from a report, including unused frontal views."""

    def __init__(self):
        self.parent = {}

    def root(self, item):
        path = []
        while self.parent.setdefault(item, item) != item:
            path.append(item)
            item = self.parent[item]
        for child in path:
            self.parent[child] = item
        return item

    def connect(self, values):
        roots = sorted(set(self.root(x) for x in values))
        for value in roots[1:]:
            self.parent[value] = roots[0]
        return roots[0]


def group_rows(rows, index):
    groups = Groups()
    for asset, desc in index.items():
        families = [asset, "file:" + desc["file_sha256"], "pixel:" + desc["pixel_sha256"]]
        if asset.startswith("openi/") and (match := OPENI_CASE.search(PurePosixPath(asset).stem)):
            families.append("study:openi:" + match.group(1))
        groups.connect(families)
    for row in rows:
        keys = list(row["all_assets"])
        if row["study_id"] is not None:
            keys.append("study:" + row["study_id"])
        if row["patient_id"] is not None:
            family = keys[0].split("/")[0]
            keys.append(f"patient:{family}:{row['patient_id']}")
        groups.connect(keys)
    return {r["question_id"]: groups.root(r["all_assets"][0]) for r in rows}


def suspicious(index, left, right):
    """Flag visually similar originals without treating resemblance as identity."""
    bits = {key: (int(x["phash"], 16), int(x["dhash"], 16)) for key, x in index.items()}
    for asset in sorted(left):
        p, d = bits[asset]
        for other in sorted(right - {asset}):
            q, e = bits[other]
            p_delta = (p ^ q).bit_count()
            if p_delta <= PHASH_RADIUS and (d_delta := (d ^ e).bit_count()) <= DHASH_RADIUS:
                yield {"candidate": asset, "comparison": other, "phash_distance": p_delta,
                       "dhash_distance": d_delta, "disposition": "quarantined_candidate_group"}


def stratified(rows, count, groups, seed, source, group_use, image_use):
    keys = defaultdict(list)
    for r in sorted(rows, key=lambda r: r["question_id"]):
        if source == "rad_restruct":
            stratum = (r["answer_text"], r["anatomy"])
        else:
            stratum = (r["modality"], r["question_type"])
        keys[stratum].append(r)
    rng = random.Random(seed)
    strata = sorted(keys)
    if source == "rad_restruct":
        positives = [k for k in strata if k[0] == "yes"]
        negatives = [k for k in strata if k[0] != "yes"]
        strata = [part[i] for i in range(max(len(positives), len(negatives)))
                  for part in (positives, negatives) if i < len(part)]
    for bucket in keys.values():
        rng.shuffle(bucket)
    selected = []
    selected_qids = set()
    for max_per_group in range(1, CAP + 1):
        changed = True
        while changed and len(selected) < count:
            changed = False
            for stratum in strata:
                if len(selected) >= count:
                    break
                for r in keys[stratum]:
                    qid = r["question_id"]
                    group = groups[qid]
                    if (qid in selected_qids or group_use[group] >= max_per_group
                            or any(image_use[a] >= CAP for a in r["all_assets"])):
                        continue
                    selected.append(r)
                    selected_qids.add(qid)
                    group_use[group] += 1
                    image_use.update(r["all_assets"])
                    changed = True
                    break
    rng.shuffle(selected)
    return selected


def write_manifest(destination, rows, index, group_ids, *, eval_order=None):
    public = []
    answers = []
    for r in rows:
        d = {k: v for k, v in r.items() if k not in ("answer", "answer_text", "images", "all_assets")}
        d["group_id"] = group_ids[r["question_id"]]
        d["image_hashes"] = [{"asset": key, **index[key]} for key in r["all_assets"]]
        d["images"] = ["images/" + key for key in r["all_assets"]]
        if eval_order is None:
            d["image_id"] = d["group_id"]
        public.append(d)
        answers.append({k: r[k] for k in ("question_id", "answer", "answer_text")})
    payload = {"inputs": public, "order": eval_order or [r["question_id"] for r in public]}
    write(destination / "inputs.json", payload)
    write(destination / "labels.json", answers)
    return {name: digest(destination / name) for name in ("inputs.json", "labels.json")}


def prepare(workspace, home, prior, *, seed=42, openi=None):
    rad = home / "upstream" / "Rad-ReStruct"
    openi = openi or home / "upstream" / "NLMCXR_png.tgz"
    slake = workspace / "local_assets" / "slake_official_r44_cache"
    vqarad = workspace / "data" / "vqarad_cxr"
    rad_sha = subprocess.check_output(["git", "-C", str(rad), "rev-parse", "HEAD"], text=True).strip()
    if rad_sha != RAD_SHA:
        raise ValueError("Wrong Rad-ReStruct author revision")
    for name, sha in SLAKE_HASHES.items():
        if digest(slake / name) != sha:
            raise ValueError(f"SLAKE bytes do not match the pinned cache: {name}")
    if not openi.exists() or openi.stat().st_size != OPENI_BYTES:
        raise FileNotFoundError(f"Complete official NLM archive required at {openi}")
    rad_root = rad / "data" / "radrestruct"
    rad_rows, rad_stats = collect_rad(rad_root)
    slake_rows, slake_stats = collect_slake(slake)
    eval_rows, eval_order = collect_eval(workspace, prior)
    dev_rows = rad_rows + slake_rows
    all_rows = dev_rows + eval_rows
    assert len({r["question_id"] for r in all_rows}) == len(all_rows)
    needed = {a for r in all_rows for a in r["all_assets"]}
    index = originals(home, openi, slake, vqarad, needed)
    for row in eval_rows:
        for asset, expected in zip(row["all_assets"], row["source"].get("image_pixel_ids", []), strict=False):
            if asset not in index or index[asset]["pixel_sha256"] != expected:
                raise ValueError(f"OpenI/SLAKE original differs from frozen pixels for {row['question_id']}: {asset}")
    missing_eval = sorted({a for r in eval_rows for a in r["all_assets"] if a not in index})
    if missing_eval:
        raise ValueError(f"Missing {len(missing_eval)} original evaluation images")
    groups = group_rows(all_rows, index)
    eval_groups = {groups[r["question_id"]] for r in eval_rows}
    eval_assets = {a for r in eval_rows for a in r["all_assets"]}
    stats = {"rad_restruct": rad_stats, "slake": slake_stats}
    clean_rows = []
    for row in dev_rows:
        counts = stats[row["source"]][row["original_split"]]
        if any(a not in index for a in row["all_assets"]):
            counts["missing_image"] += 1
        elif groups[row["question_id"]] in eval_groups:
            counts["confirmed_eval_overlap"] += 1
        else:
            clean_rows.append(row)
    asset_group = {}
    for row in clean_rows:
        for asset in row["all_assets"]:
            asset_group[asset] = groups[row["question_id"]]
    suspects = list(suspicious(index, set(asset_group), eval_assets))
    quarantine = {asset_group[x["candidate"]] for x in suspects}
    finals = {}
    blocked_groups = set()
    for split in ("train", "validation"):
        selected = []
        group_use = Counter()
        image_use = Counter()
        for source, target in TARGETS[split].items():
            counts = stats[source][split]
            pool = []
            for row in clean_rows:
                if row["source"] != source or row["original_split"] != split:
                    continue
                group = groups[row["question_id"]]
                if group in blocked_groups:
                    counts["confirmed_train_overlap"] += 1
                elif group in quarantine:
                    counts["suspected_overlap_quarantine"] += 1
                else:
                    pool.append(row)
            chosen = stratified(pool, target, groups, seed, source, group_use, image_use)
            selected.extend(chosen)
            counts.update({"clean_pool": len(pool), "selected": len(chosen), "quota_shortfall": target - len(chosen)})
        if split == "train":
            blocked_groups.update(group_use)
            train_assets = set(image_use)
            validation_assets = {a for r in clean_rows if r["original_split"] == "validation"
                                 and groups[r["question_id"]] not in blocked_groups for a in r["all_assets"]}
            more = list(suspicious(index, validation_assets, train_assets))
            quarantine.update(asset_group[x["candidate"]] for x in more)
            suspects.extend(more)
        random.Random(seed).shuffle(selected)
        finals[split] = selected
    out = home / "manifests"
    hashes = {split: write_manifest(out / name, finals[split], index, groups)
              for split, name in (("train", "train_new"), ("validation", "val_new"))}
    hashes["eval"] = {}
    for dataset, order in eval_order.items():
        rows = [r for r in eval_rows if r["dataset"] == dataset]
        hashes["eval"][dataset] = write_manifest(out / "eval_848" / dataset, rows, index, groups, eval_order=order)
    sources = {
        "rad_restruct": {"repository": "https://github.com/ChantalMP/Rad-ReStruct", "revision": rad_sha,
                         "mapping_sha256": digest(rad_root / "id_to_img_mapping_frontal_reports.json")},
        "openi": {"url": OPENI_URL, "local_archive": str(openi),
                  "bytes": openi.stat().st_size, "sha256": digest(openi)},
        "slake": {"repository": "https://huggingface.co/datasets/BoKelvin/SLAKE", "revision": SLAKE_SHA,
                  "files_sha256": SLAKE_HASHES},
        "r55": {"report_commit": R55_REPORT, "archive": str(prior), "counts": EVAL_COUNTS},
    }
    selected_stats = {}
    for split, rows in (*finals.items(), ("eval", eval_rows)):
        selected_stats[split] = {
            "questions": len(rows), "groups": len({groups[r["question_id"]] for r in rows}),
            "original_images": len({a for r in rows for a in r["all_assets"]}),
            "by_source": dict(Counter(r["source"] if isinstance(r["source"], str) else r["dataset"] for r in rows)),
            "composition": {src: {"modality": dict(Counter(r.get("modality", "original_cxr") for r in rows if r["source"] == src)),
                                  "question_type": dict(Counter(r["question_type"] for r in rows if r["source"] == src)),
                                  "yes_no": dict(Counter(r["answer_text"].lower() for r in rows
                                                        if r["source"] == src and r["answer_text"].lower() in {"yes", "no"}))}
                            for src in TARGETS["train"]} if split != "eval" else {},
        }
    ready = all(not stats[source][split]["quota_shortfall"] for split in TARGETS for source in TARGETS[split])
    report = {
        "status": "frozen" if ready else "quota_shortfall", "seed": seed, "targets": TARGETS,
        "counts": stats, "selected": selected_stats, "suspect_pairs": len(suspects),
        "quarantine_groups": len(quarantine), "originals_hashed": len(index),
        "image_choice": "retain every mapped frontal original per study in fixed filename order",
        "patient_ids_available": sum(row["patient_id"] is not None for row in all_rows),
        "external_overlap": "ChestAgentBench not used; external overlap not assessed",
        "manifest_sha256": hashes,
    }
    write(out / "suspicious_image_pairs.json", suspects)
    write(out / "source_lock.json", sources)
    write(out / "sampling_report.json", report)
    return report
