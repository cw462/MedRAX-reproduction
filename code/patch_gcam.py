import re
p = r"rag_eval/gradcam_measure.py"
s = open(p, encoding="utf-8").read()
s = s.replace("""    def hook(m, inp, out):
        feats["act"] = out""", """    def hook(m, inp, out):
        out.retain_grad()
        feats["act"] = out""")
s = s.replace("""    x = torch.from_numpy(arr[None, ...]).to(dev)""", """    x = torch.from_numpy(arr[None, ...]).to(dev)
    model.zero_grad()""")
open(p, "w", encoding="utf-8").write(s)
print("patched")
