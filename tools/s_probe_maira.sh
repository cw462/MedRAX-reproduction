set -u
echo "=== API keys on box? ==="
find /root -maxdepth 4 -type f \( -name '*.key' -o -name '*api*key*' -o -name '.env' \) 2>/dev/null | grep -v autodl-tmp/medrax_m5_rrsi | head -20
grep -rl "token-plan\|DASHSCOPE\|dashscope" /root/.bashrc /root/.config 2>/dev/null | head

echo
echo "=== big dirs: what's inside ==="
for d in v6_pilot_20261120 run run_parallel_20261120; do
  p=/root/autodl-tmp/medrax_m5_rrsi_acc_ttl_v4_20261119/$d
  echo "--- $p ---"
  du -sh "$p"/* 2>/dev/null | sort -h | tail -6
done

echo
echo "=== test848 19G breakdown ==="
du -sh /root/autodl-tmp/medrax_m5_rrsi_acc_ttl_v4_20261119/m5_rrsi_dev50_val100_test848_v5/* 2>/dev/null | sort -h

echo
echo "=== modelscope search: maira ==="
curl -s --max-time 20 -X POST 'https://modelscope.cn/api/v1/dolphin/models' \
  -H 'Content-Type: application/json' \
  -d '{"PageSize":20,"PageNumber":1,"Name":"maira","SortBy":"Default"}' | head -c 3000
echo

echo
echo "=== pip: transformers/accelerate ==="
/root/miniconda3/bin/python -c "import transformers, torch; print('transformers', transformers.__version__); print('torch', torch.__version__, torch.cuda.is_available())" 2>&1
