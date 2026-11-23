import os, sys, tarfile, time
SRC = "H:/RAG_KB/statpearls3.tar.gz"
DST = "H:/RAG_KB/sp_full"
os.makedirs(DST, exist_ok=True)
t0 = time.time()
n = 0
with tarfile.open(SRC, "r:gz") as tf:
    for m in tf:
        if not m.isfile() or not m.name.endswith(".nxml"):
            continue
        base = os.path.basename(m.name)
        out = os.path.join(DST, base)
        with tf.extractfile(m) as src, open(out, "wb") as dst:
            dst.write(src.read())
        n += 1
        if n % 1000 == 0:
            print(n, round(time.time() - t0, 1), flush=True)
print("extracted", n, "in", round(time.time() - t0, 1), "s")
