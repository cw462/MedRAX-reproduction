set -u
/root/miniconda3/bin/python - <<'PYEOF'
import json, re
from collections import Counter, defaultdict

tasks = {t['qid']: t for t in json.load(open('/dev/shm/lat_tasks_maira.json'))}
reports = json.load(open('/dev/shm/maira_reports.json'))
scored = {r['qid']: r for r in json.load(open('/dev/shm/maira_scored.json'))}
side = [q for q in tasks if tasks[q]['kind'] == 'side']

def sidewords(text):
    w = re.findall(r'[a-z]+', text.lower())
    return {x for x in w if x in ('left', 'right')}

print('=== why unanswered? (side tasks) ===')
no_kw = no_side = 0
for q in side:
    t = tasks[q]
    rep = reports.get(t['image']) or {}
    sents = rep.get('sentences') or []
    kw = t['phrase'].split()[-1].lower().rstrip('.,')
    has_kw = any(kw in s['text'].lower() for s in sents)
    raw = rep.get('raw', '')
    if not has_kw:
        no_kw += 1
    elif not sidewords(raw):
        no_side += 1
print(f'  no sentence mentions keyword: {no_kw}/{len(side)}')
print(f'  keyword present but report has no left/right word: {no_side}/{len(side)}')

print()
print('=== 8 unanswered examples ===')
n = 0
for q in side:
    t = tasks[q]
    rep = reports.get(t['image']) or {}
    sents = rep.get('sentences') or []
    kw = t['phrase'].split()[-1].lower().rstrip('.,')
    has_kw = any(kw in s['text'].lower() for s in sents)
    if has_kw and any(sidewords(s['text']) for s in sents):
        continue
    print(f"  {q[-4:]} gold={t['gold_attr']:5s} kw={kw!r}")
    print(f"     raw={rep.get('raw','')[:220]!r}")
    n += 1
    if n >= 8:
        break

print()
print('=== accuracy split: keyword-sentence vs whole-report fallback ===')
kw_ok = kw_n = fb_ok = fb_n = 0
for q in side:
    t = tasks[q]
    rep = reports.get(t['image']) or {}
    sents = rep.get('sentences') or []
    kw = t['phrase'].split()[-1].lower().rstrip('.,')
    hit = None
    for s in sents:
        if kw in s['text'].lower():
            sw = sidewords(s['text'])
            if len(sw) == 1:
                hit = sw.pop(); break
    if hit:
        kw_n += 1; kw_ok += hit == t['gold_attr']
    else:
        sw = sidewords(rep.get('raw', ''))
        if sw:
            fb_n += 1; fb_ok += (sw.pop() if len(sw) == 1 else None) == t['gold_attr']
print(f'  keyword sentence, single side: n={kw_n} acc={100*kw_ok/max(1,kw_n):.1f}%')
print(f'  whole-report fallback:        n={fb_n} acc={100*fb_ok/max(1,fb_n):.1f}%')

print()
print('=== report sentence example (one image) ===')
for k, v in list(reports.items())[:1]:
    print(' image', k.split('/')[-1])
    for s in (v.get('sentences') or [])[:0]:
        pass
    print('  raw:', v.get('raw', '')[:400])
PYEOF
