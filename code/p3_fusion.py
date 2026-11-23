#!/usr/bin/env python3
"""P3 fusion: VLM + detector probability priors on CheXBench yes/no."""
import base64, io, json, os, re, ssl, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

BASE = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
MODEL = os.environ.get("RAG_MODEL", "qwen3.6-flash")
IMG = "H:/RAG_KB/images/chexbench"
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
OP = urllib.request.build_opener(urllib.request.ProxyHandler({"http":"http://127.0.0.1:7897","https":"http://127.0.0.1:7897"}),
                                 urllib.request.HTTPSHandler(context=ctx))

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
    im=Image.open(p).convert("RGB"); buf=io.BytesIO(); im.save(buf,"JPEG",quality=92)
    return base64.b64encode(buf.getvalue()).decode()
def letter(t):
    m=re.search(r"\b([a-d])\b", str(t).lower()); return m.group(1) if m else None

def main():
    probs = json.load(open("rag_eval/detector_probs.json", encoding="utf-8"))
    qm = {r["question_id"]: r for r in json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))}
    inp = {json.loads(l)["question_id"]: json.loads(l) for l in open("rag_eval/data/chexbench_inputs.jsonl", encoding="utf-8")}
    base = {x["qid"]: x for x in json.load(open("rag_eval/p1_chexbench_yn.json", encoding="utf-8"))}
    items = []
    for qid, q in qm.items():
        if q["dataset"] != "chexbench": continue
        opts = q.get("options") or {}
        if set(str(v).lower() for v in opts.values()) != {"yes","no"}: continue
        img = os.path.basename(inp[qid]["images"][0])
        pr = probs.get("chexbench/" + img)
        if not pr: continue
        items.append((qid, q, opts, pr, os.path.join(IMG, img)))
    print("fusion items:", len(items), flush=True)

    def run(it):
        qid, q, opts, pr, path = it
        top = sorted(pr.items(), key=lambda x: -x[1])[:6]
        prior = ", ".join(f"{k} {v:.2f}" for k, v in top)
        txt = (q["question"] + "\nOptions: " + "; ".join(f"{k}. {v}" for k,v in opts.items()) +
               f"\nA separate CXR classifier gave these pathology probabilities for this image: {prior}. "
               "Treat them as weak evidence, the image is primary.\nAnswer with the option letter only.")
        out = vlm([{"role":"user","content":[
            {"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+b64(path)}},
            {"type":"text","text":txt}]}])
        pred = letter(out)
        ref = str(q["reference"]).strip().lower()
        return {"qid": qid, "pred": pred, "ok": pred == ref, "raw": out[:120], "prior": prior}

    res = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for f in as_completed([ex.submit(run, it) for it in items]):
            res.append(f.result())
    ok = sum(1 for r in res if r["ok"])
    b_ok = sum(1 for r in res if base.get(r["qid"], {}).get("base", {}).get("correct"))
    print(f"fusion: {ok}/{len(res)} = {100*ok/len(res):.1f}%")
    print(f"baseline (same items): {b_ok}/{len(res)} = {100*b_ok/len(res):.1f}%")
    json.dump(res, open("rag_eval/p3_fusion.json", "w"), ensure_ascii=False)

if __name__ == "__main__":
    main()
