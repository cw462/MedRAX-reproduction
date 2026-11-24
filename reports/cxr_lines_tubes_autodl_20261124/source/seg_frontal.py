#!/usr/bin/env python3
"""Segment the 147 frontal CheXBench/OpenI images with CXAS M2F_anatomy_v2 (frontal bundle).

Writes one .npz per image (masks, packed bits) + a summary json with per-class area/bbox/score.
Resumable: existing .npz files are skipped.
"""
import json
import os
import re
import sys
import time

import numpy as np

TASKS = "/dev/shm/lat_tasks_maira.json"
OUT = "/root/autodl-tmp/m2f_frontal"
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


def frontal_images():
    tasks = [t for t in json.load(open(TASKS)) if t["kind"] == "side"]
    out = []
    for t in tasks:
        if view_of(t["image"].rsplit("/", 1)[-1]) == "frontal":
            out.append(t["image"])
    return sorted(dict.fromkeys(out))


def main():
    imgs = frontal_images()
    print(f"frontal images: {len(imgs)}", flush=True)
    os.makedirs(OUT, exist_ok=True)
    if LIMIT:
        imgs = imgs[:LIMIT]

    from cxas import CXAS
    t0 = time.time()
    seg = CXAS("M2F_anatomy_v2", gpus="0")
    print(f"model loaded in {time.time()-t0:.1f}s", flush=True)
    try:
        seg.model.view_override = "frontal"
        print("view forced to frontal", flush=True)
    except Exception as exc:  # noqa: BLE001
        print("WARN no view_override:", exc, flush=True)
    names = list(seg.model.cxas_names)
    print(f"classes: {len(names)}", flush=True)

    summary = {}
    t_start = time.time()
    for i, path in enumerate(imgs, 1):
        stem = os.path.basename(path).rsplit(".", 1)[0]
        outp = os.path.join(OUT, stem + ".npz")
        if os.path.exists(outp):
            print(f"[{i}/{len(imgs)}] cached {stem}", flush=True)
            continue
        t = time.time()
        try:
            pred = seg.process_file(path)
        except Exception as exc:  # noqa: BLE001
            print(f"[{i}/{len(imgs)}] FAIL {stem}: {exc}", flush=True)
            summary[stem] = {"error": str(exc)}
            continue
        mask = pred["segmentation_preds"][0].numpy()          # (159, H, W) bool
        scores = pred["instances"][0]
        extra = pred.get("extra_segmentation", [{}])[0]
        H, W = mask.shape[-2:]
        packed = np.packbits(mask, axis=-1)                    # (159, H, ceil(W/8))
        np.savez_compressed(outp, packed=packed, names=np.array(names),
                            hw=np.array([H, W]), scores=json.dumps(scores))
        rows = {}
        for ci, n in enumerate(names):
            m = mask[ci]
            if not m.any():
                continue
            ys, xs = np.nonzero(m.any(0)), np.nonzero(m.any(1))
            rows[n] = {"px": int(m.sum()), "score": scores.get(n),
                       "bbox": [int(xs[0][0]), int(ys[0][0]), int(xs[0][-1]), int(ys[0][-1])]}
        summary[stem] = {"hw": [H, W], "view": pred.get("view", [None])[0],
                         "n_classes": len(rows), "classes": rows,
                         "extra": sorted(extra.keys())}
        print(f"[{i}/{len(imgs)}] {stem} {W}x{H} {len(rows)}cls "
              f"{os.path.getsize(outp)/1e6:.2f}MB {time.time()-t:.2f}s", flush=True)
        if i % 20 == 0:
            json.dump(summary, open("/dev/shm/m2f_frontal_summary.json", "w"), indent=1)

    json.dump(summary, open("/dev/shm/m2f_frontal_summary.json", "w"), indent=1)
    print(f"DONE {len(summary)} images in {time.time()-t_start:.0f}s -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
