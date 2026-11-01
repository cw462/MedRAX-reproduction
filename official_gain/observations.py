"""Preserve tool values and actual visual artifacts with current-image binding."""
import json
from pathlib import Path
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
 for value in dictionaries(result):
  if value.get('error'):errors.append(str(value['error']))
  if value.get('analysis_status') in ('failed','error'):errors.append(value['analysis_status'])
  coords=value.get('bounding_boxes',{}).get('image_coordinates',[])
  for b in coords:
   if isinstance(b,(tuple,list)) and len(b)==4:boxes.append(list(b))
  for key in ('visualization_path','segmentation_image_path'):
   if not value.get(key):continue
   p=Path(value[key]).resolve()
   if p.is_relative_to(root) and p.is_file() and p.suffix.lower() in ('.png','.jpg','.jpeg'):
    if not any(v['path']==str(p) for v in views):views.append(artifact(p,'artifact:'+str(len(views)+1),[source['image_id']],'anatomical_or_location_overlay'))
 return dict(source_image_id=source['image_id'],tool=tool,raw_result=result,original_pixel_boxes=boxes,artifacts=views,execution='failed' if errors else 'returned',errors=errors,
  limits='Tool text is fallible; box is conditional localization; anatomical mask is not lesion truth; physical metrics on uncalibrated JPEG are not reliable millimeters.')

def compact(observation):
 # Retain full raw output on disk; omit uncalibrated area/size fields in solver.
 def clean(v):
  if isinstance(v,dict):return {k:clean(x) for k,x in v.items() if not any(s in k.lower() for s in ('area','perimeter','pixel_spacing','confidence','path','traceback'))}
  if isinstance(v,(tuple,list)):return [clean(x) for x in v]
  return v
 return {'source_image_id':observation['source_image_id'],'tool':observation['tool'],'result':clean(observation['raw_result']),'limits':observation['limits'],'execution':observation['execution']}
