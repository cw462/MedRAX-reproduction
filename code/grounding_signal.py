import json, re
D = r"H:/RAG_KB/qwen8_m5"
rows = [json.loads(l) for l in open(f"{D}/flash_m5_chexbench.jsonl", encoding="utf-8")]
LAT = {"left","right"}
def opts_of(r):
    o=r.get("options")
    if isinstance(o,str):
        try:o=json.loads(o)
        except:o={}
    return o or {}
def is_lat(r):
    o=opts_of(r); vals=[str(v).lower() for v in o.values()]
    if len(vals)<2: return False
    toks=[set(re.findall(r"[a-z]+",v)) for v in vals]; diff=set()
    for i in range(len(toks)):
        for j in range(i+1,len(toks)): diff|=(toks[i]-toks[j])|(toks[j]-toks[i])
    return bool(diff) and diff<=LAT

def walk(o, acc):
    if isinstance(o, dict):
        if "predictions" in o and isinstance(o["predictions"], list):
            for p in o["predictions"]:
                if isinstance(p, dict):
                    bb = (p.get("bounding_boxes") or {}).get("image_coordinates") or []
                    if bb:
                        try:
                            x1,y1,x2,y2 = bb[0][:4]
                            acc.append({"phrase": str(p.get("phrase","")), "area": abs(float(x2)-float(x1))*abs(float(y2)-float(y1))})
                        except Exception: pass
        for v in o.values(): walk(v, acc)
    elif isinstance(o, list):
        for v in o: walk(v, acc)
    elif isinstance(o, str):
        try:
            d = json.loads(o)
            walk(d, acc)
        except Exception:
            pass

def boxes(r):
    acc = []
    for o in (r.get("tool_observations") or []):
        walk(o, acc)
    return acc

stat = {"gold_smaller":0,"distractor_smaller":0,"tie":0,"no_pair":0}
n=0
for r in rows:
    if not is_lat(r) or r["correct"]: continue
    bs = boxes(r)
    if len(bs) < 2: stat["no_pair"] += 1; continue
    o = opts_of(r); ref = str(r["reference"]).strip().lower()
    gold_txt = str(o.get(ref) or o.get(ref.upper()) or "").lower()
    gw = [w for w in re.findall(r"[a-z]{5,}", gold_txt)]
    gold_area = dist_area = None
    for b in bs:
        ph = b["phrase"].lower()
        if gold_txt and any(w in ph for w in gw):
            gold_area = b["area"] if gold_area is None else min(gold_area, b["area"])
        else:
            dist_area = b["area"] if dist_area is None else min(dist_area, b["area"])
    if gold_area is None or dist_area is None: stat["no_pair"] += 1; continue
    n += 1
    if abs(gold_area - dist_area) < 1e-6: stat["tie"] += 1
    elif gold_area < dist_area: stat["gold_smaller"] += 1
    else: stat["distractor_smaller"] += 1
print("paired laterality failures:", n, stat)
if n: print(f"gold 框更紧的比例: {100*stat['gold_smaller']/n:.1f}%")
