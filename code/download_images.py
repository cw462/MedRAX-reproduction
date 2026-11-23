import json, os, ssl, urllib.request, re
SHA = "3aeead0d68da870cb0aea7c45fa3c5d2a0ba2732"
BASE = f"https://raw.githubusercontent.com/cw462/MedRAX-reproduction/{SHA}/"
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
op = urllib.request.build_opener(urllib.request.ProxyHandler({"http":"http://127.0.0.1:7897","https":"http://127.0.0.1:7897"}), urllib.request.HTTPSHandler(context=ctx))
op.addheaders=[("User-Agent","Mozilla/5.0")]

OUT = r"H:/RAG_KB/images"
os.makedirs(OUT, exist_ok=True)
jobs = [("slake_inputs.jsonl", "data/slake_cxr/"), ("vqarad_inputs.jsonl", "data/vqarad_cxr/")]
ok = fail = 0
for fname, prefix in jobs:
    for line in open(fname, encoding="utf-8"):
        if not line.strip(): continue
        d = json.loads(line)
        rel = d["images"][0]
        ds = "slake" if "slake" in prefix else "vqarad"
        dest = os.path.join(OUT, ds, rel)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            ok += 1; continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            data = op.open(BASE + prefix + rel, timeout=40).read()
            open(dest, "wb").write(data); ok += 1
        except Exception as e:
            fail += 1
            if fail < 5: print("FAIL", rel, repr(e)[:100])
print("downloaded", ok, "failed", fail, flush=True)
