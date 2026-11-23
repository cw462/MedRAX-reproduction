#!/usr/bin/env python3
"""Resumable MAIRA-2 download (size-verified) + verified upload."""
import json, os, ssl, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, "medrax_work")
import remote

LOCAL = r"H:/RAG_KB/maira2"
REMOTE = "/home/imss/cw/radiology_rag_p3/maira2"
API = "https://modelscope.cn/api/v1/models/microsoft/maira-2/repo"
SIZES = json.load(open("rag_eval/maira2_sizes.json", encoding="utf-8"))
LOG = open("rag_eval/maira2_transfer3.log", "a", encoding="utf-8")
def log(m):
    print(m, flush=True); LOG.write(m+"\n"); LOG.flush()

ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
OP = urllib.request.build_opener(urllib.request.ProxyHandler({"http":"http://127.0.0.1:7897","https":"http://127.0.0.1:7897"}),
                                 urllib.request.HTTPSHandler(context=ctx))

def url_for(fn):
    return API + "?" + urllib.parse.urlencode({"Revision":"master","FilePath":fn})

def fetch(fn, expect):
    dst = os.path.join(LOCAL, fn)
    for attempt in range(12):
        cur = os.path.getsize(dst) if os.path.exists(dst) else 0
        if cur >= expect:
            return True
        req = urllib.request.Request(url_for(fn))
        if cur > 0:
            req.add_header("Range", f"bytes={cur}-")
        try:
            with OP.open(req, timeout=600) as r, open(dst, "ab") as w:
                while True:
                    c = r.read(1 << 20)
                    if not c: break
                    w.write(c)
        except Exception as e:
            log(f"  {fn} attempt {attempt} err {repr(e)[:60]}")
        time.sleep(2)
        cur = os.path.getsize(dst) if os.path.exists(dst) else 0
        log(f"  {fn}: {cur/1e9:.2f}/{expect/1e9:.2f} GB")
    return os.path.getsize(dst) >= expect

def upload(fn, expect):
    local = os.path.join(LOCAL, fn)
    CH = 20 * 1024 * 1024
    n = (expect + CH - 1) // CH
    for i in range(n):
        with open(local, "rb") as f:
            f.seek(i*CH); data = f.read(CH)
        tmp = f"rag_eval/_up_{fn}_{i:03d}"
        open(tmp, "wb").write(data)
        ok = False
        for t in range(4):
            try:
                c = remote.connect(); sftp = c.open_sftp()
                sftp.put(tmp, f"{REMOTE}/{fn}.part{i:03d}"); sftp.close(); c.close(); ok = True; break
            except Exception as e:
                log(f"  up retry {fn} {i}: {repr(e)[:60]}"); time.sleep(2)
        os.remove(tmp)
        if not ok: log(f"  UPLOAD FAILED {fn} part {i}")
    log(f"uploaded {fn}")

def main():
    c = remote.connect(); sftp = c.open_sftp()
    try: sftp.mkdir(REMOTE)
    except Exception: pass
    sftp.close(); c.close()
    shards = [f for f in SIZES if f.endswith(".safetensors")]
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(fetch, f, SIZES[f]): f for f in shards}
        for fu in as_completed(futs):
            f = futs[fu]
            log(f"download done {f}: {'OK' if fu.result() else 'FAILED'}")
    ok = all(os.path.getsize(os.path.join(LOCAL,f)) == SIZES[f] for f in shards)
    log(f"all shards verified: {ok}")
    if not ok: return
    for f in [x for x in SIZES if not x.endswith(".safetensors")]:
        c = remote.connect(); sftp = c.open_sftp()
        sftp.put(os.path.join(LOCAL,f), f"{REMOTE}/{f}"); sftp.close(); c.close()
    for f in shards:
        upload(f, SIZES[f])
    log("TRANSFER_DONE")

if __name__ == "__main__":
    main()
