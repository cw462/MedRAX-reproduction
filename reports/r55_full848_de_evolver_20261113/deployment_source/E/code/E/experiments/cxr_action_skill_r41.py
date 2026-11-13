"""Pure label-blind retrieval. Existing v2 cards remain specific, never generalized silently."""
import json, hashlib
from pathlib import Path
import cxr_skill_r41_base as old

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def rows(path): return [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines() if x.strip()]
def write(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f: json.dump(obj,f,ensure_ascii=False,indent=2)
def load(path,tools):
    bank=read(path)
    if bank.get('source_only') is not True or bank.get('frozen') is not True: raise ValueError('source_bank_not_frozen')
    if bank.get('schema') not in ('cxr_skill_v2','cxr_skill_r41_base','cxr_action_skill_r41'): raise ValueError('bank_schema')
    cards=[]
    for item in bank['items']:
        c=dict(item); kind=c.pop('kind','specific')
        if kind not in ('task','specific'): raise ValueError('kind')
        old.validate_card(c,tools)
        if kind=='task' and 'other' in c['tasks']: raise ValueError('task_card_needs_explicit_task')
        cards.append(dict(c,kind=kind))
    if len({c['id'] for c in cards})!=len(cards):raise ValueError('duplicate_card')
    return cards

def select(row,cards,tools):
    # Use ONLY question, options and image count. Never labels, historical answers, filenames or dataset names.
    clean={k:row[k] for k in ('question_id','question','images','options') if k in row}
    if not isinstance(clean.get('options',{}),dict): clean['options']={str(i):str(v) for i,v in enumerate(clean['options'])}
    candidates=[]; traces=[]
    for card in cards:
        c={k:v for k,v in card.items() if k!='kind'}
        cond,trace=old.select(clean,[c],tools,max_cards=1)
        info=trace['candidates'][0]
        # Task cards need task + explicit preconditions, but not arbitrary lexical overlap.
        if card['kind']=='task' and info['rejection']=='weak_question_match':info['rejection']=None
        traces.append(info)
        if info['rejection'] is None: candidates.append(c)
    # Rank eligible cards together using BM25 over their full procedural text.
    # old.select's overlap filter is bypassed only after the audited applicability pass.
    docs=[old.tokens(old.document(c)) for c in cards]; avg=sum(map(len,docs))/max(1,len(docs)) or 1
    df=old.Counter(t for d in docs for t in set(d))
    opts=clean.get('options',{}); opts=opts.values() if isinstance(opts,dict) else opts
    query=set(old.tokens(clean['question']+' '+' '.join(map(str,opts))))
    scored=[]
    for c in candidates:
        d=old.tokens(old.document(c));tf=old.Counter(d)
        score=sum(old.math.log(1+(len(docs)-df[t]+.5)/(df[t]+.5))*tf[t]*2.5/(tf[t]+1.5*(.25+.75*len(d)/avg)) for t in query if tf[t])
        item={k:c[k] for k in ('id','topic','actions','avoid')}
        if len(json.dumps(item,ensure_ascii=False))<=2200:scored.append((score,c['id'],item))
    scored.sort(key=lambda x:(-x[0],x[1])); picked=scored[0][2] if scored else None
    conditioning=None if picked is None else ('Optional source-derived action skill; not findings of this patient. Apply its preconditions to the original images. No tool is mandatory.\n'+json.dumps(picked,ensure_ascii=False))
    return {'selected_ids':[] if picked is None else [picked['id']], 'conditioning':conditioning,'candidates':traces}
