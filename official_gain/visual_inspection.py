"""Original-pixel views with explicit image coordinates, never superresolution."""
import base64,json,math
from pathlib import Path
from PIL import Image,ImageDraw

def valid_box(b):
 return isinstance(b,list) and len(b)==4 and all(type(x) in (float,int) and math.isfinite(x) for x in b) and 0<=b[0]<b[2]<=1 and 0<=b[1]<b[3]<=1

def artifact(path,image_id,parents,kind,**extra):
 with Image.open(path) as im:size=list(im.size)
 return dict(image_id=image_id,path=str(path),source_filename=Path(path).name,parent_image_ids=parents,parent_image_id=parents[0],kind=kind,size=size,**extra)

def manual_box_allowed(action,metadata):
 b=action.get('box');side=action.get('target_patient_side','unknown')
 if not valid_box(b):return False
 if side in ('bilateral','midline'):return b[0]<.5<b[2]
 if side in ('unknown','not_applicable'):
  return b[0]<.5<b[2]  # Unverified laterality never authorizes a unilateral crop.
 marker=metadata.get('marker') or {};mb=marker.get('box');letter=marker.get('text')
 if metadata.get('view') not in ('frontal','axial') or not valid_box(mb) or letter not in ('R','L'):return False
 display='left' if mb[2]<=.5 else 'right' if mb[0]>=.5 else None
 if display is None:return False
 right=display if letter=='R' else ('right' if display=='left' else 'left')
 desired=right if side=='right' else ('right' if right=='left' else 'left') if side=='left' else None
 return desired is not None and (b[2]<=.5 if desired=='left' else b[0]>=.5)

def roi(source,box,out,name,normalized=True):
 with Image.open(source['path']) as raw:
  image=raw.convert('RGB');w,h=image.size
  if normalized:
   if not valid_box(box):raise ValueError('invalid_normalized_box')
   b=[math.floor(box[0]*w),math.floor(box[1]*h),math.ceil(box[2]*w),math.ceil(box[3]*h)]
  else:
   if len(box)!=4 or not all(type(v) in (float,int) and math.isfinite(v) for v in box):raise ValueError('invalid_original_pixel_box')
   if not (0<=box[0]<box[2]<=w and 0<=box[1]<box[3]<=h):raise ValueError('original_pixel_box_out_of_bounds')
   # Context padding remains in original coordinates. No model-space guess.
   x0,y0,x1,y1=box;px=max(8,.15*(x1-x0));py=max(8,.15*(y1-y0))
   b=[max(0,math.floor(x0-px)),max(0,math.floor(y0-py)),min(w,math.ceil(x1+px)),min(h,math.ceil(y1+py))]
  if not (0<=b[0]<b[2]<=w and 0<=b[1]<b[3]<=h) or b[2]-b[0]<=10 or b[3]-b[1]<=10:raise ValueError('invalid_original_pixel_crop')
  out=Path(out);out.mkdir(parents=True,exist_ok=True);p=out/(name+'_roi.png');image.crop(b).save(p)
  q=out/(name+'_location.png');overlay=image.copy();ImageDraw.Draw(overlay).rectangle(b,outline='yellow',width=max(2,w//250));overlay.save(q)
 return [artifact(p,name+':roi',[source['image_id']],'unmodified_pixel_roi',original_pixel_box=b),artifact(q,name+':location',[source['image_id']],'location_overlay',original_pixel_box=b)]

def paired(sources,out,name):
 if len(sources)<2:raise ValueError('paired_requires_two_current_images')
 images=[]
 for s in sources:
  with Image.open(s['path']) as im:images.append(im.convert('RGB'))
 # No resampling, rotation, flip or equal-size implication. Original scale kept.
 height=max(im.height for im in images)+32;width=sum(im.width for im in images)
 if width*height>50_000_000:raise ValueError('paired_canvas_too_large_use_originals')
 canvas=Image.new('RGB',(width,height),'black');d=ImageDraw.Draw(canvas);x=0
 for source,im in zip(sources,images):canvas.paste(im,(x,32));d.text((x+4,6),source['image_id']+' '+source.get('figure_id','unknown'),fill='white');x+=im.width
 Path(out).mkdir(parents=True,exist_ok=True);p=Path(out)/(name+'_paired.png');canvas.save(p)
 return [artifact(p,name+':paired',[s['image_id'] for s in sources],'paired_original_pixels',resampled=False,time_order='only_explicit_question_chronology')]

def content(payload,images):
 result=[{'type':'text','text':payload if isinstance(payload,str) else json.dumps(payload,ensure_ascii=False)}]
 for im in images:
  meta={k:v for k,v in im.items() if k!='data'}
  result.append({'type':'text','text':'BOUND CURRENT IMAGE: '+json.dumps(meta,ensure_ascii=False)})
  suffix=Path(im['path']).suffix.lower();mime='image/jpeg' if suffix in ('.jpg','.jpeg') else 'image/png'
  result.append({'type':'image_url','image_url':{'url':'data:'+mime+';base64,'+base64.b64encode(Path(im['path']).read_bytes()).decode('ascii'),'detail':'auto'}})
 return result

def aligned_anatomy(source,pred_masks,indices,organ_map,out,name):
 """Invert XRayCenterCrop + 512 resize; outside observed square is unknown."""
 with Image.open(source['path']) as raw:im=raw.convert('RGB')
 w,h=im.size;s=min(w,h);left=w//2-s//2;top=h//2-s//2
 Path(out).mkdir(parents=True,exist_ok=True);over=im.copy();bounds=[]
 for idx in indices:
  data=(pred_masks[0,idx].detach().cpu().numpy()>0).astype('uint8')*255
  square=Image.fromarray(data).resize((s,s),Image.Resampling.NEAREST)
  mask=Image.new('L',(w,h));mask.paste(square,(left,top))
  organ=next(k for k,v in organ_map.items() if v==idx);box=mask.getbbox()
  mask_path=Path(out)/(name+'_mask_'+str(idx)+'.png');mask.save(mask_path)
  if box:bounds.append({'organ':organ,'original_pixel_box':list(box),'mask_path':str(mask_path)})
  shade=Image.new('RGB',(w,h),'cyan');alpha=mask.point(lambda x:int(x*.25));over=Image.composite(shade,over,alpha)
 p=Path(out)/(name+'_aligned_anatomy.png');over.save(p)
 return {'artifact':artifact(p,name+':anatomy',[source['image_id']],'aligned_anatomical_overlay',observed_original_box=[left,top,left+s,top+s],outside_center_square='not assessed',pathology_mask=False),'anatomical_boxes':bounds,'mapping':'inverse center-square crop, nearest-neighbor mask resize; no diagnostic image resampling'}
