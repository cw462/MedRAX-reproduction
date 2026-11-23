#!/usr/bin/env python3
"""Keep only imaging-relevant paragraphs from the Wikipedia corpus."""
import json, re
SRC = "H:/RAG_KB/corpus_wiki.jsonl"
DST = "H:/RAG_KB/corpus_wiki_img.jsonl"
IMG = re.compile(r"(radiograph|x-?ray|\bct\b|computed tomograph|\bmri\b|magnetic resonance|ultrasound|ultrasonograph|"
                 r"imaging|radiolog|roentgen|fluoroscop|mammogra|opacity|consolidat|atelecta|cardiomegal|"
                 r"pneumothorax|effusion|nodule|infiltrat|interstitial|pulmonary edema|hilar|mediastin|"
                 r"chest film|costophrenic|tomography|silhouette|ratio|sign\b|shadow|calcif)", re.I)
n_in = n_out = 0
with open(SRC, encoding="utf-8") as f, open(DST, "w", encoding="utf-8") as w:
    for line in f:
        d = json.loads(line); n_in += 1
        if len(d["contents"]) < 120: continue
        if IMG.search(d["contents"]):
            w.write(line); n_out += 1
print("kept", n_out, "of", n_in, "->", DST)
