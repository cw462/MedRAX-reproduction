import json, urllib.request
key = open("medrax_work/.secrets/token_plan_api.key").read().strip()
base = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
req = urllib.request.Request(base + "/models")
req.add_header("Authorization", "Bearer " + key)
try:
    with urllib.request.urlopen(req, timeout=40) as r:
        ids = [m["id"] for m in json.loads(r.read())["data"]]
    print("models:", len(ids))
    for tag in ["qwen3.6", "qwen3.7", "deepseek", "vl", "flash"]:
        print(tag, "->", [i for i in ids if tag in i.lower()][:10])
except Exception as e:
    print("ERR", repr(e)[:200])
