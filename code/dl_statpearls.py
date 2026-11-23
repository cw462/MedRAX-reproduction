import os, ssl, urllib.request
ROOT = r"H:/RAG_KB"
dest = os.path.join(ROOT, "statpearls.tar.gz")
if os.path.exists(dest) and os.path.getsize(dest) > 1_000_000_000:
    print("already", os.path.getsize(dest)); raise SystemExit
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
op = urllib.request.build_opener(urllib.request.ProxyHandler({"http":"http://127.0.0.1:7897","https":"http://127.0.0.1:7897"}), urllib.request.HTTPSHandler(context=ctx))
url="https://ftp.ncbi.nlm.nih.gov/pub/litarch/3d/12/statpearls_NBK430685.tar.gz"
tmp=dest+".part"; n=0
with op.open(url, timeout=600) as r, open(tmp,"wb") as f:
    while True:
        c=r.read(1<<20)
        if not c: break
        f.write(c); n+=len(c)
        if n % (100<<20) < (1<<20): print("MB", n>>20, flush=True)
os.replace(tmp,dest); print("done", n, flush=True)