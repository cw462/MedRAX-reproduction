"""Pure Plus-only history/skills contracts; no client, ledger or reference I/O."""
import json
import math
import random
import re
from collections import Counter

ID='history_skills_plus_20261103'
VERSION='2'
CATEGORIES={'detection','localization','comparison','classification','characterization','diagnosis','reasoning','relationship','general'}
REFLECTION_SYSTEM='''Create at most two reusable medical-image reading skills from this training example. The saved answer/reason may be wrong. Return only JSON {"skills":[{"category":"general or one supplied official category","trigger":"when to apply","steps":["concrete image check","how to distinguish alternatives"]}]}. No case/patient ID, option letter, figure number, patient-specific number, copied question, or rule merely repeating the reference diagnosis. General medical findings are allowed. Skills will only be used on other patients. An empty skills list is allowed.'''


def words(text):
    return re.findall(r'[a-z]+',str(text).casefold())


def folds_and_reflections(rows, baseline):
    cases=sorted({r['case_id'] for r in rows});random.Random(20261103).shuffle(cases)
    fold={c:('A' if i<50 else 'B') for i,c in enumerate(cases)}
    correct=sorted(r['question_id'] for r in rows if baseline[r['question_id']]['correct'])
    wrong=sorted(r['question_id'] for r in rows if not baseline[r['question_id']]['correct'])
    sampled=random.Random(20261104).sample(correct,len(correct)//3)
    return fold,sorted(wrong+sampled)


def clinical_record(record, policy):
    # The answer-facing object is constructed, never copied from metadata.
    safe={k:str(record.get(k) or '') for k in ('age','gender','history')}
    history=' '.join(words(safe['history']))
    reasons=[]
    for term in policy['risk_terms']:
        normalized=' '.join(words(term))
        if re.search(r'\b'+re.escape(normalized)+r'\b',history):
            reasons.append('imaging_term');break
    stop=set(policy['diagnosis_overlap']['stopwords'])
    content=lambda s:{w for w in words(s) if len(w)>=4 and w not in stop}
    if content(safe['history']) & content(record.get('diagnosis','')):
        reasons.append('diagnosis_word_overlap')
    return safe,{'flagged':bool(reasons),'rule_codes':reasons}


def history_block(value):
    if set(value)!={'age','gender','history'}:raise ValueError('history_field_allowlist')
    return 'Clinical history (case record; may contain prior observations):\n'+ '\n'.join(k+': '+value[k] for k in ('age','gender','history'))+'\n\n'


def parse_reflection(text, categories):
    try:
        s=str(text or '').strip()
        if s.startswith('```'):s=re.sub(r'^```(?:json)?\s*|\s*```$','',s)
        x=json.loads(s)
        if not isinstance(x,dict) or set(x)!={'skills'} or not isinstance(x['skills'],list) or len(x['skills'])>2:raise ValueError()
        for skill in x['skills']:
            if set(skill)!={'category','trigger','steps'} or not isinstance(skill['trigger'],str) or not skill['trigger'].strip():raise ValueError()
            if not isinstance(skill['steps'],list) or not 1<=len(skill['steps'])<=5 or any(not isinstance(t,str) or not t.strip() for t in skill['steps']):raise ValueError()
            if skill['category'] not in (set(categories)|{'general'}):raise ValueError()
        return {'answer':'SKILLS','status':'completed','skills':x['skills']}
    except (ValueError,TypeError):return {'answer':None,'status':'unparsed','skills':[]}


def filter_reason(skill, row):
    text=skill['trigger']+' '+ ' '.join(skill['steps'])
    if re.search(r'\b(?:case|patient)\s*(?:id|number|#)|\b(?:option|answer|choice)\s*[:=]?\s*[A-Z]\b|\bfig(?:ure)?\s*\.?\s*\d',text,re.I):return 'identifier_option_or_figure'
    if re.search(r'\d',text):return 'numeric_patient_specific_risk'
    tokens=words(text);question=words(row['question'])
    if str(row['case_id']) in text or row['question_id'] in text:return 'source_identifier'
    for i in range(max(0,len(tokens)-11)):
        if ' '.join(tokens[i:i+12]) in ' '.join(question):return 'copied_question_span'
    if len(words(' '.join(skill['steps'])))<6:return 'insufficient_concrete_steps'
    return None


def rank_skills(query,skills):
    docs=[Counter(words(s['trigger']+' '+' '.join(s['steps']))) for s in skills]
    df=Counter(w for d in docs for w in d)
    idf={w:math.log((1+len(docs))/(1+n))+1 for w,n in df.items()}
    def vec(count):
        v={w:n*idf[w] for w,n in count.items() if w in idf};norm=math.sqrt(sum(n*n for n in v.values()))
        return {w:n/norm for w,n in v.items()} if norm else {}
    q=vec(Counter(words(query)));rank=[]
    for s,d in zip(skills,docs):
        v=vec(d);score=sum(n*v.get(w,0) for w,n in q.items())
        rank.append((score,s))
    return sorted(rank,key=lambda pair:(-pair[0],pair[1]['skill_id']))


def merge_skills(skills,cap,utility_order=False):
    kept=[];rejected=[]
    for s in sorted(skills,key=lambda s:(-s.get('utility',0),s['skill_id']) if utility_order else s['skill_id']):
        near=rank_skills(s['trigger']+' '+' '.join(s['steps']),kept)
        if near and near[0][0]>=.9:
            rejected.append({'skill_id':s['skill_id'],'reason':'near_duplicate','representative':near[0][1]['skill_id']});continue
        if len(kept)>=cap:rejected.append({'skill_id':s['skill_id'],'reason':'store_cap'});continue
        kept.append(s)
    return kept,rejected


def retrieve(row,categories,fold,stores):
    source='B' if fold=='A' else 'A'
    skills=stores[source]
    if any(s['source_fold']!=source or s['source_case_id']==row['case_id'] for s in skills):raise ValueError('crossfit_source_violation')
    rank=rank_skills(row['question'],skills)
    category=[s for score,s in rank if score>0 and s['category'] in categories and s['category']!='general'][:3]
    general=[s for score,s in rank if score>0 and s['category']=='general'][:2]
    return category+general


def skills_block(skills):
    return 'Experience from other cases; may not apply. Check against the current original images; these are not answers for this patient.\n'+json.dumps([{k:s[k] for k in ('category','trigger','steps')} for s in skills],ensure_ascii=False)+'\n\n'
