#!/bin/bash
R=/home/imss/cw/MedRAX_reproduction_20261027
date +%H:%M:%S
grep -E '^=== ' "$R/logs/full_experiment.log" | tail -8
for d in train60_full_r0 val29_full_r0 val29_full_r1 val29_full_r2 val29_full_r3; do
  n=$(grep -c terminal "$R/runs/$d/results.jsonl" 2>/dev/null || echo 0)
  echo "$d terminals=$n"
done
ps -eo pid,etime,args | grep '[m]emory_agent' | cut -c1-60
nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader
