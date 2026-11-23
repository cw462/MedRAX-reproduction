set -u
TAR=/root/.medrax-private-transfer/preserved-frozen-inputs/medrax_r55_top4_full848-frozen-inputs.tar
echo "=== entries total ==="
tar -tf "$TAR" | wc -l
echo
echo "=== non-image entries (first 40) ==="
tar -tf "$TAR" | grep -v '\.png$\|\.jpg$' | head -40
echo
echo "=== chexbench structure ==="
tar -tf "$TAR" | grep -i chexbench | grep -v '\.png$\|\.jpg$' | head -20
echo
echo "=== image path prefixes ==="
tar -tf "$TAR" | grep '\.png$\|\.jpg$' | sed 's#/[^/]*$##' | sort | uniq -c | sort -rn | head -10
