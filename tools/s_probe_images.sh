set -u
echo "=== dirs named image/img/maira under autodl-tmp (depth<=5) ==="
find /root/autodl-tmp -maxdepth 5 -type d \( -iname '*image*' -o -iname '*img*' -o -iname '*maira*' \) 2>/dev/null | head -30

echo
echo "=== png/jpg count per top-level dir (depth<=4) ==="
for d in /root/autodl-tmp/*/; do
  n=$(find "$d" -maxdepth 4 -type f \( -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' \) 2>/dev/null | wc -l)
  echo "$n	$d"
done

echo
echo "=== system disk images ==="
find /root -maxdepth 3 -type d \( -iname '*image*' -o -iname '*img*' \) -not -path '/root/autodl-tmp/*' 2>/dev/null | head -20

echo
echo "=== test848 dir listing ==="
ls -la /root/autodl-tmp/medrax_m5_rrsi_acc_ttl_v4_20261119/m5_rrsi_dev50_val100_test848_v5 2>/dev/null | head -20

echo
echo "=== /root listing ==="
ls -la /root/ | head -30

echo
echo "=== any jsonl/json mentioning 848 or slake/vqarad ==="
find /root/autodl-tmp -maxdepth 4 -type f \( -name '*848*' -o -name '*slake*' -o -name '*vqarad*' -o -name '*chexbench*' \) 2>/dev/null | head -20
