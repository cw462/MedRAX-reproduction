"""D-shared initial answer, small plan, actual observations, full-option final."""
import hashlib,json,time,types
from pathlib import Path
from .runtime import read,write,now,answer,StopRun
from .visual_inspection import content,manual_box_allowed,roi,paired,artifact,aligned_anatomy
from .observations import normalize,compact
from .prompts import PLANNER,OBSERVER,FINAL

class ToolSession:
 def __init__(self,tools,images,out,folder,arm):
  self.tools,self.images,self.out,self.folder,self.arm=tools,images,Path(out),Path(folder),arm
  self.requested=0;self.actual=0;self.cache_hits=0;self.observations=[];self.unresolved_prior=0
  self.argument_normalizations=read(self.folder/'argument_normalizations.json') if (self.folder/'argument_normalizations.json').exists() else []
 def normalize_organs_arguments(self,name,values,ordinal):
  if not isinstance(values,dict) or not isinstance(values.get('organs'),str):return values
  try:decoded=json.loads(values['organs'])
  except (TypeError,ValueError):return values
  if not isinstance(decoded,list) or not all(isinstance(x,str) for x in decoded):return values
  event={'tool':name,'next_tool_ordinal':ordinal,'field':'organs','raw':values['organs'],'normalized':decoded,'reason':'strict_JSON_array_of_strings_format_only'}
  if event not in self.argument_normalizations:
   self.argument_normalizations.append(event);write(self.folder/'argument_normalizations.json',self.argument_normalizations)
  return dict(values,organs=decoded)
 def execute(self,name,args,source=None,sources=None):
  from .runtime import encode_tool as encode_value,decode_tool as decode_value
  self.requested+=1
  if self.requested>4:return {'error':'experimental_four_medical_tool_budget_exhausted'}
  if name not in self.tools:return {'error':'unknown_tool'}
  args=dict(args)
  if 'organs' in getattr(self.tools[name].args_schema,'model_fields',{}):args=self.normalize_organs_arguments(name,args,self.requested)
  originals={im['path']:im for im in self.images}
  if sources is None and source is not None:sources=[source]
  if sources is None:
   paths=args.get('image_paths') if name=='chest_xray_expert' else [args.get('image_path')]
   if not isinstance(paths,list) or not paths or any(not isinstance(p,str) or p not in originals for p in paths):return {'error':'tool_image_not_a_current_original'}
   sources=[originals[p] for p in paths]
  if not sources or any(s.get('path') not in originals or originals[s['path']]['image_id']!=s.get('image_id') for s in sources):return {'error':'tool_image_not_a_current_original'}
  paths=[s['path'] for s in sources]
  if len(set(paths))!=len(paths):return {'error':'duplicate_bound_original'}
  source=sources[0]
  # Paths are supplied by the current-image binding, never a guessed first image.
  # Any explicit tool argument must agree with the full action binding.
  if name=='chest_xray_expert':
   if args.get('image_paths') is not None and args['image_paths']!=paths:return {'error':'tool_paths_conflict_with_bound_sources'}
   if args.get('image_path') is not None and args['image_path']!=paths[0]:return {'error':'tool_paths_conflict_with_bound_sources'}
   args['image_paths']=paths;args.pop('image_path',None)
  else:
   if len(sources)!=1:return {'error':'tool_requires_one_bound_original'}
   if args.get('image_path') is not None and args['image_path']!=paths[0]:return {'error':'tool_paths_conflict_with_bound_sources'}
   if args.get('image_paths') is not None:return {'error':'single_image_tool_does_not_accept_image_paths'}
   args['image_path']=paths[0]
  tool=self.tools[name]
  try:tool.args_schema.model_validate(args)
  except Exception as exc:return {'error':'invalid_tool_arguments','type':type(exc).__name__}
  # Paths are exact frozen originals; this cache stores only raw model outputs.
  key=hashlib.sha256(json.dumps({'tool':name,'args':args},sort_keys=True).encode()).hexdigest()
  p=self.out/'tool_cache'/(key+'.json');call=self.folder/'tools'/str(self.requested)
  if (call/'result.json').exists():
   v=read(call/'result.json')
   if v.get('request_key',key)!=key:raise StopRun('saved_tool_request_binding_conflict')
   result=decode_value(v['encoded_result']);started=(call/'started.json').exists();self.actual+=int(started);self.cache_hits+=int(not started)
   self.unresolved_prior+=int(isinstance(result,dict) and result.get('error')=='interrupted_tool_result_unavailable_not_reissued')
  elif p.exists():result=decode_value(read(p)['encoded_result']);self.cache_hits+=1
  elif (call/'started.json').exists():
   result={'error':'interrupted_tool_result_unavailable_not_reissued'};self.actual+=1;self.unresolved_prior+=1
  else:
   write(call/'started.json',{'tool':name,'args':args,'utc':now()});self.actual+=1;began=time.monotonic()
   original_save=None
   if name=='chest_xray_segmentation':
    original_save=tool._save_visualization
    def save_and_capture(_self,original_img,masks,indices):
     value=original_save(original_img,masks,indices)
     mapped=aligned_anatomy(source,masks,indices,tool.organ_map,self.out/'artifacts'/'anatomy_cache',key)
     write(p.with_suffix('.anatomy.json'),mapped);return value
    object.__setattr__(tool,'_save_visualization',types.MethodType(save_and_capture,tool))
   try:result=tool.invoke(args)
   except Exception as exc:result={'error':type(exc).__name__,'message':str(exc)[:1600]}
   finally:
    if original_save is not None:object.__setattr__(tool,'_save_visualization',original_save)
   write(p,{'tool':name,'args':args,'raw_result':result,'encoded_result':encode_value(result),'elapsed_s':time.monotonic()-began})
  ob=normalize(name,source,result,self.out/'artifacts');ob.update(tool_call_ordinal=self.requested,encoded_result=encode_value(result),request_key=key,source_image_ids=[s['image_id'] for s in sources])
  mapped=p.with_suffix('.anatomy.json')
  if name=='chest_xray_segmentation' and mapped.exists():
   ob['anatomical_mapping']=read(mapped)
   if self.arm=='P':ob['artifacts']=[read(mapped)['artifact']]
  write(call/'result.json',ob);self.observations.append(ob);return result
 def proxies(self):
  from langchain_core.tools import StructuredTool
  from pydantic import model_validator
  result=[]
  for name,tool in self.tools.items():
   def call(_name=name,**kwargs):return self.execute(_name,kwargs)
   schema=tool.args_schema
   if 'organs' in getattr(schema,'model_fields',{}):
    # Format compatibility only: decode an actual JSON array of strings.
    # The advertised schema remains list[str], and all raw/decoded values persist.
    def make_schema(base,tool_name):
     def normalize_organs(cls,values):
      return self.normalize_organs_arguments(tool_name,values,self.requested+1)
     validator=model_validator(mode='before')(classmethod(normalize_organs))
     return type(base.__name__+'StrictJSONListCompatibility',(base,),{'normalize_organs_json':validator})
    schema=make_schema(schema,name)
   result.append(StructuredTool.from_function(call,name=name,description=tool.description,args_schema=schema,
    handle_validation_error=lambda exc:'TOOL_ARGUMENT_ERROR: arguments did not match the advertised schema; no medical observation was produced. Correct the arguments within the remaining experimental budget.'))
  return result


