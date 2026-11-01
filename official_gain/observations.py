"""Preserve tool values and actual visual artifacts with current-image binding."""
import json,math
from pathlib import Path
from PIL import Image
from .visual_inspection import artifact

def dictionaries(value):
 if isinstance(value,dict):
  yield value
  for v in value.values():yield from dictionaries(v)
 elif isinstance(value,(tuple,list)):
  for v in value:yield from dictionaries(v)

def normalize(tool,source,result,allowed_artifact_root):
 boxes=[];views=[];errors=[]
 root=Path(allowed_artifact_root).resolve()
 values=list(dictionaries(result));localization=None
 if tool=='xray_phrase_grounding':
  # MAIRA's adjust_box_for_original_image_size returns ORIGINAL-IMAGE
  # NORMALIZED coordinates. The tool_registry_ext adapter preserves them in
  # bounding_boxes.image_coordinates; they are not pixel coordinates.
  localization={'input_coordinate_space':'original_image_normalized_xyxy',
   'output_coordinate_space':'original_image_pixel_xyxy',
   'source_image_id':source['image_id'],'source_size':None,
   'original_normalized_boxes':[],'original_pixel_boxes':boxes,
   'conversion':'x * original width; y * original height; no flip, rotation or clipping',
   'provenance':'MAIRA adjust_box_for_original_image_size -> tool_registry_ext bounding_boxes.image_coordinates'}
  try:
   if source.get('role','original')!='original' or source.get('parent_image_id') or source.get('parent_image_ids'):
    raise ValueError('grounding_requires_bound_original_image')
   source_path=Path(source['path']).resolve(strict=True)
   with Image.open(source_path) as im:w,h=im.size
   if source.get('size') is not None and list(source['size'])!=[w,h]:
    raise ValueError('grounding_source_size_mismatch')
   for value in values:
    if value.get('image_path') and Path(value['image_path']).resolve()!=source_path:
     raise ValueError('grounding_result_source_mismatch')
   localization['source_size']=[w,h]
   for value in values:
    coordinate_record=value.get('bounding_boxes')
    if not isinstance(coordinate_record,dict):continue
    coords=coordinate_record.get('image_coordinates',[])
    if not isinstance(coords,(tuple,list)):raise ValueError('invalid_grounding_coordinate_container')
    for b in coords:
     # Reject unsupported coordinates instead of inferring pixel-vs-normalized
     # from magnitude, silently clipping, or mirroring patient laterality.
     if not isinstance(b,(tuple,list)) or len(b)!=4 or not all(type(x) in (int,float) and math.isfinite(x) for x in b):
      raise ValueError('invalid_grounding_normalized_box')
     if not (0<=b[0]<b[2]<=1 and 0<=b[1]<b[3]<=1):raise ValueError('grounding_normalized_box_out_of_bounds')
     localization['original_normalized_boxes'].append(list(b))
     boxes.append([b[0]*w,b[1]*h,b[2]*w,b[3]*h])
  except (OSError,ValueError,TypeError,KeyError) as exc:
   # Keep the raw tool result. An unusable geometric projection cannot become
   # a purported valid crop, even if an earlier box in the batch was valid.
   boxes.clear();errors.append('grounding_coordinate_error:'+str(exc))
 for value in values:
  if value.get('error'):errors.append(str(value['error']))
  if value.get('analysis_status') in ('failed','error'):errors.append(value['analysis_status'])
  for key in ('visualization_path','segmentation_image_path'):
   if not value.get(key):continue
   p=Path(value[key]).resolve()
   if p.is_relative_to(root) and p.is_file() and p.suffix.lower() in ('.png','.jpg','.jpeg'):
    if not any(v['path']==str(p) for v in views):views.append(artifact(p,'artifact:'+str(len(views)+1),[source['image_id']],'anatomical_or_location_overlay'))
 return dict(source_image_id=source['image_id'],tool=tool,raw_result=result,original_pixel_boxes=boxes,grounding_coordinates=localization,artifacts=views,execution='failed' if errors else 'returned',errors=errors,
  limits='Tool text is fallible; box is conditional localization; anatomical mask is not lesion truth; physical metrics on uncalibrated JPEG are not reliable millimeters.')

def compact(observation):
 # Retain full raw output on disk; omit uncalibrated area/size fields in solver.
 def clean(v):
  if isinstance(v,dict):return {k:clean(x) for k,x in v.items() if not any(s in k.lower() for s in ('area','perimeter','pixel_spacing','confidence','path','traceback'))}
  if isinstance(v,(tuple,list)):return [clean(x) for x in v]
  if type(v).__module__.startswith('numpy'):return v.tolist() if hasattr(v,'tolist') else v.item()
  return v
 return {'source_image_id':observation['source_image_id'],'source_image_ids':observation.get('source_image_ids',[observation['source_image_id']]),'tool':observation['tool'],'result':clean(observation['raw_result']),'grounding_coordinates':clean(observation.get('grounding_coordinates')),'limits':observation['limits'],'execution':observation['execution']}
