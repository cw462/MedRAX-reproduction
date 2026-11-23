import sys, os, time
sys.path.insert(0, "medrax_work")
import remote

def put_once(local, dest, tries=3):
    for t in range(tries):
        c = None
        try:
            c = remote.connect()
            sftp = c.open_sftp()
            sftp.put(local, dest)
            n = sftp.stat(dest).st_size
            sftp.close()
            if n == os.path.getsize(local):
                return True
        except Exception as e:
            print("  retry", os.path.basename(local), repr(e)[:80], flush=True)
        finally:
            if c: c.close()
        time.sleep(2)
    return False

def upload(src, remote_prefix, chunk_mb=8):
    size = os.path.getsize(src)
    n = (size + chunk_mb*1024*1024 - 1)//(chunk_mb*1024*1024)
    ok = 0
    with open(src, "rb") as f:
        for i in range(n):
            data = f.read(chunk_mb*1024*1024)
            tmp = os.path.join(os.getcwd(), f"_chunk_{i:03d}")
            with open(tmp, "wb") as w: w.write(data)
            if put_once(tmp, f"{remote_prefix}_{i:03d}"):
                ok += 1
            os.remove(tmp)
            print(f"chunk {i+1}/{n} {'ok' if ok else 'FAIL'}", flush=True)
    print(f"uploaded {ok}/{n}", flush=True)

if __name__ == "__main__":
    upload(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 8)
