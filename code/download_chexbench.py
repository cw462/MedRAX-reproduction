import json, os, ssl, urllib.request
SHA = "3aeead0d68da870cb0aea7c45fa3c5d2a0ba2732"
BASE = f"https://raw.githubusercontent.com/cw462/MedRAX-reproduction/{SHA}/reports/cxr_action_r41_20261108/results/chexbench/"
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
op = urllib.request.build_opener(urllib.request.ProxyHandler({"http":"http://127.0.0.1:7897","https":"http://127.0.0.1:7897"}), urllib.request.HTTPSHandler(context=ctx))
op.addheaders=[("User-Agent","Mozilla/5.0")]
root = r"H:/RAG_KB/images/chexbench"
os.makedirs(root, exist_ok=True)
need = set()
for line in open("C:/Users/cheng/Documents/deepseek-harness/default-workspace/rag_eval/data/chexbench_inputs.jsonl", encoding="utf-8"):
    d = json.loads(line)
    need.add(os.path.basename(d["images"][0]))
print("unique assets:", len(need), flush=True)
ok = fail = 0
for i, name in enumerate(sorted(need), 1):
    dest = os.path.join(root, name)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        ok += 1; continue
    try:
        data = op.open(BASE + "assets/" + name, timeout=40).read()
        open(dest, "wb").write(data); ok += 1
    except Exception as e:
        fail += 1
    if i % 100 == 0: print(i, ok, fail, flush=True)
print("done ok", ok, "fail", fail, flush=True)
