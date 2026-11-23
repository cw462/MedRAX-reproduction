#!/usr/bin/env python3
"""Parallel download of MAIRA-2 from ModelScope + pipelined upload to the lab server."""
import os, ssl, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, "medrax_work")
import remote

LOCAL = r"H:/RAG_KB/maira2"
REMOTE = "/home/imss/cw/radiology_rag_p3/maira2"
API = "https://modelscope.cn/api/v1/models/microsoft/maira-2/repo"
LOG = open("rag_eval/maira2_transfer2.log", "a", encoding="utf-8")

def log(m):
    print(m, flush=True); LOG.write(m + "\n"); LOG.flush()

ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
OP = urllib.request.build_opener(urllib.request.ProxyHandler({"http":"http://127.0.0.1:7897","https":"http://127.0.0.1:7897"}),
                                 urllib.request.HTTPSHandler(context=ctx))

SHARDS = [f"model-0000{i}-of-00006.safetensors" for i in range(1, 7)]
SMALL = ["config.json","configuration.json","generation_config.json","added_tokens.json","chat_template.json",
         "special_tokens_map.json","tokenizer.json","tokenizer.model","tokenizer_config.json",
         "preprocessor_config.json","processor_config.json","configuration_maira2.py","modeling_maira2.py",
         "processing_maira2.py","model.safetensors.index.json"]

def dl(fn):
    dst = os.path.join(LOCAL, fn)
    if os.path.exists(dst) and os.path.getsize(dst) > 1_000_000:
        return dst
    if fn.startswith("model-") and os.path.exists(dst) and os.path.getsize(dst) > 4_000_000_000:
        return dst
    os.makedirs(LOCAL, exist_ok=True)
    url = API + "?" + urllib.parse.urlencode({"Revision": "master", "FilePath": fn})
    tmp = dst + ".part"
    n = 0
    with OP.open(url, timeout=1200) as r, open(tmp, "wb") as w:
        while True:
            c = r.read(1 << 20)
            if not c: break
            w.write(c); n += len(c)
    os.replace(tmp, dst)
    log(f"downloaded {fn} {n/1e6:.1f}MB")
    return dst

def up(fn):
    local = os.path.join(LOCAL, fn)
    size = os.path.getsize(local)
    CH = 20 * 1024 * 1024
    if size <= CH:
        c = remote.connect(); sftp = c.open_sftp()
        sftp.put(local, f"{REMOTE}/{fn}"); sftp.close(); c.close()
        log(f"uploaded {fn}"); return
    n = (size + CH - 1) // CH
    for i in range(n):
        with open(local, "rb") as f:
            f.seek(i*CH); data = f.read(CH)
        tmp = f"rag_eval/_up_{fn}_{i:03d}"
        open(tmp, "wb").write(data)
        for t in range(4):
            try:
                c = remote.connect(); sftp = c.open_sftp()
                sftp.put(tmp, f"{REMOTE}/{fn}.part{i:03d}"); sftp.close(); c.close(); break
            except Exception as e:
                log(f"  retry {fn} {i}: {repr(e)[:60]}"); time.sleep(2)
        os.remove(tmp)
    log(f"uploaded {fn} ({n} parts)")

def main():
    c = remote.connect(); sftp = c.open_sftp()
    try: sftp.mkdir(REMOTE)
    except Exception: pass
    sftp.close(); c.close()
    for fn in SMALL: dl(fn)
    # parallel download of shards
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(dl, f): f for f in SHARDS}
        done = []
        for f in as_completed(futs):
            done.append(futs[f]); log(f"shard ready: {futs[f]} ({len(done)}/6)")
    for fn in SMALL + SHARDS: up(fn)
    log("TRANSFER_DONE")

if __name__ == "__main__":
    main()
