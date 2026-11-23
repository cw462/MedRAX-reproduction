set -u
PY=/root/miniconda3/bin/python
TAR=/root/.medrax-private-transfer/preserved-frozen-inputs/medrax_r55_top4_full848-frozen-inputs.tar
echo "=== extract chexbench images ==="
tar -xf "$TAR" -C /dev/shm/frozen data/chexbench/images 2>/dev/null
find /dev/shm/frozen/data/chexbench/images -type f | wc -l
du -sh /dev/shm/frozen/data/chexbench/images
echo
echo "=== build tasks ==="
$PY /root/mk_tasks_maira.py
