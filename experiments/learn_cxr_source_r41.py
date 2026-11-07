"""Generate source-only structured cards using actual source images and feedback.
The source package must already be isolated from ALL target patients/images.
Image map is explicit; this module never guesses image paths or fetches target data.
"""
import argparse
import base64
import hashlib
import json
import mimetypes
from pathlib import Path
import sys
from cxr_skill_r41_base import validate_card as validate_base

def validate_card(c,tools):
    if c.get('kind') not in ('task','specific'):raise ValueError('kind')
    return validate_base({k:v for k,v in c.items() if k!='kind'},tools)

SYSTEM='''You learn an OPTIONAL action skill from one isolated historical CXR case.
Read the supplied ORIGINAL images, full questions/options, old predictions, released
correct answers, and tool observations. Feedback is source-only. Distinguish an
observed visual fact from an old model claim. If the source is not CXR, image binding
is unclear, or feedback cannot support a transferable action, return {"skip":"reason"}.
Do not generate a diagnosis lookup table, copy a correct option, require tool use,
or invent patient history. The card must help choose a concrete observation or
an available tool and say when enough evidence exists to stop.
Prefer a transferable TASK action card when source evidence supports it: location/laterality,
count/extent, morphology, spatial relation, or temporal comparison. The skill should
identify which observable attribute separates complete answer options and which original
region/image or available tool can resolve it. Do not transfer source diagnoses or laterality.
A task card must keep necessary clinical/context preconditions; if abstraction loses them,
return a specific card or skip. Unknown evidence is neither positive nor negative.
Do not prescribe arbitrary measurements or force tools; retain concrete stopping conditions.
Return one bare JSON object with EXACT fields:
{"kind":"task or specific", "id":"source-id", "source_ids":["source-id"], "topic":"concise concepts",
 "tasks":["presence|location|comparison|severity|view|diagnosis|count|morphology|relation|other"],
 "requires_pair":false, "required_question_terms":[],
 "actions":[{"observe":"specific region/attribute to inspect",
 "tool":"none or exact registered name", "when":"precondition",
 "stop":"sufficient evidence or tool insufficiency condition"}],
 "avoid":"specific misleading inference to avoid",
 "source_evidence":"old mistake, released correction and supporting source observation; identify uncertainty"}.
Use 1-3 actions. tasks is a subset of the ten literal labels, not the pipe string.
If a skill requires prior imaging, requires_pair MUST be true. If it needs postoperative
history or another contextual fact, required_question_terms MUST contain the relevant
words/phrases that must actually occur in a target question. A general-purpose keyword
like chest is NOT an applicability condition. Do not omit a clinically necessary
condition to increase retrieval. If such applicability cannot be expressed, skip.
Do not assert that tools were responsible for a correction without source evidence.
Keep each action field <=400 characters and all other text fields <=1200 characters.
'''

def main():
    p=argparse.ArgumentParser()
    for k in ('config','source','image-map','out'): p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--source-sha256',required=True)
    p.add_argument('--execute',action='store_true'); p.add_argument('--api-key-stdin',action='store_true')
    a=p.parse_args()
    from run_cxr_vqa_toolsets import PaidCalls, read, save, exclusive_lock
    raw=a.source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=a.source_sha256: raise ValueError('source_changed')
    source=json.loads(raw); mapping=read(a.image_map)
    if source.get('source_only') is not True: raise ValueError('source_only_required')
    cfg=read(a.config); protocol=read(cfg['protocol']); runtime=read(cfg['runtime'])
    tools=runtime['arms']['M-S']['tools']; messages_by_case={}; manifest={}
    for case in source['cases']:
        cid=str(case['case_id'])
        if cid in messages_by_case: raise ValueError('duplicate_source')
        if not mapping.get(cid): raise ValueError('original_images_required:'+cid)
        content=[{'type':'text','text':json.dumps(case,ensure_ascii=False)}]; manifest[cid]=[]
        for img in mapping[cid]:
            # Mapping entries carry image labels identical to source figure references.
            if set(img)!={'label','path'}: raise ValueError('image_map_schema')
            path=Path(img['path']).resolve(); data=path.read_bytes()
            mime=mimetypes.guess_type(path.name)[0]
            if mime not in ('image/jpeg','image/png'): raise ValueError('image_type')
            manifest[cid].append({'label':img['label'],'sha256':hashlib.sha256(data).hexdigest()})
            content.extend([{'type':'text','text':'Source original: '+img['label']},
                            {'type':'image_url','image_url':{'url':'data:'+mime+';base64,'+base64.b64encode(data).decode()}}])
        messages_by_case[cid]=[{'role':'system','content':SYSTEM+'\nRegistered tools: '+json.dumps(tools)},
                               {'role':'user','content':[{'type':'text','text':'Use id and source_ids equal to the following case_id, not question IDs: '+cid}]+content}]
    frozen={'source_sha256':a.source_sha256,'images':manifest,'system':SYSTEM,'tools':tools,'protocol':protocol}
    if not a.execute:
        print(json.dumps({'source_cases':len(messages_by_case),'max_paid_calls':len(messages_by_case),'paid_calls':0}));return
    if not a.api_key_stdin: raise ValueError('stdin_key_required')
    key=sys.stdin.readline().strip()
    if not key: raise ValueError('missing_key')
    a.out.mkdir(parents=True,exist_ok=True)
    with exclusive_lock(a.out/'.learning.lock'):
        marker=a.out/'source_v2_manifest.json'
        if marker.exists():
            if read(marker)!=frozen: raise ValueError('source_manifest_changed')
        else: save(marker,frozen)
        paid=PaidCalls(cfg,protocol,a.out,key)
        cards=[]; rejected=[]
        for cid,messages in messages_by_case.items():
            # Unknown sends deliberately raise and stop. No automatic resend.
            response=paid.call({'question_id':cid},'M-S',1,messages)
            try:
                obj=json.loads(response)
                if isinstance(obj,dict) and set(obj)=={'skip'}:
                    rejected.append({'source_id':cid,'reason':obj['skip']});continue
                validate_card(obj,tools)
                if obj['id']!=cid or obj['source_ids']!=[cid]: raise ValueError('source_binding')
                cards.append(obj)
            except (ValueError,TypeError,KeyError) as exc:
                rejected.append({'source_id':cid,'reason':str(exc)})
        if not cards: raise ValueError('no_valid_cards')
        bank={'schema':'cxr_action_skill_r41_candidates','source_only':True,'frozen':False,'source_sha256':a.source_sha256,
              'items':cards,'rejected':rejected,'source_image_manifest':manifest}
        path=a.out/'candidate_bank_r41.json'
        if path.exists():
            if read(path)!=bank: raise ValueError('frozen_bank_changed')
        else: save(path,bank)
        print(json.dumps({'cards':len(cards),'rejected':len(rejected),'bank_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}))

if __name__=='__main__': main()
