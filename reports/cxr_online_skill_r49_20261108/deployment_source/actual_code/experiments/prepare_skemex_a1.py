"""Map only known completed baselines and prepare official A1 metadata; no API."""
import argparse
import json
from pathlib import Path


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def prepare(root,a0_is_d=False):
    root=Path(root);out=root/'reports/skemex_a1_20261103';out.mkdir(parents=True,exist_ok=True)
    target=read(root/'reports/qwen37_token_plan_20261102/phase1/per_question.json')['records']
    qids={r['question_id'] for r in target};cases={r['case_id'] for r in target}
    candidates=[]
    for run in ('official_gain60','official_gain60_fixed'):
        folder=root/'reports'/run;cfg=read(folder/'protocol.json')
        rows=read(folder/'answer_extraction.json')['records'];ids={r['question_id'] for r in rows if r['arm']=='M'}
        candidates.append({'run_id':run,'arm':'M','role':'actual historical multistep no-memory Agent candidate; not automatically A0',
            'model':cfg['model'],'question_n':len(ids),'common_target_question_n':len(ids&qids),
            'common_target_case_n':len({q.split('_')[0] for q in ids}&cases),
            'central_calls_per_episode':cfg['central_calls_per_arm'],'medical_calls_per_episode':cfg['medical_tool_calls_per_arm'],
            'temperature':cfg['temperature'],'top_p':cfg['top_p'],'max_tokens':cfg['max_tokens'],
            'protocol':'../'+run+'/protocol.json','results':'../'+run+'/answer_extraction.json',
            'trajectory_index':'../'+run+'/cases/README.md','compatible_with_402_target':False,
            'reason':'zero shared question IDs/cases; different historical model and task split'})
    manifest={'experiment_id':'skemex_a1_20261103','status':'awaiting_A0_identity','target_question_n':402,'target_case_n':99,
        'target_question_ids':sorted(qids),'target_case_ids':sorted(cases),
        'D':{'run_id':'qwen37_token_plan_20261102','phase':1,'arm':'D','model':'qwen3.7-plus','question_n':402,'correct':295,'common_question_n':402,
             'per_question':'../qwen37_token_plan_20261102/phase1/per_question.json','raw_record_index':'../qwen37_token_plan_20261102/phase1/evidence/arms/D/predictions.jsonl'},
        'A0':{'status':'unresolved','common_question_n':0,'run_id':None,'reason':'No completed multistep A0 on these402questions identified in existing published protocols or remote run-directory inventory.'},
        'historical_multistep_candidates':candidates,
        'old_skill_controls':[{'run_id':'history_skills_plus_20261103','arms':['S1','HS'],'model':'qwen3.7-plus','n':402,'correct':{'S1':279,'HS':300},'path':'../history_skills_plus_20261103/results/analysis/per_question.json','exact_A2_alias_proven':False,'strict_ablation':False}],
        'ineligible_A0_aliases':{'case_information_20261103/E3':'one-shot evidence injection; not a multistep A0','qwen_agent_v2_20261102':'name contains agent but executed only direct/high-resolution/sampling work; stopped historical qwen3-vl-plus run'},
        'new_paid_calls':0,'reference_answers_used_to_choose_A0':False}
    if a0_is_d:
        manifest['status']='A0_D_confirmed_by_user'
        manifest['A0']={**manifest['D'],'status':'matched_complete','runner_entrypoint':'experiments/run_direct_vlm.py','trajectory_index':manifest['D']['raw_record_index'],'user_clarification':'A0 is direct D; replace the prior S1 memory mechanism with official SkeMex. No multi-step/tool A0 is intended.'}
    (out/'baseline_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    folds=read(root/'reports/history_skills_plus_20261103/prepared/folds_and_reflections.json')['case_folds']
    (out/'folds.json').write_text(json.dumps({'source':'../history_skills_plus_20261103/prepared/folds_and_reflections.json','case_folds':folds,'target_A_source_B':True,'target_B_source_A':True},indent=2)+'\n',encoding='utf-8')
    defaults=read(root/'third_party/skemex/configs/evolution/default.json')
    (out/'upstream_settings.json').write_text(json.dumps({k:defaults[k] for k in ('retrieval','buffer','utility','governance','context_guard')},indent=2)+'\n',encoding='utf-8')
    (out/'upstream_commit.txt').write_text('a640474590e384669dd71b657c441264beef73d2\n',encoding='utf-8')
    print(json.dumps({'status':manifest['status'],'candidate_A0_overlap':[c['common_target_question_n'] for c in candidates],'new_paid_calls':0}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--a0-is-d',action='store_true');a=p.parse_args();prepare(a.root,a.a0_is_d)
