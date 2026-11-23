set -u
R=/root/autodl-tmp/medrax_m5_rrsi_acc_ttl_v4_20261119
echo "=== process-checks content type ==="
find "$R/process-checks" -type f | head -8
find "$R/process-checks" -type f | sed 's/.*\.//' | sort | uniq -c | sort -rn | head
echo
echo "=== evidence content type ==="
find "$R/evidence" -type f | head -6
find "$R/evidence" -type f | sed 's/.*\.//' | sort | uniq -c | sort -rn | head
echo
echo "=== top-level of run/code and source ==="
ls "$R/run/code" | head -10
echo "--- source ---"
ls "$R/source" | head -10
