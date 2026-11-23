set -u
# bracket trick: the pattern text itself will not match this bash -c cmdline
for p in $(pgrep -f 'pip insta[l]l' 2>/dev/null); do
  [ "$p" = "$$" ] && continue
  kill -9 "$p" 2>/dev/null || true
done
sleep 1

echo "=== verify downloaded files ==="
/root/miniconda3/bin/python - <<'PYEOF'
import json, os
man = json.load(open('/root/maira2_sizes.json'))
d = '/dev/shm/maira2'
bad = tot = 0
for p, s in sorted(man.items()):
    fp = os.path.join(d, p)
    if s == 0:
        continue
    tot += s
    if not os.path.exists(fp):
        print('MISSING', p); bad += 1; continue
    got = os.path.getsize(fp)
    if got != s:
        print(f'MISMATCH {p}: {got} != {s}'); bad += 1
print(f'big files ok={len([1 for p,s in man.items() if s>0])-bad}, bad={bad}, total={tot/1e9:.2f} GB')
small = [p for p, s in man.items() if s == 0]
print('small files present:', sum(1 for p in small if os.path.exists(os.path.join(d, p))), '/', len(small))
PYEOF

echo
echo "=== launch pip (detached) ==="
nohup /root/miniconda3/bin/pip install --no-input --progress-bar off \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  "transformers==4.47.1" accelerate sentencepiece pillow \
  < /dev/null > /dev/shm/pip2.log 2>&1 &
echo "launched"
sleep 3
tail -2 /dev/shm/pip2.log 2>/dev/null || true
