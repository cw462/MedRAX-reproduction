import ssl, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
op = urllib.request.build_opener(urllib.request.ProxyHandler({"http":"http://127.0.0.1:7897","https":"http://127.0.0.1:7897"}),
                                 urllib.request.HTTPSHandler(context=ctx))
URL = "https://modelscope.cn/api/v1/models/microsoft/maira-2/repo?Revision=master&FilePath=model-00001-of-00006.safetensors"
def grab(nbytes_range):
    req = urllib.request.Request(URL, headers={"Range": nbytes_range})
    t0 = time.time(); got = 0
    with op.open(req, timeout=60) as r:
        while time.time() - t0 < 10:
            c = r.read(1 << 20)
            if not c: break
            got += len(c)
    return got
t0 = time.time()
with ThreadPoolExecutor(max_workers=4) as ex:
    res = list(ex.map(grab, ["bytes=0-", "bytes=2000000000-", "bytes=4000000000-", "bytes=1000000000-"]))
dt = time.time() - t0
print("4 连接并行 10s 合计", sum(res)/1e6, "MB ->", sum(res)/1e6/dt, "MB/s")
for r in res: print("  ", r/1e6, "MB")
