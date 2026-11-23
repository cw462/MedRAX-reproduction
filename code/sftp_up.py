import sys, os, time
sys.path.insert(0, "medrax_work")
import remote

def up(local, dest):
    c = remote.connect()
    sftp = c.open_sftp()
    t0 = time.time()
    size = os.path.getsize(local)
    def cb(done, total):
        if done == total or int(time.time() - t0) % 20 == 0:
            pass
    sftp.put(local, dest, callback=cb)
    sftp.close(); c.close()
    print(f"uploaded {local} -> {dest} ({size/1e6:.1f} MB, {time.time()-t0:.1f}s)")

if __name__ == "__main__":
    up(sys.argv[1], sys.argv[2])
