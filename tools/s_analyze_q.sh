set -u
PY=/root/miniconda3/bin/python
$PY - <<'EOF'
import json, collections
p = '/dev/shm/frozen/data/chexbench/inputs.jsonl'
rows = [json.loads(l) for l in open(p, encoding='utf-8')]

def optpair(r):
    o = r.get('options') or {}
    if set(o.keys()) >= {'A','B'}:
        return (str(o['A']).strip().lower(), str(o['B']).strip().lower())
    return None

c = collections.Counter(optpair(r) for r in rows)
print('=== option pairs ===')
for k, v in c.most_common(20):
    print(f'{v:4d}  {k}')

print()
print('=== subsets ===')
print(collections.Counter(r['source']['subset'] for r in rows))

print()
print('=== left/right questions ===')
lr = [r for r in rows if optpair(r) == ('left','right')]
print('n =', len(lr))
print(collections.Counter(r['source']['subset'] for r in lr))
print(collections.Counter(r['question'] for r in lr).most_common(8))
for r in lr[:3]:
    print(json.dumps({k: r[k] for k in ('question_id','question','options','images')}, ensure_ascii=False))

print()
print('=== image dirs referenced ===')
dirs = collections.Counter()
for r in rows:
    for im in r['images']:
        dirs[im.rsplit('/',1)[0]] += 1
for k, v in dirs.most_common(10):
    print(f'{v:4d}  {k}')

print()
print('=== unique images ===')
imgs = {im for r in rows for im in r['images']}
print('unique', len(imgs))
EOF
echo
tail -2 /dev/shm/dl.log
