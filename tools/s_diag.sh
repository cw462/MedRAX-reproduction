set -u
/root/miniconda3/bin/python - <<'PYEOF'
import json
tasks = {t['qid']: t for t in json.load(open('/dev/shm/lat_tasks_maira.json'))}
boxes = json.load(open('/dev/shm/maira_boxes.json'))
scored = {r['qid']: r for r in json.load(open('/dev/shm/maira_scored.json'))}

side = [(q, t) for q, t in tasks.items() if t['kind'] == 'side']
print(f'side tasks {len(side)}')
print()
n = 0
for q, t in side:
    r = scored[q]
    if 'cx' not in r:
        continue
    b = boxes[q]['boxes'][0]
    x1, y1, x2, y2 = b['norm']
    ok = (r['cx'] < 0.5 and r['gold_attr'] == 'right') or (r['cx'] >= 0.5 and r['gold_attr'] == 'left')
    print(f"{q[-4:]} {'OK ' if ok else 'BAD'} gold={r['gold_attr']:5s} cx={r['cx']:.2f} w={x2-x1:.2f} h={y2-y1:.2f} phrase={t['phrase']!r}")
    print(f"     A={t['options']['A']!r} B={t['options']['B']!r}")
    print(f"     txt={boxes[q]['text'][:140]!r}")
    n += 1
    if n >= 12:
        break

print()
print('=== box width distribution (side tasks) ===')
ws = [scored[q]['w'] for q, _t in side if 'cx' in scored[q]]
import collections
bins = collections.Counter()
for w in ws:
    bins[round(w, 1)] += 1
for k in sorted(bins):
    print(f'  w~{k:.1f}: {bins[k]}')
print()
print('=== predicted side distribution ===')
pred = ['right' if scored[q]['cx'] < 0.5 else 'left' for q, _t in side if 'cx' in scored[q]]
print(collections.Counter(pred))
PYEOF
