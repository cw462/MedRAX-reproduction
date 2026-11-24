#!/usr/bin/env python3
"""Segment the lateral CheXBench/OpenI images with the M2F lateral bundle.

Set = filenames that look lateral  U  frontal-labelled images that the frontal
model failed to give bilateral lung lobes (those looked lateral on inspection,
e.g. CXR808_IM-2341-1001 carries a burned-in "LT LAT").
"""
import json
import os
import re
import sys
import time

import numpy as np

TASKS = "/dev/shm/lat_tasks_maira.json"
FRONT_FEATURES = "/dev/shm/m2f_features2.json"
OUT = "/root/autodl-tmp/m2f_lateral"
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 0


def view_of(fn):
    m = re.search(r"_IM-\d+-([0-9]+)(?:-[0-9]+)?\.", fn)
    if not m:
        return "unknown"
    s = m.group(1)
    if s in ("1001", "1002", "1003", "4001", "4004", "9001"):
        return "frontal"
    if s in ("2001", "2002", "3001", "3003", "5001"):
        return "lateral"
    return "unknown"


def lateral_images():
    tasks = [t for t in json.load(open(TASKS)) if t["kind"] == "side"]
    feats = json.load(open(FRONT_FEATURES)) if os.path.exists(FRONT_FEATURES) else {}
    out = []
    for t in tasks:
        fn = t["image"].rsplit("/", 1)[-1]
        v = view_of(fn)
        f = feats.get(t["qid"]) or {}
        bilat = bool(f.get("lung upper lobe left") and f.get("lung upper lobe right"))
        if v == "lateral" or (v == "frontal" and not bilat):
            out.append(t["image"])
    return sorted(dict.fromkeys(out))


def main():
    imgs = lateral_images()
    print(f"lateral-set images: {len(imgs)}", flush=True)
    os.makedirs(OUT, exist_ok=True)
    if LIMIT:
        imgs = imgs[:LIMIT]

    from cxas import CXAS
    t0 = time.time()
    seg = CXAS("M2F_anatomy_v2", gpus="0")
    print(f"model loaded in {time.time()-t0:.1f}s", flush=True)
    try:
        seg.model.view_override = "lateral"
        print("view forced to lateral", flush=True)
    except Exception as exc:  # noqa: BLE001
        print("WARN no view_override:", exc, flush=True)
    names = list(seg.model.cxas_names)
    print(f"classes: {len(names)}", flush=True)

    done = 0
    t1 = time.time()
    for i, path in enumerate(imgs, 1):
        stem = os.path.basename(path).rsplit(".", 1)[0]
        op = os.path.join(OUT, stem + ".npz")
        if os.path.exists(op):
            done += 1
            continue
        try:
            pred = seg.process_file(path)
            masks = pred["segmentation_preds"][0]
            if hasattr(masks, "cpu"):
                masks = masks.cpu().numpy()
            m = np.asarray(masks)
            if m.ndim == 4:
                m = m[0]
            packed = np.packbits((m > 0.5).astype(np.uint8), axis=None)
            np.savez_compressed(op, packed=packed, names=np.asarray(names),
                                hw=np.asarray(m.shape[-2:]))
            done += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[{i}] FAIL {stem}: {type(exc).__name__}: {exc}", flush=True)
        if i % 10 == 0:
            el = time.time() - t1
            print(f"{i}/{len(imgs)} {el/i:.2f}s/it eta {el/i*(len(imgs)-i)/60:.1f}min", flush=True)
    print(f"DONE {done}/{len(imgs)} in {(time.time()-t1)/60:.1f}min", flush=True)


if __name__ == "__main__":
    main()
