set -u
pkill -f "pip install" 2>/dev/null; sleep 1
echo "=== pip config ==="
/root/miniconda3/bin/pip config list 2>&1 | head
cat /etc/pip.conf 2>/dev/null | head
cat /root/.pip/pip.conf 2>/dev/null | head
cat /root/.config/pip/pip.conf 2>/dev/null | head
echo
echo "=== index reachability ==="
curl -s -o /dev/null -w 'tuna:%{http_code} %{time_total}s\n' --max-time 15 https://pypi.tuna.tsinghua.edu.cn/simple/transformers/
echo
echo "=== install with visible log (max 300s) ==="
timeout 300 /root/miniconda3/bin/pip install --no-input --progress-bar off \
  -i https://pypi.tuna.tsinghua.edu.cn/simple "transformers==4.47.1" accelerate sentencepiece pillow \
  > /dev/shm/pip2.log 2>&1
rc=$?
echo "pip rc=$rc"
tail -25 /dev/shm/pip2.log
echo
/root/miniconda3/bin/python -c "import transformers; print('transformers', transformers.__version__)" 2>&1 | tail -2
