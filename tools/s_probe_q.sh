set -u
PY=/root/miniconda3/bin/python
TAR=/root/.medrax-private-transfer/preserved-frozen-inputs/medrax_r55_top4_full848-frozen-inputs.tar
mkdir -p /dev/shm/frozen
tar -xf "$TAR" -C /dev/shm/frozen data/chexbench/inputs.jsonl data/slake/inputs.jsonl data/vqarad/inputs.jsonl 2>/dev/null
ls -la /dev/shm/frozen/data/chexbench/

$PY - <<'EOF'
import json, collections, itertools
p = '/dev/shm/frozen/data/chexbench/inputs.jsonl'
rows = [json.loads(l) for l in open(p, encoding='utf-8')]
print('n rows', len(rows))
print('keys', list(rows[0].keys()))
print(json.dumps(rows[0], ensure_ascii=False)[:1200])
print()
c = collections.Counter(r.get('task') or r.get('type') or r.get('category') for r in rows)
print('task field counter:', c.most_common(12))
EOF

echo
echo "=== download progress ==="
tail -2 /dev/shm/dl.log
