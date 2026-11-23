set -u
echo "=== README lines 120-240 ==="
sed -n '120,240p' /dev/shm/maira2/README.md
echo
echo "=== processor methods ==="
grep -n "def format_and_preprocess\|def postprocess\|def __call__" /dev/shm/maira2/processing_maira2.py
