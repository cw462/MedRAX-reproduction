"""Real extended local backends; missing dependencies fail explicitly, never fabricate evidence."""
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time


def plain(x):
    import numpy as np
    if isinstance(x,dict):return {str(k):plain(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [plain(v) for v in x]
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    return x


def cxas_masks(req):
    """One exact model-image inference shared by parsing and gated geometry."""
    import numpy as np
    from PIL import Image
    cfg=req['runtime'];root=Path(cfg['root']);image=Path(req['image'])
    key=hashlib.sha256(image.read_bytes()).hexdigest()
    cache=Path(cfg['cxas_cache'])/key;result=cache/'result.json'
    if result.exists():
        info=json.loads(result.read_text());return np.load(cache/'masks.npz')['masks'],info,False
    if (cache/'started.json').exists():raise RuntimeError('cxas_started_unknown_no_reissue')
    cache.mkdir(parents=True,exist_ok=True)
    (cache/'started.json').write_text(json.dumps({'image_sha256':key,'model':'CXAS UNet_ResNet50_default','utc':time.time()}))
    sys.path.insert(0,str(root/'models/cxr_vqa_xdeps'))
    os.environ['CXAS_PATH']=str(root/'models/cxr_vqa_xdeps');os.environ['CXAS_NO_WELCOME']='1'
    import torch
    from cxas import CXAS
    from cxas.label_mapper import id2label_dict
    tick=time.monotonic();model=CXAS(model_name='UNet_ResNet50_default',gpus='0')
    with torch.inference_mode():prediction=model.process_file(str(image),output_directory=str(cache))
    masks=prediction['segmentation_preds'][0].detach().cpu().numpy().astype(bool)
    width,height=Image.open(image).size
    masks=np.stack([np.asarray(Image.fromarray(m.astype('uint8')).resize((width,height),Image.Resampling.NEAREST)).astype(bool) for m in masks])
    info={'model':'CXAS UNet_ResNet50_default','labels':{str(k):str(v) for k,v in id2label_dict.items()},'original_size':[width,height],
          'inference_seconds':time.monotonic()-tick,'image_sha256':key,'mask_shape':list(masks.shape),'threshold':.5,
          'coordinates':'original pixel coordinates: origin top-left, x right, y down; nearest-neighbor inverse resize'}
    np.savez_compressed(cache/'masks.npz',masks=masks)
    result.write_text(json.dumps(info,ensure_ascii=False,indent=2))
    return masks,info,True


def mask_for(masks,info,name):
    matches=[int(k) for k,v in info['labels'].items() if v.lower()==name.lower()]
    if len(matches)!=1 or not 0<=matches[0]<len(masks):return None
    return masks[matches[0]]


def bbox(mask):
    import numpy as np
    y,x=np.where(mask)
    if not len(x):return None
    return [int(x.min()),int(y.min()),int(x.max()+1),int(y.max()+1)]


def geometry(masks,info):
    """Declared geometry adaptation; suppress the whole bundle on failed quality."""
    import numpy as np
    width,height=info['original_size'];labels={v.lower():v for v in info['labels'].values()}
    def resolve(options):
        for name in options:
            if name in labels:return mask_for(masks,info,labels[name])
        return None
    left=resolve(['lung left','left lung']);right=resolve(['lung right','right lung']);heart=resolve(['heart'])
    central=resolve(['trachea'])
    unavailable={'measurement_available':False,'values':None,'reason':'required_masks_missing_or_failed_quality'}
    if any(m is None or not m.any() for m in [left,right,heart,central]):return unavailable
    if any(not .02<float(m.mean())<.65 for m in [left,right,heart]):return unavailable
    if np.logical_and(left,right).sum()/max(np.logical_or(left,right).sum(),1)>.1:return unavailable
    heart_spans=[(np.flatnonzero(r)[-1]-np.flatnonzero(r)[0]+1) if r.any() else 0 for r in heart]
    row=int(np.argmax(heart_spans));cols=np.flatnonzero((left|right)[row])
    if len(cols)<2:return unavailable
    thorax_width=int(cols[-1]-cols[0]+1);ctr=float(heart_spans[row]/thorax_width)
    if not 0<ctr<1:return unavailable
    bilateral=np.flatnonzero((left|right).any(axis=0));mid=float((bilateral[0]+bilateral[-1])/2)
    cy,cx=np.where(central);shift=float(cx.mean()-mid)/thorax_width
    if not math.isfinite(shift) or abs(shift)>.5:return unavailable
    return {'measurement_available':True,'values':{'CTR':ctr,'heart_widest_original_row':row,
        'heart_width_px':int(heart_spans[row]),'bilateral_lung_span_px_same_row':thorax_width,
        'lung_field_asymmetry_log_AR_over_AL':float(math.log(right.sum()/left.sum())),
        'thoracic_shift_fraction_of_thorax_width':shift,
        'thoracic_shift_direction_in_image':'right' if shift>0 else 'left' if shift<0 else 'centered'},
        'interpretation':{'CTR_gt_0_5':bool(ctr>.5)},
        'limitations':'PA-only geometric estimates from unverified anatomical masks. Shift is tracheal centroid relative to bilateral-lung horizontal midline; this explicit rule is an adaptation, not the unreleased original implementation. Image-direction sign is not converted to patient laterality.'}


def execute_extended(req):
    cfg=req['runtime'];root=Path(cfg['root']);name=req['backend'];args=req['args'];image=Path(req['image']);folder=Path(req['artifact_dir']);derived=[]
    if name=='view_check':
        sys.path.insert(0,str(root/'models/cxr_vqa_xdeps'))
        os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['TF_CPP_MIN_LOG_LEVEL']='2'
        import opencxr
        from opencxr.utils.file_io import read_file
        sorter=opencxr.load(opencxr.algorithms.image_sorter)
        readable=image
        if image.suffix.lower() in ['.jpg','.jpeg']:
            from PIL import Image
            readable=folder/'decoded_original.png'
            Image.open(image).save(readable)  # Lossless container for the same decoded pixels.
        pixels,spacing,_=read_file(str(readable));raw=plain(sorter.run(pixels))
        obs={'view_result':raw,'measurement_applicable':raw['Type']=='PA' and raw['Rotation']=='0',
             'gate_rule':'OpenCXR argmax view PA and rotation 0; geometry still requires nonempty, plausible anatomical masks.',
             'backend':'OpenCXR Image Sorter; CPU execution',
             'input_binding':'Original pixels; JPEG decoded once into lossless PNG for the official PNG reader; original retained.'}
    elif name in ['region_parse','measurement']:
        import numpy as np
        from PIL import Image,ImageDraw
        masks,info,fresh=cxas_masks(req)
        if name=='measurement':obs=geometry(masks,info)
        else:
            regions=args.get('regions') or [args.get('region','left lung')]
            if not isinstance(regions,list) or not 1<=len(regions)<=4 or any(not isinstance(x,str) for x in regions):raise ValueError('one_to_four_anatomical_regions_required')
            boxes={};selected=[]
            for region in regions:
                mask=mask_for(masks,info,region)
                if mask is None:raise ValueError('CXAS_anatomical_label_not_supported:'+region)
                b=bbox(mask);boxes[region]=b
                if b is not None:selected.append(mask)
            combined=np.logical_or.reduce(selected) if selected else np.zeros(masks.shape[1:],dtype=bool)
            b=bbox(combined);w,h=info['original_size']
            obs={'boxes_original_pixels':boxes,'combined_box_original_pixels':b,
                 'combined_box_normalized':[b[0]/w,b[1]/h,b[2]/w,b[3]/h] if b else None,
                 'original_size':[w,h],'coordinate_mapping':info['coordinates'],
                 'mask_file':str(Path(cfg['cxas_cache'])/info['image_sha256']/'masks.npz'),
                 'scope':'CXAS anatomy only. No BiomedParse pathology localization is claimed.'}
            overlay=Image.open(image).convert('RGBA')
            rgba=np.zeros((h,w,4),dtype=np.uint8);rgba[combined]=[255,0,0,70]
            overlay=Image.alpha_composite(overlay,Image.fromarray(rgba));drawing=ImageDraw.Draw(overlay)
            for region,b in boxes.items():
                if b:drawing.rectangle(b,outline='red',width=2);drawing.text((b[0],b[1]),region,fill='red')
            overlay.save(folder/'anatomy_boxes.png');derived=[str(folder/'anatomy_boxes.png')]
        obs.update(cxas_inference_performed=fresh,cxas_model=info['model'],cxas_inference_seconds_if_fresh=info['inference_seconds'] if fresh else 0)
        raw={'returned_observation':obs,'mask_provenance':info}
    elif name=='evidence_lookup':
        import torch
        from transformers import AutoProcessor,AutoModelForImageTextToText,FineGrainedFP8Config
        model_path=Path(cfg['knowledge_model']);processor=AutoProcessor.from_pretrained(model_path,local_files_only=True)
        model=AutoModelForImageTextToText.from_pretrained(model_path,local_files_only=True,dtype=torch.bfloat16,
            device_map='auto',max_memory={0:'20GiB',1:'20GiB','cpu':'35GiB'},
            quantization_config=FineGrainedFP8Config(dequantize=True),offload_folder=str(folder/'offload'),attn_implementation='eager')
        query=args.get('query') or args.get('conditions')
        if not isinstance(query,str) or not query.strip() or len(query)>1800:raise ValueError('condition_knowledge_query_required')
        messages=[{'role':'system','content':'Provide concise general chest-radiograph knowledge only: characteristic findings, distribution and discriminating features. No patient-specific diagnosis. No invented citations.'},
                  {'role':'user','content':query}]
        inputs=processor.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,return_dict=True,return_tensors='pt',enable_thinking=False).to(model.device)
        length=inputs['input_ids'].shape[-1]
        with torch.inference_mode():generated=model.generate(**inputs,max_new_tokens=512,do_sample=False)
        answer=processor.decode(generated[0,length:],skip_special_tokens=True)
        raw=obs={'knowledge':answer,'knowledge_source':'local model knowledge; not literature retrieval','citations':[],
            'model':'Qwen/Qwen3.5-27B-FP8','revision':'97f5941bf617e31c5e237364a8602ce3f03a551a',
            'deployment_adaptation':'official FP8 checkpoint dequantized for 3090, split GPU/CPU; not a replacement main model',
            'backend_input_tokens':length,'backend_output_tokens':int(generated.shape[-1]-length)}
    elif name=='medvlm_r1':
        import torch
        from PIL import Image
        from transformers import AutoProcessor,Qwen2VLForConditionalGeneration
        model_path=Path(cfg['medvlm_model']);model=Qwen2VLForConditionalGeneration.from_pretrained(model_path,local_files_only=True,torch_dtype=torch.bfloat16,device_map='cuda:0')
        processor=AutoProcessor.from_pretrained(model_path,local_files_only=True)
        question=args.get('question','Describe the visible findings.')
        question=question+'\nThink through the question step by step in <think>...</think>, then give the result in <answer>...</answer>.'
        messages=[{'role':'user','content':[{'type':'image','image':str(image)},{'type':'text','text':question}]}]
        text=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
        inputs=processor(text=[text],images=[Image.open(image).convert('RGB')],padding=True,return_tensors='pt').to(model.device)
        length=inputs.input_ids.shape[-1]
        with torch.inference_mode():generated=model.generate(**inputs,max_new_tokens=1024,do_sample=False)
        raw=obs={'answer':processor.batch_decode(generated[:,length:],skip_special_tokens=True,clean_up_tokenization_spaces=False)[0],
            'model':'JZPeterPan/MedVLM-R1','revision':'d256f2cfdf98c6872c1dc9f20b7dd52f49374fe9',
            'backend_input_tokens':length,'backend_output_tokens':int(generated.shape[-1]-length),
            'adaptation':'CXRAgent MedVLM-R1 input/generation mechanism with explicit bound image and pinned local assets.'}
    elif name=='medgemma':
        import torch
        from PIL import Image
        from transformers import AutoModelForImageTextToText,AutoProcessor
        path=Path(cfg['medgemma_model']);model=AutoModelForImageTextToText.from_pretrained(path,torch_dtype=torch.bfloat16,device_map='cuda:0',local_files_only=True)
        processor=AutoProcessor.from_pretrained(path,local_files_only=True)
        messages=[{'role':'system','content':[{'type':'text','text':'You are an expert radiologist.'}]},
                  {'role':'user','content':[{'type':'image','image':Image.open(image).convert('RGB')},{'type':'text','text':args.get('question','Describe the visible findings.')}]}]
        inputs=processor.apply_chat_template(messages,add_generation_prompt=True,tokenize=True,return_dict=True,return_tensors='pt').to(model.device,dtype=torch.bfloat16)
        length=inputs['input_ids'].shape[-1]
        with torch.inference_mode():generated=model.generate(**inputs,max_new_tokens=512,do_sample=False)
        raw=obs={'answer':processor.decode(generated[0,length:],skip_special_tokens=True),'model':'google/medgemma-4b-it',
            'revision':'290cda5eeccbee130f987c4ad74a59ae6f196408','backend_input_tokens':length,'backend_output_tokens':int(generated.shape[-1]-length)}
    elif name=='llava_rad':
        import torch
        from PIL import Image
        from unittest.mock import patch
        from transformers import AutoConfig,AutoTokenizer
        source=Path(cfg['llavarad_source']);model_path=Path(cfg['llavarad_model']);base_path=Path(cfg['vicuna_model']);bert_path=Path(cfg['biomedbert_config'])
        sys.path.insert(0,str(source));os.environ['HF_HUB_OFFLINE']='1'
        from llava.model.builder import load_pretrained_model
        from llava.constants import IMAGE_TOKEN_INDEX,DEFAULT_IMAGE_TOKEN,DEFAULT_IM_START_TOKEN,DEFAULT_IM_END_TOKEN
        from llava.conversation import conv_templates
        from llava.mm_utils import tokenizer_image_token
        import llava.model.multimodal_encoder.open_clip_encoder.utils as clip_utils
        original_config=AutoConfig.from_pretrained;original_tokenizer=AutoTokenizer.from_pretrained
        original_clip=clip_utils.create_model_from_pretrained
        def local_config(path,*a,**kw):
            if str(path).startswith('microsoft/BiomedNLP-'):path=bert_path
            kw['local_files_only']=True;value=original_config(path,*a,**kw)
            if Path(str(path)).resolve()==model_path.resolve():
                value.mm_vision_tower_config=str(model_path/'biomedclipcxr_518.json')
                value.mm_vision_tower_checkpoint=str(model_path/'biomedclipcxr_518_checkpoint.pt')
            return value
        def local_tokenizer(path,*a,**kw):
            if str(path).startswith('microsoft/BiomedNLP-'):path=bert_path
            kw['local_files_only']=True;return original_tokenizer(path,*a,**kw)
        def local_clip(*a,**kw):
            # The full official CLIP checkpoint is loaded below. Initializing its
            # text tower from config avoids an unnecessary external BERT load.
            kw['pretrained_hf']=False;return original_clip(*a,**kw)
        with patch.object(AutoConfig,'from_pretrained',side_effect=local_config),patch.object(AutoTokenizer,'from_pretrained',side_effect=local_tokenizer),patch.object(clip_utils,'create_model_from_pretrained',side_effect=local_clip):
            tokenizer,model,processor,context=load_pretrained_model(str(model_path),str(base_path),'llavarad',device_map='auto',device='cuda:0')
        question=args.get('question','Describe the visible findings.')
        image_token=DEFAULT_IM_START_TOKEN+DEFAULT_IMAGE_TOKEN+DEFAULT_IM_END_TOKEN if getattr(model.config,'mm_use_im_start_end',False) else DEFAULT_IMAGE_TOKEN
        conversation=conv_templates['v1'].copy();conversation.append_message(conversation.roles[0],image_token+'\n'+question);conversation.append_message(conversation.roles[1],None)
        ids=tokenizer_image_token(conversation.get_prompt(),tokenizer,IMAGE_TOKEN_INDEX,return_tensors='pt').unsqueeze(0).cuda()
        pixels=processor.preprocess(Image.open(image).convert('RGB'),return_tensors='pt')['pixel_values'][0].unsqueeze(0).half().cuda()
        with torch.inference_mode():generated=model.generate(ids,images=pixels,do_sample=False,max_new_tokens=512,use_cache=True)
        raw=obs={'answer':tokenizer.batch_decode(generated[:,ids.shape[-1]:],skip_special_tokens=True)[0],
            'model':'microsoft/llava-rad','revision':'dcdbc6caf6806c9acb66e12a827a39c86e00f6a7',
            'base_model':'lmsys/vicuna-7b-v1.5','base_revision':'3321f76e3f527bd14065daf69dad9344000a201d',
            'official_source_commit':'1fc44096cc5766c28d8a3329240c8423100ce3df',
            'backend_input_tokens':int(ids.shape[-1]),'backend_output_tokens':int(generated.shape[-1]-ids.shape[-1]),
            'adaptation':'Original LoRA/base/BiomedCLIP loading and generation, local path binding; text tower config initialization before the complete official CLIP checkpoint load.'}
    else:raise ValueError('unsupported_extended_backend')
    return plain(raw),plain(obs),derived
