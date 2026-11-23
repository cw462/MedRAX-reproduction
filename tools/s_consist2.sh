set -u
/root/miniconda3/bin/python - <<'PYEOF'
import json
from collections import Counter, defaultdict

tasks = json.load(open('/dev/shm/lat_tasks_maira.json', encoding='utf-8'))
side = [t for t in tasks if t['kind'] == 'side']

# 1) same image + same finding issued twice -> contradiction check
by = defaultdict(list)
for t in side:
    by[(t['image'], t['phrase'])].append(t)
dup = {k: v for k, v in by.items() if len(v) > 1}
print(f'images+finding appearing more than once: {len(dup)}')
for k, v in list(dup.items())[:8]:
    g = Counter(x['gold_attr'] for x in v)
    flag = 'CONTRADICTION' if len(g) > 1 else 'consistent'
    print(f'  {k[0].split("/")[-1]:34s} {k[1]:30s} {dict(g)} {flag}')

# 2) how many distinct images, and questions per image
imgq = defaultdict(list)
for t in side:
    imgq[t['image']].append(t)
cnt = Counter(len(v) for v in imgq.values())
print(f'\ndistinct images: {len(imgq)}')
print('questions per image:', dict(sorted(cnt.items())))

# 3) multiple findings on the same image: are their gold sides correlated?
pairs = []
for img, ts in imgq.items():
    if len(ts) >= 2:
        for i in range(len(ts) - 1):
            a, b = ts[i], ts[i + 1]
            if a['phrase'] != b['phrase']:
                pairs.append((a['gold_attr'], b['gold_attr']))
if pairs:
    same = sum(1 for a, b in pairs if a == b)
    print(f'\ncross-finding side pairs on same image: {len(pairs)}, same side {same} '
          f'({100*same/len(pairs):.1f}%)')
    print('  (if findings were placed independently, expect ~50%)')

# 4) subset breakdown
print('\nsubsets:', Counter(t['subset'] for t in side))
PYEOF
