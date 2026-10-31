"""Sourced static knowledge retrieval. No diagnostic decisions or label ingestion.

Only curated knowledge cards are indexed. Candidate hypotheses are retrieval hints,
never observations. Optional dense vectors come from an actual neural encoder.
"""
from __future__ import annotations
import collections
import json
import math
import re
import functools
from pathlib import Path

STOP = set('a an the is are was were be been being of to in for on with and or as at by from it this that which what does do can may should would image images patient patients case question chest xray radiograph radiographs finding findings'.split())
STOP.update({'no','not','without','unknown','affirmed','negated','asserted_as_supplied'})
MODALITY_ALIASES = {'cxr':'radiograph','x-ray':'radiograph','xray':'radiograph','chest x-ray':'radiograph','chest radiograph':'radiograph','chest radiography':'radiograph','x_ray':'radiograph','ct':'ct','computed tomography':'ct','ctpa':'ct','hrct':'ct','contrast_ct':'ct','cta':'ct','us':'ultrasound','胸片':'radiograph'}
TASK_ALIASES = {'detect':'detection','localization':'localization','localisation':'localization','location':'localization','locate':'localization','diagnostic':'diagnosis','classification':'classification','comparison':'comparison','compare':'comparison','relationship':'relation','relationship reasoning':'relation','relation':'relation','characterization':'description','feature description':'description','feature_description':'description','features':'description','描述':'description','定位':'localization','检测':'detection','诊断':'diagnosis','比较':'comparison','关系':'relation','分类':'classification'}
EXCLUDED_TYPES = {'method','methods','evaluation','dev_analysis','development_analysis','benchmark_answer','test_answer','experience','case_trajectory','research_method','experiment_plan'}
DEFAULT = {'top_k':3,'candidate_k':30,'rrf_k':60,'max_per_source':1,'min_main_matches':1,'dense_min_cosine':0.36,'hypothesis_weight':0.2,'min_relative_score':0.55,'parent_max_chars':2000,'max_context_chars':6000}


def tokens(s):
    s = str(s or '').lower()
    english = [w for w in re.findall(r"[a-z0-9]+(?:[-'][a-z0-9]+)*", s) if w not in STOP and len(w)>1]
    chinese = re.findall(r'[\u3400-\u9fff]+',s)
    return english + [x[i:i+2] for x in chinese for i in range(max(1,len(x)-1))]


def strings(value):
    if value is None: return []
    if isinstance(value, str): return [value]
    if isinstance(value, dict): return [json.dumps(value,ensure_ascii=False)]
    return [str(v) if not isinstance(v,dict) else json.dumps(v,ensure_ascii=False) for v in value]


def modality(value):
    return MODALITY_ALIASES.get(str(value).lower().strip(), str(value).lower().strip())


def tasks(value):
    return [TASK_ALIASES.get(v.lower().strip().replace('_',' '),TASK_ALIASES.get(v.lower().strip(),v.lower().strip())) for v in strings(value)]


def canonical_card(card):
    c=dict(card)
    c['knowledge_id']=str(c.get('knowledge_id') or c.get('card_id') or c.get('id') or '')
    c['source_id']=str(c.get('source_id') or c.get('document_id') or '')
    if not c['knowledge_id'] or not c['source_id']: raise ValueError('Each card requires knowledge_id and source_id')
    c['title']=c.get('title') or c.get('source_section') or c['knowledge_id']
    c['keywords']=c.get('keywords') or c.get('retrieval_terms_en') or c.get('keywords_en',[])
    c['task_scope']=c.get('task_scope') or c.get('task_tags') or c.get('task_types',[])
    c['required_patient_evidence']=c.get('required_patient_evidence') or c.get('required_evidence',[])
    c['source_pages']=c.get('source_pages') or c.get('pages',[])
    c['limitations']=c.get('limitations') or c.get('limits',[])
    for key in ('title','summary_zh','summary_en'):
        c[key]=str(c.get(key) or (c.get('summary','') if key=='summary_en' else ''))
    for key in ('keywords','modality','task_scope','required_patient_evidence','limitations','source_pages'):
        c[key]=strings(c.get(key))
    c['modality']=[modality(x) for x in c['modality']]
    c['task_scope']=tasks(c['task_scope'])
    c['source_file']=str(c.get('source_file',''))
    c['kind']=str(c.get('kind',c.get('card_type',c.get('knowledge_type','static_medical_knowledge')))).lower()
    return c


