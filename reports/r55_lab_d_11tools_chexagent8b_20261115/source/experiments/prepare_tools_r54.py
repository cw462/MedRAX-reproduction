"""Create an isolated R54 private runtime from the actual R49 config and deployed extended-tool runtime."""
import argparse,copy,json,sys
from pathlib import Path
from online_memory_r49 import save_once
from skill_services_r54 import TOOLS,validate_runtime

def prepare(config,extended,views,out):
    config=Path(config).resolve();cfg=json.loads(config.read_text());old=json.loads(Path(cfg['runtime']).read_text())
    ext=json.loads(Path(extended).read_text());viewmap=json.loads(Path(views).read_text())
    for name,v in viewmap.items():
        if not Path(name).is_absolute():raise ValueError('canonical_original_path_required')
        if not v.get('source') or v.get('modality') not in ('CXR','other','unknown') or v.get('view') not in ('AP','PA','frontal','lateral','unknown'):raise ValueError('view_provenance_required')
    runtime=copy.deepcopy(old)
    for name in ('medgemma','llava_rad','medvlm_r1'):
        runtime['tools'][name]=copy.deepcopy(ext['tools'][name])
        for field in ('python','revision'):
            if not runtime['tools'][name].get(field) or '[REDACTED]' in str(runtime['tools'][name][field]):raise ValueError('real_deployed_tool_required:'+name)
    for k in ('medgemma_model','medvlm_model','llavarad_source','llavarad_model','vicuna_model','biomedbert_config'):
        if k not in ext['backend_config']:raise ValueError('missing_extended_backend_config:'+k)
        runtime['backend_config'][k]=ext['backend_config'][k]
    runtime['backend_config']['r54_image_views_by_path']=viewmap
    spec=copy.deepcopy(old['tools']['xray_phrase_grounding']);spec.update(backend='maira2_grounded_report',revision=str(spec['revision'])+'+r54-grounded-report-v1',
        description='args={}. MAIRA-2 grounded findings report for verified frontal chest X-rays only. Lateral-only, non-CXR or unknown views return not_applicable. Findings and original-image boxes remain fallible; no history is inferred.')
    runtime['tools']['maira2_grounded_report']=spec
    phrase=runtime['tools']['xray_phrase_grounding']
    phrase['revision']=str(phrase['revision'])+'+r54-frontal-gate-v1'
    phrase['description']='args={"phrase":"specific finding"}. MAIRA-2 phrase localization on verified frontal CXR only. Box presence is not proof of disease; no box does not exclude it. Coordinates are normalized to the original image.'
    runtime['tools']['roi_crop']={'backend':'roi_crop','python':sys.executable,'revision':'r54-roi-v1', 'gpu':'',
        'description':'args={"box":[x0,y0,x1,y1],"zoom":2}. Crop original image in normalized [0,1] coordinates (top-left origin), zoom 1-4. Returns untouched original, marked full image and enlarged crop. Use original-image boxes, never MAIRA model-crop coordinates. No new detail is synthesized; retain anatomical context. Main model reinspects images; other model tools still receive original image.'}
    names=list(TOOLS)
    runtime['tools']={name:runtime['tools'][name] for name in names}
    runtime['arms']={}
    for arm in ('M','R49-AGENT'):runtime['arms'][arm]={'ready':True,'tools':names,'label':'R54 eight interfaces; report, phrase grounding and ROI'}
    validate_runtime(runtime);out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    cfg['runtime']=str(out/'runtime_r54.json');cfg['protocol']=str(Path(cfg['protocol']).resolve())
    save_once(out/'runtime_r54.json',runtime);save_once(out/'config_r54.json',cfg)
    return out/'config_r54.json'
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','extended-runtime','views','out'):p.add_argument('--'+key,required=True)
    a=p.parse_args();print(prepare(a.config,a.extended_runtime,a.views,a.out))
