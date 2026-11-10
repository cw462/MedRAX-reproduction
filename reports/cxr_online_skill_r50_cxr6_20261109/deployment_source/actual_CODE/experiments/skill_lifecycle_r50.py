"""Three-branch lifecycle. Paper mechanisms with explicitly documented CXR adaptations."""
import copy,math,json,hashlib
from collections import Counter,defaultdict
BRANCHES=('general','task_level','action_level')
DEFAULTS=dict(window=30,buffer=20,top_k=6,similarity_min=.2,merge_similarity=.8,
             weights=[.4,.4,.2],ema=.2,baseline_min=3,lr_base=.05,lr_max=.2,warmup=5,decay=20,
             positive=1.,negative=.1,harm=.5,epsilon=.02,strength_tau=60,
             govern_every=2,deprecate=.3,mature=.75,mature_usage=15,
             capacities={'general':12,'task_level':8,'action_level':5})
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def cosine(a,b):
    if len(a)!=len(b):raise ValueError('embedding_dimension')
    d=math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
    return sum(x*y for x,y in zip(a,b))/d if d else 0.
def initial():return {'schema':'r50','skills':{},'baselines':{},'window':0,'clock':0,'frozen':False}
def validate(c,tools):
    required={'name','description','applicable_conditions','branch','tool_name','task_category','required_tools','risk_level','core_action'}
    if set(c)!=required:raise ValueError('skill_fields')
    for k in ('name','description','applicable_conditions','task_category','core_action'):
        if not isinstance(c[k],str) or not c[k].strip() or len(c[k])>2400:raise ValueError('text:'+k)
    if c['branch'] not in BRANCHES or c['risk_level'] not in ('low','medium','high'):raise ValueError('branch_or_risk')
    if not isinstance(c['required_tools'],list) or not set(c['required_tools'])<=set(tools):raise ValueError('unknown_tools')
    if c['branch']=='action_level' and (c['tool_name'] not in tools or c['tool_name'] not in c['required_tools']):raise ValueError('action_tool')
    if c['branch']!='action_level' and c['tool_name'] is not None:raise ValueError('unexpected_tool_name')
    return c
def scope(c):return (c['branch'], c['tool_name'] if c['branch']=='action_level' else c['task_category'] if c['branch']=='task_level' else 'all')
def category(question):
    # Deterministic CXR task router, explicitly differs from paper LLM category classification.
    import re
    q=question.lower()
    for label,pat in [('comparison','prior|previous|interval|compared|change'),('location','where|location|lobe|left|right|side'),
      ('severity','severity|size|extent|mild|moderate'),('view','view|projection|position|plane'),('diagnosis','diagnos|likely|cause'),
      ('count','how many|number of'),('morphology','shape|pattern|appearance|describe')]:
        if re.search(pat,q):return label
    return 'presence'
def learning_rate(n,cfg):
    if n<=cfg['warmup']:return cfg['lr_base']+(cfg['lr_max']-cfg['lr_base'])*n/cfg['warmup']
    progress=min(1,(n-cfg['warmup'])/cfg['decay'])
    return cfg['lr_base']+(cfg['lr_max']-cfg['lr_base'])*.5*(1+math.cos(math.pi*progress))
def retrieve(repo,query_vector,cat,tools,cfg,prescreen=None):
    candidates=[]
    for sid,m in repo['skills'].items():
        c=m['c']
        if m['status'] not in ('active','mature') or not set(c['required_tools'])<=set(tools):continue
        if c['branch']=='task_level' and c['task_category']!=cat:continue
        sim=cosine(query_vector,m['vector'])
        if sim<cfg['similarity_min']:continue
        u=m['u_by_category'].get(cat,m['u']) if c['branch']=='general' else m['u']
        h=math.exp(-max(0,repo['clock']-m['last_reinforced'])/cfg['strength_tau'])
        score=sum(w*v for w,v in zip(cfg['weights'],[sim,u,h]))*(1.1 if m['status']=='mature' else 1)
        candidates.append({'id':sid,'branch':c['branch'],'score':score,'similarity':sim,'c':c})
    candidates.sort(key=lambda x:(-x['score'],x['id']))
    if candidates and prescreen:
        pool=[x for b in BRANCHES for x in [y for y in candidates if y['branch']==b][:5]]
        chosen=prescreen(pool)
        if not set(chosen)<={x['id'] for x in pool}:raise ValueError('prescreen_unknown_id')
        candidates=[x for x in pool if x['id'] in chosen];candidates.sort(key=lambda x:(-x['score'],x['id']))
    # Round-robin branch balancing is our explicit allocation rule (paper leaves tie details open).
    queues={b:[x for x in candidates if x['branch']==b] for b in BRANCHES};selected=[]
    while len(selected)<cfg['top_k']:
        added=False
        for b in BRANCHES:
            if queues[b] and len(selected)<cfg['top_k']:selected.append(queues[b].pop(0));added=True
        if not added:break
    return selected

def gate(t):
    if t.get('technical_failure') or t.get('max_step_failure') or t.get('repeated_no_progress'):return False
    steps=t['steps']
    if t['reward']==1 and len(steps)<=2:return False
    signatures=Counter(digest(x) for x in steps)
    return not any(n>=3 for n in signatures.values())
