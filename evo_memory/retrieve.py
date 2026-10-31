from collections import Counter
from math import log
import re
from .io import token_estimate
from .prompts import episode_text,rule_text

STOP=set('a an the this that these those of to in on at for by from with without as is are was were be been and or but it its which what who how does do based provided shown shows showing image images figure figures fig finding findings patient patients question option options following most likely chest radiograph radiographs xray cxr ct scan scans please only'.split())


def terms(text):return [w for w in re.findall(r'[a-z][a-z0-9-]*',str(text).casefold()) if len(w)>2 and w not in STOP]
def current_modality(stem):
    found=[]
    if re.search(r'(?i)chest\s*(?:x[ -]?rays?|radiograph\w*)|\bCXR\b',stem):found.append('CXR')
    if re.search(r'(?i)\bCT\b|computed tomography',stem):found.append('CT')
    if re.search(r'(?i)\bMRI\b|ultrasound',stem):found.append('other')
    return found[0] if len(set(found))==1 else 'unknown'


def bm25(query,documents):
    q=Counter(terms(query));tokens=[terms(d) for d in documents];n=len(tokens)
    if not n:return []
    avg=sum(map(len,tokens))/n or 1;df=Counter(w for doc in tokens for w in set(doc));scores=[]
    for doc in tokens:
        tf=Counter(doc);score=0.
        for word,freq in q.items():
            f=tf[word]
            if f:score+=freq*log(1+(n-df[word]+.5)/(df[word]+.5))*f*2.5/(f+1.5*(.25+.75*len(doc)/avg))
        scores.append(score)
    return scores


def retrieve(store,row,*,step,current_case,seed_cases,past_cases,top_k_e=3,top_k_s=2,limit=1600):
    from experiments.v12_evidence import question_parts
    stem,options=question_parts(row['question']);option_text='\n'.join(options.values());modality=current_modality(stem)
    episodes,rules=store.visible(step=step,current_case=current_case,seed_cases=seed_cases,past_cases=past_cases)
    episodes=[e for e in episodes if modality=='unknown' or e['modality']==modality]
    rules=[r for r in rules if modality=='unknown' or modality in r['source_modalities']]
    def rank(items,kind):
        docs=[' '.join(str(e.get(k,'')) for k in (('case_pattern','decisive_difference','inspection_action') if kind=='E' else ('condition','action','limitation'))) for e in items]
        first=bm25(stem,docs);second=bm25(option_text,docs);ranked=[]
        for item,doc,a,b in zip(items,docs,first,second):
            overlap=sorted(set(terms(stem+' '+option_text))&set(terms(doc)));score=a+.25*b
            if overlap and score>0:ranked.append({'id':item['id'],'score':score,'stem_score':a,'option_score':b,'overlap':overlap,'item':item})
        maximum=max([x['score'] for x in ranked]+[1e-12])
        for value in ranked:
            r=value['item'];value['normalized_relevance']=value['score']/maximum
            value['association_smooth_prior']=(r['n_correct_when_selected']+1)/(r['n_selected']+2) if kind=='S' else None
            value['rank_score']=.8*value['normalized_relevance']+.2*value['association_smooth_prior'] if kind=='S' else value['score']
        return sorted(ranked,key=lambda x:(-x['rank_score'],x['id']))
    erank=rank(episodes,'E');srank=rank(rules,'S');selected_e=[];selected_s=[];parts=[]
    # Reserve possible S context before filling E; both groups use the same
    # per-entry projection and E top-K; total length may reduce accepted entries.
    schoices=srank[:top_k_s]
    st=[rule_text(v['item'],i+1) for i,v in enumerate(schoices)]
    s_budget=sum(token_estimate(s) for s in st)
    for value in erank[:top_k_e]:
        text=episode_text(value['item'],len(selected_e)+1)
        if sum(token_estimate(p) for p in parts)+token_estimate(text)+s_budget<=limit:
            selected_e.append(value['item']);parts.append(text)
    for value,text in zip(schoices,st):
        if token_estimate('\n'.join(parts+[text]))<=limit:selected_s.append(value['item']);parts.append(text)
    context='\n'.join(parts) if parts else 'No relevant historical memory was selected.'
    def audit(values):return [{k:v for k,v in x.items() if k!='item'} for x in values]
    return {'step':step,'current_case_id':current_case,'current_modality_from_stem':modality,
            'query_stem':stem,'query_options_without_letters':option_text,'memory_version':store.state['version'],
            'visible_episode_ids':[x['id'] for x in episodes],'visible_rule_ids':[x['id'] for x in rules],
            'candidate_E':audit(erank),'candidate_S':audit(srank),'selected_E_ids':[x['id'] for x in selected_e],
            'selected_S_ids':[x['id'] for x in selected_s],'memory_context':context,'context_token_estimate':token_estimate(context),
            'projection_contains_source_case_or_question_ids':False},selected_e,selected_s,{'episodes':episodes,'rules':rules}
