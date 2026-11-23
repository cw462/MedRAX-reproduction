import os, subprocess
URL = "https://ftp.ncbi.nlm.nih.gov/pub/litarch/3d/12/statpearls_NBK430685.tar.gz"
TMP = r"H:/RAG_KB/_sp_parts"
SIZE = 2067549006
CH = 258443626
procs = []
for i in (3, 5):
    st = i * CH
    en = min(st + CH - 1, SIZE - 1)
    out = os.path.join(TMP, f"fix_{i}")
    need = en - st + 1
    print(f"part {i}: range {st}-{en} bytes {need}", flush=True)
    cmd = ["curl", "-s", "--max-time", "2400", "-x", "http://127.0.0.1:7897",
           "-r", f"{st}-{en}", URL, "-o", out]
    procs.append((i, need, subprocess.Popen(cmd)))
for i, need, p in procs:
    p.wait()
    path = os.path.join(TMP, f"fix_{i}")
    got = os.path.getsize(path) if os.path.exists(path) else 0
    print(f"part {i}: {got}/{need} {'OK' if got == need else 'SHORT'}", flush=True)
