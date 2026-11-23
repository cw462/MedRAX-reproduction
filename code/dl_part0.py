import os, subprocess
URL = "https://ftp.ncbi.nlm.nih.gov/pub/litarch/3d/12/statpearls_NBK430685.tar.gz"
TMP = r"H:/RAG_KB/_sp_parts"
CH = 258443626
st, en = 0, CH - 1
out = os.path.join(TMP, "fix_0")
if os.path.exists(out) and os.path.getsize(out) == CH:
    print("already"); raise SystemExit
cmd = ["curl", "-s", "--max-time", "2400", "-x", "http://127.0.0.1:7897", "-r", f"{st}-{en}", URL, "-o", out]
p = subprocess.Popen(cmd); p.wait()
print("got", os.path.getsize(out), "need", CH)
