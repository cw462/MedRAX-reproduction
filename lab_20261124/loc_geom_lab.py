#!/usr/bin/env python3
"""Generate CXAS landmark geometry evidence for the 291 side tasks (lab).

Only filename-frontal images (147) get landmarks; the VLM will see per-side
diaphragm dome tops + confidence, and judge elevation itself.
"""
import json
import os
import time

import numpy as np
from PIL import Image

os.environ.setdefault("CXAS_PATH", "/home/imss/cw")
os.environ.setdefault("CXAS_NO_WELCOME", "1")
os.environ.setdefault("HF_HOME", "/home/imss/cw/hf")

from cxas.landmarks import LandmarkDetector  # noqa: E402

ROOT = "/home/imss/cw/radiology_rag_p3"
TASKS = ROOT + "/lat_tasks_maira.json"
OUT = ROOT + "/loc_geom.json"

FRONTAL_SUFFIX = {"1001", "1002", "1003", "4001", "4004", "9001"}


def frontal_p(name):
    parts = name.rsplit(".", 1)[0].split("-")
    if len(parts) < 3:
        return False
    return parts[2] in FRONTAL_SUFFIX


def main():
    tasks = [t for t in json.load(open(TASKS, encoding="utf-8")) if t["kind"] == "side"]
    # build basename -> lab path (openi images)
    index = {}
    for dp, _, fn in os.walk("/home/imss/cw/MedRAX_reproduction_20261027/"
                             "code_cxr_vqa_extension/data/chexbench/images/openi"):
        for f in fn:
            if f.endswith((".png", ".jpg")):
                index.setdefault(f, os.path.join(dp, f))
    todo = []
    for t in tasks:
        b = t["image"].rsplit("/", 1)[-1]
        t["_basename"] = b
        if frontal_p(b) and b in index:
            todo.append((t, index[b]))
        else:
            t["_path"] = index.get(b, "")
    print(f"side tasks {len(tasks)}, frontal with path {len(todo)}", flush=True)

    det = LandmarkDetector(device="cuda:0")
    out = {}
    if os.path.exists(OUT):
        try:
            out = json.load(open(OUT, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            out = {}
        # invalidate entries without dome info (recompute after field-name fix)
        out = {q: v for q, v in out.items() if v.get("domes")}
    todo = [(t, p) for (t, p) in todo if t["qid"] not in out]
    names_seen = set()
    t0 = time.time()
    for i, (t, path) in enumerate(todo, 1):
        qid = t["qid"]
        try:
            img = np.asarray(Image.open(path).convert("L"))
            lms = det.predict(img, view="frontal")
            domes = {}
            all_names = {}
            for l in lms:
                nm = str(l.get("class") or l.get("name") or "").lower()
                kp = str(l.get("keypoint") or l.get("kp") or "").lower()
                names_seen.add(f"{nm}/{kp}" if kp else nm)
                all_names.setdefault(nm, []).append(kp)
                if "hemidiaphragm" in nm or ("diaphragm" in nm and "dome" in kp):
                    side = "right" if "right" in nm else "left"
                    domes[side] = {"y": int(l["y"]), "x": int(l["x"]),
                                   "conf": float(l.get("confidence", 0))}
            out[qid] = {"path": path, "h": int(img.shape[0]), "w": int(img.shape[1]),
                        "domes": domes}
            if len(out) <= 5:
                out[qid]["debug_names"] = all_names
        except Exception as exc:  # noqa: BLE001
            out[qid] = {"error": f"{type(exc).__name__}: {exc}"}
        if i % 20 == 0 or i == len(todo):
            json.dump(out, open(OUT, "w"), indent=0)
            el = time.time() - t0
            print(f"{i}/{len(todo)} {el/i:.2f}s/it eta {el/i*(len(todo)-i)/60:.1f}min",
                  flush=True)
    json.dump(out, open(OUT, "w"), indent=0)
    print("landmark names seen:", sorted(names_seen), flush=True)
    print("remaining:", len(todo), "total saved:", len(out), flush=True)
    print("saved", OUT, flush=True)


if __name__ == "__main__":
    main()
