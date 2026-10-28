#!/bin/bash
# Plan-only with the full seven-tool registry (loads every model, no API call).
set -e
R=/home/imss/cw/MedRAX_reproduction_20261027
cd "$R/code"
export HOME="$R/models/home"
export HF_HOME="$R/models/hf_full"
export HF_HUB_OFFLINE=1
unset CUDA_VISIBLE_DEVICES
cat /tmp/.qwen_key | "$R/.venv/bin/python" -u experiments/memory_agent_eval.py \
  --repo "$R/source/MedRAX" \
  --input "$R/data/memory_v1/inputs/memory_train_subset_v1.jsonl" \
  --images-root "$R/data/memory_v1/images" \
  --output "$R/runs/plan_full" \
  --ledger "$R/reports/api_budget_qwen_100cny_v7.json" \
  --inherit-ledger "$R/reports/api_budget_qwen_100cny_v6.json" \
  --cap-cny 1000000 \
  --profile qwen3-vl-plus --arm r0 --plan-only \
  --classifier-checkpoint "$R/models/home/.torchxrayvision/models_data/nih-pc-chex-mimic_ch-google-openi-kaggle-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt" \
  --report-cache "$R/models/hf_report" \
  --segmentation-checkpoint "$R/models/home/.torchxrayvision/models_data/pspnet_chestxray_best_model_4.pth" \
  --max-cases 60 --max-tool-calls 4 --max-model-calls 6 --max-output-tokens 1024 \
  --api-key-stdin
