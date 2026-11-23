set -u
R=/root/autodl-tmp/medrax_m5_rrsi_acc_ttl_v4_20261119
T=$R/m5_rrsi_dev50_val100_test848_v5

echo "=== before ==="
df -h /root/autodl-tmp | tail -1

# explicit list, no globs; every path must sit under autodl-tmp and must not be images
DROP="
$R/run/search
$R/run/runtime_audit
$R/run_parallel_20261120/search
$R/run_parallel_20261120/runtime_audit
$R/v6_pilot_20261120/validation100
$R/v6_pilot_20261120/events
$R/v6_pilot_20261120/gateway_audit
$R/gateway_audit
$R/cpu-rootfs
$R/cpu-rootfs002
$T/dev
$T/interim_validation
"

freed=0
for p in $DROP; do
  case "$p" in
    /root/autodl-tmp/*) ;;
    *) echo "REFUSE (outside autodl-tmp): $p"; continue ;;
  esac
  case "$p" in
    *artifacts/images*|*data_rsi_v2*) echo "REFUSE (protected): $p"; continue ;;
  esac
  if [ -d "$p" ]; then
    sz=$(du -sm "$p" 2>/dev/null | cut -f1)
    echo "rm -rf $p  (${sz} MB)"
    rm -rf "$p"
    freed=$((freed + ${sz:-0}))
  else
    echo "skip (absent): $p"
  fi
done

echo
echo "freed approx: ${freed} MB"
echo
echo "=== after ==="
df -h / | tail -1
df -h /root/autodl-tmp | tail -1
echo
echo "=== protected assets still present ==="
du -sh /root/autodl-tmp/medrax_m5_data_rsi_8tools_300_20261118_plus/artifacts/images 2>/dev/null
find /root/autodl-tmp/medrax_m5_data_rsi_8tools_300_20261118_plus/artifacts/images -type f | wc -l
ls /root/autodl-tmp/ 2>/dev/null
