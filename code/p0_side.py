#!/usr/bin/env python3
"""P0: does a side-first answer beat letter-choice on CheXBench laterality questions?

Arm A (baseline): show options, answer with letter.
Arm B (side-first): ask explicitly "is the finding on the patient's LEFT or RIGHT side?"
                    then map the word back to the option letter.
"""
import base64, json, os, re, ssl, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

BASE = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
MODEL = os.environ.get("RAG_MODEL", "qwen3.6-flash")
IMG = "H:/RAG_KB/images/chexbench"
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
OP = urllib.request.build_opener(urllib.request.ProxyHandler({"http":"http://127.0.0.1:7897","https":"http://127.0.0.1:7897"}),
                                 urllib.request.HTTPSHandler(context=ctx))
LAT = {"right","left"}
SITE = {"upper","lower","mid","apex","base","lateral","medial","basal","hilar","peripheral","central","anterior","posterior","superior","inferior"}

def key(): return open("medrax_work/.secrets/token_plan_api.key").read().strip()

def vlm(msgs, mt=60, retries=3):
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
    im = Image.open(p).convert("RGB")
    import io; buf=io.BytesIO(); im.save(buf,"JPEG",quality=92)
    return base64.b64encode(buf.getvalue()).decode()

def toks(s): return set(re.findall(r"[a-z]+", str(s).lower())) - {"the","a","of","in","with","and","patient","side"}

def parse_options(o):
    """Return (kind, differing token, common phrase, options) or None."""
    if not o or len(o) < 2: return None
    keys = list(o.keys())
    a, b = str(o[keys[0]]), str(o[keys[1]])
    ta, tb = toks(a), toks(b)
    diff = (ta - tb) | (tb - ta)
    if diff and diff <= LAT:
        return ("side", sorted(diff), a, b, o)
    if diff and diff <= SITE:
        return ("site", sorted(diff), a, b, o)
    return None

def letter_of(text):
    m = re.search(r"\b([a-d])\b", str(text).lower())
    return m.group(1) if m else None

def run_one(item):
    qid, question, opts, ref, path = item
    parsed = parse_options(opts)
    data = b64(path)
    # Arm A: plain letter
    txtA = question + "\nOptions: " + "; ".join(f"{k}. {v}" for k,v in opts.items()) + "\nAnswer with the option letter only."
    outA = vlm([{"role":"user","content":[{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+data}},
                                          {"type":"text","text":txtA}]}])
    # Arm B: side-first
    kind, words, a, b, _ = parsed
    common = " ".join(sorted((toks(a) & toks(b)) - SITE)) or "the finding"
    if kind == "side":
        txtB = (f"Look at the chest radiograph. In standard radiograph display the left side of the image is the patient's RIGHT side.\n"
                f"Is the {common} on the patient's LEFT side or the patient's RIGHT side?\n"
                "Answer with one word: left or right.")
        outB = vlm([{"role":"user","content":[{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+data}},
                                              {"type":"text","text":txtB}]}])
        side = "left" if re.search(r"\bleft\b", outB.lower()) else ("right" if re.search(r"\bright\b", outB.lower()) else "?")
        predB = None
        for k,v in opts.items():
            if side != "?" and side in str(v).lower(): predB = k.lower()
    else:
        txtB = (f"Look at the chest radiograph.\nIs the {common} in the UPPER or LOWER part of the image?\n"
                "Answer with one word: upper or lower.")
        outB = vlm([{"role":"user","content":[{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+data}},
                                              {"type":"text","text":txtB}]}])
        w = "upper" if re.search(r"\bupper\b", outB.lower()) else ("lower" if re.search(r"\blower\b", outB.lower()) else "?")
        predB = None
        for k,v in opts.items():
            if w != "?" and w in str(v).lower(): predB = k.lower()
    predA = letter_of(outA)
    ref = str(ref).strip().lower()
    return {"qid": qid, "ref": ref, "predA": predA, "predB": predB,
            "okA": predA == ref, "okB": predB == ref,
            "ansA": outA[:80], "ansB": outB[:80], "kind": kind, "common": common}

def main():
    qm = {r["question_id"]: r for r in json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))}
    inp = {json.loads(l)["question_id"]: json.loads(l) for l in open("rag_eval/data/chexbench_inputs.jsonl", encoding="utf-8")}
    items = []
    for qid, q in qm.items():
        if q["dataset"] != "chexbench": continue
        o = q.get("options") or {}
        if not parse_options(o): continue
        p = os.path.join(IMG, os.path.basename(inp[qid]["images"][0]))
        if not os.path.exists(p): continue
        items.append((qid, q["question"], o, q["reference"], p))
    print("laterality/site questions:", len(items), flush=True)
    res = []
    with ThreadPoolExecutor(max_workers=int(os.environ.get("WORKERS","6"))) as ex:
        for f in as_completed([ex.submit(run_one, it) for it in items]):
            res.append(f.result())
    n = len(res)
    okA = sum(1 for r in res if r["okA"]); okB = sum(1 for r in res if r["okB"])
    print(f"baseline letter : {okA}/{n} = {100*okA/n:.1f}%")
    print(f"side-first      : {okB}/{n} = {100*okB/n:.1f}%")
    side_sub = [r for r in res if r["kind"] == "side"]
    if side_sub:
        a = sum(1 for r in side_sub if r["okA"]); b = sum(1 for r in side_sub if r["okB"])
        print(f"  其中 side 类 n={len(side_sub)}: letter {100*a/len(side_sub):.1f}% -> side-first {100*b/len(side_sub):.1f}%")
    json.dump(res, open("rag_eval/p0_side_result.json","w"), ensure_ascii=False)
    print("saved rag_eval/p0_side_result.json")

if __name__ == "__main__":
    main()
