#!/usr/bin/env python3
"""Second-generation features: internal-control opacity asymmetry.

Absolute brightness failed (44%) because every image has its own exposure.
Instead compare each side's lower lobe against its OWN upper lobe, then compare
the two ratios — that cancels global exposure and patient build.

Also records lobe area ratios (volume loss) and the diaphragm/zone geometry.
"""
import glob
import json
import os
import re

import numpy as np
from PIL import Image

M2F = "/root/autodl-tmp/m2f_frontal"
TASKS = "/dev/shm/lat_tasks_maira.json"
OUT = "/dev/shm/m2f_features2.json"

STRUCTS = ["lung upper lobe left", "lung lower lobe left", "lung upper lobe right",
           "lung lower lobe right", "lung middle lobe right",
           "left lung base", "right lung base", "left upper zone lung", "right upper zone lung",
           "left hemidiaphragm", "right hemidiaphragm", "heart", "trachea", "spine"]


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
    out = {}
    for i, t in enumerate(tasks, 1):
        stem = t["image"].rsplit("/", 1)[-1].rsplit(".", 1)[0]
        p = os.path.join(M2F, stem + ".npz")
        if not os.path.exists(p):
            continue
        d = np.load(p, allow_pickle=True)
        names = [str(x) for x in d["names"]]
        H, W = int(d["hw"][0]), int(d["hw"][1])
        bits = np.unpackbits(d["packed"], axis=None)
        idx = {n: k for k, n in enumerate(names)}
        img = np.asarray(Image.open(t["image"]).convert("L").resize((W, H), Image.BILINEAR),
                         dtype=np.float32) / 255.0

        rec = {}
        for name in STRUCTS:
            k = idx.get(name)
            if k is None:
                continue
            m = bits[k * H * W:(k + 1) * H * W].reshape(H, W) > 0
            if not m.any():
                continue
            ys, xs = np.nonzero(m)
            rec[name] = {
                "area": float(m.mean()),
                "cx": float(xs.mean() / W),
                "cy": float(ys.mean() / H),
                "top": float(ys.min() / H),
                "bottom": float(ys.max() / H),
                "mean": float(img[m].mean()),
                "p10": float(np.percentile(img[m], 10)),
                "p90": float(np.percentile(img[m], 90)),
            }
        out[t["qid"]] = rec
        if i % 40 == 0:
            json.dump(out, open(OUT, "w"), indent=0)
            print(f"{i}/{len(tasks)}", flush=True)
    json.dump(out, open(OUT, "w"), indent=0)
    print("saved", OUT, "images:", len(out), flush=True)


if __name__ == "__main__":
    main()
