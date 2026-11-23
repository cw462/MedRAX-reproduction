import json, ssl, urllib.request
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
op = urllib.request.build_opener(urllib.request.ProxyHandler({"http":"http://127.0.0.1:7897","https":"http://127.0.0.1:7897"}),
                                 urllib.request.HTTPSHandler(context=ctx))
url = "https://modelscope.cn/api/v1/models/microsoft/maira-2/repo/files?Revision=master&Recursive=true"
d = json.loads(op.open(url, timeout=60).read())
files = d["Data"]["Files"]
print("files:", len(files))
total = 0
for f in files:
    sz = f.get("Size", 0) or 0
    total += sz
    print(f"{sz/1e6:10.1f} MB  {f['Path']}")
print(f"TOTAL {total/1e9:.2f} GB")