ACTION_ALIASES={
 'ground':'ground','localize-and-inspect':'ground','xray_phrase_grounding':'ground',
 'anatomy':'anatomy','anatomical reference':'anatomy','chest_xray_segmentation':'anatomy',
 'expert':'expert','focused expert observation':'expert','chest_xray_expert':'expert',
 'chest_xray_classifier':'expert','chest_xray_report_generator':'expert','llava_med_qa':'expert',
 'roi':'roi','paired':'paired','paired-image comparison':'paired',
}
TOOL_KINDS={
 'xray_phrase_grounding':'ground','chest_xray_segmentation':'anatomy',
 'chest_xray_expert':'expert','chest_xray_classifier':'expert',
 'chest_xray_report_generator':'expert','llava_med_qa':'expert',
}

def normalize_action(action):
 if not isinstance(action,dict):raise ValueError('action_must_be_object')
 raw_kind=action.get('kind');key=str(raw_kind).strip().lower()
 if key not in ACTION_ALIASES:raise ValueError('unknown_action')
 value=dict(action,kind=ACTION_ALIASES[key]);changes=[]
 if value['kind']!=raw_kind:changes.append({'field':'kind','raw':raw_kind,'normalized':value['kind']})
 if key in TOOL_KINDS and not value.get('tool'):
  value['tool']=key;changes.append({'field':'tool','raw':action.get('tool'),'normalized':key})
 return value,changes

