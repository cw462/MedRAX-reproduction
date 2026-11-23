import os, ssl, urllib.request
SHA = "39c598862713f730c0710054e4f74e842b263531"
BASE = f"https://raw.githubusercontent.com/cw462/MedRAX-reproduction/{SHA}/reports/r55_autodl_qwen8_20261116/"
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
op = urllib.request.build_opener(urllib.request.ProxyHandler({"http":"http://127.0.0.1:7897","https":"http://127.0.0.1:7897"}),
                                 urllib.request.HTTPSHandler(context=ctx))
os.makedirs(r"H:/RAG_KB/qwen8_m5", exist_ok=True)
files = ["README.md"] + [f"flash/m5/{d}.jsonl" for d in ["slake","vqarad","chexbench"]]
for f in files:
    dst = os.path.join(r"H:/RAG_KB/qwen8_m5", f.replace("/", "_"))
    try:
        data = op.open(BASE + f, timeout=120).read()
        open(dst, "wb").write(data)
        print("ok", f, len(data))
    except Exception as e:
        print("ERR", f, repr(e)[:150])
