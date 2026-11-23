#!/usr/bin/env python3
"""MedSAM demo on the server: box-prompted segmentation + geometric measurements."""
import glob, json, os
import numpy as np
import torch
from PIL import Image
from transformers import SamModel, SamProcessor

ROOT = "/home/imss/cw/radiology_rag_p3"
MD = os.path.join(ROOT, "medsam")
OUT = os.path.join(ROOT, "medsam_measure.json")

def main():
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = SamModel.from_pretrained(MD).to(dev).eval()
    proc = SamProcessor.from_pretrained(MD)
    files = sorted(glob.glob(os.path.join(ROOT, "chexbench", "*.png")))[:12]
    print("images:", len(files), "device:", dev, flush=True)
    res = {}
    for p in files:
        img = Image.open(p).convert("RGB")
        w, h = img.size
        # heart region prior: central column, lower thorax
        box = [int(w * 0.20), int(h * 0.30), int(w * 0.80), int(h * 0.85)]
        inputs = proc(img, input_boxes=[[box]], return_tensors="pt").to(dev)
        with torch.no_grad():
            out = model(**inputs, multimask_output=False)
        masks = proc.image_processor.post_process_masks(
            out.pred_masks.cpu(), inputs["original_sizes"].cpu(), inputs["reshaped_input_sizes"].cpu())
        m = masks[0][0][0].numpy() > 0.5
        area = float(m.mean())
        ys, xs = np.where(m)
        if len(xs) == 0:
            res[os.path.basename(p)] = {"area_ratio": 0.0}
            continue
        bw = float((xs.max() - xs.min() + 1) / w)
        bh = float((ys.max() - ys.min() + 1) / h)
        res[os.path.basename(p)] = {"area_ratio": round(area, 4),
                                    "bbox_w_ratio": round(bw, 4),
                                    "bbox_h_ratio": round(bh, 4),
                                    "centroid_x": round(float(xs.mean() / w), 4),
                                    "prompt_box": box}
        print(os.path.basename(p), res[os.path.basename(p)], flush=True)
    json.dump(res, open(OUT, "w"), indent=0)
    print("saved", OUT, len(res), flush=True)

if __name__ == "__main__":
    main()
