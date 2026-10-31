#!/bin/bash
set -euo pipefail
R=/home/imss/cw/MedRAX_reproduction_20261027
cd "$R/code_v12"
export HF_HOME="$R/models/hf_full"
export HF_HUB_OFFLINE=1
export CUDA_VISIBLE_DEVICES=0,1
export LANGCHAIN_TRACING_V2=false
export LANGSMITH_TRACING=false
"$R/.venv/bin/python" -u experiments/run_v12_resume.py \
  --config configs/v12_ab60.json --out "$R/runs/v12_ab60" --api-key-stdin
"$R/.venv/bin/python" -u experiments/v12_metrics.py \
  --run "$R/runs/v12_ab60" --labels "$R/data/prepared_v2/validation.labels.jsonl" \
  --v10-run "$R/runs/v10_accuracy60"
