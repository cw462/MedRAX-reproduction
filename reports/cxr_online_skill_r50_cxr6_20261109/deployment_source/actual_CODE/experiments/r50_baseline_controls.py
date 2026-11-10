"""R50 baseline controls inherited uniformly; no old recovery registrations."""
import os
from pathlib import Path
import json
TOOLS=('medgemma','llava_rad','chest_xray_expert','llava_med_qa','xray_phrase_grounding','medvlm_r1')
def validate_runtime(runtime):
    if runtime['arms']['M']['tools']!=list(TOOLS):raise ValueError('exact_six_tool_menu_required')
    if set(runtime['tools'])!=set(TOOLS):raise ValueError('only_six_registered_tools_required')
    if any(v.get('gpu')!='1' for v in runtime['tools'].values()):raise ValueError('GPU1_only')
    device=json.loads((Path(__file__).resolve().parents[1]/'configs/cxr_vqa_tool_worker_gpu.json').read_text())
    if device.get('cuda_visible_devices')!='1':raise ValueError('new_CODE_worker_must_mask_GPU1')
    for name in ('CUDA_LAUNCH_BLOCKING','TORCH_SHOW_CPP_STACKTRACES'):os.environ.pop(name,None)
