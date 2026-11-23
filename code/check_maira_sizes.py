import json, os, ssl, urllib.request, urllib.parse
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
op = urllib.request.build_opener(urllib.request.ProxyHandler({"http":"http://127.0.0.1:7897","https":"http://127.0.0.1:7897"}),
                                 urllib.request.HTTPSHandler(context=ctx))
url = "https://modelscope.cn/api/v1/models/microsoft/maira-2/repo/files?Revision=master&Recursive=true"
d = json.loads(op.open(url, timeout=60).read())
sizes = {f["Path"]: f.get("Size", 0) for f in d["Data"]["Files"]}
print("expected sizes:")
for k, v in sizes.items():
    if k.endswith(".safetensors"): print(f"  {k}: {v/1e9:.3f} GB")
print("\nlocal actual:")
for fn in sorted(os.listdir(r"H:/RAG_KB/maira2")):
    if fn.endswith(".safetensors"):
        p = os.path.join(r"H:/RAG_KB/maira2", fn)
        act = os.path.getsize(p); exp = sizes.get(fn, 0)
        print(f"  {fn}: {act/1e9:.3f} / {exp/1e9:.3f} GB  {'OK' if act==exp else 'TRUNCATED'}")
json.dump(sizes, open("rag_eval/maira2_sizes.json", "w"), indent=0)
