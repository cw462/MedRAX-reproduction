set -u
echo "=== persist MAIRA weights from shm to disk ==="
if [ -d /root/autodl-tmp/maira2 ]; then
  echo "already on disk, skipping copy"
else
  T0=$(date +%s)
  cp -a /dev/shm/maira2 /root/autodl-tmp/maira2
  echo "copied in $(( $(date +%s) - T0 ))s"
fi

echo
echo "=== verify persisted copy against manifest ==="
/root/miniconda3/bin/python - <<'PYEOF'
import json, os
man = json.load(open('/root/maira2_sizes.json'))
d = '/root/autodl-tmp/maira2'
bad = 0
tot = 0
for p, s in man.items():
    if s == 0:
        continue
    fp = os.path.join(d, p)
    tot += s
    if not os.path.exists(fp) or os.path.getsize(fp) != s:
        print('BAD', p, os.path.getsize(fp) if os.path.exists(fp) else 'missing', '!=', s)
        bad += 1
print(f'files checked, bad={bad}, total={tot/1e9:.2f} GB')
PYEOF

echo
echo "=== free the shm copy ==="
rm -rf /dev/shm/maira2
df -h /dev/shm | tail -1
df -h /root/autodl-tmp | tail -1

echo
echo "=== remove temporary deploy key ==="
rm -f /root/.ssh/medrax_deploy_key
ls -la /root/.ssh/ | grep -c medrax_deploy_key || echo "deploy key removed"
