import json, os, ssl, urllib.request
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
op = urllib.request.build_opener(urllib.request.ProxyHandler({"http":"http://127.0.0.1:7897","https":"http://127.0.0.1:7897"}),
                                 urllib.request.HTTPSHandler(context=ctx))
os.makedirs("rag_eval/medsam", exist_ok=True)
base = "https://huggingface.co/wanglab/medsam-vit-base/resolve/main/"
for f in ["config.json", "preprocessor_config.json", "pytorch_model.bin"]:
    dst = os.path.join("rag_eval/medsam", f)
    if os.path.exists(dst) and os.path.getsize(dst) > 1000:
        print("skip", f, os.path.getsize(dst)); continue
    with op.open(base + f, timeout=600) as r, open(dst, "wb") as w:
        n = 0
        while True:
            c = r.read(1 << 20)
            if not c: break
            w.write(c); n += len(c)
    print("ok", f, n, flush=True)
