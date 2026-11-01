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
 def execute(self,name,args,source=None):
  from .runtime import encode_tool as encode_value,decode_tool as decode_value
  self.requested+=1
  if self.requested>4:return {'error':'experimental_four_medical_tool_budget_exhausted'}
  if name not in self.tools:return {'error':'unknown_tool'}
  args=dict(args)
  if source is None:
   paths=args.get('image_paths') if name=='chest_xray_expert' else [args.get('image_path')]
   if not paths or any(p not in {im['path'] for im in self.images} for p in paths):return {'error':'tool_image_not_a_current_original'}
   source=next((im for im in self.images if im['path']==paths[0]),None)
  if source is None:return {'error':'tool_image_not_a_current_original'}
  if name=='chest_xray_expert':args['image_paths']=args.get('image_paths') or [source['path']];args.pop('image_path',None)
  else:args['image_path']=source['path']
  tool=self.tools[name]
  try:tool.args_schema.model_validate(args)
  except Exception as exc:return {'error':'invalid_tool_arguments','type':type(exc).__name__}
  # Paths are exact frozen originals; this cache stores only raw model outputs.
  key=hashlib.sha256(json.dumps({'tool':name,'args':args},sort_keys=True).encode()).hexdigest()
  p=self.out/'tool_cache'/(key+'.json');call=self.folder/'tools'/str(self.requested)
  if (call/'result.json').exists():
   v=read(call/'result.json');result=decode_value(v['encoded_result']);self.actual+=int((call/'started.json').exists())
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
  ob=normalize(name,source,result,self.out/'artifacts');ob.update(tool_call_ordinal=self.requested,encoded_result=encode_value(result))
  mapped=p.with_suffix('.anatomy.json')
  if name=='chest_xray_segmentation' and mapped.exists():
   ob['anatomical_mapping']=read(mapped)
   if self.arm=='P':ob['artifacts']=[read(mapped)['artifact']]
  write(call/'result.json',ob);self.observations.append(ob);return result
 def proxies(self):
  from langchain_core.tools import StructuredTool
  result=[]
  for name,tool in self.tools.items():
   def call(_name=name,**kwargs):return self.execute(_name,kwargs)
   result.append(StructuredTool.from_function(call,name=name,description=tool.description,args_schema=tool.args_schema,
    handle_validation_error=lambda exc:'TOOL_ARGUMENT_ERROR: arguments did not match the advertised schema; no medical observation was produced. Correct the arguments within the remaining experimental budget.'))
  return result

def evidence_payload(questions,observations):
 # The observer gets neither the initial answer/reason nor plan diagnostic text.
 return {'neutral_attribute_questions':questions,'tool_observations':[compact(x) for x in observations]}

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
  if len(plan['actions'])>4 or len(plan['attributes'])>2:raise ValueError('plan_exceeds_frozen_budget')
 except Exception as exc:return terminal(direct['raw_response'],True,'plan_format:'+type(exc).__name__)
 write(folder/'plan.json',plan)
 if not plan['actions']:
  if not str(plan.get('no_action_reason','')).strip():return terminal(direct['raw_response'],True,'no_action_reason_missing')
  return terminal(direct['raw_response'],True,'no_applicable_action_stop')
 registry={im['image_id']:im for im in images};meta={m['image_id']:m for m in plan['image_metadata']};questions=[];success=False
 for i,a in enumerate(plan['actions'],1):
  try:
   ids=a.get('image_ids') or [];sources=[registry[x] for x in ids]
   if not sources or not str(a.get('question','')).strip():raise ValueError('action_current_image_or_neutral_question_missing')
   kind=a.get('kind');s=sources[0];m=meta.get(s['image_id'],{});extra=[]
   if kind in ('ground','anatomy','expert'):
    tool=a.get('tool');args=a.get('tool_args') or {}
    expected={'ground':{'xray_phrase_grounding'},'anatomy':{'chest_xray_segmentation'},'expert':{'chest_xray_expert','chest_xray_classifier','chest_xray_report_generator','llava_med_qa'}}
    if tool not in expected[kind]:raise ValueError('tool_kind_mismatch')
    if len(sources)!=1:raise ValueError('medical_tool_requires_one_bound_source')
    if tool!='llava_med_qa' and m.get('modality')!='CXR':raise ValueError('cxr_tool_requires_confirmed_CXR')
    if kind=='ground' and m.get('view')!='frontal':raise ValueError('grounding_requires_frontal_CXR')
    if tool=='chest_xray_expert':args['prompt']=a['question'];args.pop('question',None)
    if tool=='llava_med_qa':args['question']=a['question']
    if kind=='ground':args['phrase']=a['target_region']
    previous_n=len(session.observations);session.execute(tool,args,s);ob=session.observations[-1] if len(session.observations)>previous_n else None
    if ob and ob['execution']=='returned':
     success=True;extra.extend(ob['artifacts'])
     if kind=='ground' and new_view_n<2:
      boxes=ob['original_pixel_boxes']
      if boxes:extra+=roi(s,boxes[0],Path(out)/'artifacts'/row['question_id'],f'p{i}',normalized=False);new_view_n+=1
      elif manual_box_allowed(a,m):extra+=roi(s,a['box'],Path(out)/'artifacts'/row['question_id'],f'p{i}');new_view_n+=1
   elif kind=='roi':
    if len(sources)!=1 or new_view_n>=2 or not manual_box_allowed(a,m):raise ValueError('unbound_or_excess_roi')
    extra=roi(s,a['box'],Path(out)/'artifacts'/row['question_id'],f'p{i}');new_view_n+=1;success=True
   elif kind=='paired':
    if new_view_n>=2:raise ValueError('new_view_budget')
    extra=paired(sources,Path(out)/'artifacts'/row['question_id'],f'p{i}');new_view_n+=1;success=True
   else:raise ValueError('unknown_action')
   questions.append({'image_ids':ids,'question':a['question']});views.extend(extra);events.append({'action':i,'status':'executed','views':extra})
  except Exception as exc:events.append({'action':i,'status':'failed','error':str(exc)[:800]})
 write(folder/'observations.json',session.observations);write(folder/'views.json',views);write(folder/'action_events.json',events)
 if not success:return terminal(direct['raw_response'],True,'no_successful_new_observation')
 observer_payload=evidence_payload(questions,session.observations);write(folder/'observer_payload.json',observer_payload)
 observation=client.invoke(folder/'calls/observe',[{'role':'system','content':OBSERVER},{'role':'user','content':content(observer_payload,images+views)}])
 if observation is None:return terminal(direct['raw_response'],True,'observer_technical_failure')
 write(folder/'observer.json',{'content':observation.content})
 payload={'question_and_all_options':row['question'],'neutral_attribute_questions':questions,'new_observation':observation.content,'tools':[compact(x) for x in session.observations]}
 final=client.invoke(folder/'calls/final',[{'role':'system','content':FINAL},{'role':'user','content':content(payload,images+views)}])
 if final is None:return terminal(direct['raw_response'],True,'final_technical_failure')
 return terminal(final.content)
