#!/usr/bin/env python3
"""Convert the human laterality packet (single HTML with base64 images) into a
machine/LLM-readable bundle.

Input : results/human_lat_packet_50.html        self-contained annotation sheet
        results/human_lat_manifest_50.json     answer key (gold + stratum)
        results/maira2_20261123/lat_tasks_maira.json  optional cross-check

Output: results/human_lat_packet_50_llm/
          images/case_NN.jpg      one JPEG per case (bytes exactly as in the HTML)
          packet.jsonl            50 blind items, image by relative path
          packet_b64.jsonl        50 blind items, image inlined as data URL
          answers.template.jsonl  50 empty answer slots
          answer_key.json         gold + stratum (KEEP AWAY FROM THE MODEL)
          prompt.txt              instruction block to prepend
          index.md                human-browsable table
          score.py                answer scorer

Design notes
------------
* blind: packet.jsonl carries no gold, no stratum, no left/right hint.
* options are verbatim from the HTML, so the LLM sees exactly what the human saw.
* images are not re-encoded: same pixels, so results are comparable 1:1.
"""
import base64
import io
import json
import os
import re
import shutil
import sys
from collections import Counter, OrderedDict

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HTML = os.path.join(ROOT, "results", "human_lat_packet_50.html")
MANIFEST = os.path.join(ROOT, "results", "human_lat_manifest_50.json")
TASKS = os.path.join(ROOT, "results", "maira2_20261123", "lat_tasks_maira.json")
OUT = os.path.join(ROOT, "results", "human_lat_packet_50_llm")

CASE_RE = re.compile(r'<div class="case" data-case="(\d+)" data-qid="([^"]+)">(.*?)(?=<div class="case"|\Z)', re.S)
GRP_RE = re.compile(r'<span class="grp">([^<]*)</span>')
IMG_RE = re.compile(r'<img src="data:image/jpeg;base64,([^"]+)"')
OPT_RE = re.compile(r'<input type="radio" name="c\d+" value="([AB?])">\s*([^<]*?)</label>', re.S)

PROMPT = """\
You are reading chest radiographs. Each case shows one image and two statements
that differ only in one laterality word (left vs right).

Laterality convention: standard PA/AP chest radiograph. The patient's LEFT side
appears on the RIGHT side of the image, and the patient's right side on the left.
Judge the patient's side, not the image's side. (The heart shadow normally lies on
the patient's left, which can help confirm the orientation.)

For each case pick the one statement that matches the image. If the image does not
allow a decision, answer "?" instead of guessing from which side is more common.

Reply with a single line and nothing else, case number followed by the letter:
1B 2A 3? 4A ... 50B
"""

README = """\
# CheXBench 侧别题 · 大模型可读包（50 题）

由 `results/human_lat_packet_50.html` 转出。题目、选项、图像与人类判读表**完全一致**
（图是原 HTML 里的同一份 JPEG 字节，没重新编码、没改尺寸），只是把 50 张内嵌 base64
拆成文件、把交互界面换成机器可读清单。所以人类答案与模型答案可以直接同表比较。

## 文件

| 文件 | 用途 |
|---|---|
| `packet.jsonl` | 50 条盲评item：`case` `qid` `finding` `question` `options{A,B}` `image`(相对路径) `image_width/height` |
| `packet_b64.jsonl` | 同上，但 `image` 是 `data:image/jpeg;base64,...`，可直接塞进 API 请求体 |
| `images/case_NN.jpg` | 50 张胸片，JPEG，同 HTML |
| `answers.template.jsonl` | 50 行空答案槽 `{"case":1,"qid":"...","answer":null}` |
| `answer_key.json` | **金标准**（gold 字母、gold_text、真实侧别、stratum）—— 别给模型看 |
| `prompt.txt` | 给模型的指令原文（方向约定 + 输出格式） |
| `index.md` | 50 题一览表，方便人工核对 |
| `score_llm_answers.py` | 打分脚本 |

## 怎么用

1. 读 `prompt.txt` 作为指令；把每条 item 的 `question` + `options` + 图片一起发给多模态模型。
2. 模型只回一串 `1B 2A 3? ... 50A`（与 HTML 判读表"生成答案串"格式相同）。
3. 存成 `answers.txt`，然后：

```
python score_llm_answers.py answers.txt --json scores.json
```

脚本也接受 JSONL / JSON 字典，`X` 与 `?` 都当作"看不出来"。它会给出：总体准确率
（Wilson 95% 区间）、只算已答题的准确率、无法判断率、按 stratum（`m5_right` /
`m5_wrong`）和按 finding 的分组结果，以及"选 left 的比例""选 A 的比例"两个偏置指标
——后者用来看模型是不是在按位置瞎猜。

想和人类成绩并排看：

```
python score_llm_answers.py model_answers.txt --human human_answers.txt
```

## 注意

* **盲评**：`packet*.jsonl` 里没有 gold、没有 stratum、没有任何侧别提示。别把
  `answer_key.json` 或上游的 `human_lat_manifest_50.json` 一起喂给模型。
* `case` 编号与人类判读表一致（1–50），人类答案串可直接当参考答案对照。
* 选项顺序（哪个是 A）与人类看到的一致，所以"选 A 的比例"在两边的含义也是可比的。
* 图片是 820 px 宽的灰度 JPEG，和人在网页上看到的分辨率相同；要更高分辨率得回原始
  CheXBench 图像重做，届时结果就不能和这批人类答案直接比了。
"""


