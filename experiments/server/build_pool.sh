#!/bin/bash
# Score a completed training run, compile it and freeze the success pool.
#   build_pool.sh <run_name> <pool_output_name> [answer_key]
set -e
R=/home/imss/cw/MedRAX_reproduction_20261027
RUN=${1:?run}
POOL=${2:?pool}
KEY=${3:-relaxed}
EXC_SHA=665ee67f9fd62a8739997e48637a31771f0d76a8382dae53ed8ab0851e6b98c1
cd "$R/code"
"$R/.venv/bin/python" experiments/score_memory_runs.py \
  --run "$R/runs/$RUN" \
  --splits "$R/data/prepared_v2" \
  --labels "$R/data/prepared_v2/memory_train.labels.jsonl" \
  --outcomes "$R/runs/${RUN}_scored/outcomes.json" \
  --report "$R/runs/${RUN}_scored/score.json" \
  --answer-key "$KEY"
"$R/.venv/bin/python" -m memory_pipeline \
  --splits "$R/data/prepared_v2" \
  --exclusions "$R/data/audit_v3/leakage_exclusion_manifest.json" \
  --exclusions-sha256 "$EXC_SHA" \
  --run "$R/runs/$RUN" \
  --outcomes "$R/runs/${RUN}_scored/outcomes.json" \
  --output "$R/runs/$POOL" \
  --pool-version 1 \
  --allow-image-integrity-skip
