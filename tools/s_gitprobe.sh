set -u
echo "=== git on box? ==="
command -v git || echo "no git"
echo
echo "=== ssh keys for github ==="
ls -la /root/.ssh/
grep -l "github" /root/.ssh/config 2>/dev/null || echo "no ssh config"
echo
echo "=== does the box have a clone of the repo? ==="
find / -maxdepth 6 -type d -name "MedRAX-reproduction*" 2>/dev/null | head -5
echo
echo "=== RRSI dirs and their git state ==="
for d in /root/autodl-tmp/medrax_m5_rrsi_acc_ttl_v4_20261119 /root/autodl-tmp/medrax_m5_data_rsi_8tools_300_20261118_plus; do
  echo "--- $d"
  ls -a "$d" | head -12
  [ -d "$d/.git" ] && (cd "$d" && git remote -v 2>/dev/null | head -2 && git log --oneline -3 2>/dev/null) || echo "  (no .git)"
done
echo
echo "=== github reachable with turbo? ==="
. /etc/network_turbo >/dev/null 2>&1
curl -s -o /dev/null -w 'github:%{http_code}\n' --max-time 15 https://github.com
curl -s -o /dev/null -w 'raw:%{http_code}\n' --max-time 15 https://raw.githubusercontent.com
