set -u
echo "=== download ==="
tail -4 /dev/shm/dl.log
echo "--- files ---"
ls -la /dev/shm/maira2/ 2>/dev/null | head -12
du -sh /dev/shm/maira2
echo
echo "=== pip ==="
tail -3 /dev/shm/pip.log
/root/miniconda3/bin/python -c "import transformers; print('transformers', transformers.__version__)" 2>&1 | tail -2