def card_text(c):
    # Omit study labels, developer notes, diagnostic answers, and trajectory text.
    return '\n'.join([c['title'],c['summary_en'],c['summary_zh'],' '.join(c['keywords']),
                       ' '.join(c['required_patient_evidence']),' '.join(c['limitations'])])


def dense_card_text(c):
    # MiniLM shipped example is English; bilingual cards carry English summaries.
    return '\n'.join([c['title'],c['summary_en'] or c['summary_zh'],' '.join(c['keywords']),
                       ' '.join(c['required_patient_evidence'])])


class BM25:
    def __init__(self, documents, k1=1.5,b=0.75):
        self.docs=[collections.Counter(tokens(x)) for x in documents]
        self.lengths=[sum(x.values()) for x in self.docs]
        self.avg=sum(self.lengths)/max(len(self.docs),1)
        self.df=collections.Counter(t for d in self.docs for t in d)
        self.k1,self.b=k1,b
    def scores(self,query):
        result=[]
        for doc,n in zip(self.docs,self.lengths):
            score=0.0
            for term in set(tokens(query)):
                f=doc[term]
                if not f: continue
                idf=math.log(1+(len(self.docs)-self.df[term]+.5)/(self.df[term]+.5))
                score+=idf*f*(self.k1+1)/(f+self.k1*(1-self.b+self.b*n/(self.avg or 1)))
            result.append(score)
        return result


def normalized_query(q):
    q=dict(q)
    observed=[]; hypotheses=strings(q.get('candidate_hypotheses'))
    for item in q.get('visible_evidence',[]):
        if isinstance(item,str):
            # A free-text observation must still preserve its original negation.
            item={'text':item,'status':'asserted_as_supplied','source':'user_supplied'}
        item=dict(item)
        status=str(item.get('status','unknown')).lower()
        if status in {'hypothesis','suspected','possible','candidate','uncertain'}:
            hypotheses.append(item.get('text') or item.get('entity',''))
        else:
            item['status']=status
            observed.append(item)
    return {'question_stem':str(q.get('question_stem',q.get('query',''))),
            'visible_evidence':observed,'candidate_hypotheses':hypotheses,
            'missing_attributes':strings(q.get('missing_attributes')),
            'modality':modality(q.get('modality','unknown')),
            'task':tasks(q.get('task',q.get('task_scope',[]))),
            'population':str(q.get('population','unknown')).lower()}


def evidence_text(e):
    return ' '.join(str(e.get(k,'')) for k in ['entity','attribute','value','text','status','laterality','time'])


def query_text(q):
    return '\n'.join([q['question_stem'],' '.join(evidence_text(x) for x in q['visible_evidence']),
                      ' '.join(q['missing_attributes'])])


def scope(c,q):
    reasons=[]; penalties=[]; multiplier=1.0
    cm=set(c['modality'])-{'any','all','unknown','unspecified','general'}
    if q['modality'] not in {'unknown','any',''} and cm and q['modality'] not in cm:
        return False,0.0,['modality_mismatch'],[]
    if cm and q['modality'] in {'unknown','any',''}: penalties.append('query_modality_unknown');multiplier*=.92
    ct=set(c['task_scope'])-{'any','all','general','unknown'}
    if ct and q['task'] and not ct.intersection(q['task']):
        return False,0.0,['task_scope_mismatch'],[]
    pop=set(x.lower() for x in strings(c.get('population')))-{'all','any','general','unknown',''}
    if q['population'] not in {'unknown','any',''} and pop and q['population'] not in pop:
        return False,0.0,['population_mismatch'],[]
    if cm and q['modality'] in cm: reasons.append('modality_match')
    if ct.intersection(q['task']): reasons.append('task_scope_match')
    if not cm: reasons.append('modality_scope_unspecified')
    if not ct: reasons.append('task_scope_unspecified')
    return True,multiplier,reasons,penalties


