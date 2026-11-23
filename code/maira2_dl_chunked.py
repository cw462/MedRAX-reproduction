#!/usr/bin/env python3
"""Chunked (100MB range) download of MAIRA-2 with retries, then verified upload."""
import json, os, ssl, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, "medrax_work")
import remote

LOCAL = r"H:/RAG_KB/maira2"
REMOTE = "/home/imss/cw/radiology_rag_p3/maira2"
API = "https://modelscope.cn/api/v1/models/microsoft/maira-2/repo"
SIZES = json.load(open("rag_eval/maira2_sizes.json", encoding="utf-8"))
CHUNK = 100 * 1024 * 1024
LOG = open("rag_eval/maira2_transfer4.log", "a", encoding="utf-8")
def log(m):
    print(m, flush=True); LOG.write(m+"\n"); LOG.flush()

ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
OP = urllib.request.build_opener(urllib.request.ProxyHandler({"http":"http://127.0.0.1:7897","https":"http://127.0.0.1:7897"}),
                                 urllib.request.HTTPSHandler(context=ctx))

def url_for(fn):
    return API + "?" + urllib.parse.urlencode({"Revision":"master","FilePath":fn})

def get_chunk(fn, idx, start, end):
    part = os.path.join(LOCAL, f"{fn}.chunk{idx:03d}")
    need = end - start + 1
    if os.path.exists(part) and os.path.getsize(part) == need:
        return part
    for t in range(6):
        try:
            req = urllib.request.Request(url_for(fn), headers={"Range": f"bytes={start}-{end}"})
            with OP.open(req, timeout=300) as r, open(part, "wb") as w:
                while True:
                    c = r.read(1 << 20)
                    if not c: break
                    w.write(c)
            if os.path.getsize(part) == need:
                return part
        except Exception as e:
            pass
        time.sleep(1)
    log(f"CHUNK FAIL {fn} {idx}")
    return None

def main():
    shards = [f for f in SIZES if f.endswith(".safetensors")]
    jobs = []
    for fn in shards:
        size = SIZES[fn]
        n = (size + CHUNK - 1) // CHUNK
        for i in range(n):
            s = i*CHUNK; e = min(size-1, s+CHUNK-1)
            jobs.append((fn, i, s, e))
    log(f"chunks total {len(jobs)}")
    ok = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(get_chunk, *j): j for j in jobs}
        for fu in as_completed(futs):
            if fu.result(): ok += 1
            if ok % 20 == 0: log(f"chunks {ok}/{len(jobs)}")
    log(f"chunks done {ok}/{len(jobs)}")
    if ok < len(jobs): return
    for fn in shards:
        out = os.path.join(LOCAL, fn)
        with open(out, "wb") as w:
            for i in range((SIZES[fn] + CHUNK - 1)//CHUNK):
                p = os.path.join(LOCAL, f"{fn}.chunk{i:03d}")
                with open(p, "rb") as f: w.write(f.read())
                os.remove(p)
        log(f"assembled {fn} {os.path.getsize(out)/1e9:.2f} GB {'OK' if os.path.getsize(out)==SIZES[fn] else 'BAD'}")
    log("DOWNLOAD_DONE")

if __name__ == "__main__":
    main()
