#!/usr/bin/env python3
"""Does higher effective resolution rescue fine-detail yes/no questions?

Split each CXR into 2x2 overlapping tiles (upscaled), ask the same question on
the full image and on the tiles, compare accuracy.
"""
import base64, io, json, os, re, ssl, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

BASE = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
MODEL = "deepseek-v4.1-flash-1017"
IMGDIR = "H:/RAG_KB/images/vqarad"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
OP = urllib.request.build_opener(urllib.request.ProxyHandler({"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}),
                                 urllib.request.HTTPSHandler(context=ctx))

FINE = re.compile(r"(pneumothorax|pleural|lymphadenopath|hilar|free air|mass|nodule|catheter|fracture|"
                  r"contour|border|outline|narrowing|obscured|apex|fossa|calcif)", re.I)

def key():
    return open("medrax_work/.secrets/token_plan_api.key").read().strip()

def vlm(messages, max_tokens=40, retries=3):
    body = json.dumps({"model": MODEL, "messages": messages, "max_tokens": max_tokens,
                       "temperature": 0, "enable_thinking": False}).encode()
    for attempt in range(retries):
        req = urllib.request.Request(BASE + "/chat/completions", data=body, method="POST")
        req.add_header("Authorization", "Bearer " + key()); req.add_header("Content-Type", "application/json")
        try:
            with OP.open(req, timeout=180) as r:
                return (json.loads(r.read())["choices"][0]["message"].get("content") or "").strip()
        except Exception as e:
            if attempt == retries - 1:
                return "ERROR:" + str(e)[:60]
            time.sleep(2)

def b64(img):
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode()

def tiles(im):
    w, h = im.size
    out = []
    for i in range(2):
        for j in range(2):
            x0 = int(j * (w / 2) * 0.9); x1 = min(w, int(w / 2 + j * w / 2 + w * 0.05))
            y0 = int(i * (h / 2) * 0.9); y1 = min(h, int(h / 2 + i * h / 2 + h * 0.05))
            out.append(im.crop((x0, y0, x1, y1)).resize((int((x1 - x0) * 1.6), int((y1 - y0) * 1.6)), Image.LANCZOS))
    return out

def ask(img, q):
    msgs = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64(img)}},
        {"type": "text", "text": q + "\nAnswer with one word only: yes or no."}]}]
    return vlm(msgs)

def norm(s):
    s = s.lower()
    return "yes" if re.search(r"\byes\b", s) else ("no" if re.search(r"\bno\b", s) else "?")

def main():
    d = json.load(open("rag_eval/res_vqarad_wiki.json", encoding="utf-8"))
    qmap = {r["question_id"]: r for r in json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))}
    inp = {json.loads(l)["question_id"]: json.loads(l) for l in open("rag_eval/data/vqarad_inputs.jsonl", encoding="utf-8")}
    items = []
    for x in d:
        q = qmap.get(x["qid"], {})
        if not FINE.search(q.get("question", "")): continue
        ref = str(q.get("reference", "")).strip().lower()
        if ref not in ("yes", "no"): continue
        items.append((x["qid"], q["question"], ref))
    print("fine-detail yes/no questions:", len(items), flush=True)

    def run(item):
        qid, question, ref = item
        path = os.path.join(IMGDIR, inp[qid]["images"][0])
        im = Image.open(path).convert("RGB")
        full = ask(im, question)
        tls = tiles(im)
        votes = [norm(ask(t, question)) for t in tls]
        maj = "yes" if votes.count("yes") >= votes.count("no") else "no"
        return qid, ref, norm(full), maj, votes

    res = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(run, it) for it in items]
        for f in as_completed(futs):
            res.append(f.result())
    full_ok = sum(1 for _, ref, f, m, v in res if f == ref)
    tile_ok = sum(1 for _, ref, f, m, v in res if m == ref)
    print(f"full-image acc: {full_ok}/{len(res)} = {100*full_ok/len(res):.1f}%")
    print(f"2x2-tile majority acc: {tile_ok}/{len(res)} = {100*tile_ok/len(res):.1f}%")
    for qid, ref, f, m, v in res[:12]:
        print(" ", qid, "ref", ref, "full", f, "tiles", v, "->", m)
    json.dump(res, open("rag_eval/tile_experiment.json", "w"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
