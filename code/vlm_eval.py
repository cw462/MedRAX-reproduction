#!/usr/bin/env python3
"""VLM (+/- RAG) evaluation on the frozen cohorts (concurrent)."""
import argparse, base64, json, os, re, ssl, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, "rag_eval")
import index as bidx

BASE = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
MODEL = os.environ.get("RAG_MODEL", "deepseek-v4.1-flash-1017")
IMG = {"slake": "H:/RAG_KB/images/slake", "vqarad": "H:/RAG_KB/images/vqarad", "chexbench": "H:/RAG_KB/images/chexbench"}
INP = {"slake": "rag_eval/data/slake_inputs.jsonl", "vqarad": "rag_eval/data/vqarad_inputs.jsonl",
       "chexbench": "rag_eval/data/chexbench_inputs.jsonl"}
RETRIEVAL = os.environ.get("RAG_RETRIEVAL", "")

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
OP = urllib.request.build_opener(urllib.request.ProxyHandler({"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}),
                                 urllib.request.HTTPSHandler(context=ctx))

def key():
    return open("medrax_work/.secrets/token_plan_api.key").read().strip()

def vlm(messages, max_tokens=60, retries=3):
    body = json.dumps({"model": MODEL, "messages": messages, "max_tokens": max_tokens,
                       "temperature": 0, "enable_thinking": False}).encode()
    for attempt in range(retries):
        req = urllib.request.Request(BASE + "/chat/completions", data=body, method="POST")
        req.add_header("Authorization", "Bearer " + key()); req.add_header("Content-Type", "application/json")
        try:
            with OP.open(req, timeout=180) as r:
                d = json.loads(r.read())
            return (d["choices"][0]["message"].get("content") or "").strip()
        except Exception as e:
            if attempt == retries - 1:
                return "ERROR:" + str(e)[:80]
            time.sleep(3)

def norm_ans(s):
    s = re.sub(r"[^a-z0-9 ]", " ", str(s).lower())
    return re.sub(r"\s+", " ", s).strip()

def score(pred, ref, options):
    if pred.startswith("ERROR:"): return None
    p, r = norm_ans(pred), norm_ans(ref)
    if options:
        m = re.search(r"\b([a-d])\b", p)
        if m and m.group(1) in [k.lower() for k in options]:
            return m.group(1) == r
        for k, v in options.items():
            nv = norm_ans(v)
            if nv and nv in p: return k.lower() == r
        return False
    if r in ("yes", "no"):
        if re.search(r"\byes\b", p): return r == "yes"
        if re.search(r"\bno\b", p): return r == "no"
        return False
    return r == p or r in p.split()

def b64(path):
    return base64.b64encode(open(path, "rb").read()).decode()

def evidence(docs):
    return "\n\n".join(f"[{i}] {d['title'][:140]}\n{d['contents'][:600]}" for i, d in enumerate(docs, 1))

PROMPT_VARIANT = os.environ.get("RAG_PROMPT", "plain")
GATE = os.environ.get("RAG_GATE", "") == "1"
GATE_STOP = set("""a an the of in on at to for with and or is are was were be been being this that these those
what which who whom how why when where does do did can could should would may might will patient patients
image images picture show shows seen evidence present observed any there normal abnormal chest x-ray""".split())

def gate_docs(docs, question):
    """Keep only evidence whose title shares a content word with the question."""
    if not GATE:
        return docs
    toks = {w for w in re.findall(r"[a-z]{3,}", question.lower()) if w not in GATE_STOP}
    keep = []
    for d in docs:
        hay = (d["title"] + " " + d["contents"][:240]).lower()
        if any(t in hay for t in toks):
            keep.append(d)
    return keep[:3]

def task(ds, row, meta, arm, idx, ranking):
    qid = row["question_id"]
    opts = meta.get("options") or {}
    ref = meta.get("reference", "")
    ipath = os.path.join(IMG[ds], os.path.basename(row["images"][0]) if ds == "chexbench" else row["images"][0])
    if not os.path.exists(ipath):
        return ds, qid, arm, {"error": "missing_image", "path": ipath}
    qtext = row["question"]
    if opts:
        qtext += "\nOptions: " + "; ".join(f"{k}. {v}" for k, v in opts.items())
    if arm == "rag":
        docs = ranking.get(qid) if ranking else bidx.search(idx, qtext, 5)
        if not docs:
            docs = []
        docs = gate_docs(docs, qtext)
        if PROMPT_VARIANT == "criteria":
            prompt = ("Background medical knowledge (reference only, NOT a description of this image):\n"
                      + evidence(docs) + "\n\nNow look at the image and answer: " + qtext +
                      "\nBase the answer on what you see in the image. Use the reference only to know what to look for. "
                      "Answer with the single best word/phrase or option letter only.")
        else:
            prompt = ("You are given retrieved medical reference material (may be irrelevant).\n\nEVIDENCE:\n"
                      + evidence(docs) + "\n\nQuestion about the image: " + qtext +
                      "\nUse the evidence only if it is relevant. Answer with the single best word/phrase or option letter only.")
    else:
        prompt = ("Question about the image: " + qtext +
                  "\nAnswer with the single best word/phrase or option letter only.")
    msgs = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64(ipath)}},
        {"type": "text", "text": prompt}]}]
    out = vlm(msgs)
    return ds, qid, arm, {"raw": out, "correct": score(out, ref, opts)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, choices=["slake", "vqarad", "chexbench"])
    ap.add_argument("--arm", default="both", choices=["base", "rag", "both"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--subset", default="all", choices=["all", "yn"])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    idx = bidx.load()
    ranking = json.load(open(RETRIEVAL, encoding="utf-8")) if RETRIEVAL else None
    meta = {r["question_id"]: r for r in json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))}
    rows = [json.loads(l) for l in open(INP[a.dataset], encoding="utf-8") if l.strip()]
    if a.subset == "yn":
        def is_yn(r):
            o = r.get("options") or {}
            if o: return set(str(v).lower() for v in o.values()) <= {"yes", "no"}
            return str(meta[r["question_id"]].get("reference", "")).strip().lower() in ("yes", "no")
        rows = [r for r in rows if is_yn(r)]
    if a.limit: rows = rows[:a.limit]
    arms = ["base", "rag"] if a.arm == "both" else [a.arm]

    results = {r["question_id"]: {"dataset": a.dataset, "qid": r["question_id"], "reference": meta[r["question_id"]].get("reference")} for r in rows}
    jobs = [(r, arm) for r in rows for arm in arms]
    t0 = time.time(); done = 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(task, a.dataset, r, meta[r["question_id"]], arm, idx, ranking) for r, arm in jobs]
        for f in as_completed(futs):
            ds, qid, arm, out = f.result()
            results[qid][arm] = out
            done += 1
            if done % 20 == 0:
                print(done, "/", len(jobs), round(time.time() - t0, 1), flush=True)
    json.dump(list(results.values()), open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for arm in arms:
        vals = [v[arm]["correct"] for v in results.values() if arm in v and v[arm].get("correct") is not None]
        print(f"{a.dataset} {arm}: {sum(vals)}/{len(vals)} = {100*sum(vals)/max(1,len(vals)):.2f}%")
    print("saved", a.out)

if __name__ == "__main__":
    main()