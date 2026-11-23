set -u
PY=/root/miniconda3/bin/python

bench() {
  label="$1"; url="$2"; n="$3"; mb="$4"
  rm -rf /dev/shm/dltest; mkdir -p /dev/shm/dltest
  sz=$((mb*1048576)); chunk=$((sz/n))
  T0=$(date +%s.%N)
  for i in $(seq 0 $((n-1))); do
    S=$((i*chunk)); E=$((S+chunk-1))
    curl -sL --max-time 90 -r ${S}-${E} -o /dev/shm/dltest/p$i "$url" &
  done
  wait
  T1=$(date +%s.%N)
  BYTES=$(du -sb /dev/shm/dltest | cut -f1)
  $PY -c "import sys;t0,t1,b=map(float,sys.argv[1:4]);d=t1-t0;print(f'$label: {b/1e6:.1f} MB in {d:.1f}s -> {b/1e6/d:.2f} MB/s')" "$T0" "$T1" "$BYTES"
  rm -rf /dev/shm/dltest
}

MSURL='https://modelscope.cn/api/v1/models/microsoft/maira-2/repo?Revision=master&FilePath=model-00001-of-00006.safetensors'

echo "=== ModelScope, no turbo ==="
bench "MS 1x64MB" "$MSURL" 1 64
bench "MS 4x32MB" "$MSURL" 4 128
bench "MS 8x24MB" "$MSURL" 8 192

echo
echo "=== with network_turbo ==="
. /etc/network_turbo >/dev/null 2>&1
bench "MS 8x24MB turbo" "$MSURL" 8 192

echo
echo "=== HF small file speed (bert-base config? use safetensors of a public repo) ==="
HFURL='https://huggingface.co/microsoft/rad-dino/resolve/main/model.safetensors'
curl -sL --max-time 60 -r 0-33554431 -o /dev/null -w 'rad-dino 32MB: http=%{http_code} speed=%{speed_download}B/s\n' "$HFURL"
