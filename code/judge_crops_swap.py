#!/usr/bin/env python3
"""Judge paired crops with swapped order to cancel position bias."""
import base64, json, os, re, ssl, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

BASE = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
MODEL = os.environ.get("JUDGE_MODEL", "qwen3.6-flash")
CROPDIR = "rag_eval/crops"
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
OP = urllib.request.build_opener(urllib.request.ProxyHandler({"http":"http://127.0.0.1:7897","https":"http://127.0.0.1:7897"}),
                                 urllib.request.HTTPSHandler(context=ctx))
def key(): return open("medrax_work/.secrets/token_plan_api.key").read().strip()
def b64(p):
    im = Image.open(p).convert("RGB"); im.thumbnail((640,640))
    import io; buf=io.BytesIO(); im.save(buf,"JPEG",quality=90)
    return base64.b64encode(buf.getvalue()).decode()
def ask(msgs, retries=3):
    body = json.dumps({"model":MODEL,"messages":msgs,"max_tokens":30,"temperature":0,"enable_thinking":False}).encode()
    for a in range(retries):
        req = urllib.request.Request(BASE+"/chat/completions", data=body, method="POST")
        req.add_header("Authorization","Bearer "+key()); req.add_header("Content-Type","application/json")
        try:
            with OP.open(req, timeout=120) as r: return (json.loads(r.read())["choices"][0]["message"].get("content") or "").strip()
        except Exception:
            if a==retries-1: return "ERR"
            time.sleep(2)
def main():
    meta = json.load(open("rag_eval/crop_boxes.json", encoding="utf-8"))
    items=[]
    for qid, rec in meta.items():
        fa, fb = rec["files"].get("A"), rec["files"].get("B")
        if not fa or not fb: continue
        pa, pb = os.path.join(CROPDIR,fa), os.path.join(CROPDIR,fb)
        if not (os.path.exists(pa) and os.path.exists(pb)): continue
        finding = re.sub(r"\b(left|right)\b","",str(rec["options"]["A"]).lower()).strip()
        items.append((qid,pa,pb,finding,rec["gold"],rec["options"]))
    print("items:", len(items), flush=True)
    def run(it):
        qid,pa,pb,finding,gold,opts = it
        # swapped: B first
        msgs=[{"role":"user","content":[
            {"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+b64(pb)}},
            {"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+b64(pa)}},
            {"type":"text","text":f"Two crops from the same chest radiograph. Exactly one of them shows: {finding}. Which crop is it, 1 or 2? Reply with only 1 or 2."}]}]
        ans=ask(msgs)
        pick=1 if re.search(r"\b1\b",ans) else (2 if re.search(r"\b2\b",ans) else None)
        # 1 -> B, 2 -> A
        pred = "B" if pick==1 else ("A" if pick==2 else None)
        gold_key=None
        for k,v in opts.items():
            if gold in str(v).lower(): gold_key=k
        return {"qid":qid,"pred":pred,"gold_key":gold_key,"ok":pred==gold_key if pred and gold_key else None}
    res=[]
    with ThreadPoolExecutor(max_workers=6) as ex:
        for f in as_completed([ex.submit(run,it) for it in items]): res.append(f.result())
    valid=[r for r in res if r["ok"] is not None]
    ok=sum(1 for r in valid if r["ok"])
    print(f"swapped-order judge: {ok}/{len(valid)} = {100*ok/max(1,len(valid)):.1f}%", flush=True)
    json.dump(res, open("rag_eval/paired_crop_judged_swap.json","w"), ensure_ascii=False)
if __name__=="__main__": main()
