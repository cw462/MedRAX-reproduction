set -u
PY=/root/miniconda3/bin/python
TAR=/root/.medrax-private-transfer/preserved-frozen-inputs/medrax_r55_top4_full848-frozen-inputs.tar
mkdir -p /dev/shm/frozen
tar -xf "$TAR" -C /dev/shm/frozen refs/chexbench 2>/dev/null
echo "=== ref files ==="
ls /dev/shm/frozen/refs/chexbench | wc -l
echo
echo "=== one ref file ==="
cat /dev/shm/frozen/refs/chexbench/chexbench_openi_0004.json 2>/dev/null | head -c 2000
echo
echo
$PY - <<'PYEOF'
import json, glob, collections
files = sorted(glob.glob('/dev/shm/frozen/refs/chexbench/*.json'))
print('ref files', len(files))
d = json.load(open(files[0], encoding='utf-8'))
print('keys', list(d.keys()) if isinstance(d, dict) else type(d))
PYEOF
