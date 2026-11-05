"""A single real local backend in its existing interpreter; no paid tool API."""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time


def serial(value, folder, name='raw'):
    import numpy as np
    if isinstance(value, np.ndarray):
        path=folder/(name+'.npy');np.save(path,value)
        return {'array_file':str(path),'shape':list(value.shape),'dtype':str(value.dtype)}
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,dict):return {str(k):serial(v,folder,name+'_'+str(k)) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [serial(v,folder,name+'_'+str(i)) for i,v in enumerate(value)]
    if isinstance(value,Path):return str(value)
    if value is None or isinstance(value,(str,int,float,bool)):return value
    return str(value)


def execute(req):
    cfg=req['runtime'];root=Path(cfg['root']);repo=root/cfg['tool_repo'];cache=root/'models/hf_full'
    folder=Path(req['artifact_dir']);folder.mkdir(parents=True,exist_ok=True)
    name=req['backend'];args=dict(req['args']);image=Path(req['image']);start=time.monotonic()
    # Paths always come from the bound executor; the model cannot open arbitrary files.
    if set(args)&{'image','image_path','image_paths','path','output','output_path'}:raise ValueError('model_paths_forbidden')
    raw=None;observation=None;derived=[]
    if name=='roi_crop':
        from PIL import Image
        box=args.get('box')
        if not isinstance(box,list) or len(box)!=4 or any(type(v) not in (float,int) for v in box):raise ValueError('normalized_box_required')
        x0,y0,x1,y1=box
        if not (0<=x0<x1<=1 and 0<=y0<y1<=1):raise ValueError('invalid_box')
        im=Image.open(image);w,h=im.size;pixel=[round(x0*w),round(y0*h),round(x1*w),round(y1*h)]
        crop=im.crop(pixel);crop=crop.resize((crop.width*2,crop.height*2));dest=folder/'crop.png';crop.save(dest)
        raw=observation={'original_size':[w,h],'normalized_box':box,'original_pixel_box':pixel,'zoom':2,'crop_size':list(crop.size),'coordinates':'origin top-left; x right, y down; original retained'};derived=[str(dest)]
    elif name in ['chest_xray_classifier','chest_xray_report_generator','chest_xray_segmentation','image_visualizer','dicom_processor']:
        from tool_registry_ext import build_tools
        from build_case_tool_evidence import CLASSIFIER_FILENAME
        tools,prov=build_tools(repo,cache_dir=cache,classifier_checkpoint=root/'models/home/.torchxrayvision/models_data'/CLASSIFIER_FILENAME,
            report_cache=root/'models/hf_report',segmentation_checkpoint=root/'models/home/.torchxrayvision/models_data/pspnet_chestxray_best_model_4.pth',
            temp_dir=folder/'runtime',tools=[name],device_main='cuda:0')
        tool=tools[name]
        raw=tool.invoke(dict(args,image_path=str(image)))
        observation=serial(raw,folder)
        (folder/'provenance.json').write_text(json.dumps(prov,ensure_ascii=False,indent=2),encoding='utf-8')
        if name=='chest_xray_classifier':observation={'finding_scores':observation[0],'limitations':'Operating-point normalized finding scores, not calibrated disease probabilities, severity, localization or temporal change.'}
        elif name=='chest_xray_report_generator':observation={'report':observation[0],'limitations':'Unverified single-image report; interval statements have no prior-image evidence.'}
    elif name=='llava_med_qa':
        from llava_smoke import create_llava_tool
        tool,prov=create_llava_tool(repo,cache_dir=cache,device='cuda:0')
        raw=tool.invoke({'question':args.get('question','Describe the visible findings.'),'image_path':str(image)})
        observation=serial(raw,folder)
        (folder/'provenance.json').write_text(json.dumps(prov,ensure_ascii=False,indent=2),encoding='utf-8')
    elif name=='chest_xray_expert':
        import chexagent_smoke as smoke
        audit={'loader_calls':[],'generate_calls':0,'visual_forward_calls':0}
        raw=smoke.execute_tool(repo,Path(cfg['chexagent_snapshot']),Path(cfg['vision_snapshot']),image,
                               args.get('question','Describe the visible findings.'),512,'cuda:0',audit)
        observation=serial(raw,folder)
        (folder/'provenance.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    elif name=='xray_phrase_grounding':
        from maira_smoke import create_maira_tool
        tool,prov=create_maira_tool(repo,cache_dir=cache,temp_dir=folder/'maira_runtime',device='cuda:0')
        raw=tool.invoke({'image_path':str(image),'phrase':args.get('phrase','lung opacity')})
        observation=serial(raw,folder)
        (folder/'provenance.json').write_text(json.dumps(prov,ensure_ascii=False,indent=2),encoding='utf-8')
    elif name in ['region_parse','view_check','measurement','evidence_lookup','medvlm_r1','llava_rad','medgemma']:
        from cxr_vqa_extended_backends import execute_extended
        raw,observation,derived=execute_extended(req)
    else:raise ValueError('unknown_backend')
    (folder/'raw.json').write_text(json.dumps(serial(raw,folder),ensure_ascii=False,indent=2),encoding='utf-8')
    return {'status':'completed','observation':observation,'derived_images':derived,'backend_compute_seconds':time.monotonic()-start,
            'original_image':str(image),'raw_result_file':str(folder/'raw.json'),'clinical_correctness_verified':False}


if __name__=='__main__':
    req=json.load(sys.stdin)
    with contextlib.redirect_stdout(sys.stderr):
        try:result=execute(req)
        except Exception as exc:
            import traceback;traceback.print_exc();raise
    print('CXR_VQA_RESULT='+json.dumps(result,ensure_ascii=False))
