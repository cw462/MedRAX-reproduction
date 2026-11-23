#!/usr/bin/env python3
"""P3 evaluation: detector-only and detector+VLM fusion on CheXBench yes/no."""
import base64, io, json, os, re, ssl, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

BASE = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
MODEL = os.environ.get("RAG_MODEL", "qwen3.6-flash")
IMGDIR = "H:/RAG_KB/images/chexbench"
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
OP = urllib.request.build_opener(urllib.request.ProxyHandler({"http":"http://127.0.0.1:7897","https":"http://127.0.0.1:7897"}),
                                 urllib.request.HTTPSHandler(context=ctx))

MAP = [
    (r"atelecta", ["Atelectasis"]),
    (r"cardiomegal|heart (size|enlarg)|enlarged heart|cardiovascular", ["Cardiomegaly", "Enlarged Cardiomediastinum"]),
    (r"effusion", ["Effusion"]),
    (r"pneumothorax", ["Pneumothorax"]),
    (r"consolidat", ["Consolidation"]),
    (r"edema", ["Edema"]),
    (r"emphysem|hyperinfl|hyperdistention", ["Emphysema"]),
    (r"fibros|interstitial", ["Fibrosis"]),
    (r"nodule", ["Nodule"]),
    (r"mass", ["Mass"]),
    (r"fracture", ["Fracture"]),
    (r"hernia", ["Hernia"]),
    (r"opacit", ["Lung Opacity"]),
    (r"lesion", ["Lung Lesion"]),
    (r"pleural", ["Pleural_Thickening", "Effusion"]),
]

def key(): return open("medrax_work/.secrets/token_plan_api.key").read().strip()
def vlm(msgs, mt=40, retries=3):
    body = json.dumps({"model":MODEL,"messages":msgs,"max_tokens":mt,"temperature":0,"enable_thinking":False}).encode()
    for a in range(retries):
        req = urllib.request.Request(BASE+"/chat/completions", data=body, method="POST")
        req.add_header("Authorization","Bearer "+key()); req.add_header("Content-Type","application/json")
        try:
            with OP.open(req, timeout=180) as r: return (json.loads(r.read())["choices"][0]["message"].get("content") or "").strip()
        except Exception:
            if a==retries-1: return "ERR"
            time.sleep(2)
def b64(p):
    im = Image.open(p).convert("RGB"); buf=io.BytesIO(); im.save(buf,"JPEG",quality=92)
    return base64.b64encode(buf.getvalue()).decode()

def target(q):
    s = q.lower()
    for pat, labs in MAP:
        if re.search(pat, s): return labs
    return None

def main():
    probs = json.load(open("rag_eval/detector_probs.json", encoding="utf-8"))
    qm = {r["question_id"]: r for r in json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))}
    inp = {json.loads(l)["question_id"]: json.loads(l) for l in open("rag_eval/data/chexbench_inputs.jsonl", encoding="utf-8")}
    base = {x["qid"]: x for x in json.load(open("rag_eval/p1_chexbench_yn.json", encoding="utf-8"))}
    rows = []
    for qid, q in qm.items():
        if q["dataset"] != "chexbench": continue
        opts = q.get("options") or {}
        if set(str(v).lower() for v in opts.values()) != {"yes","no"}: continue
        labs = target(q["question"])
        if not labs: continue
        img = os.path.basename(inp[qid]["images"][0])
        pr = probs.get("chexbench/" + img)
        if not pr: continue
        vals = {k.lower(): str(v).lower() for k, v in opts.items()}
        ref = str(q["reference"]).strip().lower()
        gold = vals.get(ref)
        if gold not in ("yes","no"): continue
        p = max(pr.get(l, 0.0) for l in labs)
        rows.append({"qid": qid, "q": q["question"], "opts": opts, "gold": gold, "p": p,
                     "path": os.path.join(IMGDIR, img), "labs": labs})
    # detector only
    ok = sum(1 for r in rows if (r["p"] >= 0.5) == (r["gold"] == "yes"))
    print(f"detector-only (threshold 0.5) on {len(rows)} finding-specific yes/no: {ok}/{len(rows)} = {100*ok/len(rows):.1f}%")
    # VLM baseline on same subset
    vb = [r for r in rows if base.get(r["qid"], {}).get("base", {}).get("correct") is not None]
    bok = sum(1 for r in vb if base[r["qid"]]["base"]["correct"])
    print(f"VLM baseline on same subset: {bok}/{len(vb)} = {100*bok/len(vb):.1f}%")
    json.dump(rows, open("rag_eval/p3_rows.json", "w"), ensure_ascii=False)
    print("saved rows", len(rows))

if __name__ == "__main__":
    main()
