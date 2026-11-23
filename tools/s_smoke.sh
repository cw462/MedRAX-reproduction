set -u
export LIMIT=8
export OUT=/dev/shm/maira_smoke.json
nohup /root/miniconda3/bin/python -u /root/maira_ground.py \
  < /dev/null > /dev/shm/maira_smoke.log 2>&1 &
echo "launched"
sleep 20
tail -5 /dev/shm/maira_smoke.log
