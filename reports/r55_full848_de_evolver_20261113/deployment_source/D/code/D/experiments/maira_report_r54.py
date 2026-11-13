"""Grounded findings via pinned existing MAIRA-2; only verified frontal CXR inputs.
Reference: https://huggingface.co/microsoft/maira-2 (reporting use case).
No synthetic history, options or label text is passed to the report generator.
"""
import json,math
from pathlib import Path

def normalize(parsed,processor,width,height):
    if not isinstance(parsed,(list,tuple)) or not parsed:raise ValueError('grounded_report_parse_failed')
    if len(parsed)==2 and isinstance(parsed[0],str):parsed=[parsed]
    out=[]
    for item in parsed:
        if not isinstance(item,(list,tuple)) or len(item)!=2 or not isinstance(item[0],str):raise ValueError('invalid_report_item')
        text,boxes=item;converted=[]
        for box in boxes or []:
            if len(box)!=4 or not all(math.isfinite(float(v)) for v in box):raise ValueError('invalid_report_box')
            if not (0<=box[0]<box[2]<=1 and 0<=box[1]<box[3]<=1):raise ValueError('invalid_report_box_order')
            orig=list(processor.adjust_box_for_original_image_size(box,width=width,height=height))
            if len(orig)!=4 or not all(math.isfinite(float(v)) and 0<=v<=1 for v in orig):raise ValueError('invalid_original_box')
            converted.append({'model_normalized':list(box),'original_normalized':orig,
                              'original_pixels':[orig[0]*width,orig[1]*height,orig[2]*width,orig[3]*height]})
        out.append({'finding':text,'boxes':converted})
    return out

def eligibility(req):
    # Reuse the declared original path and previously recorded asset identity.
    # No new image checksum/pixel audit is introduced by this interface.
    record=req['runtime'].get('r54_image_views_by_path',{}).get(str(Path(req['image']).resolve()),{})
    return record.get('modality')=='CXR' and record.get('view') in ('PA','AP','frontal'),record

def execute_report(req):
    if req['args']:raise ValueError('maira_report_accepts_empty_args_only')
    eligible,view=eligibility(req)
    if not eligible:
        result={'analysis_status':'not_applicable','reason':'Verified frontal CXR required; lateral-only, non-CXR and unknown views are not converted to frontal.', 'view_record':view}
        return result,result,[]
    from unittest.mock import patch
    import torch
    from PIL import Image,ImageDraw
    import maira_smoke as smoke
    from cxr_vqa_tool_worker import existing_snapshot
    cfg=req['runtime'];root=Path(cfg['root']);folder=Path(req['artifact_dir'])
    with patch.object(smoke.audit,'inspect_snapshot',existing_snapshot):
        tool,prov=smoke.create_maira_tool(root/cfg['tool_repo'],cache_dir=root/'models/hf_full/hub',temp_dir=folder/'maira_report_runtime',device='cuda:0')
    im=Image.open(req['image']).convert('RGB');proc=tool.processor;model=tool.model
    inputs=proc.format_and_preprocess_reporting_input(current_frontal=im,current_lateral=None,
        prior_frontal=None,indication=None,technique=None,comparison=None,prior_report=None,
        return_tensors='pt',get_grounding=True).to(model.device)
    # Align vision inputs with the existing quantized model's vision dtype.
    if 'pixel_values' in inputs:inputs['pixel_values']=inputs['pixel_values'].to(next(model.vision_tower.parameters()).dtype)
    eos=model.generation_config.eos_token_id
    if eos is None:eos=proc.tokenizer.eos_token_id
    with torch.inference_mode():
        generated=model.generate(**inputs,max_new_tokens=450,use_cache=True,do_sample=False,eos_token_id=eos)
    tokens=generated[0][inputs['input_ids'].shape[-1]:]
    decoded=proc.decode(tokens,skip_special_tokens=True).lstrip()
    # Preserve a completed generation even when the official parser later fails.
    from online_memory_r49 import save_once
    ids=tokens.detach().cpu().tolist()
    eos_ids=eos if isinstance(eos,(list,tuple)) else [eos]
    save_once(folder/'report_generation.json',{'token_ids':ids,'generated_tokens':len(ids),
        'max_new_tokens':450,'eos_token_ids':eos_ids,'ended_with_eos':bool(ids and ids[-1] in eos_ids),
        'reached_token_cap':len(ids)>=450,'decoded':decoded,'output_repaired':False})
    parsed=proc.convert_output_to_plaintext_or_grounded_sequence(decoded)
    findings=normalize(parsed,proc,*im.size)
    overlay=im.copy();draw=ImageDraw.Draw(overlay);count=0
    for i,f in enumerate(findings,1):
        for b in f['boxes']:
            draw.rectangle(b['original_pixels'],outline='red',width=3);draw.text(tuple(b['original_pixels'][:2]),str(i),fill='red');count+=1
    derived=[]
    if count:
        dest=folder/'grounded_report.png';overlay.save(dest);derived=[str(dest)]
    result={'analysis_status':'completed','findings':findings,'report':' '.join(f['finding'] for f in findings),
        'original_size':list(im.size),'view_record':view,'grounded_box_count':count,
        'generated_tokens':len(tokens),'reached_token_cap':len(tokens)>=450,
        'limitations':'Unverified findings; boxes are model outputs, not independent confirmation. No prior image or history supplied. Findings without boxes are retained.'}
    (folder/'report_provenance.json').write_text(json.dumps(prov,ensure_ascii=False,indent=2))
    return {'decoded':decoded,'parsed':parsed,'result':result},result,derived
