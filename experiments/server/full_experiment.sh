#!/bin/bash
# Full seven-tool experiment: pool build, then R0/R1/R2/R3 on the same validation set.
# Every stage continues on failure and logs a marker; the report can quote partial state.
R=/home/imss/cw/MedRAX_reproduction_20261027
LOG="$R/logs/full_experiment.log"
L="$R/reports/api_budget_qwen_100cny_v8.json"
INHERIT="$R/reports/api_budget_qwen_100cny_v7.json"
TRAIN="$R/data/memory_v1/inputs/memory_train_subset_v1.jsonl"
VAL="$R/data/memory_v1/inputs/validation_subset_v2.jsonl"
POOL="$R/runs/memory_pool_v3/pool.json"
set +e
stage() { echo "=== $1 $(date +%H:%M:%S)" | tee -a "$LOG"; }
run() { LEDGER="$L" INHERIT="$INHERIT" CAP=1000000 bash "$R/code/run_arm.sh" "$@" >>"$LOG" 2>&1; echo "=== exit $? $* $(date +%H:%M:%S)" | tee -a "$LOG"; }

stage "pool train start"
cat /tmp/.qwen_key | LEDGER="$L" INHERIT="$INHERIT" CAP=1000000 \
  bash "$R/code/run_arm.sh" r0 "$TRAIN" train60_full_r0 60 0 '' '' 3 >>"$LOG" 2>&1
echo "=== pool train exit $? $(date +%H:%M:%S)" | tee -a "$LOG"

stage "pool score+compile"
cd "$R/code"
"$R/.venv/bin/python" "$R/code/experiments/score_memory_runs.py" \
  --run "$R/runs/train60_full_r0" --splits "$R/data/prepared_v2" \
  --labels "$R/data/prepared_v2/memory_train.labels.jsonl" \
  --outcomes "$R/runs/train60_full_r0_scored/outcomes.json" \
  --report "$R/runs/train60_full_r0_scored/score.json" --answer-key relaxed >>"$LOG" 2>&1
"$R/.venv/bin/python" -m memory_pipeline \
  --splits "$R/data/prepared_v2" \
  --exclusions "$R/data/audit_v3/leakage_exclusion_manifest.json" \
  --exclusions-sha256 665ee67f9fd62a8739997e48637a31771f0d76a8382dae53ed8ab0851e6b98c1 \
  --run "$R/runs/train60_full_r0" \
  --outcomes "$R/runs/train60_full_r0_scored/outcomes.json" \
  --output "$R/runs/memory_pool_v3" --pool-version 1 \
  --allow-image-integrity-skip >>"$LOG" 2>&1
echo "=== compile exit $? $(date +%H:%M:%S)" | tee -a "$LOG"
POOL_SHA=$("$R/.venv/bin/python" -c "import json;print(json.load(open('$R/runs/memory_pool_v3/compile_report.json'))['pool_sha256'])" 2>/dev/null)
echo "=== pool sha $POOL_SHA" | tee -a "$LOG"

for arm in r0 r1 r2 r3; do
  stage "$arm start"
  if [ "$arm" = "r0" ]; then
    cat /tmp/.qwen_key | LEDGER="$L" INHERIT="$INHERIT" CAP=1000000 \
      bash "$R/code/run_arm.sh" r0 "$VAL" "val29_full_$arm" 29 0 '' '' 3 >>"$LOG" 2>&1
  else
    cat /tmp/.qwen_key | LEDGER="$L" INHERIT="$INHERIT" CAP=1000000 \
      bash "$R/code/run_arm.sh" "$arm" "$VAL" "val29_full_$arm" 29 0 "$POOL" "$POOL_SHA" 3 >>"$LOG" 2>&1
  fi
  echo "=== $arm exit $? $(date +%H:%M:%S)" | tee -a "$LOG"
done

stage "score+compare"
for arm in r0 r1 r2 r3; do
  "$R/.venv/bin/python" "$R/code/experiments/score_memory_runs.py" \
    --run "$R/runs/val29_full_$arm" --splits "$R/data/prepared_v2" \
    --labels "$R/data/prepared_v2/validation.labels.jsonl" \
    --outcomes "$R/runs/val29_full_${arm}_scored/outcomes.json" \
    --report "$R/runs/val29_full_${arm}_scored/score.json" --expected-split validation >>"$LOG" 2>&1
done
for arm in r1 r2 r3; do
  "$R/.venv/bin/python" "$R/code/experiments/compare_memory_arms.py" \
    --baseline "$R/runs/val29_full_r0" --compare "$R/runs/val29_full_$arm" \
    --labels "$R/data/prepared_v2/validation.labels.jsonl" \
    --report "$R/runs/val29_full_comparison_$arm.json" >>"$LOG" 2>&1
done
echo "=== ALL DONE $(date +%H:%M:%S)" | tee -a "$LOG"
rm -f /tmp/.qwen_key
