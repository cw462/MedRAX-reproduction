import re


def norm_ans(s):
    s = re.sub(r"[^a-z0-9 ]", " ", str(s).lower())
    return re.sub(r"\s+", " ", s).strip()


def score(pred, ref, options):
    if pred.startswith("ERROR:"): return None
    p, r = norm_ans(pred), norm_ans(ref)
    if options:
        m = re.search(r"\b([a-d])\b", p)
        if m and m.group(1) in [k.lower() for k in options]:
            return m.group(1) == r
        for k, v in options.items():
            nv = norm_ans(v)
            if nv and nv in p: return k.lower() == r
        return False
    if r in ("yes", "no"):
        if re.search(r"\byes\b", p): return r == "yes"
        if re.search(r"\bno\b", p): return r == "no"
        return False
    return r == p or r in p.split()