def buffer_select(trajectories,cfg):
    valid=[t for t in trajectories if gate(t)];counts=Counter(t['category'] for t in valid)
    def rank(t):return (math.log1p(len(t['steps']))+bool(t['injected']))/(1+counts[t['category']])
    good=sorted([t for t in valid if t['reward']>0],key=lambda t:(-rank(t),t['id']))
    bad=sorted([t for t in valid if t['reward']<=0],key=lambda t:(-rank(t),t['id']))
    cap=cfg['buffer'];selected=good[:cap//2]+bad[:cap//2];ids={t['id'] for t in selected}
    rest=sorted([t for t in valid if t['id'] not in ids],key=lambda t:(-rank(t),t['id']))
    return selected+rest[:cap-len(selected)]

def assess(repo,trajectories,analyses,cfg):
    if repo['frozen']:raise ValueError('frozen_repo')
    contributions=defaultdict(list);events=[]
    for t in trajectories:
        baseline=repo['baselines'].get(t['category'],{'n':0,'mean':.5})
        adv=t['reward']-(baseline['mean'] if baseline['n']>=cfg['baseline_min'] else .5)
        attributed=set()
        for adoption in analyses.get(t['id'],{}).get('skill_adoption',[]):
            sid=adoption['skill_id'];status=adoption['status']
            if sid in attributed:raise ValueError('duplicate_skill_adoption')
            attributed.add(sid)
            if sid not in t['injected'] or sid not in repo['skills']:raise ValueError('adoption_not_injected')
            if status not in ('ADOPTED_POSITIVE','ADOPTED_NEGATIVE','IGNORED'):raise ValueError('adoption_status')
            if status=='IGNORED':continue
            # An evidence index is mandatory; adoption is an LLM attribution, not causal proof.
            index=adoption['step_index']
            if type(index)!=int or not 0<=index<len(t['steps']) or not adoption.get('evidence'):raise ValueError('adoption_evidence')
            m=repo['skills'][sid];u=m['u_by_category'].get(t['category'],m['u']) if m['c']['branch']=='general' else m['u']
            credit=cfg['positive']*adv if status=='ADOPTED_POSITIVE' else -(cfg['negative']+cfg['harm']*max(0,-adv))-cfg['epsilon']*u
            key=(sid,t['category'] if m['c']['branch']=='general' else '*');contributions[key].append(credit)
            events.append({'trajectory':t['id'],'skill':sid,'advantage':adv,'credit':credit,'status':status})
            m['usage']+=1
            if status=='ADOPTED_POSITIVE':m['last_reinforced']=repo['clock']
    for (sid,cat),values in contributions.items():
        m=repo['skills'][sid];old=m['u_by_category'].get(cat,m['u']) if cat!='*' else m['u']
        new=max(0,min(1,old+learning_rate(m['usage'],cfg)*sum(values)/len(values)))
        if cat=='*':m['u']=new
        else:m['u_by_category'][cat]=new;m['u']=sum(m['u_by_category'].values())/len(m['u_by_category'])
    groups=defaultdict(list)
    for t in trajectories:
        if not t.get('technical_failure'):groups[t['category']].append(t['reward'])
    for cat,values in groups.items():
        old=repo['baselines'].get(cat,{'n':0,'mean':.5});mean=sum(values)/len(values)
        repo['baselines'][cat]={'n':old['n']+len(values),'mean':(1-cfg['ema'])*old['mean']+cfg['ema']*mean}
    return events

def commit(repo,operation,content,vector,source_ids,tools,target=None):
    if repo['frozen']:raise ValueError('frozen_repo')
    validate(content,tools)
    if operation=='CREATE':
        sid='s_'+digest([content,source_ids])[:16]
        if sid in repo['skills']:return sid
        repo['skills'][sid]={'k':content['name']+' '+content['description'],'c':content,'u':.5,'u_by_category':{},'usage':0,
            'vector':vector,'status':'active','last_reinforced':repo['clock'],'source_ids':source_ids,'versions':[]}
    elif operation=='PATCH':
        sid=target
        if sid not in repo['skills']:raise ValueError('patch_missing')
        m=repo['skills'][sid]
        if scope(m['c'])!=scope(content):raise ValueError('patch_scope_changed')
        m['versions'].append({'c':m['c'],'vector':m['vector'],'window':repo['window']})
        m.update(c=content,k=content['name']+' '+content['description'],vector=vector,
            source_ids=sorted(set(m['source_ids']+source_ids)))
    else:raise ValueError('operation')
    return sid

def govern(repo,cfg,merge):
    if repo['frozen']:raise ValueError('frozen_repo')
    events=[];skills=repo['skills']
    for sid,m in skills.items():
        if m['status'] not in ('active','mature'):continue
        if m['u']<cfg['deprecate'] and m['usage']>0:m['status']='deprecated';events.append(['deprecate',sid])
        elif m['u']>=cfg['mature'] and m['usage']>=cfg['mature_usage']:m['status']='mature';events.append(['mature',sid])
    ids=sorted(skills,key=lambda sid:(-skills[sid]['u'],sid))
    for i,a in enumerate(ids):
        x=skills[a]
        if x['status'] not in ('active','mature'):continue
        for b in ids[i+1:]:
            y=skills[b]
            if y['status'] not in ('active','mature') or scope(x['c'])!=scope(y['c']):continue
            if cosine(x['vector'],y['vector'])>=cfg['merge_similarity']:
                result=merge(a,x,b,y)
                if result is not None:
                    content,vector=result;x['versions'].append({'c':x['c'],'window':repo['window'],'merged':b})
                    x.update(c=content,vector=vector,k=content['name']+' '+content['description'],source_ids=sorted(set(x['source_ids']+y['source_ids'])))
                    y['status']='merged';y['merged_into']=a;events.append(['merge',a,b])
    groups=defaultdict(list)
    for sid,m in skills.items():
        if m['status'] in ('active','mature'):groups[scope(m['c'])].append(sid)
    for group,ids in groups.items():
        ids.sort(key=lambda sid:(-skills[sid]['u'],-skills[sid]['usage'],sid))
        for sid in ids[cfg['capacities'][group[0]]:]:skills[sid]['status']='capacity_archived';events.append(['capacity_archive',sid])
    return events
