set -u
export OUT=/dev/shm/maira_reports.json
nohup /root/miniconda3/bin/python -u /root/maira_report.py \
  < /dev/null > /dev/shm/maira_report.log 2>&1 &
echo launched
sleep 40
tail -4 /dev/shm/maira_report.log