def load_manifest(path):
    """Accept either a bare list or {"meta": ..., "cases": [...]}."""
    obj = json.load(open(path, encoding="utf-8"))
    if isinstance(obj, dict):
        meta = obj.get("meta", {})
        cases = obj.get("cases")
        if cases is None:
            raise SystemExit("manifest object has no 'cases' key")
        return meta, cases
    return {}, obj


def parse_html(text):
    cases = []
    for num, qid, body in CASE_RE.findall(text):
        grp = GRP_RE.search(body).group(1).strip()
        b64 = IMG_RE.search(body).group(1)
        opts = OrderedDict()
        for letter, label in OPT_RE.findall(body):
            label = label.strip()
            if letter in "AB":
                label = re.sub(r"^%s\.\s*" % letter, "", label)  # "A. left ..." -> "left ..."
                opts[letter] = label
        cases.append({"case": int(num), "qid": qid, "phrase": grp, "b64": b64, "options": opts})
    return cases


def main():
    html = open(HTML, encoding="utf-8").read()
    cases = parse_html(html)
    meta, man_list = load_manifest(MANIFEST)
    man = {m["qid"]: m for m in man_list}
    tasks = {}
    if os.path.exists(TASKS):
        tasks = {t["qid"]: t for t in json.load(open(TASKS, encoding="utf-8"))}

    errs = []
    if len(cases) != 50:
        errs.append("parsed %d cases, expected 50" % len(cases))
    if [c["case"] for c in cases] != list(range(1, len(cases) + 1)):
        errs.append("case numbers are not 1..N")
    if len({c["qid"] for c in cases}) != len(cases):
        errs.append("duplicate qid in HTML")
    if len(man) != len(man_list):
        errs.append("duplicate qid in manifest")
    missing = [c["qid"] for c in cases if c["qid"] not in man]
    if missing:
        errs.append("qids missing from manifest: %r" % missing)
    extra = [q for q in man if q not in {c["qid"] for c in cases}]
    if extra:
        errs.append("manifest qids absent from HTML: %r" % extra)
    if not errs:
        for c in cases:
            m = man[c["qid"]]
            if m.get("case") != c["case"]:
                errs.append("case %d: qid %s sits at position %r in manifest"
                            % (c["case"], c["qid"], m.get("case")))
                break
    if errs:
        print("REFUSING TO BUILD:", file=sys.stderr)
        for e in errs:
            print(" -", e, file=sys.stderr)
        return 2

    imgdir = os.path.join(OUT, "images")
    os.makedirs(imgdir, exist_ok=True)
    for stale in os.listdir(imgdir):
        if re.fullmatch(r"case_\d+\.jpg", stale):
            os.remove(os.path.join(imgdir, stale))

    packet, packet_b64, key, rows = [], [], [], []
    sizes = []
    for c in cases:
        i, qid = c["case"], c["qid"]
        m = man[qid]
        raw = base64.b64decode(c["b64"])
        im = Image.open(io.BytesIO(raw))
        im.load()
        with open(os.path.join(imgdir, "case_%02d.jpg" % i), "wb") as f:
            f.write(raw)  # keep the packet's own bytes: no re-encode, no resample
        w, h = im.size
        sizes.append((w, h))

        gold_text = c["options"][m["gold"]]
        # the gold letter must be the option that carries the gold attribute
        if m["gold_attr"] not in gold_text:
            errs.append("case %d: gold %s=%r does not contain attr %r"
                        % (i, m["gold"], gold_text, m["gold_attr"]))
        if m.get("phrase") and m["phrase"] != c["phrase"]:
            errs.append("case %d: phrase %r vs %r" % (i, m["phrase"], c["phrase"]))
        # the two options must differ in exactly one token, else "which side" is ill-posed
        ta, tb = c["options"]["A"].split(), c["options"]["B"].split()
        if len(ta) != len(tb) or sum(x != y for x, y in zip(ta, tb)) != 1:
            errs.append("case %d: options differ by more than one token: %r / %r"
                        % (i, c["options"]["A"], c["options"]["B"]))
        # optional cross-check against the task file that generated the packet
        if qid in tasks and tasks[qid].get("options") != dict(c["options"]):
            errs.append("case %d: options differ from lat_tasks_maira.json" % i)

        item = OrderedDict([
            ("case", i),
            ("qid", qid),
            ("finding", c["phrase"]),
            ("question", "Which option matches the image?"),
            ("options", {"A": c["options"]["A"], "B": c["options"]["B"]}),
            ("image", "images/case_%02d.jpg" % i),
            ("image_width", w),
            ("image_height", h),
            ("allow_indeterminate", True),
        ])
        packet.append(item)
        b64item = OrderedDict(item)
        b64item["image"] = "data:image/jpeg;base64," + base64.b64encode(raw).decode()
        packet_b64.append(b64item)

        key.append(OrderedDict([
            ("case", i), ("qid", qid), ("gold", m["gold"]),
            ("gold_text", gold_text), ("gold_attr", m["gold_attr"]),
            ("finding", c["phrase"]), ("stratum", m.get("stratum")),
        ]))
        rows.append((i, qid, c["phrase"], c["options"]["A"], c["options"]["B"],
                     "images/case_%02d.jpg" % i))

    if errs:
        print("REFUSING TO BUILD:", file=sys.stderr)
        for e in errs:
            print(" -", e, file=sys.stderr)
        return 3

    def dump_jsonl(name, items):
        with open(os.path.join(OUT, name), "w", encoding="utf-8", newline="\n") as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")

    dump_jsonl("packet.jsonl", packet)
    dump_jsonl("packet_b64.jsonl", packet_b64)
    dump_jsonl("answers.template.jsonl",
               [{"case": r["case"], "qid": r["qid"], "answer": None} for r in packet])
    with open(os.path.join(OUT, "answer_key.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "cases": key}, f, ensure_ascii=False, indent=1)

    with open(os.path.join(OUT, "index.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# CheXBench laterality packet - 50 items (blind)\n\n")
        f.write("Options are verbatim; gold answers live only in `answer_key.json`.\n\n")
        f.write("| # | qid | finding | A | B | image |\n")
        f.write("|---|---|---|---|---|---|\n")
        for i, qid, ph, a, b, p in rows:
            f.write("| %d | `%s` | %s | %s | **%s** | [jpg](%s) |\n" % (i, qid, ph, a, b, p))

    with open(os.path.join(OUT, "prompt.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(PROMPT)
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(README)
    scorer = os.path.join(HERE, "score_llm_answers.py")
    if os.path.exists(scorer):
        shutil.copyfile(scorer, os.path.join(OUT, "score_llm_answers.py"))

    n = len(packet)
    print("built %d cases -> %s" % (n, OUT))
    print("image sizes:", dict(Counter("%dx%d" % s for s in sizes)))
    print("findings (%d):" % len({r["finding"] for r in packet}))
    for k, v in Counter(r["finding"] for r in packet).most_common():
        print("  %-40s %2d" % (k, v))
    print("gold letters:", dict(Counter(k["gold"] for k in key)))
    print("gold attrs  :", dict(Counter(k["gold_attr"] for k in key)))
    if any(k["stratum"] for k in key):
        print("strata      :", dict(Counter(k["stratum"] for k in key)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
