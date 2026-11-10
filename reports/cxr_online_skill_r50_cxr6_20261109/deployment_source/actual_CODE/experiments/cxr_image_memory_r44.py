"""Same-original-image sequential memory; no model-based summarization or reference reads."""
import hashlib,json
from pathlib import Path

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def rows(p):return [json.loads(x) for x in Path(p).read_text(encoding='utf-8').splitlines() if x.strip()]
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
def image_key(row,data):
    from PIL import Image
    hashes=[]
    for name in row['images']:
        path=(Path(data)/name).resolve()
        if not path.is_relative_to(Path(data).resolve()):raise ValueError('image_outside_root')
        with Image.open(path) as im:
            im=im.convert('RGB');hashes.append(hashlib.sha256(str(im.size).encode()+im.tobytes()).hexdigest())
    if not hashes:raise ValueError('no_images')
    # Multi-image rows match only the entire original-image sequence, preserving index binding.
    return digest(hashes)
def schedule(inputs,data):
    seen={};items=[]
    for row in inputs:
        key=image_key(row,data);prior=seen.setdefault(key,[])
        items.append({'question_id':row['question_id'],'image_key':key,'previous_ids':list(prior)})
        prior.append(row['question_id'])
    return items

def tool_failure_reason(record):
    """Recognize actual failed MedRAX envelopes, including nested worker errors."""
    if record.get('status')!='completed':return 'outer_status_not_completed'
    if record.get('observation') is None:return 'missing_observation'
    for event in record.get('actual_model_events',[]):
        if event.get('status')!='completed':return 'backend_model_event_not_completed'
    def inspect(value):
        if isinstance(value,dict):
            if 'error' in value and value['error'] is not None and value['error'] is not False:
                return 'nested_backend_error'
            analysis=value.get('analysis_status')
            if analysis is not None and analysis not in ('completed','completed_no_finding','not_applicable','success'):
                return 'analysis_status_not_completed'
            if value.get('status') in ('failed','error','unknown','started_unknown','started'):
                return 'nested_status_not_completed'
            for item in value.values():
                failure=inspect(item)
                if failure:return failure
        elif isinstance(value,(list,tuple)):
            for item in value:
                failure=inspect(item)
                if failure:return failure
        return None
    return inspect(record['observation'])

def memory_entry(row,result):
    observations=result.get('observations') or result.get('inherited_observations') or []
    evidence=[{k:x[k] for k in ('tool','image_index','observation') if k in x}
              for x in observations if tool_failure_reason(x) is None]
    return {'question_id':row['question_id'],'question':row['question'],'options':row.get('options',{}),
            'previous_answer':result.get('answer'),'previous_model_reason':result.get('reason'),
            'previous_status':result.get('status'),'tool_evidence':evidence,
            'provenance':'earlier_model_output_not_ground_truth'}

def context(entries,max_chars=12000,max_entries=8):
    # Preserve whole JSON records; deterministic recent-first selection then chronological presentation.
    picked=[];used=0
    for e in reversed(entries[-max_entries:]):
        e=dict(e);e['tool_evidence']=[x for x in e['tool_evidence'] if len(json.dumps(x,ensure_ascii=False))<=4000]
        size=len(json.dumps(e,ensure_ascii=False))
        if used+size>max_chars:continue
        picked.append(e);used+=size
    picked.reverse()
    if not picked:return None,[]
    prompt=('Earlier questions about the EXACT SAME supplied original image(s), in chronological order. '
            'The prior answers and reasons are fallible model judgments, not reference labels. '
            'Tool observations are auxiliary evidence. Reinspect the original pixels for the CURRENT question; '
            'question wording and options may differ. Correct an earlier error when supported; do not copy '
            'its option letter or treat an earlier question as an established finding. No future questions, '
            'patient history or external-case skills are supplied.\n'+json.dumps(picked,ensure_ascii=False))
    return prompt,[e['question_id'] for e in picked]
