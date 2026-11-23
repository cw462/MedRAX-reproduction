#!/usr/bin/env python3
"""Filter the corpus down to radiology/imaging-relevant material."""
import json, re, sys

RAD = re.compile(r"(radiograph|x-?ray|ct\b|computed tomograph|mri\b|magnetic resonance|ultrasound|ultrasonograph|"
                 r"imaging|radiolog|roentgen|fluoroscop|mammogra|opacity|consolidat|atelecta|cardiomegal|"
                 r"pneumothorax|effusion|nodule|infiltrat|interstitial|pulmonary edema|hilar|mediastin|"
                 r"chest film|chest radiograph|costophrenic|opacities|radiopaque|tomography)", re.I)

def main(src, dst, keep_textbooks=False):
    articles = {}
    rows = 0
    with open(src, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            rows += 1
            if d["source"] == "Textbooks" and not keep_textbooks:
                continue
            art = d["title"].split(" -- ")[0].strip()
            articles.setdefault(art, []).append(d)
    keep = {a for a, ds in articles.items() if any(RAD.search(d["contents"][:1200]) for d in ds[:3])}
    n = 0
    with open(dst, "w", encoding="utf-8") as w:
        for a in sorted(keep):
            for d in articles[a]:
                w.write(json.dumps(d, ensure_ascii=False) + "\n"); n += 1
    print("articles total", len(articles), "radiology", len(keep), "snippets", n, "from", rows)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], len(sys.argv) > 3)
