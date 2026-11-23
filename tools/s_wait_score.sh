set -u
for i in $(seq 1 45); do
  pgrep -f 'maira_groun[d]' >/dev/null || break
  sleep 10
done
tail -3 /dev/shm/maira_smoke.log
echo "=== score ==="
/root/miniconda3/bin/python /root/score_maira_side.py
