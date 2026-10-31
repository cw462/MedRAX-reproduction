"""Export explicit historical design documents and frozen K/E assets for review.

No experiment, model call, ledger access, or score recomputation is performed.
Design documents are historical proposals, not evidence of completed execution.
"""
import argparse
import json
from pathlib import Path
import re

PLANS={
 'MedRAX_Codex_Plan_Step_Credit_Memory_v2.md':'v2-step-credit-memory.md',
 'MedRAX_Full_Experiment_Codex_Plan_v3 (1).md':'v3-full-experiment.md',
 'MedRAX_Skill_Method_Validation_Plan_v4.md':'v4-skill-validation.md',
 'MedRAX_BC_Case_Analysis_and_Recovery_Plan_v7.md':'v7-bc-recovery.md',
 'MedRAX_V7_Result_Analysis_and_V9_Plan.md':'v7-results-v9-plan.md',
 'Codex_Experiment_Plan_v8.md':'v8-experiment-plan.md',
 'Clinical_Knowledge_Cards.md':'v8-clinical-knowledge-cards.md',
 'Experience_Synthesis.md':'v8-experience-synthesis.md',
 'MedRAX_V10_Accuracy_Plan.txt':'v10-accuracy-plan.txt',
 'MedRAX_V11_Results_Analysis_and_Gain_Plan (1).txt':'v11-results-gain-plan.txt',
}
SECRETS={'api_key','password','authorization','access_token','refresh_token','private_key'}
def clean(value):
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items() if k.lower() not in SECRETS}
    if isinstance(value,list):return [clean(v) for v in value]
    if not isinstance(value,str):return value
    value=re.sub(r'/home/[^/\s]+/[^/\s]+/MedRAX_reproduction_\d+', '[runtime_root]', value)
    value=re.sub(r'(?i)(?:(?<![A-Za-z0-9])[a-z]:[\\/]|/(?:home|tmp|mnt|Users)/)[^\s\"\'<>\]\},]+','[private_path_omitted]',value)
    if re.search(r'(?i)\b(?:sk-[a-z0-9_-]{20,}|gh[pousr]_[a-z0-9]{25,})\b|data:image/[^;]+;base64,',value):raise ValueError('credential or embedded image needs explicit handling')
    return value
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--documents',type=Path,required=True)
    p.add_argument('--assets',type=Path,default=Path('local_assets'))
    p.add_argument('--out',type=Path,default=Path('reports/history'))
    args=p.parse_args();rows=[]
    def save(name,text,source,kind):
        f=args.out/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(text,encoding='utf-8')
        rows.append({'path':name,'source':source,'kind':kind,'bytes':f.stat().st_size})
    def save_json(name,value,source):save(name,json.dumps(clean(value),ensure_ascii=False,indent=2)+'\n',source,'saved_asset')
    for source,dest in PLANS.items():
        save('plans/'+dest,clean((args.documents/source).read_text(encoding='utf-8-sig')),source,'historical_design_not_execution')
    pack=args.assets/'MedRAX_Knowledge_Pack_v8'
    for name in ['PACKAGE_INFO.json','knowledge/source_manifest.json','configs/experiment_matrix.json','configs/skill_template.json','retrieval/config.json','retrieval/index_hybrid/metadata.json','retrieval/index_lexical/metadata.json']:
        save_json('assets/knowledge_pack/'+name,json.loads((pack/name).read_text(encoding='utf-8-sig')),'knowledge_pack/'+name)
    for name in ['knowledge/clinical_cards.jsonl','retrieval/index_hybrid/cards.jsonl','retrieval/index_lexical/cards.jsonl']:
        vals=[clean(json.loads(s)) for s in (pack/name).read_text(encoding='utf-8-sig').splitlines() if s.strip()]
        save('assets/knowledge_pack/'+name,'\n'.join(json.dumps(v,ensure_ascii=False) for v in vals)+'\n','knowledge_pack/'+name,'saved_asset')
    for name in ['core.py','dense.py','build_index.py','retrieve.py','config.json','requirements.txt','requirements-dense.txt','README.md']:
        if name=='config.json':continue
        save('assets/knowledge_pack/retrieval/'+name,clean((pack/'retrieval'/name).read_text(encoding='utf-8-sig')),'knowledge_pack/retrieval/'+name,'retrieval_implementation')
    for src,dest in [('server/pool.json','experience_pool.json'),('server/skills.json','skills.json')]:
        value=json.loads((args.assets/src).read_text(encoding='utf-8-sig'))
        save_json('assets/'+dest,value,'local transport snapshot '+src)
    save_json('assets/manifest.json',{'publication_date':'2026-10-31','transform':'UTF-8 text; private runtime paths/credential fields removed; saved checksum fields retained as source metadata and not recomputed. Excludes full third-party literature, weights, dense vectors, and credentials.','files':rows},'this export')
    print(json.dumps({'published_files':len(rows),'plans':len(PLANS),'pool_records':len(json.loads((args.out/'assets/experience_pool.json').read_text(encoding='utf-8'))['payload']['records'])}))
if __name__=='__main__':main()
