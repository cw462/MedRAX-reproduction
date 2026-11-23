#!/usr/bin/env python3
"""Grad-CAM box from the CXR detector -> MedSAM mask -> measurement."""
import glob, json, os
import numpy as np
import torch
import torch.nn.functional as F
import torchxrayvision as xrv
from PIL import Image
from transformers import SamModel, SamProcessor

ROOT = "/home/imss/cw/radiology_rag_p3"
MD = os.path.join(ROOT, "medsam")
OUT = os.path.join(ROOT, "gradcam_measure.json")

LABEL_MAP = {
    "cardiomegaly": "Cardiomegaly", "heart": "Cardiomegaly",
    "effusion": "Effusion", "pleural": "Effusion",
    "hyperdistention": "Emphysema", "emphysem": "Emphysema",
    "scoliosis": "Fracture", "degeneration": "Fracture",
    "atelectasis": "Atelectasis", "consolidation": "Consolidation",
    "pneumothorax": "Pneumothorax", "nodule": "Nodule", "mass": "Mass",
}

def gradcam_box(model, dev, pil, label):
    arr = np.asarray(pil.convert("L"), dtype=np.float32)
    arr = xrv.datasets.normalize(arr, 255)[None, ...]
    arr = xrv.datasets.XRayCenterCrop()(arr)
    arr = xrv.datasets.XRayResizer(224)(arr)
    x = torch.from_numpy(arr[None, ...]).to(dev)
    model.zero_grad()
    feats = {}
    def hook(m, inp, out):
        out.retain_grad()
        feats["act"] = out
    h = model.features.norm5.register_forward_hook(hook)
    out = model(x)
    h.remove()
    idx = model.pathologies.index(label)
    model.zero_grad()
    out[0, idx].backward()
    full = feats["act"]
    gfull = full.grad
    if gfull is None:
        return None
    act = full[0].detach()
    grad = gfull[0].detach()
    w = grad.mean(dim=(1, 2), keepdim=True)
    cam = F.relu((w * act).sum(0))
    cam = cam - cam.min()
    cam = cam / (cam.max() + 1e-8)
    cam_np = cam.detach().cpu().numpy()
    cw, ch = cam_np.shape
    ys, xs = np.where(cam_np > 0.5)
    if len(xs) == 0: return None
    W, H = pil.size
    return [int(xs.min() / cw * W), int(ys.min() / ch * H), int((xs.max() + 1) / cw * W), int((ys.max() + 1) / ch * H)]

def seg_measure(sam, proc, dev, pil, box):
    y0, x0, y1, x1 = max(0, box[1]), max(0, box[0]), min(pil.size[1], box[3]), min(pil.size[0], box[2])
    if x1 - x0 < 8 or y1 - y0 < 8: return None
    inputs = proc(pil, input_boxes=[[[x0, y0, x1, y1]]], return_tensors="pt").to(dev)
    with torch.no_grad():
        out = sam(**inputs, multimask_output=False)
    masks = proc.image_processor.post_process_masks(out.pred_masks.cpu(), inputs["original_sizes"].cpu(), inputs["reshaped_input_sizes"].cpu())
    m = masks[0][0][0].numpy() > 0.5
    ys, xs = np.where(m)
    if len(xs) == 0: return None
    W, H = pil.size
    return {"area_ratio": float(m.mean()), "bbox_w_ratio": float((xs.max()-xs.min()+1)/W),
            "bbox_h_ratio": float((ys.max()-ys.min()+1)/H), "centroid_x": float(xs.mean()/W), "box": box}

def main():
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    det = xrv.models.DenseNet(weights="densenet121-res224-all").to(dev).eval()
    sam = SamModel.from_pretrained(MD).to(dev).eval()
    proc = SamProcessor.from_pretrained(MD)
    tasks = json.load(open(os.path.join(ROOT, "measure_tasks.json"), encoding="utf-8"))
    print("tasks:", len(tasks), flush=True)
    res = {}
    for i, t in enumerate(tasks, 1):
        p = os.path.join(ROOT, t["image"])
        if not os.path.exists(p): continue
        pil = Image.open(p).convert("RGB")
        lab = None
        for k, v in LABEL_MAP.items():
            if k in t.get("question", "").lower() or k in jstr(t.get("options")):
                lab = v; break
        if not lab:
            res[t["qid"]] = {"skip": "no_label"}; continue
        box = gradcam_box(det, dev, pil, lab)
        if not box:
            res[t["qid"]] = {"skip": "no_box"}; continue
        m = seg_measure(sam, proc, dev, pil, box)
        res[t["qid"]] = {"label": lab, "measure": m}
        if i % 10 == 0: print(i, flush=True)
    json.dump(res, open(OUT, "w"), indent=0)
    print("saved", OUT, len(res), flush=True)

def jstr(o):
    return json.dumps(o, ensure_ascii=False).lower() if o else ""

if __name__ == "__main__":
    main()
