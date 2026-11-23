set -u
echo "=== phrase grounding section ==="
sed -n '/hrase grounding/,/^## /p' /dev/shm/maira2/README.md | head -60
echo
echo "=== code blocks in README ==="
awk '/```python/,/```/' /dev/shm/maira2/README.md | head -160
