#!/bin/bash
set -euo pipefail
R=/home/imss/cw/MedRAX_reproduction_20261027
cd "$R/code_v9"
export HF_HOME="$R/models/hf_full"
export HF_HUB_OFFLINE=1
export CUDA_VISIBLE_DEVICES=0,1
export LANGCHAIN_TRACING_V2=false
export LANGSMITH_TRACING=false
"$R/.venv/bin/python" -u experiments/run_v9_diagnostic.py \
  --config configs/v9_diagnostic20.json --out "$R/runs/v9_diagnostic20" --api-key-stdin
# Evaluation is a separate process, after generation has closed its API client and ledger.
"$R/.venv/bin/python" -u experiments/v9_metrics.py \
  --run "$R/runs/v9_diagnostic20" --labels "$R/data/prepared_v2/validation.labels.jsonl"
