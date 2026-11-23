set -u
echo "=== pip process ==="
pgrep -af "pip install" | head -5 || echo "no pip running"
echo "--- pip.log size/content ---"
ls -la /dev/shm/pip.log 2>/dev/null
cat /dev/shm/pip.log 2>/dev/null | tail -20
echo
echo "=== pip version ==="
/root/miniconda3/bin/pip --version 2>&1
echo
echo "=== retry install (foreground, verbose tail) ==="
timeout 240 /root/miniconda3/bin/pip install -q -i https://pypi.tuna.tsinghua.edu.cn/simple "transformers==4.47.1" accelerate sentencepiece pillow 2>&1 | tail -15
echo "exit=$?"
/root/miniconda3/bin/python -c "import transformers, accelerate; print('transformers', transformers.__version__, '| accelerate', accelerate.__version__)" 2>&1 | tail -2
