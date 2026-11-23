#!/usr/bin/env python3
"""Build a unified snippet corpus from MedRAG textbooks + NCBI StatPearls.

Output: H:/RAG_KB/corpus.jsonl  (fields: id, source, title, contents)
"""
import glob, json, os, sys, tarfile
import xml.etree.ElementTree as ET

ROOT = r"H:/RAG_KB"
OUT = os.path.join(ROOT, "corpus.jsonl")

def ends_punct(s):
    return any(s.strip().endswith(c) for c in ".?!")

def concat(title, content):
    t = title.strip()
    return (t + " " + content.strip()) if ends_punct(t) else (t + ". " + content.strip())

def extract_text(el):
    text = (el.text or "").strip()
    for ch in el:
        text += (" " if text else "") + extract_text(ch)
        if ch.tail and ch.tail.strip():
            text += (" " if text else "") + ch.tail.strip()
    return text.strip()

def is_subtitle(el):
    if el.tag != "p" or len(list(el)) != 1 or list(el)[0].tag != "bold":
        return False
    return not (list(el)[0].tail and list(el)[0].tail.strip())

def extract_nxml(fpath):
    fname = os.path.basename(fpath).replace(".nxml", "")
    try:
        tree = ET.parse(fpath)
    except Exception:
        return []
    root = tree.getroot()
    t = root.find(".//title")
    if t is None or not (t.text or "").strip():
        return []
    title = t.text.strip()
    out, j = [], 0
    for sec in root.findall(".//sec"):
        st = sec.find("./title")
        if st is None or not (st.text or "").strip():
            continue
        prefix = " -- ".join([title, st.text.strip()])
        last_text, last_json = None, None
        for ch in sec:
            if is_subtitle(ch):
                last_text = last_json = None
                prefix = " -- ".join(prefix.split(" -- ")[:2] + [extract_text(ch)])
            elif ch.tag == "p":
                cur = extract_text(ch)
                if len(cur) < 200 and last_text is not None and len(last_text + cur) < 1000:
                    last_text = " ".join([last_json["content"], cur])
                    last_json = {"id": last_json["id"], "title": last_json["title"], "content": last_text}
                    last_json["contents"] = concat(last_json["title"], last_json["content"])
                    out[-1] = last_json
                else:
                    last_text = cur
                    last_json = {"id": f"{fname}_{j}", "title": prefix, "content": cur}
                    last_json["contents"] = concat(last_json["title"], last_json["content"])
                    out.append(last_json); j += 1
            elif ch.tag == "list":
                lt = [extract_text(c) for c in ch]
                joined = " ".join(lt)
                if last_text is not None and len(joined + last_text) < 1000:
                    last_text = " ".join([last_json["content"]] + lt)
                    last_json = {"id": last_json["id"], "title": last_json["title"], "content": last_text}
                    last_json["contents"] = concat(last_json["title"], last_json["content"])
                    out[-1] = last_json
                elif len(joined) < 1000:
                    last_text = joined
                    last_json = {"id": f"{fname}_{j}", "title": prefix, "content": joined}
                    last_json["contents"] = concat(last_json["title"], last_json["content"])
                    out.append(last_json); j += 1
    return [o for o in out if o.get("contents")]

def main():
    n_tb = n_sp = 0
    with open(OUT, "w", encoding="utf-8") as w:
        # textbooks
        for p in sorted(glob.glob(os.path.join(ROOT, "textbooks", "*.jsonl"))):
            book = os.path.basename(p)[:-6]
            with open(p, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    d = json.loads(line)
                    w.write(json.dumps({"id": f"tb:{book}:{d.get('id')}", "source": "Textbooks",
                                        "title": d.get("title", ""), "contents": d.get("contents") or d.get("content", "")},
                                       ensure_ascii=False) + "\n")
                    n_tb += 1
            print("textbook", book, n_tb, flush=True)
        # statpearls
        if "--textbooks-only" in sys.argv:
            print("skip statpearls", flush=True)
            print("DONE textbooks=%d statpearls=%d" % (n_tb, n_sp), flush=True)
            return
        sp_dir = os.path.join(ROOT, "statpearls")
        if not os.path.isdir(sp_dir):
            os.makedirs(sp_dir, exist_ok=True)
            with tarfile.open(os.path.join(ROOT, "statpearls.tar.gz")) as tf:
                tf.extractall(sp_dir)
            print("extracted statpearls", flush=True)
        files = glob.glob(os.path.join(sp_dir, "**", "*.nxml"), recursive=True)
        print("statpearls nxml:", len(files), flush=True)
        for i, p in enumerate(files):
            for d in extract_nxml(p):
                w.write(json.dumps({"id": f"sp:{d['id']}", "source": "StatPearls",
                                    "title": d.get("title", ""), "contents": d["contents"]}, ensure_ascii=False) + "\n")
                n_sp += 1
            if i % 500 == 0:
                print("sp", i, n_sp, flush=True)
    print("DONE textbooks=%d statpearls=%d" % (n_tb, n_sp), flush=True)

if __name__ == "__main__":
    main()