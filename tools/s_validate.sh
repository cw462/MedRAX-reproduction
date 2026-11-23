set -u
/root/miniconda3/bin/python - <<'PYEOF'
import json
from collections import Counter

tasks = {t['qid']: t for t in json.load(open('/dev/shm/lat_tasks_maira.json'))}
scored = {r['qid']: r for r in json.load(open('/dev/shm/maira_scored.json'))}
p0 = {r['qid']: r for r in json.load(open('/root/p0_side_result.json'))}
base = {r['qid']: r for r in json.load(open('/root/res_chexbench_base.json'))}

side = [q for q in tasks if tasks[q]['kind'] == 'side']

# 1) label agreement: my gold letter vs p0 ref
both = [q for q in side if q in p0]
agree = sum(1 for q in both if p0[q]['ref'].upper() == tasks[q]['gold'])
print(f'gold letter agreement with p0 ref: {agree}/{len(both)} = {100*agree/max(1,len(both)):.1f}%')

# 2) label agreement: my gold letter vs DeepSeek baseline reference
both2 = [q for q in side if q in base]
agree2 = sum(1 for q in both2 if str(base[q]['reference']).upper() == tasks[q]['gold'])
print(f'gold letter agreement with baseline ref: {agree2}/{len(both2)} = {100*agree2/max(1,len(both2)):.1f}%')

# 3) M5 accuracy on MY side subset (letter mode = okA)
m5 = [q for q in both if 'okA' in p0[q]]
m5ok = sum(1 for q in m5 if p0[q]['okA'])
print(f'\nM5 (letter mode) on my {len(m5)} side tasks: {100*m5ok/len(m5):.1f}%')
m5b = [q for q in both if 'okB' in p0[q]]
print(f'M5 (left/right mode) on {len(m5b)}: {100*sum(1 for q in m5b if p0[q]["okB"])/len(m5b):.1f}%')

# 4) DeepSeek baseline accuracy on my side subset
b = [q for q in both2 if 'base' in base[q]]
bok = sum(1 for q in b if base[q]['base'].get('correct'))
print(f'DeepSeek baseline on my {len(b)} side tasks: {100*bok/len(b):.1f}%')

# 5) always-B and prior on the same rows
for name, sel in [('M5-subset', m5)]:
    alw = sum(1 for q in sel if tasks[q]['gold'] == 'B')
    print(f'  always-B on {name}: {100*alw/len(sel):.1f}%')

# 6) MAIRA vs M5 on exactly the same qids
same = [q for q in m5 if 'cx' in scored[q]]
if same:
    m_ok = sum(1 for q in same if ('right' if scored[q]['cx'] < 0.5 else 'left') == tasks[q]['gold_attr'])
    m5_ok = sum(1 for q in same if p0[q]['okA'])
    print(f'\non identical {len(same)} tasks: MAIRA={100*m_ok/len(same):.1f}%  M5={100*m5_ok/len(same):.1f}%')

# 7) M5 per-group accuracy
print('\n=== M5 per-group (letter mode) ===')
from collections import defaultdict
g = defaultdict(list)
for q in m5:
    g[tasks[q]['phrase']].append(q)
for k, qs in sorted(g.items(), key=lambda kv: -len(kv[1]))[:10]:
    print(f'  {k:34s} n={len(qs):3d} M5={100*sum(1 for q in qs if p0[q]["okA"])/len(qs):5.1f}%  goldmajor={Counter(tasks[q]["gold_attr"] for q in qs).most_common(1)[0]}')
PYEOF