def negation_assessment(c,q):
    """Exact structured prerequisites only; never invert a general rule by keyword.

    Optional applicability_conditions use {entity, attribute, value, status}.
    Absence/unknown are distinct; unmet conditions prevent recommendation use,
    but do not hide the educational/checking card itself.
    """
    conflicts=[]; unmet=[]
    for condition in c.get('applicability_conditions',[]):
        if not isinstance(condition,dict): continue
        matches=[e for e in q['visible_evidence'] if str(e.get('entity','')).lower()==str(condition.get('entity','')).lower()
                 and (not condition.get('attribute') or str(e.get('attribute','')).lower()==str(condition['attribute']).lower())]
        if not matches:
            unmet.append(condition);continue
        expected=condition.get('status','affirmed')
        accepted={'affirmed':{'affirmed','present','positive'},'negated':{'negated','absent','negative'}}.get(expected,{expected})
        if not any(e.get('status') in accepted and (condition.get('value') is None or e.get('value')==condition['value']) for e in matches):
            conflicts.append({'condition':condition,'observations':matches})
    # Preserve explicit negative evidence, even when no formal condition exists.
    negatives=[e for e in q['visible_evidence'] if e.get('status') in {'negated','absent','negative'} or re.search(r'\b(no|without|absent|negative)\b',e.get('text',''),re.I)]
    penalty=0.65 if conflicts else (0.90 if unmet else 1.0)
    return penalty,{'condition_conflicts':conflicts,'unverified_structured_conditions':unmet,
                    'negative_observations_preserved':negatives,
                    'structured_conditions_satisfied':not conflicts and not unmet and bool(c.get('applicability_conditions')),
                    'recommendation_applicable':False if conflicts else None,
                    'applicability_status':'structured_condition_conflict' if conflicts else 'clinical_applicability_not_determined',
                    'required_evidence_checklist':c['required_patient_evidence'],
                    'use_rule':'Knowledge is a conditional rule/checklist, never a new patient observation.'}


@functools.lru_cache(maxsize=8)
def read_source_pages(index_dir):
    path=Path(index_dir)/'source_pages.jsonl'
    if not path.is_file():return {}
    out={}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():continue
        entry=json.loads(line)
        out[(str(entry['source_id']),str(entry['page']))]=entry
    return out


def page_numbers(values):
    nums=[]
    for v in values:
        m=re.match(r'^(?:p\.?\s*)?(\d+)(?:\s*[-–]\s*(\d+))?$',v)
        if m:nums.extend(range(int(m[1]),int(m[2] or m[1])+1))
    return nums


def extract_parent(c,selected,max_chars):
    paragraphs=[x.strip() for x in re.split(r'\n\s*\n','\n'.join(selected)) if x.strip()]
    if not paragraphs:return ''
    topic=set(tokens(c['title']+' '+' '.join(c['keywords'])))
    i=max(range(len(paragraphs)),key=lambda j:len(topic.intersection(tokens(paragraphs[j]))))
    if not topic.intersection(tokens(paragraphs[i])):return ''
    # Center the matched paragraph; neighbors cannot crowd it out of the budget.
    center=paragraphs[i]
    if len(center)>max_chars:
        lines=center.splitlines()
        j=max(range(len(lines)),key=lambda j:len(topic.intersection(tokens(lines[j]))))
        center='\n'.join(lines[max(0,j-2):j+8])
    passage=center[:max_chars]
    for j in (i-1,i+1):
        if 0<=j<len(paragraphs) and len(passage)+len(paragraphs[j])+2<=max_chars:
            passage=(paragraphs[j]+'\n\n'+passage) if j<i else (passage+'\n\n'+paragraphs[j])
    return passage


