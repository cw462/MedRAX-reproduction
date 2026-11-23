"""Original MAIRA phrase invocation with existing 300-token EOS policy and raw capture.

The caller enforces the image-only frontal gate. No generation retry, parser
fallback, output truncation/repair or additional model image is permitted.
"""
import json
from pathlib import Path
from maira_capture_r54 import capture_tool
from maira_eos_guard_r54 import install_eos_guard
from online_memory_r49 import save_once

def execute_phrase(req):
    from unittest.mock import patch
    import maira_smoke as smoke
    from cxr_vqa_tool_worker import existing_snapshot
    from cxr_image_memory_r44 import tool_failure_reason
    from tool_worker_r54 import serial
    cfg=req['runtime'];root=Path(cfg['root']);folder=Path(req['artifact_dir'])
    with patch.object(smoke.audit,'inspect_snapshot',existing_snapshot):
        tool,provenance=smoke.create_maira_tool(root/cfg['tool_repo'],cache_dir=root/'models/hf_full/hub',
            temp_dir=folder/'maira_runtime',device='cuda:0')
    captures={'generations':[],'decodes':[],'conversion_inputs':[],'swallowed_exceptions':[],'observability_errors':[]}
    policy={};raw=None
    try:
        with capture_tool(tool,captures),install_eos_guard(tool,policy):
            raw=tool.invoke({'image_path':req['image'],'phrase':req['args'].get('phrase','lung opacity')})
    finally:
        # Complete generation/decode/parser evidence survives even if the official parser fails.
        for name,value in (('phrase_generation_tokens.json',captures['generations']),('phrase_decode.json',captures['decodes']),
            ('phrase_conversion_inputs.json',captures['conversion_inputs']),('phrase_parser_exceptions.json',captures['swallowed_exceptions']),
            ('phrase_observability_errors.json',captures['observability_errors']),('phrase_eos_guard.json',policy),('phrase_provenance.json',provenance)):
            save_once(folder/name,value)
    original=serial(raw,folder);save_once(folder/'phrase_original_result.json',original)
    generations=captures['generations']
    ids=generations[0].get('generated_token_ids') if len(generations)==1 else None
    eos=bool(ids and len(ids)==1 and ids[0] and ids[0][-1]==2)
    complete=(len(generations)==len(captures['decodes'])==len(captures['conversion_inputs'])==1 and
        not captures['observability_errors'] and len(policy.get('calls',[]))==1)
    failure=tool_failure_reason({'status':'completed','observation':original})
    status={'policy_id':policy.get('policy_id'),'status':'completed_healthy' if complete and eos and not failure else 'failed',
        'capture_complete':complete,'eos_terminated':eos,'generated_tokens':len(ids[0]) if ids else None,
        'max_new_tokens':300,'source_failure':failure,'output_repaired':False,'backend_regenerated':False,
        'parser_changed':False,'inserted_tokens':0}
    save_once(folder/'phrase_policy_status.json',status)
    if not complete or not eos or failure:raise RuntimeError('r54_phrase_incomplete_or_non_eos_or_original_failure')
    return raw,original,[]
