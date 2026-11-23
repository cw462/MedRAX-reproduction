#!/usr/bin/env python3
"""LLM query rewriting: question -> radiology search queries (no answer leakage)."""
import argparse, json, ssl, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
MODEL = "deepseek-v4.1-flash-1017"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
OP = urllib.request.build_opener(urllib.request.ProxyHandler({"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}),
                                 urllib.request.HTTPSHandler(context=ctx))

SYSTEM = ("You convert radiology exam questions into retrieval queries for a medical knowledge base. "
          "Use standard radiology terminology (e.g. 'enlarged heart' -> 'cardiomegaly', 'hylar' -> 'hilar', "
          "'fluid in the lung' -> 'pleural effusion'). Never mention answer options or guess the answer. "
          'Return strict JSON: {"concept": "<main imaging concept>", "queries": ["<q1>", "<q2>"]}')

def key():
    return open("medrax_work/.secrets/token_plan_api.key").read().strip()

def call(question, options):
    user = f"Question: {question}"
    if options:
        user += "\nOptions: " + "; ".join(f"{k}. {v}" for k, v in options.items())
    body = json.dumps({"model": MODEL, "messages": [{"role": "system", "content": SYSTEM},
                                                   {"role": "user", "content": user}],
                       "max_tokens": 160, "temperature": 0, "enable_thinking": False}).encode()
    for attempt in range(3):
        req = urllib.request.Request(BASE + "/chat/completions", data=body, method="POST")
        req.add_header("Authorization", "Bearer " + key()); req.add_header("Content-Type", "application/json")
        try:
            with OP.open(req, timeout=90) as r:
                txt = json.loads(r.read())["choices"][0]["message"]["content"]
            txt = txt.strip()
            s = txt[txt.find("{"): txt.rfind("}") + 1]
            return json.loads(s)
        except Exception as e:
            if attempt == 2:
                return {"concept": question, "queries": [question], "error": str(e)[:80]}
            time.sleep(2)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="rag_eval/data/queries_848.json")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    rows = json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))
    res = {}
    t0 = time.time(); done = 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(call, r["question"], r.get("options") or {}): r for r in rows}
        for f in as_completed(futs):
            r = futs[f]
            res[r["question_id"]] = f.result()
            done += 1
            if done % 50 == 0:
                print(done, "/", len(rows), round(time.time() - t0, 1), flush=True)
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved", a.out, len(res))
    for qid in list(res)[:5]:
        print(qid, res[qid])

if __name__ == "__main__":
    main()
