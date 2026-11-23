#!/usr/bin/env python3
"""Test positional bias: present options in reversed order and map the answer back."""
import base64, io, json, os, re, ssl, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

BASE = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
MODEL = "deepseek-v4.1-flash-1017"
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
def b64(im):
    buf=io.BytesIO(); im.save(buf,"JPEG",quality=92); return base64.b64encode(buf.getvalue()).decode()
def letter(p):
    m=re.search(r"\b([a-d])\b", (p or "").lower()); return m.group(1) if m else "?"

def main():
    d = json.load(open("rag_eval/lat_experiment.json", encoding="utf-8"))
    qm = {r["question_id"]: r for r in json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))}
    inp = {json.loads(l)["question_id"]: json.loads(l) for l in open("rag_eval/data/chexbench_inputs.jsonl", encoding="utf-8")}
    # recover qids in the same order as the original experiment
    LAT = {"right","left","bilateral","both","upper","lower","mid","apex","base","lateral","medial","basal","hilar","peripheral","central","anterior","posterior","superior","inferior"}
    cands=[]
    for qid,q in qm.items():
        if q["dataset"]!="chexbench": continue
        opts=q.get("options") or {}; vals=[str(v).lower() for v in opts.values()]
        if not opts or set(vals)<={"yes","no"}: continue
        toks=[set(v.split()) for v in vals]; diff=set()
        for i in range(len(toks)):
            for j in range(i+1,len(toks)): diff |= (toks[i]-toks[j])|(toks[j]-toks[i])
        if diff and diff <= LAT:
            p=os.path.join(IMG, os.path.basename(inp[qid]["images"][0]))
            if os.path.exists(p): cands.append((qid,q["question"],opts,q["reference"],p))
    items=cands[:len(d)]
    print("items:", len(items), flush=True)
    def run(it):
        qid,question,opts,ref,path = it
        im=Image.open(path).convert("RGB")
        keys=list(opts.keys())
        swapped={keys[0]:opts[keys[1]], keys[1]:opts[keys[0]]}
        txt=(question+"\nOptions: "+"; ".join(f"{k}. {v}" for k,v in swapped.items())+
             "\nAnswer with the option letter only.")
        out=vlm([{"role":"user","content":[
            {"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+b64(im)}},
            {"type":"text","text":txt}]}])
        pred=letter(out)
        # map back to original label
        inv={keys[1]:keys[0], keys[0]:keys[1]}
        mapped=inv.get(pred,"?")
        return mapped==str(ref).strip().lower(), pred
    good=0; n=0; preds=[]
    with ThreadPoolExecutor(max_workers=6) as ex:
        for f in as_completed([ex.submit(run,it) for it in items]):
            ok_,p=f.result(); good+=1 if ok_ else 0; n+=1; preds.append(p)
    from collections import Counter
    print(f"swapped-order accuracy: {good}/{n} = {100*good/n:.1f}%")
    print("swapped prompt predictions:", Counter(preds))
if __name__=="__main__": main()
