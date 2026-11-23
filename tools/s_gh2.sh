set -u
cd /dev/shm/gh1
echo "=== ls ==="
ls -la | head -20
echo
echo "=== git status/branch ==="
git log --oneline -3
git branch -a
echo
echo "=== tree ==="
git ls-tree -r --name-only HEAD | head -40
echo "count: $(git ls-tree -r --name-only HEAD | wc -l)"
