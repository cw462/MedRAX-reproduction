#!/usr/bin/env python3
"""Qwen2.5-VL phrase grounding -> bbox centroid -> patient side."""
import json, os, re, sys
import torch
from PIL import Image
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor

ROOT = "/home/imss/cw/radiology_rag_p3"
MODEL = "/home/imss/688/python学习/Qwen_/models/Qwen2.5-VL-7B-Instruct"
OUT = os.path.join(ROOT, "qwen_ground_side.json")
TASKS = os.path.join(ROOT, "lat_tasks.json")
LIMIT = int(os.environ.get("LIMIT", "40"))

def main():
    tasks = json.load(open(TASKS, encoding="utf-8"))[:LIMIT]
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        MODEL, torch_dtype=torch.bfloat16, device_map="cuda:0", local_files_only=True)
    proc = AutoProcessor.from_pretrained(MODEL, local_files_only=True)
    print("loaded, tasks", len(tasks), flush=True)
    out = {}
    for i, t in enumerate(tasks, 1):
        p = os.path.join(ROOT, t["image"])
        if not os.path.exists(p): continue
        img = Image.open(p).convert("RGB")
        W, H = img.size
        finding = t.get("finding", "abnormality") or "abnormality"
        msgs = [{"role": "user", "content": [
            {"type": "image", "image": p},
            {"type": "text", "text": f"Locate the {finding} in this chest radiograph. "
                                     f"Reply with only a bounding box in pixel coordinates as [x1,y1,x2,y2]. "
                                     f"The image is {W} pixels wide and {H} pixels high."}]}]
        text = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inputs = proc(text=[text], images=[img], return_tensors="pt").to("cuda:0")
        with torch.no_grad():
            gen = model.generate(**inputs, max_new_tokens=64)
        ans = proc.batch_decode(gen[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]
        m = re.search(r"\[?\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]?", ans)
        if not m:
            out[t["qid"]] = {"raw": ans[:80], "box": None}; continue
        x1, y1, x2, y2 = [int(v) for v in m.groups()]
        cx = ((x1 + x2) / 2) / W
        out[t["qid"]] = {"raw": ans[:80], "box": [x1, y1, x2, y2], "cx": cx,
                         "side_imgleft_is_right": "right" if cx < 0.5 else "left"}
        if i % 10 == 0: print(i, flush=True)
    json.dump(out, open(OUT, "w"), indent=0)
    gold = {t["qid"]: t["gold_side"] for t in tasks}
    n = [q for q in out if out[q].get("box")]
    a = sum(1 for q in n if out[q]["side_imgleft_is_right"] == gold.get(q))
    b = sum(1 for q in n if out[q]["side_imgleft_is_right"] != gold.get(q))
    print(f"parsed {len(n)}/{len(tasks)}; acc(convention img-left=patient-right)={100*a/max(1,len(n)):.1f}%")
    print(f"acc(opposite convention)={100*b/max(1,len(n)):.1f}%", flush=True)
    print("saved", OUT)

if __name__ == "__main__":
    main()
