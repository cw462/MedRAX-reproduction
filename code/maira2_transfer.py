#!/usr/bin/env python3
"""Download MAIRA-2 from ModelScope then stream-upload shards to the lab server."""
import json, os, ssl, sys, time, urllib.parse, urllib.request
sys.path.insert(0, "medrax_work")
import remote

LOCAL = r"H:/RAG_KB/maira2"
REMOTE = "/home/imss/cw/radiology_rag_p3/maira2"
API = "https://modelscope.cn/api/v1/models/microsoft/maira-2/repo"
LOG = open("rag_eval/maira2_transfer.log", "a", encoding="utf-8")

def log(msg):
    print(msg, flush=True)
    LOG.write(msg + "\n"); LOG.flush()

ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
op = urllib.request.build_opener(urllib.request.ProxyHandler({"http":"http://127.0.0.1:7897","https":"http://127.0.0.1:7897"}),
                                 urllib.request.HTTPSHandler(context=ctx))

FILES = [
    "config.json", "configuration.json", "generation_config.json", "added_tokens.json",
    "chat_template.json", "special_tokens_map.json", "tokenizer.json", "tokenizer.model",
    "tokenizer_config.json", "preprocessor_config.json", "processor_config.json",
    "configuration_maira2.py", "modeling_maira2.py", "processing_maira2.py",
    "model.safetensors.index.json",
    "model-00001-of-00006.safetensors", "model-00002-of-00006.safetensors",
    "model-00003-of-00006.safetensors", "model-00004-of-00006.safetensors",
    "model-00005-of-00006.safetensors", "model-00006-of-00006.safetensors",
]

def download(fn):
    dst = os.path.join(LOCAL, fn)
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        return dst
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    url = API + "?" + urllib.parse.urlencode({"Revision": "master", "FilePath": fn})
    tmp = dst + ".part"
    n = 0
    with op.open(url, timeout=600) as r, open(tmp, "wb") as w:
        while True:
            c = r.read(1 << 20)
            if not c: break
            w.write(c); n += len(c)
    os.replace(tmp, dst)
    return dst

def upload(local, fn, chunk=20 * 1024 * 1024):
    size = os.path.getsize(local)
    if size <= chunk:
        c = remote.connect(); sftp = c.open_sftp()
        sftp.put(local, f"{REMOTE}/{fn}"); sftp.close(); c.close()
        return
    n = (size + chunk - 1) // chunk
    for i in range(n):
        with open(local, "rb") as f:
            f.seek(i * chunk); data = f.read(chunk)
        tmp = f"rag_eval/_up_{i:03d}"
        open(tmp, "wb").write(data)
        for t in range(4):
            try:
                c = remote.connect(); sftp = c.open_sftp()
                sftp.put(tmp, f"{REMOTE}/{fn}.part{i:03d}"); sftp.close(); c.close()
                break
            except Exception as e:
                log(f"  retry {fn} part{i}: {repr(e)[:60]}")
                time.sleep(2)
        os.remove(tmp)
        log(f"  {fn} part {i+1}/{n}")

def main():
    c = remote.connect(); sftp = c.open_sftp()
    try: sftp.mkdir(REMOTE)
    except Exception: pass
    sftp.close(); c.close()
    for fn in FILES:
        t0 = time.time()
        p = download(fn)
        sz = os.path.getsize(p)
        log(f"downloaded {fn} {sz/1e6:.1f}MB in {time.time()-t0:.0f}s")
        if fn.endswith(".safetensors") and sz > 20*1024*1024:
            upload(p, fn)
            os.remove(p)
            log(f"uploaded {fn}")
    log("TRANSFER_DONE")

if __name__ == "__main__":
    main()
