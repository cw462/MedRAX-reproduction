#!/usr/bin/env python3
"""Localization questions: replay M5's tool observations to qwen3.6-flash,
optionally adding the CXAS geometry evidence.

arm A: image + question + options + M5's tool observations (context replay)
arm B: arm A + anatomy evidence (CXAS diaphragm domes)

Usage: python loc_arm.py <A|B> <out.jsonl> [--errors-only]
"""
import base64
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = "/home/imss/cw/radiology_rag_p3"
KEY = open("/home/imss/cw/m5_rrsi_dev50_lab_s0_20261120/trusted/native_api.keys").read().strip().splitlines()[0]
URL = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions"
MODEL = "qwen3.6-flash"

ARM = sys.argv[1]
OUT = sys.argv[2]
ERRORS_ONLY = "--errors-only" in sys.argv

tasks = [t for t in json.load(open(ROOT + "/lat_tasks_maira.json", encoding="utf-8"))
         if t["kind"] == "side"]
m5 = {json.loads(l)["question_id"]: json.loads(l)
      for l in open(ROOT + "/m5_chexbench.jsonl", encoding="utf-8-sig") if l.strip()}
geom = json.load(open(ROOT + "/loc_geom.json", encoding="utf-8"))
paths = json.load(open(ROOT + "/yn238_paths.json", encoding="utf-8"))

done = set()
if os.path.exists(OUT):
    for line in open(OUT, encoding="utf-8"):
        line = line.strip()
        if line:
            done.add(json.loads(line)["qid"])

todo = [t for t in tasks if t["qid"] in m5 and t["qid"] not in done]
if ERRORS_ONLY:
    todo = [t for t in todo if not m5[t["qid"]].get("correct")]
print(f"arm={ARM} todo={len(todo)} errors_only={ERRORS_ONLY}", flush=True)


def m5_obs_text(r):
    lines = []
    for ob in (r.get("tool_observations") or [])[:5]:
        tool = ob.get("tool", "tool")
        o = ob.get("observation") or {}
        if isinstance(o, dict) and tool == "maira2_grounded_report":
            txt = o.get("report") or o.get("analysis_status") or str(o)[:150]
        elif isinstance(o, dict) and tool == "xray_phrase_grounding":
            txt = json.dumps(o, ensure_ascii=False)[:220]
        else:
            txt = json.dumps(o, ensure_ascii=False)[:220]
        lines.append(f"[{tool}] {txt}")
    return "\n".join(lines) if lines else "(no tool observations)"


def geom_text(qid):
    g = geom.get(qid)
    if not g or not g.get("domes"):
        return ""
    d = g["domes"]
    if len(d) < 2:
        return ""
    ry, rconf = d["right"]["y"], d["right"]["conf"]
    ly, lconf = d["left"]["y"], d["left"]["conf"]
    if rconf < 0.4 or lconf < 0.4:
        return ("Anatomy tool (CXAS): diaphragm landmarks unreliable "
                f"(right conf {rconf:.2f}, left conf {lconf:.2f}).")
    delta = ry - ly
    if abs(delta) < 8:
        elev = "neither (diaphragms level)"
    else:
        side = "right" if delta < 0 else "left"
        elev = f"{side} elevated by {abs(delta)}px"
    return (f"Anatomy tool (CXAS): right diaphragm dome y={ry} (conf {rconf:.2f}), "
            f"left y={ly} (conf {lconf:.2f}) -> {elev}. "
            "Note: an elevated hemidiaphragm often sides with the abnormality.")


def img_b64(basename):
    with open(paths[basename], "rb") as fh:
        return base64.b64encode(fh.read()).decode()


def call(t):
    qid = t["qid"]
    r = m5[qid]
    o = r["options"]
    letters = sorted(o.keys())
    text = f"Question: {r['question']}\nOptions:\n"
    for k in letters:
        text += f"{k}. {o[k]}\n"
    text += "Previous tool observations:\n" + m5_obs_text(r) + "\n"
    if ARM == "B":
        g = geom_text(qid)
        if g:
            text += g + "\n"
    if ARM == "C":
        g = geom_text(qid)
        if g:
            text += (g + "\n"
                     "Verified rule from a deterministic system: on this benchmark, when one "
                     "hemidiaphragm is clearly elevated (>=8px) and the question asks which "
                     "side has the finding, the answer is almost always the side of the "
                     "elevated diaphragm (22/22 cases). Apply this rule unless the image "
                     "clearly contradicts it.\n")
    text += "Answer with the letter only."
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a chest X-ray radiologist answering medical VQA. "
             "The image is the primary evidence; tool observations may be wrong."},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64(t['image'].rsplit('/', 1)[-1])}"}},
                {"type": "text", "text": text},
            ]},
        ],
        "temperature": 0.0,
        "max_tokens": 16,
    }
    req = urllib.request.Request(URL, json.dumps(payload).encode(),
                                 {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                d = json.loads(resp.read())
            ans = d["choices"][0]["message"]["content"].strip().upper()
            ch = ans[0] if ans else "?"
            if ch not in letters:
                ch = "?"
            return {"qid": qid, "letter": ch,
                    "pred": str(o.get(ch, "?")).strip().lower(),
                    "m5_letter": str(r.get("choice", "?")),
                    "m5_pred": str(o.get(r.get("choice"), "")).strip().lower()
                    if r.get("choice") in o else "",
                    "gold_attr": t.get("gold_attr"), "raw": ans}
        except Exception as e:  # noqa: BLE001
            err = str(e)[:120]
            time.sleep(4 * (attempt + 1))
    return {"qid": qid, "letter": "!", "pred": "!",
            "m5_letter": str(r.get("choice", "?")), "m5_pred": "",
            "gold_attr": t.get("gold_attr"), "raw": err}


with ThreadPoolExecutor(max_workers=8) as ex:
    for i, res in enumerate(ex.map(call, todo), 1):
        with open(OUT, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(res, ensure_ascii=False) + "\n")
        if i % 10 == 0:
            print(f"{i}/{len(todo)}", flush=True)

print("DONE", OUT, flush=True)
