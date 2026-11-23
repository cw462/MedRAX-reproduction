set -u
echo "=== report gen log ==="
tail -3 /dev/shm/maira_report.log 2>/dev/null
echo "--- running? ---"
pgrep -f 'maira_repor[t]' >/dev/null && echo RUNNING || echo NOT_RUNNING
echo "--- reports file ---"
ls -la /dev/shm/maira_reports.json 2>/dev/null
/root/miniconda3/bin/python -c "
import json
d=json.load(open('/dev/shm/maira_reports.json'))
print('images done', len(d))
bad=[k for k,v in d.items() if v.get('error')]
print('errors', len(bad))
if bad: print('sample err', d[bad[0]]['error'][:300])
" 2>&1 | tail -5
