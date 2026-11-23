#!/usr/bin/env python3
"""Does contralateral crop (left/right half, same scale) beat full-image for laterality questions?"""
import base64, io, json, os, re, ssl, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

BASE = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
MODEL = "deepseek-v4.1-flash-1017"
IMG = "H:/RAG_KB/images/chexbench"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
OP = urllib.request.build_opener(urllib.request.ProxyHandler({"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}),
                                 urllib.request.HTTPSHandler(context=ctx))
LAT = {"right","left","bilateral","both","upper","lower","mid","apex","base","lateral","medial","basal","hilar","peripheral","central","anterior","posterior","superior","inferior"}

def key(): return open("medrax_work/.secrets/token_plan_api.key").read().strip()

def vlm(messages, max_tokens=40, retries=3):
    body = json.dumps({"model": MODEL, "messages": messages, "max_tokens": max_tokens,
                       "temperature": 0, "enable_thinking": False}).encode()
    for a in range(retries):
        req = urllib.request.Request(BASE + "/chat/completions", data=body, method="POST")
        req.add_header("Authorization", "Bearer " + key()); req.add_header("Content-Type", "application/json")
        try:
            with OP.open(req, timeout=180) as r:
                return (json.loads(r.read())["choices"][0]["message"].get("content") or "").strip()
        except Exception:
            if a == retries - 1: return "ERR"
            time.sleep(2)

def b64(im):
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode()

def laterality(opts):
    vals = [str(v).lower() for v in opts.values()]
    s = " ".join(vals)
    return bool(re.search(r"\b(left|right)\b", s)) and not re.search(r"bilateral", s)

def norm(s): return re.sub(r"[^a-z0-9 ]", " ", str(s).lower())

def score(pred, ref, opts):
    p = norm(pred)
    m = re.search(r"\b([a-d])\b", p)
    if m: return m.group(1) == str(ref).strip().lower()
    for k, v in opts.items():
        if norm(v) and norm(v) in p: return k.lower() == str(ref).strip().lower()
    if re.search(r"\bleft\b", p): return norm(opts.get("A","")) .startswith("left") and False
    return False

def main():
    qm = {r["question_id"]: r for r in json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))}
    inp = {json.loads(l)["question_id"]: json.loads(l) for l in open("rag_eval/data/chexbench_inputs.jsonl", encoding="utf-8")}
    items = []
    for qid, q in qm.items():
        if q["dataset"] != "chexbench": continue
        opts = q.get("options") or {}
        if laterality(opts): items.append((qid, q["question"], opts, q["reference"]))
    items = [it for it in items if os.path.exists(os.path.join(IMG, os.path.basename(inp[it[0]]["images"][0])))][:100]
    print("laterality questions sampled:", len(items), flush=True)

    def run(it):
        qid, question, opts, ref = it
        path = os.path.join(IMG, os.path.basename(inp[qid]["images"][0]))
        if not os.path.exists(path):
            return None
        im = Image.open(path).convert("RGB")
        w, h = im.size
        full = vlm([{"role":"user","content":[
            {"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+b64(im)}},
            {"type":"text","text":question+"\nOptions: "+"; ".join(f"{k}. {v}" for k,v in opts.items())+"\nAnswer with the option letter only."}]}])
        # standard radiograph display: image-left half = patient's RIGHT hemithorax
        right_hemi = im.crop((0, 0, w // 2, h)).resize((w, h), Image.LANCZOS)
        left_hemi = im.crop((w // 2, 0, w, h)).resize((w, h), Image.LANCZOS)
        crop = vlm([{"role":"user","content":[
            {"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+b64(right_hemi)}},
            {"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+b64(left_hemi)}},
            {"type":"text","text":"The first image is the patient's RIGHT hemithorax, the second is the patient's LEFT hemithorax (both from the same chest radiograph, same scale).\n"+question+"\nOptions: "+"; ".join(f"{k}. {v}" for k,v in opts.items())+"\nAnswer with the option letter only."}]}])
        return norm(full), norm(crop), str(ref).strip().lower(), opts

    res = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for f in as_completed([ex.submit(run, it) for it in items]):
            out = f.result()
            if out: res.append(out)
    def ok(p, ref, opts):
        m = re.search(r"\b([a-d])\b", p)
        if m: return m.group(1) == ref
        for k, v in opts.items():
            if norm(v) and norm(v) in p: return k.lower() == ref
        return False
    fb = sum(1 for full, crop, ref, opts in res if ok(full, ref, opts))
    cb = sum(1 for full, crop, ref, opts in res if ok(crop, ref, opts))
    json.dump([{"full": a, "crop": b, "ref": c, "opts": d} for a, b, c, d in res],
              open("rag_eval/lat_experiment.json", "w"), ensure_ascii=False)
    print(f"full-image: {fb}/{len(res)} = {100*fb/len(res):.1f}%")
    print(f"left/right half crops: {cb}/{len(res)} = {100*cb/len(res):.1f}%")

if __name__ == "__main__":
    main()