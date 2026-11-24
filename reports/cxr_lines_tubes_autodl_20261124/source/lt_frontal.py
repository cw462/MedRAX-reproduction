#!/usr/bin/env python3
"""Run the lines-and-tubes runtime on the 147 frontal images (all 5 folds)."""
import json
import os
import re
import sys
import time

import cv2
import numpy as np

ROOT = "/root/autodl-tmp/cxr-lines-and-tubes"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
OUT = "/root/autodl-tmp/lt_frontal"
TASKS = "/dev/shm/lat_tasks_maira.json"
FOLDS = int(sys.argv[1]) if len(sys.argv) > 1 else 5
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 0


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


def main():
    tasks = [t for t in json.load(open(TASKS)) if t["kind"] == "side"]
    imgs = sorted({t["image"] for t in tasks
                   if view_of(t["image"].rsplit("/", 1)[-1]) == "frontal"})
    if LIMIT:
        imgs = imgs[:LIMIT]
    os.makedirs(OUT, exist_ok=True)
    print(f"frontal images: {len(imgs)}, folds={FOLDS}", flush=True)

    from local_lines_tubes_runtime import LocalLinesTubesRuntime
    rt = LocalLinesTubesRuntime(ROOT, "cuda")
    print("runtime ready", flush=True)

    t_all = time.time()
    done = n_pos = 0
    for i, path in enumerate(imgs, 1):
        stem = os.path.basename(path).rsplit(".", 1)[0]
        jp = os.path.join(OUT, stem + ".json")
        if os.path.exists(jp):
            done += 1
            continue
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            print(f"[{i}] FAIL read {stem}", flush=True)
            continue
        t = time.time()
        try:
            out = rt.predict(img, presence_folds=FOLDS, device_folds=FOLDS,
                             carina_folds=FOLDS, classifier_folds=FOLDS)
        except Exception as exc:  # noqa: BLE001
            print(f"[{i}] FAIL {stem}: {type(exc).__name__}: {exc}", flush=True)
            json.dump({"error": f"{type(exc).__name__}: {exc}"}, open(jp, "w"))
            continue
        overlays = out.pop("overlays", {})
        rec = {"image": path, "pred": out,
               "elapsed": round(time.time() - t, 2)}
        json.dump(rec, open(jp, "w"))
        for name, arr in overlays.items():
            try:
                cv2.imwrite(os.path.join(OUT, f"{stem}__{name}.png"), arr)
            except Exception:  # noqa: BLE001
                pass
        pos = any(v >= 0.5 for v in out["presence"].values())
        n_pos += pos
        done += 1
        if i % 10 == 0 or pos:
            el = time.time() - t_all
            print(f"[{i}/{len(imgs)}] {stem} {rec['elapsed']}s pos={pos} "
                  f"avg={el/i:.1f}s eta={(len(imgs)-i)*el/i/60:.1f}min", flush=True)
    print(f"DONE {done}/{len(imgs)} positives={n_pos} in {(time.time()-t_all)/60:.1f}min", flush=True)


if __name__ == "__main__":
    main()
