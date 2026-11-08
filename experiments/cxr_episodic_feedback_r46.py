"""Source-only supervised episodic memory. No evaluator labels enter retrieval."""
import base64
from collections import Counter
import hashlib
import io
import json
import math
from pathlib import Path
import re

from PIL import Image
from cxr_author_alignment import extract

EXPERIMENT='episodic_feedback_r46_20261108'
ARMS=('P0','P1')
BASE=('Answer the current visual question using the supplied original image. '
      'Give only the shortest direct answer, yes/no or the requested category; no explanation. '
      'If unsupported, answer Unknown. No patient history or prior examination is supplied. '
      'Any retrieved examples are different training cases, not facts about the current patient; '
      'use their guidelines only when applicable and judge the current image independently.')
SOURCE_SYSTEM=('Answer the current source visual question from the original image. No annotation is supplied. '
 'Return JSON with answer (short direct answer), reason, and case_description '
 '(brief visual description before receiving any reference feedback). '
 'Retrieved records are earlier, different training cases, not facts about the current image. '
 'Do not invent history or tools; if unsupported say Unknown.')
REFLECTION_SYSTEM=('Reflect on this completed training case after its dataset annotation was revealed. '
 'The annotation is a short answer, not a complete radiology report. '
 'Return JSON with sigma (one sentence contrasting the recorded model answer with the annotation) '
 'and gamma (one conditional executable checking guideline). '
 'Do not invent an error cause, history, tool trajectory, or a finding not established by the supplied evidence. '
 'Do not generalize a Yes/No label to other patients, recommend always choosing a label, or use future examples. '
 'If the answer agrees, acknowledge that no error is demonstrated rather than inventing one.')


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def rows(path):return [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines() if s.strip()]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def object_reply(raw):
    if not isinstance(raw,str):return {}
    text=raw.strip();fence=re.fullmatch(r'```(?:json)?\s*\n?(.*?)\n?```',text,flags=re.I|re.S)
    if fence:text=fence[1].strip()
    try:value=json.loads(text)
    except (ValueError,TypeError):return {}
    return value if isinstance(value,dict) else {}


def image_info(row,data):
    assert len(row['images'])==1
    path=(Path(data)/row['images'][0]).resolve();assert path.is_relative_to(Path(data).resolve())
    blob=path.read_bytes()
    with Image.open(io.BytesIO(blob)) as im:
        media=Image.MIME[im.format];rgb=im.convert('RGB');rgb.load();size=list(rgb.size)
        pixels=hashlib.sha256(json.dumps(size).encode()+rgb.tobytes()).hexdigest()
        values=list(rgb.convert('L').resize((16,16)).getdata())
    mean=sum(values)/len(values);centered=[x-mean for x in values];norm=math.sqrt(sum(x*x for x in centered))
    vector=[x/norm if norm else 0.0 for x in centered]
    encoded=base64.b64encode(blob).decode('ascii');assert base64.b64decode(encoded,validate=True)==blob
    return {'uri':'data:'+media+';base64,'+encoded,'media_type':media,'bytes_sha256':hashlib.sha256(blob).hexdigest(),
            'pixel_sha256':pixels,'size':size,'image_vector':vector}


def public_row(row):
    return {k:row[k] for k in ['question_id','question','images','image_id','source']}


def tokens(text):return re.findall(r'[a-z0-9]+',text.lower())


def retrieve(row,info,episodes,k=2,max_chars=8000):
    allowed=[e for e in episodes if e['image_pixel_sha256']!=info['pixel_sha256'] and e['question_id']!=row['question_id']]
    # Fit vocabulary/IDF only on the currently available source prefix, never
    # on future cases, gold answers, retrospective text or guidelines.
    documents=[tokens(e['question']+' '+e['phi']) for e in allowed]
    df=Counter(t for doc in documents for t in set(doc));n=len(documents)
    def vector(words):
        tf=Counter(words);v={t:(1+math.log(c))*(1+math.log((n+1)/(df[t]+1))) for t,c in tf.items() if t in df}
        norm=math.sqrt(sum(x*x for x in v.values()));return {t:x/norm for t,x in v.items()} if norm else {}
    query=vector(tokens(row['question']));ranking=[]
    for e,doc in zip(allowed,documents):
        text_score=sum(query.get(t,0)*v for t,v in vector(doc).items())
        image_cos=sum(a*b for a,b in zip(info['image_vector'],e['image_vector']))
        score=.7*text_score+.3*(image_cos+1)/2
        ranking.append((score,e))
    ranking.sort(key=lambda x:(-x[0],x[1]['question_id']))
    selected=[];used=0
    for score,e in ranking[:k]:
        item={key:e[key] for key in ['question_id','question','phi','tau','y_hat','y','sigma','gamma']}
        size=len(json.dumps(item,ensure_ascii=False))
        if used+size>max_chars:continue
        selected.append({'similarity':score,'episode':item});used+=size
    return {'included_ids':[x['episode']['question_id'] for x in selected],
            'examples':selected,'candidate_source_ids':[e['question_id'] for e in allowed],
            'query_uses_reference':False,'retrieval_fit_uses_future_cases':False,
            'similarity':'0.7 source-prefix TF-IDF(question + pre-feedback case description) cosine + 0.3 rescaled 16x16 grayscale cosine',
            'memory_chars':used}


