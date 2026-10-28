#!/bin/bash
# Fetch every model weight the seven-tool run needs, through hf-mirror.com.
# Weights are large (~34 GB); they are not part of the migration archive.
R=/home/imss/cw/MedRAX_reproduction_20261027
export HF_HOME="$R/models/hf_full"
export HF_ENDPOINT="https://hf-mirror.com"
mkdir -p "$HF_HOME"
"$R/.venv/bin/python" -u - <<'PY'
import os
from pathlib import Path
from huggingface_hub import snapshot_download

REPOS = [
    "StanfordAIMI/CheXagent-2-3b",
    "StanfordAIMI/XraySigLIP__vit-l-16-siglip-384__webli",
    "microsoft/llava-med-v1.5-mistral-7b",
    "openai/clip-vit-large-patch14-336",
]
for repo in REPOS:
    print("===", repo, flush=True)
    for attempt in range(1, 4):
        try:
            path = snapshot_download(repo, max_workers=4,
                                     ignore_patterns=["*.md", "*.png", "*.jpg", "*.gif"])
            size = sum(f.stat().st_size for f in Path(path).rglob("*") if f.is_file())
            print(f"ok {repo} {size/1e9:.1f} GB", flush=True)
            break
        except Exception as exc:  # noqa: BLE001
            print(f"attempt {attempt} failed {type(exc).__name__}: {str(exc)[:160]}", flush=True)
print("done", flush=True)
PY
