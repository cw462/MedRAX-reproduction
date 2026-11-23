#!/usr/bin/env python3
"""Classify yes/no VQA questions by what kind of visual judgement they need."""
import json, re, sys
sys.path.insert(0, "rag_eval")

CATS = [
    ("size/morphology", r"(enlarg|cardiomegal|heart size|hyperinflat|emphysem|tortuous|dilat|widened|narrow|smaller|larger|size)"),
    ("effusion/opacity", r"(effusion|consolidat|opacit|infiltrat|edema|atelecta|collapse|blunt)"),
    ("air-leak", r"(pneumothorax|pneumomediastinum|subcutaneous air|subcutaneous emphysema|free air|pneumoperitoneum)"),
    ("nodule/mass", r"(nodule|mass|lesion|tumor|tumour|metasta|cyst|cavit)"),
    ("lines/tubes/devices", r"(catheter|tube|pacemaker|hardware|stent|wire|clip|lead|prosthe|device|port)"),
    ("bone/fracture", r"(fracture|rib|clavicle|spine|vertebra|scolio|kypho|osteo|bone)"),
    ("nodes/hilum/mediastinum", r"(lymphadenopath|hilar|hilum|mediastin|node)"),
    ("non-radiology", r"(female|male|gender|sex|child|adult|infant|man|woman|neck|abdomen|chest|modality|x-ray|ct|mri)"),
]

def cat_of(q):
    s = q.lower()
    for name, pat in CATS:
        if re.search(pat, s):
            return name
    return "other"

def main(path, dsname):
    d = json.load(open(path, encoding="utf-8"))
    qtext = {r["question_id"]: r["question"] for r in json.load(open("rag_eval/data/questions_848.json", encoding="utf-8"))}
    rows = []
    for x in d:
        if "base" not in x or x["base"].get("correct") is None: continue
        q = qtext.get(x["qid"], "")
        rows.append((cat_of(q), x["base"]["correct"], x.get("rag", {}).get("correct")))
    from collections import defaultdict
    by = defaultdict(lambda: [0, 0, 0, 0])
    for c, b, r in rows:
        by[c][0] += 1
        by[c][1] += 1 if b else 0
        if r is not None:
            by[c][2] += 1
            by[c][3] += 1 if r else 0
    print(f"== {dsname}: {len(rows)} answered")
    print(f"{'category':24s} {'n':>4s} {'base':>8s} {'rag':>8s}")
    for c, v in sorted(by.items(), key=lambda kv: -kv[1][0]):
        print(f"{c:24s} {v[0]:4d} {100*v[1]/v[0]:7.1f}% {100*v[3]/max(1,v[2]):7.1f}%")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
