#!/usr/bin/env python3
"""Paired-crop comparison, fully local on the lab server (Qwen2.5-VL as grounder + judge)."""
import json, os, re, sys
import torch
from PIL import Image
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor

ROOT = "/home/imss/cw/radiology_rag_p3"
MODEL = "/home/imss/688/python学习/Qwen_/models/Qwen2.5-VL-7B-Instruct"
OUT = os.path.join(ROOT, "paired_crop.json")
LIMIT = int(os.environ.get("LIMIT", "40"))

def ask(model, proc, images, text):
    content = []
    for im in images:
        content.append({"type": "image", "image": im})
    content.append({"type": "text", "text": text})
    msgs = [{"role": "user", "content": content}]
    t = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inputs = proc(text=[t], images=images, return_tensors="pt").to("cuda:0")
    with torch.no_grad():
        gen = model.generate(**inputs, max_new_tokens=48)
    return proc.batch_decode(gen[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]

def ground(model, proc, img, phrase):
    W, H = img.size
    txt = (f"Locate the {phrase} in this chest radiograph. "
           f"Reply with only a bounding box as [x1,y1,x2,y2] in pixels. Image is {W}x{H}.")
    ans = ask(model, proc, [img], txt)
    m = re.search(r"\[?\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]?", ans)
    if not m: return None
    x1,y1,x2,y2 = [int(v) for v in m.groups()]
    return [max(0,min(x1,x2)), max(0,min(y1,y2)), min(W,max(x1,x2)), min(H,max(y1,y2))]

def crop(img, box, margin=0.25):
    W,H = img.size
    x1,y1,x2,y2 = box
    bw, bh = max(8,x2-x1), max(8,y2-y1)
    x1 = int(max(0, x1-bw*margin)); y1 = int(max(0, y1-bh*margin))
    x2 = int(min(W, x2+bw*margin)); y2 = int(min(H, y2+bh*margin))
    c = img.crop((x1,y1,x2,y2))
    return c.resize((448, 448), Image.LANCZOS)

def main():
    tasks = [t for t in json.load(open(os.path.join(ROOT, "lat_tasks.json"), encoding="utf-8"))][:LIMIT]
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        MODEL, torch_dtype=torch.bfloat16, device_map="cuda:0", local_files_only=True)
    proc = AutoProcessor.from_pretrained(MODEL, local_files_only=True)
    print("loaded; tasks", len(tasks), flush=True)
    out = {}
    for i, t in enumerate(tasks, 1):
        p = os.path.join(ROOT, t["image"])
        if not os.path.exists(p): continue
        img = Image.open(p).convert("RGB")
        opts = t["options"]
        keys = list(opts.keys())[:2]
        text_a, text_b = str(opts[keys[0]]), str(opts[keys[1]])
        ba = ground(model, proc, img, text_a)
        bb = ground(model, proc, img, text_b)
        if not ba or not bb:
            out[t["qid"]] = {"skip": "no_box"}; continue
        ca, cb = crop(img, ba), crop(img, bb)
        finding = re.sub(r"^(left|right)\s+", "", text_a.lower())
        finding = re.sub(r"\b(left|right)\b", "", finding).strip()
        q = (f"Two crops from the same chest radiograph. Exactly one of them shows: {finding}. "
             "Which crop is it, 1 or 2? Reply with only 1 or 2.")
        ans = ask(model, proc, [ca, cb], q)
        pick = 1 if re.search(r"\b1\b", ans) else (2 if re.search(r"\b2\b", ans) else None)
        pred_key = keys[0] if pick == 1 else (keys[1] if pick == 2 else None)
        out[t["qid"]] = {"gold": t["gold_side"], "pred_key": pred_key, "raw": ans[:60], "box_a": ba, "box_b": bb}
        if i % 10 == 0: print(i, flush=True)
    json.dump(out, open(OUT, "w"), indent=0)
    vals = {q: v for q, v in out.items() if v.get("pred_key")}
    print("parsed", len(vals), "/", len(out), flush=True)
    print("saved", OUT, flush=True)

if __name__ == "__main__":
    main()
