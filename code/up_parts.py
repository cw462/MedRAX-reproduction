import sys, os, time, glob
sys.path.insert(0, "medrax_work")
import remote

src_dir = sys.argv[1]
prefix = sys.argv[2]
remote_dir = sys.argv[3]
parts = sorted(glob.glob(os.path.join(src_dir, "part_*")))

def put(sftp, local, dest, tries=4):
    for t in range(tries):
        try:
            sftp.put(local, dest)
            return sftp.stat(dest).st_size == os.path.getsize(local)
        except Exception as e:
            print("retry", os.path.basename(local), repr(e)[:100], flush=True)
        time.sleep(3)
    return False

c = remote.connect()
sftp = c.open_sftp()
for i, p in enumerate(parts):
    dest = f"{remote_dir}/{prefix}_{i:02d}"
    print(os.path.basename(p), "->", "ok" if put(sftp, p, dest) else "FAILED", flush=True)
sftp.close(); c.close()
print("UPLOAD_DONE")
