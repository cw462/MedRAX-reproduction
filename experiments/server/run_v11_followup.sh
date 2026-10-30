#!/bin/bash
set -euo pipefail
R=/home/imss/cw/MedRAX_reproduction_20261027
cd "$R/code_v11"
export HF_HOME="$R/models/hf_full"
export HF_HUB_OFFLINE=1
export LANGCHAIN_TRACING_V2=false
export LANGSMITH_TRACING=false
"$R/.venv/bin/python" -u experiments/run_v11_followup.py \
  --config configs/v11_followup60.json --out "$R/runs/v11_followup60" --api-key-stdin
"$R/.venv/bin/python" -u experiments/v11_metrics.py \
  --run "$R/runs/v11_followup60" --source-run "$R/runs/v10_accuracy60" \
  --previous-run "$R/runs/v11_selector60" --labels "$R/data/prepared_v2/validation.labels.jsonl"
