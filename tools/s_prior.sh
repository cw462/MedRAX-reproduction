set -u
/root/miniconda3/bin/python - <<'PYEOF'
import json
from collections import Counter, defaultdict

tasks = {t['qid']: t for t in json.load(open('/dev/shm/lat_tasks_maira.json'))}
scored = {r['qid']: r for r in json.load(open('/dev/shm/maira_scored.json'))}
boxes = json.load(open('/dev/shm/maira_boxes.json'))

side = [q for q in tasks if tasks[q]['kind'] == 'side']

# group by the finding phrase (side token removed)
grp = defaultdict(list)
for q in side:
    grp[tasks[q]['phrase']].append(q)

print('=== per-finding gold side distribution (prior baseline) ===')
base_ok = 0
for k, qs in sorted(grp.items(), key=lambda kv: -len(kv[1])):
    if len(qs) < 5:
        continue
    g = Counter(tasks[q]['gold_attr'] for q in qs)
    maj, mjn = g.most_common(1)[0]
    base_ok += mjn
    print(f'  {k:32s} n={len(qs):3d} right={g["right"]:3d} left={g["left"]:3d} '
          f'majority={maj}({100*mjn/len(qs):.0f}%)')

# global prior baseline over ALL side tasks using per-group majority where n>=5,
# else the global majority
glob = Counter(tasks[q]['gold_attr'] for q in side).most_common(1)[0][0]
ok = 0
for q in side:
    qs = grp[tasks[q]['phrase']]
    if len(qs) >= 5:
        pred = Counter(tasks[x]['gold_attr'] for x in qs).most_common(1)[0][0]
    else:
        pred = glob
    ok += pred == tasks[q]['gold_attr']
print(f'\nprior-only baseline on {len(side)} side tasks: {100*ok/len(side):.1f}%  (n groups={len(grp)})')

# same but leave-one-out to avoid self-counting
ok_loo = 0
for q in side:
    qs = [x for x in grp[tasks[q]['phrase']] if x != q]
    if len(qs) >= 4:
        pred = Counter(tasks[x]['gold_attr'] for x in qs).most_common(1)[0][0]
    else:
        pred = glob
    ok_loo += pred == tasks[q]['gold_attr']
print(f'prior-only (leave-one-out): {100*ok_loo/len(side):.1f}%')

# MAIRA accuracy restricted to the same subset, and prior vs maira agreement
cov = [q for q in side if 'cx' in scored[q]]
maira_ok = sum(1 for q in cov if ('right' if scored[q]['cx'] < 0.5 else 'left') == tasks[q]['gold_attr'])
print(f'\nMAIRA covered {len(cov)}/{len(side)}: acc={100*maira_ok/len(cov):.1f}%')

# does MAIRA box side agree with the group prior?
agree = 0
for q in cov:
    qs = grp[tasks[q]['phrase']]
    pred = Counter(tasks[x]['gold_attr'] for x in qs).most_common(1)[0][0]
    ms = 'right' if scored[q]['cx'] < 0.5 else 'left'
    agree += pred == ms
print(f'MAIRA box side == group prior: {100*agree/len(cov):.1f}%')

# accuracy of "prior" on the covered subset (subset may be easier/harder)
okc = 0
for q in cov:
    qs = [x for x in grp[tasks[q]['phrase']] if x != q]
    pred = Counter(tasks[x]['gold_attr'] for x in qs).most_common(1)[0][0] if len(qs) >= 4 else glob
    okc += pred == tasks[q]['gold_attr']
print(f'prior-only on MAIRA-covered subset: {100*okc/len(cov):.1f}%')
PYEOF
