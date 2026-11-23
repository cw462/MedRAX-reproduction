set -u
echo "=== SECURITY: authorized_keys2 (42B, mode 755, mtime today 15:54) ==="
cat -A /root/.ssh/authorized_keys2 2>/dev/null
echo
echo "=== authorized_keys comments ==="
awk '{print $1, substr($2,1,20)"...", $3}' /root/.ssh/authorized_keys 2>/dev/null
echo
echo "=== image counts ==="
for d in /root/autodl-tmp/medrax_m5_data_rsi_8tools_300_20261118_plus/artifacts/images/*/; do
  echo "$(find "$d" -type f | wc -l)	$d"
done
echo "--- sample names ---"
ls /root/autodl-tmp/medrax_m5_data_rsi_8tools_300_20261118_plus/artifacts/images/openi | head -3
ls /root/autodl-tmp/medrax_m5_data_rsi_8tools_300_20261118_plus/artifacts/images/slake | head -3
ls /root/autodl-tmp/medrax_m5_data_rsi_8tools_300_20261118_plus/artifacts/images/vqarad | head -3

echo
echo "=== M5 traces ==="
find /root/.medrax-private-transfer/r55_autodl_qwen_8tools_20261116_001 -maxdepth 3 -type f | head -20
find /root/.medrax-private-transfer/r55_autodl_qwen_8tools_20261116_001 -type f | wc -l
du -sh /root/.medrax-private-transfer

echo
echo "=== preserved frozen inputs ==="
tar -tf /root/.medrax-private-transfer/preserved-frozen-inputs/medrax_r55_top4_full848-frozen-inputs.tar 2>/dev/null | head -15
du -sh /root/.medrax-private-transfer/preserved-frozen-inputs/*.tar

echo
echo "=== disk again ==="
df -h / /root/autodl-tmp | tail -3
