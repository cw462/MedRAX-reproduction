#!/usr/bin/env python3
"""MAIRA-2 phrase grounding over CheXBench localization questions."""
import json
import os
import sys
import time

import torch
from PIL import Image
from transformers import AutoModelForCausalLM, AutoProcessor

MODEL = os.environ.get("MODEL", "/dev/shm/maira2")
TASKS = os.environ.get("TASKS", "/dev/shm/lat_tasks_maira.json")
OUT = os.environ.get("OUT", "/dev/shm/maira_boxes.json")
LIMIT = int(os.environ.get("LIMIT", "0"))


def main():
    tasks = json.load(open(TASKS, encoding="utf-8"))
    if LIMIT:
        tasks = tasks[:LIMIT]
    print(f"tasks {len(tasks)}", flush=True)

    t0 = time.time()
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, trust_remote_code=True, torch_dtype=torch.bfloat16
    )
    processor = AutoProcessor.from_pretrained(MODEL, trust_remote_code=True)
    model = model.eval().to("cuda")
    print(f"model loaded in {time.time()-t0:.0f}s; "
          f"gpu {torch.cuda.memory_allocated()/1e9:.1f} GB", flush=True)

    out = {}
    t1 = time.time()
    for i, t in enumerate(tasks, 1):
        try:
            img = Image.open(t["image"]).convert("RGB")
            inp = processor.format_and_preprocess_phrase_grounding_input(
                frontal_image=img, phrase=t["phrase"], return_tensors="pt"
            ).to("cuda")
            with torch.no_grad():
                gen = model.generate(**inp, max_new_tokens=150, use_cache=True)
            pl = inp["input_ids"].shape[-1]
            txt = processor.decode(gen[0][pl:], skip_special_tokens=True)
            pred = processor.convert_output_to_plaintext_or_grounded_sequence(txt)
            boxes = []
            if isinstance(pred, list):
                for _ph, bs in pred:
                    for b in (bs or []):
                        ab = processor.adjust_box_for_original_image_size(
                            b, img.width, img.height
                        )
                        boxes.append({"norm": [round(float(v), 4) for v in b],
                                      "abs": [int(v) for v in ab]})
            out[t["qid"]] = {"phrase": t["phrase"], "text": txt[:300],
                             "boxes": boxes, "wh": [img.width, img.height]}
        except Exception as exc:  # noqa: BLE001
            out[t["qid"]] = {"error": f"{type(exc).__name__}: {exc}", "boxes": []}
        if i % 10 == 0 or i == len(tasks):
            json.dump(out, open(OUT, "w"), indent=0)
            el = time.time() - t1
            eta = el / i * (len(tasks) - i)
            print(f"{i}/{len(tasks)} {el/i:.2f}s/it eta {eta/60:.1f}min "
                  f"boxed={sum(1 for v in out.values() if v.get('boxes'))}", flush=True)

    json.dump(out, open(OUT, "w"), indent=0)
    print("saved", OUT, flush=True)


if __name__ == "__main__":
    main()
