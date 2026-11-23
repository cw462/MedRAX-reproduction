set -u
echo "=== network_turbo available? ==="
ls -la /etc/network_turbo 2>/dev/null || echo "no /etc/network_turbo"

echo
echo "=== parallel range test: 8 x 16MB ==="
URL='https://modelscope.cn/api/v1/models/microsoft/maira-2/repo?Revision=master&FilePath=model-00001-of-00006.safetensors'
rm -rf /dev/shm/dltest; mkdir -p /dev/shm/dltest
T0=$(date +%s.%N)
for i in 0 1 2 3 4 5 6 7; do
  S=$((i*16777216)); E=$((S+16777215))
  curl -sL --max-time 60 -r ${S}-${E} -o /dev/shm/dltest/p$i "$URL" &
done
wait
T1=$(date +%s.%N)
BYTES=$(du -sb /dev/shm/dltest | cut -f1)
python3 - "$T0" "$T1" "$BYTES" <<'EOF'
import sys
t0, t1, b = float(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])
d = t1 - t0
print(f"downloaded {b/1e6:.1f} MB in {d:.1f}s -> {b/1e6/d:.2f} MB/s aggregate")
EOF
rm -rf /dev/shm/dltest

echo
echo "=== try HF via network_turbo (if present) ==="
if [ -f /etc/network_turbo ]; then
  . /etc/network_turbo 2>/dev/null
  curl -s -o /dev/null -w 'hf:%{http_code}\n' --max-time 12 https://huggingface.co
fi

echo
echo "=== disk cleanup candidates (sizes only, nothing deleted) ==="
du -sh /root/autodl-tmp/medrax_m5_data_rsi_v2_20261117_plus 2>/dev/null
du -sh /root/autodl-tmp/medrax_m5_rrsi_acc_ttl_v4_20261119/gateway_audit 2>/dev/null
