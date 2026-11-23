#!/usr/bin/env python3
"""segment_and_measure: anatomical-box prior -> MedSAM mask -> geometric measurements."""
import glob, json, os, sys
import numpy as np
import torch
from PIL import Image
from transformers import SamModel, SamProcessor

ROOT = "/home/imss/cw/radiology_rag_p3"
MD = os.path.join(ROOT, "medsam")
OUT = os.path.join(ROOT, "measure_all.json")

PRIORS = {
    "heart":   (0.18, 0.28, 0.82, 0.88),
    "left_lung":  (0.50, 0.06, 0.97, 0.80),
    "right_lung": (0.03, 0.06, 0.50, 0.80),
    "spine":   (0.38, 0.05, 0.62, 0.95),
    "both_lungs": (0.03, 0.05, 0.97, 0.85),
    "abdomen": (0.05, 0.55, 0.95, 0.98),
}

def measure(model, proc, dev, img, region):
    w, h = img.size
    x0, y0, x1, y1 = PRIORS.get(region, PRIORS["both_lungs"])
    box = [int(w * x0), int(h * y0), int(w * x1), int(h * y1)]
    inputs = proc(img, input_boxes=[[box]], return_tensors="pt").to(dev)
    with torch.no_grad():
        out = model(**inputs, multimask_output=False)
    masks = proc.image_processor.post_process_masks(
        out.pred_masks.cpu(), inputs["original_sizes"].cpu(), inputs["reshaped_input_sizes"].cpu())
    m = masks[0][0][0].numpy() > 0.5
    ys, xs = np.where(m)
    if len(xs) == 0:
        return None
    return {
        "area_ratio": float(m.mean()),
        "bbox_w_ratio": float((xs.max() - xs.min() + 1) / w),
        "bbox_h_ratio": float((ys.max() - ys.min() + 1) / h),
        "centroid_x": float(xs.mean() / w),
        "centroid_y": float(ys.mean() / h),
        "prompt_box": box,
    }

def main():
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = SamModel.from_pretrained(MD).to(dev).eval()
    proc = SamProcessor.from_pretrained(MD)
    tasks = json.load(open(os.path.join(ROOT, "measure_tasks.json"), encoding="utf-8"))
    print("tasks:", len(tasks), "device:", dev, flush=True)
    res = {}
    for i, t in enumerate(tasks, 1):
        p = os.path.join(ROOT, t["image"])
        if not os.path.exists(p):
            continue
        img = Image.open(p).convert("RGB")
        key = t["qid"]
        res[key] = {"dataset": t["dataset"], "region": t["region"], "finding": t.get("finding", "")}
        for region in {t["region"], "both_lungs"}:
            m = measure(model, proc, dev, img, region)
            if m: res[key][region] = m
        if i % 20 == 0:
            print(i, flush=True)
    json.dump(res, open(OUT, "w"), indent=0)
    print("saved", OUT, len(res), flush=True)

if __name__ == "__main__":
    main()
