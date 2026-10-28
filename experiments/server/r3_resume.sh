#!/bin/bash
# Resume R3 after the accidental kill (same code, same pool, same ledger v5).
R=/home/imss/cw/MedRAX_reproduction_20261027
LOG="$R/logs/r3_resume.log"
set +e
echo "=== R3 resume start $(date +%H:%M:%S)" | tee -a "$LOG"
cat /tmp/.qwen_key | LEDGER="$R/reports/api_budget_qwen_100cny_v5.json" \
  INHERIT="$R/reports/api_budget_qwen_100cny_v4.json" CAP=100 \
  bash "$R/code/run_arm.sh" r3 "$R/data/memory_v1/inputs/validation_subset_v2.jsonl" \
  val29_r3_v1 29 0 "$R/runs/memory_pool_v1/pool.json" \
  806336106fa771dcc0e01db002d3e78cfd9aa428814cc670aeb04b0a3d754da3 3 --resume >>"$LOG" 2>&1
echo "=== R3 resume exit $? $(date +%H:%M:%S)" | tee -a "$LOG"
"$R/.venv/bin/python" "$R/code/experiments/score_memory_runs.py" \
  --run "$R/runs/val29_r3_v1" --splits "$R/data/prepared_v2" \
  --labels "$R/data/prepared_v2/validation.labels.jsonl" \
  --outcomes "$R/runs/val29_r3_v1_scored/outcomes.json" \
  --report "$R/runs/val29_r3_v1_scored/score.json" --expected-split validation >>"$LOG" 2>&1
"$R/.venv/bin/python" "$R/code/experiments/compare_memory_arms.py" \
  --baseline "$R/runs/val30_r0_v1" --compare "$R/runs/val29_r3_v1" \
  --labels "$R/data/prepared_v2/validation.labels.jsonl" \
  --report "$R/runs/val29_comparison_r3.json" >>"$LOG" 2>&1
echo "=== R3 flow done $(date +%H:%M:%S)" | tee -a "$LOG"
