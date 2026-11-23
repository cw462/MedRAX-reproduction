p = "rag_eval/gradcam_measure.py"
s = open(p, encoding="utf-8").read()
s = s.replace("""    act = feats["act"][0]
    grad = act.grad[0]""", """    full = feats["act"]
    gfull = full.grad
    if gfull is None:
        return None
    act = full[0].detach()
    grad = gfull[0].detach()""")
open(p, "w", encoding="utf-8").write(s)
print("patched")