def messages(row,info,system,context=None,feedback=None):
    assert not any(k in row for k in ['answer','reference','content_type'])
    text='Current question: '+row['question']
    if context and context['examples']:
        text+='\n\nEarlier different training cases (their y fields are source annotations):\n'+json.dumps(context['examples'],ensure_ascii=False)
    if feedback is not None:text+='\n\nFeedback for this ALREADY ANSWERED source case only:\n'+json.dumps(feedback,ensure_ascii=False)
    return [{'role':'system','content':system},{'role':'user','content':[
        {'type':'text','text':text},{'type':'image_url','image_url':{'url':info['uri']}}]}]


def terminal(raw,qid):
    choice=raw['choices'][0];msg=choice['message']
    final=choice.get('finish_reason')=='stop' and not msg.get('tool_calls') and not msg.get('function_call')
    answer=extract(msg.get('content'),qid) if final else None
    aux=object_reply(msg.get('content')) if final else {}
    return {'answer':answer.answer if answer else None,'extraction':answer.mechanism if answer else 'nonterminal_reply',
            'reason':aux.get('reason') if isinstance(aux.get('reason'),str) else None,
            'phi':aux.get('case_description') if isinstance(aux.get('case_description'),str) else None,
            'aux':aux,'final':final}


def make_protocol(source,development,data):
    assert len(source)==12 and len(development)==27
    assert len({x['question_id'] for x in source+development})==39
    infos={x['question_id']:image_info(x,data) for x in source+development}
    a={infos[x['question_id']]['pixel_sha256'] for x in source};b={infos[x['question_id']]['pixel_sha256'] for x in development}
    assert len(a)==12 and len(b)==8 and not a&b,'source_development_image_overlap'
    return {'experiment_id':EXPERIMENT,'model':'qwen3.7-plus','temperature':.2,'top_p':.95,
      'enable_thinking':False,'max_output_tokens':512,'request_archive':'image_base64_content_addressed_v1',
      'budget':{'existing_shared_ledger':False,'enforce_money_cap':False},
      'source_question_ids':[x['question_id'] for x in source],'development_question_ids':[x['question_id'] for x in development],
      'source_cases':12,'development_questions':27,'development_images':8,'source_inference_calls':12,
      'source_reflection_calls':12,'development_main_calls_per_arm':27,'total_new_main_ceiling':78,
      'tools':0,'tau':'empty actual medical-tool trajectory; direct answering, not fabricated agent actions',
      'source_feedback':'save prediction before opening current per-case source label; reflect; append accepted episode; subsequent source questions retrieve past episodes only',
      'development_feedback':'none; frozen source-only E for P1, P0 no E; no development answers/reasons written back',
      'source_system':SOURCE_SYSTEM,'reflection_system':REFLECTION_SYSTEM,'development_system':BASE,
      'top_k':2,'memory_max_chars':8000,'source_image_pixel_ids':sorted(a),'development_image_pixel_ids':sorted(b),
      'image_bytes_sha256':{q:v['bytes_sha256'] for q,v in infos.items()},
      'retrieval':'fixed .7 lexical TF-IDF + .3 grayscale descriptor cosine; not a learned clinical image embedding; no label/summary/guideline in fit',
      'sampling':'one sample per phase/case; no unknown-sent retry; stop on transport/error',
      'paired_order':'development input order; P0/P1 for even pair index, reversed for odd',
      'metric':'existing common explicit-answer adapter + M4CXR normalized EM; JSON diagnostic only; full27 denominator',
      'exposure':'training source and previously used development cohort; not unseen/official SOTA/independent-patient proof',
      'success_signal':'net>=2/27 and harms<=1 only a development priority signal; no automatic target expansion',
      'overall_best_target_claim':False}
