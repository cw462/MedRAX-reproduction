#!/usr/bin/env python3
"""P3: torchxrayvision multi-label CXR detector over the frozen cohorts."""
import glob, json, os, sys
import numpy as np
import torch
import torchxrayvision as xrv
from PIL import Image

ROOT = "/home/imss/cw/radiology_rag_p3"
IMGDIR = os.path.join(ROOT, "images")
OUT = os.path.join(ROOT, "detector_probs.json")

def main():
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = xrv.models.DenseNet(weights="densenet121-res224-all").to(dev).eval()
    labels = list(model.pathologies)
    print("labels:", labels, flush=True)
    files = []
    for ds in ("chexbench", "slake", "vqarad"):
        d = os.path.join(IMGDIR, ds)
        if os.path.isdir(d):
            for p in glob.glob(os.path.join(d, "**", "*.png"), recursive=True) + glob.glob(os.path.join(d, "**", "*.jpg"), recursive=True):
                files.append((ds, p))
    print("images:", len(files), "device:", dev, flush=True)
    res = {}
    with torch.no_grad():
        for i, (ds, p) in enumerate(files, 1):
            try:
                img = Image.open(p).convert("L")
                arr = np.asarray(img, dtype=np.float32)
                arr = xrv.datasets.normalize(arr, 255)
                arr = arr[None, ...]
                tr = xrv.datasets.XRayCenterCrop()(arr)
                tr = xrv.datasets.XRayResizer(224)(tr)
                t = torch.from_numpy(tr[None, ...]).to(dev)
                out = model(t)[0].cpu().numpy()
                rel = os.path.relpath(p, IMGDIR)
                res[rel] = {lab: float(v) for lab, v in zip(labels, out)}
            except Exception as e:
                print("skip", p, repr(e)[:80], flush=True)
            if i % 100 == 0:
                print(i, flush=True)
    json.dump(res, open(OUT, "w"), indent=0)
    print("saved", OUT, len(res), flush=True)

if __name__ == "__main__":
    main()
