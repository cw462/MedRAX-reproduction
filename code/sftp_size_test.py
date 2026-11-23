import sys, os
sys.path.insert(0, "medrax_work")
import remote
c = remote.connect()
sftp = c.open_sftp()
# make test files of increasing size locally
for mb in (1, 5, 20):
    p = f"rag_eval/_t{mb}.bin"
    if not os.path.exists(p):
        with open(p, "wb") as f:
            f.write(os.urandom(mb * 1024 * 1024))
    dest = f"/home/imss/cw/radiology_rag_p3/_t{mb}.bin"
    try:
        sftp.put(p, dest)
        print(mb, "MB OK", sftp.stat(dest).st_size)
    except Exception as e:
        print(mb, "MB FAIL", repr(e)[:120])
sftp.close(); c.close()
