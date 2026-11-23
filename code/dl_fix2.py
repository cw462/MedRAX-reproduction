import os, subprocess, sys
URL = "https://ftp.ncbi.nlm.nih.gov/pub/litarch/3d/12/statpearls_NBK430685.tar.gz"
TMP = r"H:/RAG_KB/_sp_parts"
SIZE = 2067549006
S = 258443751
parts = [0, 3, 5]
procs = []
for i in parts:
    st = i * S
    en = min(st + S - 1, SIZE - 1)
    out = os.path.join(TMP, f"fixed_{i}")
    if os.path.exists(out) and os.path.getsize(out) == en - st + 1:
        print("skip", i); continue
    cmd = ["curl", "-s", "--max-time", "2400", "-x", "http://127.0.0.1:7897",
           "-r", f"{st}-{en}", URL, "-o", out]
    procs.append((i, en - st + 1, subprocess.Popen(cmd)))
for i, need, p in procs:
    p.wait()
    got = os.path.getsize(os.path.join(TMP, f"fixed_{i}")) if os.path.exists(os.path.join(TMP, f"fixed_{i}")) else 0
    print(f"part {i}: {got}/{need} {'OK' if got == need else 'SHORT'}", flush=True)
