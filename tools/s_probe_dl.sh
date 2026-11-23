set -u
echo "=== shm space ==="
df -h /dev/shm

echo
echo "=== modelscope file API probe (first shard, 64MB range) ==="
URL='https://modelscope.cn/api/v1/models/microsoft/maira-2/repo?Revision=master&FilePath=model-00001-of-00006.safetensors'
curl -sL --max-time 20 -o /dev/null -w 'http=%{http_code} size=%{size_download} speed=%{speed_download}B/s time=%{time_total}s\n' \
  -r 0-67108863 "$URL"

echo
echo "=== full small-file fetch (config.json) ==="
curl -sL --max-time 20 "$URL&FilePath=config.json" 2>/dev/null | head -c 300
curl -sL --max-time 20 "https://modelscope.cn/api/v1/models/microsoft/maira-2/repo?Revision=master&FilePath=config.json" | head -c 400
echo

echo
echo "=== existing key ==="
ls -la /root/.config/medrax-autodl-r55/ 2>/dev/null
head -c 12 /root/.config/medrax-autodl-r55/qwen37_workspace.key 2>/dev/null; echo " ...(len=$(wc -c < /root/.config/medrax-autodl-r55/qwen37_workspace.key 2>/dev/null))"

echo
echo "=== can we reach dashscope endpoint from box? ==="
curl -s -o /dev/null -w 'token-plan:%{http_code} in %{time_total}s\n' --max-time 15 https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/models
