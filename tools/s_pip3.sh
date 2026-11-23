set -u
for p in $(pgrep -f 'pip insta[l]l' 2>/dev/null); do [ "$p" = "$$" ] && continue; kill -9 "$p" 2>/dev/null || true; done
sleep 1
echo "=== install transformers 4.51.3 (detached) ==="
nohup /root/miniconda3/bin/pip install --no-input --progress-bar off \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  "transformers==4.51.3" accelerate sentencepiece pillow protobuf \
  < /dev/null > /dev/shm/pip3.log 2>&1 &
sleep 45
tail -5 /dev/shm/pip3.log
echo
echo "=== phrase grounding snippet ==="
grep -n "phrase" /dev/shm/maira2/README.md | head -20
