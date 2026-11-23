#!/usr/bin/env python3
"""MAIRA-2 grounded report generation, then answer laterality from the text."""
import json
import os
import time

import torch
from PIL import Image
from transformers import AutoModelForCausalLM, AutoProcessor

MODEL = os.environ.get("MODEL", "/dev/shm/maira2")
TASKS = os.environ.get("TASKS", "/dev/shm/lat_tasks_maira.json")
OUT = os.environ.get("OUT", "/dev/shm/maira_reports.json")
LIMIT = int(os.environ.get("LIMIT", "0"))


def main():
    tasks = json.load(open(TASKS, encoding="utf-8"))
    if LIMIT:
        tasks = tasks[:LIMIT]
    imgs = []
    seen = set()
    for t in tasks:
        if t["image"] not in seen:
            seen.add(t["image"])
            imgs.append(t["image"])
    print(f"tasks {len(tasks)}, unique images {len(imgs)}", flush=True)

    t0 = time.time()
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, trust_remote_code=True, torch_dtype=torch.bfloat16
    )
    processor = AutoProcessor.from_pretrained(MODEL, trust_remote_code=True)
    model = model.eval().to("cuda")
    print(f"model loaded {time.time()-t0:.0f}s", flush=True)

    out = {}
    if os.path.exists(OUT):
        out = json.load(open(OUT, encoding="utf-8"))
    t1 = time.time()
    for i, p in enumerate(imgs, 1):
        if p in out:
            continue
        try:
            img = Image.open(p).convert("RGB")
            inp = processor.format_and_preprocess_reporting_input(
                current_frontal=img,
                current_lateral=None,
                prior_frontal=None,
                indication="",
                technique="PA view of the chest.",
                comparison="",
                prior_report=None,
                return_tensors="pt",
                get_grounding=True,
            ).to("cuda")
            with torch.no_grad():
                gen = model.generate(**inp, max_new_tokens=450, use_cache=True)
            pl = inp["input_ids"].shape[-1]
            txt = processor.decode(gen[0][pl:], skip_special_tokens=True).lstrip()
            pred = processor.convert_output_to_plaintext_or_grounded_sequence(txt)
            sents = []
            if isinstance(pred, list):
                for ph, bs in pred:
                    boxes = []
                    for b in (bs or []):
                        ab = processor.adjust_box_for_original_image_size(
                            b, img.width, img.height
                        )
                        boxes.append({"norm": [round(float(v), 4) for v in b],
                                      "abs": [int(v) for v in ab]})
                    sents.append({"text": ph, "boxes": boxes})
            else:
                sents = [{"text": str(pred), "boxes": []}]
            out[p] = {"sentences": sents, "raw": txt[:1500]}
        except Exception as exc:  # noqa: BLE001
            out[p] = {"error": f"{type(exc).__name__}: {exc}", "sentences": []}
        if i % 10 == 0 or i == len(imgs):
            json.dump(out, open(OUT, "w"), indent=0)
            el = time.time() - t1
            print(f"{i}/{len(imgs)} {el/i:.2f}s/it eta {el/i*(len(imgs)-i)/60:.1f}min",
                  flush=True)
    json.dump(out, open(OUT, "w"), indent=0)
    print("saved", OUT, flush=True)


if __name__ == "__main__":
    main()
