import sys, os, time, glob
sys.path.insert(0, "medrax_work")
import remote

REMOTE = "/home/imss/cw/radiology_rag_p3"
parts = sorted(glob.glob("rag_eval/imgparts/part_*"))

def put(c, local, dest, tries=4):
    for t in range(tries):
        try:
            sftp = c.open_sftp()
            sftp.put(local, dest)
            got = sftp.stat(dest).st_size
            sftp.close()
            if got == os.path.getsize(local):
                return True
            print("size mismatch", dest, got)
        except Exception as e:
            print("retry", os.path.basename(local), repr(e)[:100])
        time.sleep(3)
    return False

c = remote.connect()
for i, p in enumerate(parts):
    dest = f"{REMOTE}/imgpart_{i:02d}"
    ok = put(c, p, dest)
    print(os.path.basename(p), "->", dest, "ok" if ok else "FAILED", flush=True)
c.close()
print("UPLOAD_DONE")
