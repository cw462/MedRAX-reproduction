set -u
for i in $(seq 1 60); do
  pgrep -f 'maira_repor[t]' >/dev/null || break
  sleep 10
done
tail -2 /dev/shm/maira_report.log
echo "=== score ==="
/root/miniconda3/bin/python /root/score_maira_report.py
