"""Label-blind applicability filtering and BM25. Python standard library only."""
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

TASKS = {'presence', 'location', 'comparison', 'severity', 'view', 'diagnosis', 'other'}
STOP = set('a an the is are was were be been being of in on at to for with and or this that there image images chest radiograph radiographs xray shown shows show patient following which what does do it any have has seen can'.split())
ALIASES = {'opacities': 'opacity', 'effusions': 'effusion', 'lungs': 'lung', 'enlarged': 'enlargement', 'cardiomegaly': 'cardiac_enlargement', 'pneumothoraces': 'pneumothorax'}

def tokens(text):
    text = re.sub(r'cardiac enlargement|heart enlargement|enlarged heart', 'cardiac_enlargement', text.lower())
    return [ALIASES.get(w, w) for w in re.findall(r'[a-z_]{3,}', text) if w not in STOP]

def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def infer_tasks(question):
    q = question.lower()
    result = set()
    for task, pattern in {
        'comparison': r'prior|previous|follow.up|interval|compared|change|increase|decrease',
        'location': r'where|location|located|which (lung|side|lobe)|left|right|bilateral',
        'severity': r'sever|mild|moderate|size|larger|smaller|extent',
        'view': r'view|projection|posteroanterior|anteroposterior|rotat|position',
        'diagnosis': r'diagnos|most likely|cause|differential',
        'presence': r'is there|are there|present|presence|any |does |has |have |evidence of'
    }.items():
        if re.search(pattern, q):
            result.add(task)
    return result or {'other'}

def validate_card(c, tools):
    required = {'id','source_ids','topic','tasks','requires_pair','required_question_terms','actions','avoid','source_evidence'}
    if not isinstance(c, dict) or set(c) != required:
        raise ValueError('card_schema')
    if not isinstance(c['id'], str) or not c['id']:
        raise ValueError('card_id')
    if not isinstance(c['source_ids'], list) or not c['source_ids'] or not all(isinstance(x,str) and x for x in c['source_ids']):
        raise ValueError('source_ids')
    for field in ('topic','avoid','source_evidence'):
        if not isinstance(c[field], str) or not c[field].strip() or len(c[field]) > 1200:
            raise ValueError('card_text:' + field)
    if not isinstance(c['tasks'], list) or not c['tasks'] or not set(c['tasks']) <= TASKS:
        raise ValueError('tasks')
    if type(c['requires_pair']) is not bool:
        raise ValueError('requires_pair')
    if not isinstance(c['required_question_terms'], list) or not all(isinstance(x,str) and tokens(x) for x in c['required_question_terms']):
        raise ValueError('required_question_terms')
    if not isinstance(c['actions'], list) or not 1 <= len(c['actions']) <= 3:
        raise ValueError('actions')
    for action in c['actions']:
        if not isinstance(action,dict) or set(action) != {'observe','tool','when','stop'}:
            raise ValueError('action_schema')
        if not all(isinstance(v,str) and v.strip() and len(v)<=400 for v in action.values()):
            raise ValueError('action_text')
        if action['tool'] != 'none' and action['tool'] not in tools:
            raise ValueError('unregistered_tool')
    return c

def load_bank(path, expected_sha, tools):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError('bank_hash_changed')
    bank = json.loads(raw)
    if bank.get('schema') != 'cxr_skill_v2' or bank.get('source_only') is not True or bank.get('frozen') is not True:
        raise ValueError('not_frozen_source_bank')
    cards = [validate_card(c, tools) for c in bank['items']]
    if len({c['id'] for c in cards}) != len(cards):
        raise ValueError('duplicate_card_id')
    return cards

def document(c):
    return ' '.join([c['topic'], *c['tasks'], *c['required_question_terms'], c['avoid'],
                     *[v for a in c['actions'] for k,v in a.items() if k!='tool']])

def select(row, cards, tools, *, max_cards=2, min_overlap=2, max_chars=2200):
    # No labels, source answers, dataset names or image filenames enter ranking.
    if not 0 <= max_cards <= 2 or min_overlap < 2 or max_chars < 1:
        raise ValueError('invalid_retrieval_settings')
    question = row['question']
    qterms = set(tokens(question))
    options = row.get('options', {})
    query = set(tokens(question + ' ' + ' '.join(options.values())))
    tasks = infer_tasks(question)
    paired = len(row['images']) >= 2 and 'comparison' in tasks
    docs = [tokens(document(c)) for c in cards]
    avg = sum(map(len, docs))/max(1,len(docs)) or 1
    df = Counter(t for d in docs for t in set(d))
    candidates, audit = [], []
    for c,d in zip(cards,docs):
        validate_card(c, tools)
        reason = None
        if not tasks.intersection(c['tasks']): reason = 'task_mismatch'
        elif c['requires_pair'] and not paired: reason = 'paired_images_unavailable'
        elif any(not set(tokens(term)) <= qterms for term in c['required_question_terms']): reason = 'required_context_unknown'
        overlap = qterms.intersection(d)
        if reason is None and len(overlap)<min_overlap: reason = 'weak_question_match'
        tf = Counter(d)
        score = sum(math.log(1+(len(docs)-df[t]+.5)/(df[t]+.5))*tf[t]*2.5 /
                    (tf[t]+1.5*(.25+.75*len(d)/avg)) for t in query if tf[t])
        audit.append({'id':c['id'],'score':score,'question_overlap':sorted(overlap),'rejection':reason})
        if reason is None: candidates.append((score,c))
    picked=[]; used=0
    for score,c in sorted(candidates,key=lambda x:(-x[0],x[1]['id'])):
        item = {k:c[k] for k in ('id','topic','actions','avoid')}
        size = len(json.dumps(item,ensure_ascii=False))
        if len(picked) >= max_cards: break
        if used+size > max_chars: continue
        picked.append(item); used+=size
    trace={'question_id':row['question_id'],'inferred_tasks':sorted(tasks),'pair_available':paired,
           'selected_ids':[x['id'] for x in picked], 'candidates':audit,
           'settings':{'max_cards':max_cards,'min_overlap':min_overlap,'max_chars':max_chars}}
    if not picked: return None,trace
    prefix=('Optional source-derived action checks, not current-patient findings. '
            'Apply only when the current original images and question support the conditions. '
            'No tool is mandatory. Do not change an answer merely because a prior case differed. '
            'Unknown is not negative evidence. You may ignore all cards and answer directly.\n')
    return prefix+json.dumps(picked,ensure_ascii=False),trace
