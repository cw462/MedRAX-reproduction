#!/usr/bin/env python3
"""Build a stratified human-annotation packet for CheXBench laterality.

Sampling is stratified by M5 outcome (25 cases M5 got wrong + 25 it got right),
because the decision "should we train a detector" hinges on whether the cases M5
*fails* are humanly solvable. Random sampling cannot answer that at n=50.

Outputs a self-contained HTML plus a manifest carrying the stratum of each case.
"""
import base64
import io
import json
import os
import random
from collections import Counter, defaultdict

from PIL import Image

TASKS = "/dev/shm/lat_tasks_maira.json"
P0 = "/root/p0_side_result.json"
OUT_HTML = "/dev/shm/human_lat_packet.html"
OUT_MAN = "/dev/shm/human_lat_manifest.json"
PER_STRATUM = 25
MAXW = 820
SEED = 20261123

CONVENTION = (
    "标准 PA/AP 胸片：<b>患者左侧 = 图像右侧</b>，患者右侧 = 图像左侧。"
    "请按这个约定判断（心脏阴影主要位于患者左侧，可用来确认方向）。"
)


def b64_image(path):
    im = Image.open(path).convert("L")
    if im.width > MAXW:
        h = int(im.height * MAXW / im.width)
        im = im.resize((MAXW, h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=82, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def _round_robin(pool, k, rng):
    """Pick k items spreading across findings (round-robin over phrase groups)."""
    groups = defaultdict(list)
    for t in pool:
        groups[t["phrase"]].append(t)
    for g in groups.values():
        rng.shuffle(g)
    order = sorted(groups, key=lambda x: -len(groups[x]))
    picked = []
    while len(picked) < k and any(groups[x] for x in order):
        for key in order:
            if len(picked) >= k:
                break
            if groups[key]:
                picked.append(groups[key].pop())
    return picked


def sample_stratum(pool, n, rng):
    """Sample n, forcing a balanced laterality split inside the stratum.

    Without this the stratum is skewed: `M5 wrong` concentrates on whatever
    side M5 does *not* favour, so a human who cannot tell but always guesses
    the majority side would score far above chance.
    """
    rights = [t for t in pool if t["gold_attr"] == "right"]
    lefts = [t for t in pool if t["gold_attr"] == "left"]
    want_r = min(len(rights), (n + 1) // 2)
    want_l = min(len(lefts), n - want_r)
    if want_r + want_l < n:  # one side is short; top up from the other
        want_r = min(len(rights), n - want_l)
    picked = _round_robin(rights, want_r, rng) + _round_robin(lefts, want_l, rng)
    return picked


def main():
    tasks = [t for t in json.load(open(TASKS, encoding="utf-8")) if t["kind"] == "side"]
    p0 = {r["qid"]: r for r in json.load(open(P0, encoding="utf-8"))}
    known = [t for t in tasks if t["qid"] in p0]
    wrong = [t for t in known if not p0[t["qid"]]["okA"]]
    right = [t for t in known if p0[t["qid"]]["okA"]]
    err_rate = len(wrong) / len(known)
    print(f"population: {len(known)} with M5 result, M5 acc {100*(1-err_rate):.1f}%")

    rng = random.Random(SEED)
    a = sample_stratum(wrong, PER_STRATUM, rng)
    b = sample_stratum(right, PER_STRATUM, rng)
    picked = a + b
    rng.shuffle(picked)

    man, cards = [], []
    for i, t in enumerate(picked, 1):
        b64 = b64_image(t["image"])
        stratum = "m5_wrong" if p0[t["qid"]]["okA"] is False else "m5_right"
        man.append({"case": i, "qid": t["qid"], "gold": t["gold"],
                    "gold_attr": t["gold_attr"], "phrase": t["phrase"],
                    "stratum": stratum})
        cards.append(f"""
<div class="case" data-case="{i}" data-qid="{t['qid']}">
  <div class="hdr">第 {i} 题 <span class="grp">{t['phrase']}</span></div>
  <img src="data:image/jpeg;base64,{b64}" alt="case {i}">
  <div class="opts">
    <label><input type="radio" name="c{i}" value="A"> A. {t['options']['A']}</label>
    <label><input type="radio" name="c{i}" value="B"> B. {t['options']['B']}</label>
    <label><input type="radio" name="c{i}" value="?"> 看不出来 / 无法判断</label>
  </div>
</div>""")

    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>CheXBench 定位题人类基线判读表（{len(picked)} 题）</title>
<style>
 body{{font-family:-apple-system,"Segoe UI",Roboto,sans-serif;max-width:900px;margin:0 auto;
      padding:24px;background:#fafafa;color:#111;line-height:1.5}}
 h1{{font-size:22px}} .note{{background:#fff8e1;border-left:4px solid #f0b400;padding:12px 14px;
      border-radius:4px;margin:16px 0}}
 .case{{background:#fff;border:1px solid #e3e3e3;border-radius:8px;padding:14px;margin:18px 0;
      box-shadow:0 1px 2px rgba(0,0,0,.04)}}
 .hdr{{font-weight:600;margin-bottom:8px}} .grp{{font-weight:400;color:#888;font-size:13px}}
 img{{width:100%;max-width:{MAXW}px;display:block;margin:8px 0;border-radius:4px;background:#000}}
 .opts{{display:flex;flex-direction:column;gap:6px;margin-top:8px}}
 .opts label{{cursor:pointer;padding:6px 8px;border-radius:4px}}
 .opts label:hover{{background:#f0f6ff}}
 #bar{{position:sticky;top:0;background:#111;color:#fff;padding:10px 14px;border-radius:6px;
      display:flex;gap:14px;align-items:center;z-index:9;font-size:14px}}
 #bar button{{background:#2b6cb0;color:#fff;border:0;padding:7px 12px;border-radius:4px;cursor:pointer}}
 #bar .hint{{font-size:12px;color:#bbb;margin-left:auto;margin-right:10px}}
 #out{{width:100%;height:80px;margin-top:10px;font-family:ui-monospace,monospace;font-size:13px}}
</style></head><body>
<h1>CheXBench 定位题 · 人类基线判读表</h1>
<div class="note">
<b>怎么答：</b>每题一张胸片、两个选项，二者只差一个方位词，选<b>与图像相符</b>的那个。<br>
<b>方向约定：</b>{CONVENTION}<br>
<b>为什么麻烦你：</b>这批题的标签来自报告文本而不是图像标注。如果人类也只能答对七成，
说明题目本身有歧义，再投钱训练检测器也拿不到分——所以先测人类上限。<br>
<b>请只凭图像判断</b>，不要按"哪侧更常见"猜；<b>不确定就选"看不出来"</b>，这也是重要信息。
</div>
<div id="bar"><span id="cnt">已答 0 / {len(picked)}</span>
<span class="hint">键盘 <b>A</b> / <b>B</b> / <b>X</b>（看不出来）直接作答并自动跳下一题</span>
<button onclick="collect()">生成答案串</button>
<button onclick="document.getElementById('out').select();document.execCommand('copy')">复制</button>
</div>
{''.join(cards)}
<h2>答案</h2>
<p>点"生成答案串"后复制，直接贴回对话即可。</p>
<textarea id="out" placeholder="点上面的按钮生成"></textarea>
<script>
function collect(){{
  const out=[];
  document.querySelectorAll('.case').forEach(c=>{{
    const n=c.dataset.case;
    const r=document.querySelector(`input[name=c${{n}}]:checked`);
    out.push(n+(r?r.value:'-'));
  }});
  document.getElementById('out').value=out.join(' ');
}}
function upd(){{
  let k=0;
  document.querySelectorAll('.case').forEach(c=>{{
    if(document.querySelector(`input[name=c${{c.dataset.case}}]:checked`))k++;
  }});
  document.getElementById('cnt').textContent=`已答 ${{k}} / {len(picked)}`;
  const bar=document.getElementById('bar');
  bar.style.background = k==={len(picked)} ? '#1a7f37' : '#111';
}}
document.addEventListener('change',upd);

// keyboard: answer the case at the top of the viewport, then advance
const cases=[...document.querySelectorAll('.case')];
function currentIndex(){{
  let idx=0;
  cases.forEach((c,i)=>{{ if(c.getBoundingClientRect().top<=240) idx=i; }});
  return idx;
}}
document.addEventListener('keydown',e=>{{
  if(e.target.tagName==='TEXTAREA'||e.target.tagName==='INPUT') return;
  const k=e.key.toLowerCase();
  let v=null;
  if(k==='a'||k==='1') v='A';
  else if(k==='b'||k==='2') v='B';
  else if(k==='x'||k==='?'||k==='3') v='?';
  if(!v) return;
  const i=currentIndex();
  const r=document.querySelector(`input[name=c${{i+1}}][value="${{v}}"]`);
  if(r){{
    r.checked=true; upd();
    if(i+1<cases.length) cases[i+1].scrollIntoView({{behavior:'smooth',block:'start'}});
  }}
  e.preventDefault();
}});
</script></body></html>"""

    open(OUT_HTML, "w", encoding="utf-8").write(html)
    meta = {"n": len(picked), "err_rate": err_rate,
            "per_stratum": PER_STRATUM, "seed": SEED,
            "stratum_counts": dict(Counter(m["stratum"] for m in man)),
            "gold_balance": dict(Counter(m["gold_attr"] for m in man))}
    json.dump({"meta": meta, "cases": man}, open(OUT_MAN, "w"), indent=0)
    print("cases", len(picked), "html bytes", len(html))
    print(json.dumps(meta, ensure_ascii=False))
    print("groups:", dict(Counter(m["phrase"] for m in man).most_common(10)))


if __name__ == "__main__":
    main()