def parent_passage(c,index_dir,max_chars):
    for key in ('parent_text','parent_paragraph','source_excerpt'):
        if c.get(key): return {'text':str(c[key])[:max_chars],'mode':'explicit_parent','source_pages':c['source_pages'],'source_file':c['source_file']}
    pages=read_source_pages(str(index_dir))
    nums=page_numbers(c['source_pages'])
    selected=[pages[(c['source_id'],str(n))]['text'] for n in nums if (c['source_id'],str(n)) in pages]
    if selected:
        passage=extract_parent(c,selected,max_chars)
        if passage:
            return {'text':passage,'mode':'source_page_paragraph_neighbors',
                    'source_pages':c['source_pages'],'source_file':c['source_file']}
        return {'text':'\n'.join([c['summary_en'],c['summary_zh']])[:max_chars],
                'mode':'curated_card_only_no_parent_keyword_match','source_pages':c['source_pages'],
                'source_file':c['source_file'],'warning':'Cited extracted pages contain no anchor terms; inspect original PDF/OCR before using as verbatim evidence.'}
    # Text files are optional. Resolve portable paths relative to index/card root.
    value=c.get('source_text_file')
    if value:
        candidates=[Path(value),Path(index_dir)/value,Path(index_dir).parent/value,Path(index_dir).parent.parent/value]
        p=next((p for p in candidates if p.is_file() and p.suffix.lower()=='.txt'),None)
        if p:
            pages=p.read_text(encoding='utf-8').split('\f')
            nums=page_numbers(c['source_pages'])
            selected=[pages[n-1] for n in nums if 0<n<=len(pages)]
            if selected:
                passage=extract_parent(c,selected,max_chars)
                return {'text':passage,'mode':'page_paragraph_neighbors','source_pages':c['source_pages'],'source_file':c['source_file']}
    return {'text':'\n'.join([c['summary_en'],c['summary_zh']])[:max_chars],
            'mode':'curated_card_only_parent_unavailable','source_pages':c['source_pages'],'source_file':c['source_file']}


def load_index(path):
    p=Path(path)
    meta=json.loads((p/'metadata.json').read_text())
    cards=[json.loads(x) for x in (p/'cards.jsonl').read_text().splitlines() if x.strip()]
    return cards,meta


