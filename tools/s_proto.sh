set -u
/root/miniconda3/bin/python -c "import google.protobuf as p; print('protobuf', p.__version__)" 2>&1 | tail -1
echo "=== upgrade protobuf ==="
/root/miniconda3/bin/pip install --no-input -q --progress-bar off \
  -i https://pypi.tuna.tsinghua.edu.cn/simple -U "protobuf>=7.36" 2>&1 | tail -5
/root/miniconda3/bin/python -c "import google.protobuf as p; print('protobuf now', p.__version__)" 2>&1 | tail -1
echo
echo "=== retry smoke ==="
nohup /root/miniconda3/bin/python -u /root/maira_ground.py \
  < /dev/null > /dev/shm/maira_smoke.log 2>&1 &
sleep 30
tail -6 /dev/shm/maira_smoke.log