def bind_action_sources(action,registry):
 ids=action.get('image_ids')
 if not isinstance(ids,list) or not ids or any(not isinstance(x,str) or x not in registry for x in ids):raise ValueError('action_requires_current_image_ids')
 if len(set(ids))!=len(ids):raise ValueError('duplicate_action_image_ids')
 if not isinstance(action.get('question'),str) or not action['question'].strip():raise ValueError('action_neutral_question_missing')
 return [registry[x] for x in ids]


def evidence_payload(questions,observations):
 # The observer gets neither the initial answer/reason nor plan diagnostic text.
 return {'neutral_attribute_questions':questions,'tool_observations':[dict(compact(x),source_image_ids=x.get('source_image_ids',[x['source_image_id']])) for x in observations]}

def run_p(row,images,direct,client,tools,out,folder):
 from experiments.v12_evidence import question_parts,_outer_object
 folder=Path(folder);legal=question_parts(row['question'])[1]
 session=ToolSession(tools,images,out,folder,'P');views=[];new_view_n=0;events=[]
 def terminal(raw,fallback=False,reason=None):
  return dict(question_id=row['question_id'],arm='P',answer=direct['answer'] if fallback else answer(raw,legal),raw_response=raw,
   initial_answer=direct['answer'],fallback=fallback,fallback_reason=reason,tool_requested=session.requested,tool_actual=session.actual,tool_cache_hits=session.cache_hits,new_roi_or_pair_views=new_view_n,new_visual_inputs=len(views),events=events,committed_utc=now())
 plan_response=client.invoke(folder/'calls/plan',[{'role':'system','content':PLANNER},{'role':'user','content':content({'question_and_all_options':row['question'],'initial_answer':direct['answer'],'initial_reason':direct['raw_response'],'tools':[{ 'name':t.name,'description':t.description,'schema':t.args_schema.model_json_schema()} for t in tools.values()]},images)}])
 if plan_response is None:return terminal(direct['raw_response'],True,'planner_technical_failure')
 try:
  plan=_outer_object(plan_response.content,{'attributes','actions','image_metadata'})
  if not isinstance(plan['actions'],list) or not isinstance(plan['attributes'],list):raise ValueError('plan_arrays_required')
  if len(plan['actions'])>4 or len(plan['attributes'])>2:raise ValueError('plan_exceeds_frozen_budget')
 except Exception as exc:return terminal(direct['raw_response'],True,'plan_format:'+type(exc).__name__)
 write(folder/'plan.json',plan)
 if not plan['actions']:
  if not str(plan.get('no_action_reason','')).strip():return terminal(direct['raw_response'],True,'no_action_reason_missing')
  return terminal(direct['raw_response'],True,'no_applicable_action_stop')
 registry={im['image_id']:im for im in images};questions=[];success=False
 try:
  if not isinstance(plan['image_metadata'],list):raise ValueError('image_metadata_must_be_list')
  meta={}
  for item in plan['image_metadata']:
   if not isinstance(item,dict) or item.get('image_id') not in registry or item['image_id'] in meta:raise ValueError('invalid_or_duplicate_image_metadata')
   meta[item['image_id']]=item
 except Exception as exc:return terminal(direct['raw_response'],True,'plan_format:'+str(exc))
 normalized_actions=[]
 for i,raw_action in enumerate(plan['actions'],1):
  event={'action':i,'status':'failed','views':[]};extra=[];tool_returned=False
  try:
   a,changes=normalize_action(raw_action);normalized_actions.append(a)
   event.update(kind=a['kind'],normalizations=changes)
   sources=bind_action_sources(a,registry);ids=[s['image_id'] for s in sources]
   kind=a['kind'];s=sources[0];m=meta.get(s['image_id'],{})
   if kind in ('ground','anatomy','expert'):
    tool=a.get('tool');args=a.get('tool_args') or {}
    if not isinstance(args,dict):raise ValueError('tool_args_must_be_object')
    args=dict(args)
    if TOOL_KINDS.get(tool)!=kind:raise ValueError('tool_kind_mismatch')
    if tool!='chest_xray_expert' and len(sources)!=1:raise ValueError('medical_tool_requires_one_bound_source')
    if tool!='llava_med_qa' and any(meta.get(x['image_id'],{}).get('modality')!='CXR' for x in sources):raise ValueError('cxr_tool_requires_confirmed_CXR_for_every_source')
    if kind=='ground' and m.get('view')!='frontal':raise ValueError('grounding_requires_frontal_CXR')
    if tool=='chest_xray_expert':args['prompt']=a['question'];args.pop('question',None)
    if tool=='llava_med_qa':args['question']=a['question']
    if kind=='ground':args['phrase']=a['target_region']
    previous_n=len(session.observations);raw_result=session.execute(tool,args,sources=sources)
    ob=session.observations[-1] if len(session.observations)>previous_n else None
    # Preserve the neutral target before any derived-view postprocessing can fail.
    if ob:
     questions.append({'image_ids':ids,'question':a['question']})
    if not ob or ob['execution']!='returned':
     event.update(status='failed',error='medical_tool_no_observation' if not ob else 'medical_tool_execution_failed',tool_result=raw_result)
    else:
     success=True;tool_returned=True;extra.extend(ob['artifacts']);event['status']='executed'
     if kind=='ground' and new_view_n<2:
      boxes=ob['original_pixel_boxes']
      if boxes:extra+=roi(s,boxes[0],Path(out)/'artifacts'/row['question_id'],f'p{i}',normalized=False);new_view_n+=1
      elif manual_box_allowed(a,m):extra+=roi(s,a['box'],Path(out)/'artifacts'/row['question_id'],f'p{i}');new_view_n+=1
   elif kind=='roi':
    if len(sources)!=1 or new_view_n>=2 or not manual_box_allowed(a,m):raise ValueError('unbound_or_excess_roi')
    extra=roi(s,a['box'],Path(out)/'artifacts'/row['question_id'],f'p{i}');new_view_n+=1;success=True
    questions.append({'image_ids':ids,'question':a['question']});event['status']='executed'
   elif kind=='paired':
    if new_view_n>=2:raise ValueError('new_view_budget')
    extra=paired(sources,Path(out)/'artifacts'/row['question_id'],f'p{i}');new_view_n+=1;success=True
    questions.append({'image_ids':ids,'question':a['question']});event['status']='executed'
  except StopRun:raise
  except Exception as exc:
   event.update(status='partial' if tool_returned else 'failed',error=str(exc)[:800])
   if len(normalized_actions)<i:normalized_actions.append({'raw_action':raw_action,'normalization_error':str(exc)[:800]})
  event['views']=extra;views.extend(extra);events.append(event)
 write(folder/'normalized_plan.json',dict(plan,actions=normalized_actions))
 write(folder/'observations.json',session.observations);write(folder/'views.json',views);write(folder/'action_events.json',events)
 if not success:return terminal(direct['raw_response'],True,'no_successful_new_observation')
 observer_payload=evidence_payload(questions,session.observations);write(folder/'observer_payload.json',observer_payload)
 observation=client.invoke(folder/'calls/observe',[{'role':'system','content':OBSERVER},{'role':'user','content':content(observer_payload,images+views)}])
 if observation is None:return terminal(direct['raw_response'],True,'observer_technical_failure')
 write(folder/'observer.json',{'content':observation.content})
 payload={'question_and_all_options':row['question'],'neutral_attribute_questions':questions,'new_observation':observation.content,'tools':[dict(compact(x),source_image_ids=x.get('source_image_ids',[x['source_image_id']])) for x in session.observations]}
 final=client.invoke(folder/'calls/final',[{'role':'system','content':FINAL},{'role':'user','content':content(payload,images+views)}])
 if final is None:return terminal(direct['raw_response'],True,'final_technical_failure')
 return terminal(final.content)
