set -u
echo "=== pip progress ==="
tail -4 /dev/shm/pip2.log
/root/miniconda3/bin/python -c "import transformers; print('OK transformers', transformers.__version__)" 2>&1 | tail -1
echo
echo "=== maira2 files ==="
ls /dev/shm/maira2/
echo
echo "=== README (model card) ==="
head -c 4000 /dev/shm/maira2/README.md 2>/dev/null