def retrieve(cards,q,config=None,index_dir='.',dense_scores=None,dense_mode='lexical_only',runtime_log=None):
    cfg={**DEFAULT,**(config or {})}; q=normalized_query(q)
    lex=BM25([card_text(c) for c in cards]);main=query_text(q);hyp=' '.join(q['candidate_hypotheses'])
    ls=lex.scores(main); hs=lex.scores(hyp)
    eligible=[]; rejected=[]; assessments={}
    for i,c in enumerate(cards):
        ok,sm,reasons,penalties=scope(c,q)
        if not ok: rejected.append({'knowledge_id':c['knowledge_id'],'reasons':reasons});continue
        main_matches=sorted(set(tokens(main)).intersection(lex.docs[i]))
        # A hypothesis can locate a rule, but cannot be the sole reason to inject it.
        enough_lex=len(main_matches)>=cfg['min_main_matches'] and ls[i]>0
        enough_dense=dense_scores is not None and float(dense_scores[i])>=cfg['dense_min_cosine']
        if not enough_lex and not enough_dense:
            rejected.append({'knowledge_id':c['knowledge_id'],'reasons':['insufficient_nonhypothesis_match'],'main_matches':main_matches});continue
        np,na=negation_assessment(c,q)
        assessments[i]=(sm,reasons,penalties,main_matches,np,na)
        eligible.append(i)
    lex_order=sorted([i for i in eligible if ls[i]>0],key=lambda i:(-(ls[i]+cfg['hypothesis_weight']*hs[i]),cards[i]['knowledge_id']))[:cfg['candidate_k']]
    rankings={'bm25':lex_order}
    if dense_scores is not None:
        rankings['dense']=sorted([i for i in eligible if float(dense_scores[i])>=cfg['dense_min_cosine']],key=lambda i:(-float(dense_scores[i]),cards[i]['knowledge_id']))[:cfg['candidate_k']]
    rr=collections.defaultdict(float);rank_values=collections.defaultdict(dict)
    for channel,order in rankings.items():
        for rank,i in enumerate(order,1):
            rr[i]+=1/(cfg['rrf_k']+rank);rank_values[i][channel]=rank
    scored=[]
    for i,score in rr.items():
        sm,reasons,penalties,matches,np,na=assessments[i]
        needs=set(tokens(' '.join(q['missing_attributes'])))
        need_overlap=sorted(needs.intersection(tokens(card_text(cards[i]))))
        # Small deterministic task/evidence rerank; not a learned clinical score.
        coverage=min(len(need_overlap)/max(len(needs),1),1)
        relevance=(1+.15*coverage)*sm*np
        scored.append((score*relevance,i,{'bm25_main':round(ls[i],6),'bm25_hypothesis':round(hs[i],6),
            'dense_cosine':round(float(dense_scores[i]),6) if dense_scores is not None else None,
            'rrf':round(score,8),'scope_multiplier':sm,'condition_multiplier':np,'missing_attribute_coverage':coverage,
            'reranked_score':round(score*relevance,8),'channel_ranks':rank_values[i]}))
    scored.sort(key=lambda x:(-x[0],cards[x[1]]['knowledge_id']))
    hits=[];counts=collections.Counter();diversity_skipped=[]
    chars=0
    for score,i,components in scored:
        c=cards[i]
        if scored and score<scored[0][0]*cfg['min_relative_score']:
            rejected.append({'knowledge_id':c['knowledge_id'],'reasons':['weak_relative_fused_score'],
                             'relative_score':score/scored[0][0]});continue
        if counts[c['source_id']]>=cfg['max_per_source']:
            diversity_skipped.append(c['knowledge_id']);continue
        if len(hits)>=cfg['top_k']:break
        sm,reasons,penalties,matches,np,na=assessments[i]
        passage=parent_passage(c,index_dir,min(cfg['parent_max_chars'],max(0,cfg['max_context_chars']-chars)))
        chars+=len(passage['text'])
        hits.append({'rank':len(hits)+1,'knowledge_id':c['knowledge_id'],'source_id':c['source_id'],
                     'title':c['title'],'source_pages':c['source_pages'],'source_file':c['source_file'],
                     'score_components':components,'why_eligible':reasons+['nonhypothesis_relevance_gate_passed'],
                     'scope_cautions':penalties,'main_matched_terms':matches,'condition_check':na,
                     'parent_passage':passage,'knowledge_card':c})
        counts[c['source_id']]+=1
    return {'mode':dense_mode if dense_scores is not None else 'lexical_only','abstained':not hits,
            'abstention_reasons':['no_eligible_relevant_knowledge'] if not hits else [],
            'query_roles':q,'facts_added_by_retrieval':[], 'hits':hits,
            'candidate_rankings':{k:[cards[i]['knowledge_id'] for i in v] for k,v in rankings.items()},
            'rejected':rejected,'diversity_skipped':diversity_skipped,
            'log':list(runtime_log or [])+['Hypotheses are hints; never promoted to observations.',
                    'No test labels, reference answers, methods documents, or development analyses are searched.',
                    'Scope filters and low-match rejection precede reciprocal-rank fusion.',
                    'Source diversity may return fewer than top_k cards.'],
            'config':cfg}
