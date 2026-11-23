import sys, os, time
sys.path.insert(0, "medrax_work")
import remote
# create 20MB test file
p = "rag_eval/_speed.bin"
if not os.path.exists(p) or os.path.getsize(p) != 20*1024*1024:
    with open(p, "wb") as f: f.write(os.urandom(20*1024*1024))
c = remote.connect()
sftp = c.open_sftp()
t0 = time.time()
sftp.put(p, "/home/imss/cw/radiology_rag_p3/_speed.bin")
dt = time.time() - t0
sftp.close(); c.close()
print(f"20MB in {dt:.1f}s = {20/dt:.2f} MB/s")
print(f"27.5GB 预计 {27.5*1024/ (20/dt) / 60:.0f} 分钟")
os.remove(p)
