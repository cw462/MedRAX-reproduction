#!/usr/bin/env python3
"""Wire M2F masks into the evidence chain for the 147 frontal laterality questions.

Features per image (all normalised, no mm spacing needed):
  dome_top_L/R      topmost y of each hemidiaphragm mask   (higher dome = smaller y)
  dome_area_L/R     mask area fraction
  base_mean_L/R     mean grayscale inside each lung-base mask (lower = more opaque)
  base_sd_L/R       texture inside the base
  heart_cx          heart centroid x  (orientation sanity check)
  trachea_cx        trachea centroid x (midline reference)
"""
import glob
import json
import os
import re

import numpy as np
from PIL import Image

M2F = "/root/autodl-tmp/m2f_frontal"
TASKS = "/dev/shm/lat_tasks_maira.json"
OUT = "/dev/shm/m2f_features.json"

KEYS = ["left hemidiaphragm", "right hemidiaphragm", "left lung base", "right lung base",
        "heart", "trachea"]


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
    tasks = [t for t in json.load(open(TASKS, encoding="utf-8"))
             if t["kind"] == "side" and view_of(t["image"].rsplit("/", 1)[-1]) == "frontal"]
    print(f"frontal side tasks: {len(tasks)}", flush=True)

    out = {}
    for i, t in enumerate(tasks, 1):
        stem = t["image"].rsplit("/", 1)[-1].rsplit(".", 1)[0]
        p = os.path.join(M2F, stem + ".npz")
        if not os.path.exists(p):
            out[t["qid"]] = {"error": "no npz"}
            continue
        d = np.load(p, allow_pickle=True)
        names = [str(x) for x in d["names"]]
        H, W = int(d["hw"][0]), int(d["hw"][1])
        bits = np.unpackbits(d["packed"], axis=None)
        idx = {n: k for k, n in enumerate(names)}

        def mask(name):
            k = idx.get(name)
            if k is None:
                return None
            m = bits[k * H * W:(k + 1) * H * W].reshape(H, W) > 0
            return m if m.any() else None

        img = np.asarray(Image.open(t["image"]).convert("L").resize((W, H), Image.BILINEAR),
                         dtype=np.float32) / 255.0

        rec = {"hw": [H, W]}
        for name, tag in (("left hemidiaphragm", "domL"), ("right hemidiaphragm", "domR"),
                          ("left lung base", "basL"), ("right lung base", "basR"),
                          ("heart", "heart"), ("trachea", "trach")):
            m = mask(name)
            if m is None:
                rec[tag] = None
                continue
            ys, xs = np.nonzero(m)
            r = {"area": float(m.mean()), "cx": float(xs.mean() / W), "cy": float(ys.mean() / H),
                 "top": float(ys.min() / H), "bottom": float(ys.max() / H)}
            if tag.startswith("bas") or tag == "heart":
                vals = img[m]
                r["mean"] = float(vals.mean())
                r["sd"] = float(vals.std())
            rec[tag] = r
        out[t["qid"]] = rec
        if i % 30 == 0:
            json.dump(out, open(OUT, "w"), indent=0)
            print(f"{i}/{len(tasks)}", flush=True)

    json.dump(out, open(OUT, "w"), indent=0)
    ok = sum(1 for v in out.values() if "domL" in v and v.get("domL"))
    print(f"saved {OUT}; images with both domes: {ok}", flush=True)


if __name__ == "__main__":
    main()
