set -u
/root/miniconda3/bin/python - <<'PYEOF'
import json
from collections import Counter, defaultdict

tasks = {t['qid']: t for t in json.load(open('/dev/shm/lat_tasks_maira.json'))}
scored = {r['qid']: r for r in json.load(open('/dev/shm/maira_scored.json'))}
side = [q for q in tasks if tasks[q]['kind'] == 'side']

print('=== per-group MAIRA accuracy (covered only) ===')
grp = defaultdict(list)
for q in side:
    grp[tasks[q]['phrase']].append(q)
for k, qs in sorted(grp.items(), key=lambda kv: -len(kv[1])):
    cov = [q for q in qs if 'cx' in scored[q]]
    if len(cov) < 5:
        continue
    ok = sum(1 for q in cov if ('right' if scored[q]['cx'] < 0.5 else 'left') == tasks[q]['gold_attr'])
    maj = Counter(tasks[q]['gold_attr'] for q in qs).most_common(1)[0]
    print(f'  {k:34s} cov={len(cov):3d}/{len(qs):3d} maira={100*ok/len(cov):5.1f}%  goldmajor={maj[0]}({100*maj[1]/len(qs):.0f}%)')

print()
print('=== accuracy by box width (focal boxes) ===')
for lo, hi in [(0,0.15),(0.15,0.25),(0.25,0.35),(0.35,0.5),(0.5,1.1)]:
    sel = [q for q in side if 'cx' in scored[q] and lo <= scored[q]['w'] < hi]
    if not sel:
        continue
    ok = sum(1 for q in sel if ('right' if scored[q]['cx'] < 0.5 else 'left') == tasks[q]['gold_attr'])
    print(f'  w in [{lo:.2f},{hi:.2f}): n={len(sel):3d} acc={100*ok/len(sel):5.1f}%')

print()
print('=== how many boxes are near-midline (cx 0.45-0.55) ===')
for lo, hi in [(0,0.3),(0.3,0.45),(0.45,0.55),(0.55,0.7),(0.7,1.0)]:
    n = sum(1 for q in side if 'cx' in scored[q] and lo <= scored[q]['cx'] < hi)
    print(f'  cx in [{lo:.2f},{hi:.2f}): {n}')
PYEOF
