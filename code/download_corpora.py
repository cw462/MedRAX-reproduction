#!/usr/bin/env python3
"""Download retrieval corpora to H:/RAG_KB (proxy required)."""
import json, os, ssl, sys, urllib.request

ROOT = r"H:/RAG_KB"
PROXY = "http://127.0.0.1:7897"
os.makedirs(ROOT, exist_ok=True)

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
op = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}),
    urllib.request.HTTPSHandler(context=ctx))
op.addheaders = [("User-Agent", "Mozilla/5.0")]

def get(url, timeout=120):
    return op.open(url, timeout=timeout).read()

def dl(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        print("skip", dest, os.path.getsize(dest)); return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with op.open(url, timeout=300) as r, open(tmp, "wb") as f:
        total = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk: break
            f.write(chunk); total += len(chunk)
    os.replace(tmp, dest)
    print("ok", dest, total, flush=True)

# --- textbooks ---
tree = json.loads(get("https://huggingface.co/api/datasets/MedRAG/textbooks/tree/main/chunk"))
files = [f["path"] for f in tree if f["type"] == "file"]
print("textbook files:", len(files))
for p in files:
    name = os.path.basename(p)
    dl("https://huggingface.co/datasets/MedRAG/textbooks/resolve/main/" + p, os.path.join(ROOT, "textbooks", name))

# --- statpearls (NCBI bookshelf tarball) ---
dl("https://ftp.ncbi.nlm.nih.gov/pub/litarch/3d/12/statpearls_NBK430685.tar.gz",
   os.path.join(ROOT, "statpearls.tar.gz"))
print("DONE")
