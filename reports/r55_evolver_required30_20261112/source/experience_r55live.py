"""EvolveR-inspired experience memory, with a fixed Qwen policy (no RL)."""
from copy import deepcopy
from hashlib import sha256
import json
import math

from online_memory_r49 import save_once
from skill_policy_r54 import buffer_select

from experience_feedback_r54 import DISTILL, copies_source, distillation_payload

EQUIVALENCE = """Decide whether the candidate and the supplied principles are
semantically equivalent in trigger, recommended action and exception. Sharing
a topic does not imply equivalence. Return {"equivalent_id":null} or an ID
exactly as supplied. Never broaden or rewrite the stored principle."""


def cosine(a, b):
    if len(a) != len(b) or not a:
        raise ValueError('experience_embedding_dimension_mismatch')
    denom = math.hypot(*a) * math.hypot(*b)
    return sum(x*y for x,y in zip(a,b))/denom if denom else 0.0


def score(card):
    return (card['successes']+1)/(card['uses']+2)


def rank(repo, vector):
    return sorted(
        ((sid, cosine(vector, card['vector']))
         for sid,card in repo['skills'].items() if card['status']=='active'),
        key=lambda item: (-item[1], item[0]),
    )


def search(repo, vector, top_k=3):
    return [
        {'id':sid, 'c':repo['skills'][sid]['c'], 'score':score(repo['skills'][sid])}
        for sid,_ in rank(repo,vector)[:top_k]
    ]


def valid_principle(value, steps):
    if not isinstance(value,dict) or value.get('principle') is None:
        return None
    card=value['principle']
    if not isinstance(card,dict) or set(card)!={'description','triples','polarity'}:
        return None
    desc=card['description']
    triples=card['triples']
    if not isinstance(desc,str) or not desc.strip() or len(desc)>800:
        return None
    if card['polarity'] not in ('guide','caution'):
        return None
    if not isinstance(triples,list) or not 1<=len(triples)<=4:
        return None
    if any(not isinstance(t,list) or len(t)!=3 or any(
        not isinstance(x,str) or not x.strip() or len(x)>120 for x in t) for t in triples):
        return None
    index=value.get('evidence_step')
    if type(index) is not int or not 0<=index<len(steps):
        return None
    return card


def evolve(service, snapshot, batch, wi, window, data, tools, config):
    """Only completed, released episodes are supplied by the common runner."""
    repo=deepcopy(snapshot)
    repo['clock']+=len(batch)
    repo['window']=wi+1
    for t in batch:
        # Exposure proxy: once per question for each delivered principle.
        for sid in set(t.get('activated_skill_ids',[])):
            card=repo['skills'][sid]
            card['uses']+=1
            card['successes']+=int(t['reward']>0)
    events=[]
    for t in buffer_select(batch,config):
        payload = distillation_payload(t, tools)
        value=service.meta('exp_distill_'+t['id'],DISTILL,payload)
        card=valid_principle(value,t['steps'])
        if card is None:
            events.append({'question':t['id'],'operation':'skip'})
            continue
        if copies_source(card, payload, t['id']):
            events.append({'question':t['id'],'operation':'skip_source_copy'})
            continue
        text=json.dumps(card,ensure_ascii=False,sort_keys=True)
        vector=service.embed(text)
        sid='exp_'+sha256(text.encode()).hexdigest()[:24]
        if sid in repo['skills']:
            match=sid
        else:
            neighbors=[{'id':i,'principle':repo['skills'][i]['c']}
                       for i,sim in rank(repo,vector)[:3] if sim>=.85]
            match=None
            if neighbors:
                verdict=service.meta('exp_equiv_'+t['id'],EQUIVALENCE,
                                     {'candidate':card,'neighbors':neighbors})
                match=verdict.get('equivalent_id')
                if not isinstance(match,str) or match not in {n['id'] for n in neighbors}:
                    match=None
        if match is None:
            repo['skills'][sid]={'c':card,'vector':vector,'status':'active',
                                 'sources':[t['id']],'uses':0,'successes':0}
            events.append({'question':t['id'],'operation':'add','id':sid})
        else:
            stored=repo['skills'][match]
            if t['id'] not in stored['sources']:
                stored['sources'].append(t['id'])
            events.append({'question':t['id'],'operation':'merge_source','id':match})
    if repo['clock']//60>snapshot['clock']//60:
        for sid,card in repo['skills'].items():
            if card['status']=='active' and score(card)<.30:
                card['status']='pruned'
                events.append({'operation':'prune','id':sid,'score':score(card)})
    save_once(window/'experience_events.json',events)
    return repo
