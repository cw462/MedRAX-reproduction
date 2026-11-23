#!/usr/bin/env python3
"""Generate paired crops for all laterality questions (Qwen2.5-VL grounding)."""
import json, os, re
import torch
from PIL import Image
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor

ROOT = "/home/imss/cw/radiology_rag_p3"
MODEL = "/home/imss/688/python学习/Qwen_/models/Qwen2.5-VL-7B-Instruct"
CROPDIR = os.path.join(ROOT, "crops")
OUT = os.path.join(ROOT, "crop_boxes.json")

def ask(model, proc, images, text, max_new=48):
    content = [{"type": "image", "image": im} for im in images]
    content.append({"type": "text", "text": text})
    msgs = [{"role": "user", "content": content}]
    t = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inputs = proc(text=[t], images=images, return_tensors="pt").to("cuda:0")
    with torch.no_grad():
        gen = model.generate(**inputs, max_new_tokens=max_new)
    return proc.batch_decode(gen[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]

def ground(model, proc, img, phrase):
    W, H = img.size
    ans = ask(model, proc, [img], f"Locate the {phrase} in this chest radiograph. Reply only with [x1,y1,x2,y2] in pixels. Image is {W}x{H}.")
    m = re.search(r"\[?\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]?", ans)
    if not m: return None
    x1,y1,x2,y2 = [int(v) for v in m.groups()]
    return [max(0,min(x1,x2)), max(0,min(y1,y2)), min(W,max(x1,x2)), min(H,max(y1,y2))]

def crop(img, box, margin=0.3, size=448):
    W,H = img.size
    x1,y1,x2,y2 = box
    bw, bh = max(8,x2-x1), max(8,y2-y1)
    x1=max(0,int(x1-bw*margin)); y1=max(0,int(y1-bh*margin))
    x2=min(W,int(x2+bw*margin)); y2=min(H,int(y2+bh*margin))
    return img.crop((x1,y1,x2,y2)).resize((size,size), Image.LANCZOS)

def main():
    os.makedirs(CROPDIR, exist_ok=True)
    tasks = json.load(open(os.path.join(ROOT, "lat_tasks.json"), encoding="utf-8"))
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(MODEL, torch_dtype=torch.bfloat16, device_map="cuda:0", local_files_only=True)
    proc = AutoProcessor.from_pretrained(MODEL, local_files_only=True)
    print("loaded; tasks", len(tasks), flush=True)
    out = {}
    for i, t in enumerate(tasks, 1):
        p = os.path.join(ROOT, t["image"])
        if not os.path.exists(p): continue
        img = Image.open(p).convert("RGB")
        keys = list(t["options"].keys())[:2]
        rec = {"gold": t["gold_side"], "options": t["options"], "files": {}}
        for k in keys:
            box = ground(model, proc, img, str(t["options"][k]))
            if not box:
                rec["files"][k] = None; continue
            fn = f"{t['qid']}_{k}.jpg"
            crop(img, box).save(os.path.join(CROPDIR, fn), quality=92)
            rec["files"][k] = fn
            rec[f"box_{k}"] = box
        out[t["qid"]] = rec
        if i % 25 == 0: print(i, flush=True)
    json.dump(out, open(OUT, "w"), indent=0)
    print("saved", OUT, len(out), flush=True)

if __name__ == "__main__":
    main()
