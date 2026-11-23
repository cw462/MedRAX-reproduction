#!/usr/bin/env python3
"""Parallel chunked downloader from ModelScope into /dev/shm.

Reads a manifest {relpath: size} and downloads each file in chunks with a
thread pool, retrying transient failures. Skips files already at full size.

Usage: python maira2_dl.py <manifest.json> <dest_dir>
"""
import concurrent.futures as cf
import json
import os
import ssl
import sys
import threading
import time
import urllib.parse
import urllib.request

REPO = "microsoft/maira-2"
REVISION = "master"
BASE = "https://modelscope.cn/api/v1/models/{}/repo?Revision={}&FilePath={}"
CHUNK = 32 * 1024 * 1024
THREADS = 16
RETRIES = 6

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

_lock = threading.Lock()
_done = [0]
_total = [0]


def url_for(path):
    return BASE.format(REPO, REVISION, urllib.parse.quote(path))


def fetch_range(url, start, end, dest, attempts=RETRIES):
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(
                url, headers={"Range": f"bytes={start}-{end}", "User-Agent": "curl/8"}
            )
            with urllib.request.urlopen(req, timeout=120, context=CTX) as r:
                data = r.read()
            want = end - start + 1
            if len(data) != want:
                raise IOError(f"short read {len(data)} != {want}")
            with open(dest, "wb") as f:
                f.write(data)
            return len(data)
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(min(2 ** i, 20))
    raise RuntimeError(f"failed {dest} after {attempts}: {last}")


def download_file(path, size, dest_dir):
    dest = os.path.join(dest_dir, path)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest) and os.path.getsize(dest) == size:
        with _lock:
            _done[0] += size
        return "cached"
    url = url_for(path)
    parts = []
    ranges = []
    s = 0
    while s < size:
        e = min(s + CHUNK - 1, size - 1)
        ranges.append((s, e, f"{dest}.part{len(ranges)}"))
        s = e + 1

    with cf.ThreadPoolExecutor(max_workers=THREADS) as ex:
        futs = [ex.submit(fetch_range, url, a, b, p) for a, b, p in ranges]
        for fu in cf.as_completed(futs):
            n = fu.result()
            with _lock:
                _done[0] += n
                d = _done[0]
            pct = 100.0 * d / _total[0]
            if int(pct) != int(100.0 * (d - n) / _total[0]):
                print(f"  {pct:6.2f}%  {d/1e9:6.2f}/{_total[0]/1e9:.2f} GB", flush=True)

    # stitch
    with open(dest, "wb") as out:
        for _, _, p in ranges:
            with open(p, "rb") as f:
                while True:
                    buf = f.read(8 * 1024 * 1024)
                    if not buf:
                        break
                    out.write(buf)
            os.remove(p)
    got = os.path.getsize(dest)
    if got != size:
        raise RuntimeError(f"size mismatch {path}: {got} != {size}")
    return "ok"


def main():
    manifest = json.load(open(sys.argv[1], encoding="utf-8"))
    dest_dir = sys.argv[2]
    os.makedirs(dest_dir, exist_ok=True)
    files = [(p, s) for p, s in manifest.items() if s > 0]
    small = [p for p, s in manifest.items() if s == 0]
    _total[0] = sum(s for _, s in files)
    print(f"big files: {len(files)}, {_total[0]/1e9:.2f} GB -> {dest_dir}", flush=True)

    t0 = time.time()
    for p, s in sorted(files, key=lambda x: -x[1]):
        r = download_file(p, s, dest_dir)
        print(f"[{time.time()-t0:6.0f}s] {p} {s/1e9:.2f}GB {r}", flush=True)

    # small files: single request each
    for p in small:
        dest = os.path.join(dest_dir, p)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            req = urllib.request.Request(url_for(p), headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
                open(dest, "wb").write(r.read())
        except Exception as exc:  # noqa: BLE001
            print(f"WARN small file {p}: {exc}", flush=True)

    print(f"DONE in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
