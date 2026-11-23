set -u
# kill only real pip processes (this script's own cmdline does not contain the pattern)
for p in $(pgrep -f '/root/miniconda3/bin/pip install' 2>/dev/null); do kill -9 "$p" 2>/dev/null; done
sleep 1

echo "=== verify downloaded shards ==="
/root/miniconda3/bin/python - <<'EOF'
import json, os
man = json.load(open('/root/maira2_sizes.json'))
d = '/dev/shm/maira2'
bad = 0
for p, s in sorted(man.items()):
    fp = os.path.join(d, p)
    if s == 0:
        continue
    if not os.path.exists(fp):
        print('MISSING', p); bad += 1; continue
    got = os.path.getsize(fp)
    if got != s:
        print(f'MISMATCH {p}: {got} != {s}'); bad += 1
print('bad files:', bad)
print('small files present:', sum(1 for p, s in man.items() if s == 0 and os.path.exists(os.path.join(d, p))))
EOF

echo
echo "=== launch pip in background ==="
nohup /root/miniconda3/bin/pip install --no-input --progress-bar off \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  "transformers==4.47.1" accelerate sentencepiece pillow \
  < /dev/null > /dev/shm/pip2.log 2>&1 &
echo "launched pid $!"
