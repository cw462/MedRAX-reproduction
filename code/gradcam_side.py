#!/usr/bin/env python3
"""Grad-CAM centroid -> patient side for CheXBench laterality questions."""
import json, os
import numpy as np
import torch
import torch.nn.functional as F
import torchxrayvision as xrv
from PIL import Image

ROOT = "/home/imss/cw/radiology_rag_p3"
OUT = os.path.join(ROOT, "gradcam_side.json")

def cam_for(model, dev, pil, label):
    arr = np.asarray(pil.convert("L"), dtype=np.float32)
    arr = xrv.datasets.normalize(arr, 255)[None, ...]
    arr = xrv.datasets.XRayCenterCrop()(arr)
    arr = xrv.datasets.XRayResizer(224)(arr)
    x = torch.from_numpy(arr[None, ...]).to(dev)
    feats = {}
    def hook(m, inp, out):
        out.retain_grad()
        feats["act"] = out
    h = model.features.norm5.register_forward_hook(hook)
    model.zero_grad()
    logits = model(x)
    h.remove()
    idx = model.pathologies.index(label) if label in model.pathologies else 0
    logits[0, idx].backward()
    full, gfull = feats["act"], feats["act"].grad
    if gfull is None: return None
    act = full[0].detach(); grad = gfull[0].detach()
    w = grad.mean(dim=(1, 2), keepdim=True)
    cam = F.relu((w * act).sum(0)).cpu().numpy()
    if cam.max() <= 0: return None
    cam = cam / cam.max()
    return cam

def main():
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = xrv.models.DenseNet(weights="densenet121-res224-all").to(dev).eval()
    tasks = json.load(open(os.path.join(ROOT, "lat_tasks.json"), encoding="utf-8"))
    print("tasks:", len(tasks), "device:", dev, flush=True)
    out = {}
    for i, t in enumerate(tasks, 1):
        p = os.path.join(ROOT, t["image"])
        if not os.path.exists(p): continue
        pil = Image.open(p).convert("RGB")
        cam = cam_for(model, dev, pil, t["label"])
        if cam is None:
            out[t["qid"]] = {"skip": True}; continue
        ys, xs = np.mgrid[0:cam.shape[0], 0:cam.shape[1]]
        wts = cam ** 2
        cx = float((xs * wts).sum() / wts.sum() / cam.shape[1])
        cy = float((ys * wts).sum() / wts.sum() / cam.shape[0])
        # standard display: image-left = patient's RIGHT
        side = "right" if cx < 0.5 else "left"
        out[t["qid"]] = {"cx": cx, "cy": cy, "side": side, "peak": float(cam.max())}
        if i % 50 == 0: print(i, flush=True)
    json.dump(out, open(OUT, "w"), indent=0)
    ok = sum(1 for q, v in out.items() if v.get("side") and v["side"] == next((t["gold_side"] for t in tasks if t["qid"] == q), None))
    print("saved", OUT, "n=", len(out), "acc_side=", round(100*ok/max(1,len(out)),1), "%", flush=True)

if __name__ == "__main__":
    main()
