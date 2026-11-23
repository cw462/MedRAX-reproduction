#!/usr/bin/env python3
"""Score MAIRA-2 phrase-grounding boxes as answers to CheXBench localization."""
import json
from collections import Counter, defaultdict

TASKS = "/dev/shm/lat_tasks_maira.json"
BOXES = "/dev/shm/maira_boxes.json"


def main():
    tasks = {t["qid"]: t for t in json.load(open(TASKS, encoding="utf-8"))}
    boxes = json.load(open(BOXES, encoding="utf-8"))

    rows = []
    for qid, t in tasks.items():
        r = boxes.get(qid) or {}
        bs = r.get("boxes") or []
        best = None
        if bs:
            best = max(bs, key=lambda b: (b["norm"][2] - b["norm"][0]) * (b["norm"][3] - b["norm"][1]))
        row = {"qid": qid, "kind": t["kind"], "subset": t["subset"],
               "gold_attr": t["gold_attr"], "phrase": t["phrase"], "n_box": len(bs)}
        if best:
            x1, y1, x2, y2 = best["norm"]
            row["cx"] = (x1 + x2) / 2
            row["cy"] = (y1 + y2) / 2
            row["w"] = x2 - x1
            row["h"] = y2 - y1
        rows.append(row)

    def attr(kind, cx, cy, flip=False):
        if kind == "side":
            right = cx < 0.5
            if flip:
                right = not right
            return "right" if right else "left"
        if kind == "vertical":
            return "upper" if cy < 0.5 else "lower"
        return None

    for flip in (False, True):
        print(f"\n===== laterality convention flip={flip} (image-left = patient-{'left' if flip else 'right'}) =====")
        for subset in ("all", "side", "vertical", "severity"):
            sel = [r for r in rows if subset == "all" or r["kind"] == subset]
            cov = [r for r in sel if "cx" in r]
            if not sel:
                continue
            ok = sum(1 for r in cov if attr(r["kind"], r["cx"], r["cy"], flip) == r["gold_attr"])
            print(f"  {subset:9s} n={len(sel):4d} covered={len(cov):4d} "
                  f"({100*len(cov)/len(sel):5.1f}%) acc@covered={100*ok/max(1,len(cov)):5.1f}% "
                  f"acc@all={100*ok/len(sel):5.1f}%")

    print("\n===== per-subset (flip=False) =====")
    by = defaultdict(lambda: [0, 0])
    for r in rows:
        if "cx" not in r:
            continue
        k = (r["subset"], r["kind"])
        by[k][1] += 1
        if attr(r["kind"], r["cx"], r["cy"]) == r["gold_attr"]:
            by[k][0] += 1
    for k in sorted(by):
        ok, n = by[k]
        print(f"  {k[0]:12s} {k[1]:9s} n={n:4d} acc={100*ok/n:5.1f}%")

    print("\n===== gold balance in covered subset =====")
    print(Counter(r["gold_attr"] for r in rows if "cx" in r))
    print("box count distribution:", Counter(r["n_box"] for r in rows))

    # how often does the box sit near the midline (ambiguous laterality)?
    amb = [r for r in rows if "cx" in r and r["kind"] == "side" and 0.42 < r["cx"] < 0.58]
    print(f"side tasks with 0.42<cx<0.58: {len(amb)} / {sum(1 for r in rows if 'cx' in r and r['kind']=='side')}")

    json.dump(rows, open("/dev/shm/maira_scored.json", "w"), indent=0)


if __name__ == "__main__":
    main()
