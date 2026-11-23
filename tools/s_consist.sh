set -u
/root/miniconda3/bin/python - <<'PYEOF'
import json, re
from collections import Counter

tasks = {t['qid']: t for t in json.load(open('/dev/shm/lat_tasks_maira.json'))}
reports = json.load(open('/dev/shm/maira_reports.json'))
scored = {r['qid']: r for r in json.load(open('/dev/shm/maira_scored.json'))}
side = [q for q in tasks if tasks[q]['kind'] == 'side']

def sides(text):
    w = set(re.findall(r'[a-z]+', text.lower()))
    return {x for x in w if x in ('left', 'right')}

# report-side per task: sentence mentioning head noun with exactly one side
rep_side = {}
for q in side:
    t = tasks[q]
    rep = reports.get(t['image']) or {}
    kw = t['phrase'].split()[-1].lower().rstrip('.,')
    for s in (rep.get('sentences') or []):
        if kw in s['text'].lower():
            sw = sides(s['text'])
            if len(sw) == 1:
                rep_side[q] = sw.pop()
                break
    else:
        sw = sides(rep.get('raw', ''))
        if len(sw) == 1:
            rep_side[q] = sw.pop()

both = [q for q in side if q in rep_side and 'cx' in scored[q]]
print(f'tasks with BOTH report-side and box: {len(both)}')

def boxside(q):
    return 'right' if scored[q]['cx'] < 0.5 else 'left'
def boxside_flip(q):
    return 'left' if scored[q]['cx'] < 0.5 else 'right'

a = sum(1 for q in both if boxside(q) == rep_side[q])
af = sum(1 for q in both if boxside_flip(q) == rep_side[q])
print(f'box side == report side (standard conv): {100*a/len(both):.1f}%')
print(f'box side == report side (flipped conv):  {100*af/len(both):.1f}%')

# on same subset: accuracy vs gold
g1 = sum(1 for q in both if boxside(q) == tasks[q]['gold_attr'])
g2 = sum(1 for q in both if rep_side[q] == tasks[q]['gold_attr'])
print(f'\non those {len(both)}: report acc={100*g2/len(both):.1f}%  box acc={100*g1/len(both):.1f}%')

# orientation proxy from cardiac silhouette box (heart is on patient's left)
card = []
for q in side:
    t = tasks[q]
    rep = reports.get(t['image']) or {}
    for s in (rep.get('sentences') or []):
        if 'cardiac silhouette' in s['text'].lower() or 'heart' in s['text'].lower():
            boxes = s.get('boxes') or []
            if boxes:
                b = boxes[0]['norm']
                card.append(((b[0] + b[2]) / 2, q))
                break
print(f'\nimages with cardiac box: {len(card)}')
import statistics
cxs = [c for c, _ in card]
print(f'  heart cx mean={statistics.mean(cxs):.3f} median={statistics.median(cxs):.3f}')
print(f'  heart on image-left (<0.45): {sum(1 for c in cxs if c < 0.45)}')
print(f'  heart on image-right (>0.55): {sum(1 for c in cxs if c > 0.55)}')
print(f'  central: {sum(1 for c in cxs if 0.45 <= c <= 0.55)}')

# if heart is on image-left -> image is flipped (patient-left appears image-left)
orient = {q: ('flipped' if c < 0.5 else 'standard') for c, q in card}
sub = [q for q in side if q in orient and 'cx' in scored[q]]
print(f'\n=== box accuracy with per-image orientation correction (n={len(sub)}) ===')
ok = 0
for q in sub:
    pred = boxside(q) if orient[q] == 'standard' else boxside_flip(q)
    ok += pred == tasks[q]['gold_attr']
print(f'  corrected box acc = {100*ok/max(1,len(sub)):.1f}%')
ok2 = sum(1 for q in sub if boxside(q) == tasks[q]['gold_attr'])
print(f'  uncorrected box acc = {100*ok2/max(1,len(sub)):.1f}%')
print(f'  orientation split: {Counter(orient[q] for q in sub)}')
PYEOF
