set -u
echo "=== model cache tree (depth 3) ==="
du -sh /root/medrax_r55_top4_model_cache/* 2>/dev/null
find /root/medrax_r55_top4_model_cache -maxdepth 3 -type d 2>/dev/null | head -40

echo
echo "=== any safetensors/bin in cache ==="
find /root/medrax_r55_top4_model_cache -type f \( -name '*.safetensors' -o -name '*.bin' -o -name '*.json' \) 2>/dev/null | head -30
find /root/medrax_r55_top4_model_cache -type f 2>/dev/null | wc -l

echo
echo "=== images dir sample ==="
ls /root/autodl-tmp/medrax_m5_data_rsi_8tools_300_20261118_plus/artifacts/images | head -5
ls /root/autodl-tmp/medrax_m5_data_rsi_8tools_300_20261118_plus/artifacts/images | wc -l

echo
echo "=== test848/data ==="
find /root/autodl-tmp/medrax_m5_rrsi_acc_ttl_v4_20261119/m5_rrsi_dev50_val100_test848_v5/data -maxdepth 3 | head -20

echo
echo "=== .medrax-private-transfer ==="
find /root/.medrax-private-transfer -maxdepth 3 2>/dev/null | head -20

echo
echo "=== ssh keys on box ==="
ls -la /root/.ssh/ 2>/dev/null
