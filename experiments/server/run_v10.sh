#!/bin/bash
set -euo pipefail
R=/home/imss/cw/MedRAX_reproduction_20261027
cd "$R/code_v10"
export HF_HOME="$R/models/hf_full"
export HF_HUB_OFFLINE=1
export CUDA_VISIBLE_DEVICES=0,1
export LANGCHAIN_TRACING_V2=false
export LANGSMITH_TRACING=false
"$R/.venv/bin/python" -u experiments/run_v10_accuracy.py \
  --config configs/v10_accuracy60.json --out "$R/runs/v10_accuracy60" --api-key-stdin
# Reference labels are opened in a separate process only after full generation.
"$R/.venv/bin/python" -u experiments/v10_metrics.py \
  --run "$R/runs/v10_accuracy60" --labels "$R/data/prepared_v2/validation.labels.jsonl"
