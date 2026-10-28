#!/bin/bash
# One reproducible memory-agent arm (full seven-tool registry).
#   run_arm.sh <arm> <input.jsonl> <output_name> <max_cases> <gpu> [pool] [pool_sha] [top_k] [extra...]
set -e
R=/home/imss/cw/MedRAX_reproduction_20261027
ARM=${1:?arm}
INPUT=${2:?input}
OUT=${3:?output}
N=${4:-60}
GPU=${5:-0}
POOL=${6:-}
POOL_SHA=${7:-}
TOP_K=${8:-3}
shift 8
EXTRA=("$@")
cd "$R/code"
export HOME="$R/models/home"
export HF_HOME="$R/models/hf_full"
export HF_HUB_OFFLINE=1
export CUDA_VISIBLE_DEVICES="0,1"   # both cards: LLaVA is pinned to cuda:0 by its own code, VQA runs on cuda:1
export LANGCHAIN_TRACING_V2=false
export LANGSMITH_TRACING=false
ARGS=()
if [ -n "$POOL" ]; then
  ARGS+=(--pool "$POOL" --pool-sha256 "$POOL_SHA" --top-k "$TOP_K")
fi
LEDGER=${LEDGER:-$R/reports/api_budget_qwen_100cny.json}
INHERIT=${INHERIT:-$R/reports/api_budget_100cny.json}
CAP=${CAP:-1000000}
MAX_TOOL=${MAX_TOOL:-4}
MAX_MODEL=${MAX_MODEL:-6}
SEG=${SEG:-$R/models/home/.torchxrayvision/models_data/pspnet_chestxray_best_model_4.pth}
"$R/.venv/bin/python" -u experiments/memory_agent_eval.py \
  --repo "$R/source/MedRAX" \
  --input "$INPUT" \
  --images-root "$R/data/memory_v1/images" \
  --output "$R/runs/$OUT" \
  --ledger "$LEDGER" \
  --inherit-ledger "$INHERIT" \
  --cap-cny "$CAP" \
  --profile qwen3-vl-plus --arm "$ARM" \
  --classifier-checkpoint "$R/models/home/.torchxrayvision/models_data/nih-pc-chex-mimic_ch-google-openi-kaggle-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt" \
  --report-cache "$R/models/hf_report" \
  --segmentation-checkpoint "$SEG" \
  --max-cases "$N" --max-tool-calls "$MAX_TOOL" --max-model-calls "$MAX_MODEL" \
  --max-output-tokens 1024 \
  --device cuda:0 --api-key-stdin "${ARGS[@]}" "${EXTRA[@]}"
