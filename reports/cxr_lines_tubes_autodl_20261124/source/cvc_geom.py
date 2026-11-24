#!/usr/bin/env python3
"""Export CVC line/tip coordinates from the lines-and-tubes device branch.

Channel map (from local_lines_tubes_runtime._device_overlay):
  family[0..3] = line segmentation for ETT, NGT, CVC, Swan Ganz
  family[4..7] = distal endpoint for the same order
So CVC line = family[2], CVC tip = family[6].

For each catheter question image we record:
  line mask centroid / bbox / area
  entry-side x  = mean x over the top 30% of the line's y-range  (clavicular end)
  tip x,y and peak probability
All coordinates normalised to [0,1].
"""
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

TASKS = "/dev/shm/lat_tasks_maira.json"
OUT = "/dev/shm/cvc_geom.json"
FOLDS = int(os.environ.get("FOLDS", "5"))


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


def peak(prob):
    y, x = np.unravel_index(int(np.argmax(prob)), prob.shape)
    h, w = prob.shape
    return [float(x / max(w - 1, 1)), float(y / max(h - 1, 1))], float(prob[y, x])


def main():
    tasks = [t for t in json.load(open(TASKS, encoding="utf-8"))
             if t["kind"] == "side" and t["phrase"] == "indwelling catheter"
             and view_of(t["image"].rsplit("/", 1)[-1]) == "frontal"]
    print(f"catheter questions (frontal): {len(tasks)}", flush=True)

    from local_lines_tubes_runtime import LocalLinesTubesRuntime
    rt = LocalLinesTubesRuntime(ROOT, "cuda")
    print("runtime ready", flush=True)

    out = {}
    t0 = time.time()
    for i, t in enumerate(tasks, 1):
        img = cv2.imread(t["image"], cv2.IMREAD_GRAYSCALE)
        if img is None:
            out[t["qid"]] = {"error": "read fail"}
            continue
        try:
            agnostic, family, raw_family, used = rt._device(img, FOLDS)
        except Exception as exc:  # noqa: BLE001
            out[t["qid"]] = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        fam = np.asarray(family)
        rec = {"family_shape": list(fam.shape), "gold": t["gold_attr"]}
        # print once what shapes look like
        if i == 1:
            print("family shape:", fam.shape, "agnostic:", np.asarray(agnostic).shape, flush=True)
        for label, ch_line, ch_tip in (("CVC", 2, 6), ("agnostic", 1, None)):
            src = fam if ch_line < fam.shape[0] else None
            if src is None or ch_line >= src.shape[0]:
                continue
            line = src[ch_line]
            m = line > 0.5
            if not m.any():
                rec[label] = None
                continue
            ys, xs = np.nonzero(m)
            H, W = m.shape
            y0, y1 = ys.min(), ys.max()
            cut = y0 + 0.30 * (y1 - y0)
            top = ys <= cut
            r = {
                "area": float(m.mean()),
                "cx": float(xs.mean() / W),
                "cy": float(ys.mean() / H),
                "entry_cx": float(xs[top].mean() / W) if top.any() else None,
                "top": float(y0 / H),
                "bottom": float(y1 / H),
            }
            if ch_tip is not None and ch_tip < src.shape[0]:
                (tx, ty), pk = peak(src[ch_tip])
                r["tip_x"] = tx
                r["tip_y"] = ty
                r["tip_p"] = pk
            rec[label] = r
        out[t["qid"]] = rec
        if i % 5 == 0 or i == len(tasks):
            json.dump(out, open(OUT, "w"), indent=0)
            print(f"{i}/{len(tasks)} {time.time()-t0:.0f}s", flush=True)
    json.dump(out, open(OUT, "w"), indent=0)
    print("saved", OUT, flush=True)


if __name__ == "__main__":
    main()
