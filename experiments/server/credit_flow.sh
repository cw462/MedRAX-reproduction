#!/bin/bash
# R4 counterfactual memory credit: three paired replays of the frozen R3 arm.
# Each arm drops one retrieval rank for every validation question, so the whole
# measurement costs 3 tool-loads instead of 87 process starts.
# Usage: bash credit_flow.sh
set -e
R=/home/imss/cw/MedRAX_reproduction_20261027
VAL="$R/data/memory_v1/inputs/validation_subset_v2.jsonl"
POOL="$R/runs/memory_pool_v3/pool.json"
POOL_SHA=2eba53f789ea3c175e18c41f2a842c0a6dba4d3d5e73397e9d4174497a2e4644
L="$R/reports/api_budget_qwen_100cny_v8.json"
INHERIT="$R/reports/api_budget_qwen_100cny_v7.json"
LOG="$R/logs/credit_flow.log"
cd "$R/code" || exit 1

echo "=== credit flow start $(date +%F' '%T) ===" | tee -a "$LOG"
[ -s /tmp/.qwen_key ] || { echo "no api key staged"; exit 1; }

for rank in 1 2 3; do
  out="credit_r3_drop${rank}"
  echo "=== drop rank $rank start $(date +%T) ===" | tee -a "$LOG"
  if [ ! -f "$R/runs/$out/summary.json" ]; then
    cat /tmp/.qwen_key | LEDGER="$L" INHERIT="$INHERIT" CAP=1000000 \
      bash "$R/code/run_arm.sh" r3 "$VAL" "$out" 29 0 "$POOL" "$POOL_SHA" 3 \
      --drop-memory-rank "$rank" >>"$LOG" 2>&1
  fi
  echo "=== drop rank $rank done $(date +%T) ===" | tee -a "$LOG"
  "$R/.venv/bin/python" "$R/code/experiments/score_memory_runs.py" \
    --run "$R/runs/$out" --splits "$R/data/prepared_v2" \
    --labels "$R/data/prepared_v2/validation.labels.jsonl" \
    --outcomes "$R/runs/${out}_scored/outcomes.json" \
    --report "$R/runs/${out}_scored/score.json" \
    --expected-split validation >>"$LOG" 2>&1
  echo "=== scored $rank $(date +%T) ===" | tee -a "$LOG"
done

"$R/.venv/bin/python" "$R/code/experiments/memory_credit.py" \
  --reference "$R/runs/val29_full_r3" \
  --ablation "$R/runs/credit_r3_drop1" \
  --ablation "$R/runs/credit_r3_drop2" \
  --ablation "$R/runs/credit_r3_drop3" \
  --report "$R/runs/memory_credit_r3.json" 2>&1 | tee -a "$LOG"
echo "=== ALL DONE $(date +%F' '%T) ===" | tee -a "$LOG"
