"""Record the observed real launch and immutable pre-generation evidence."""
import json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];PREP=ROOT/'local_assets/r50_cxr6_preparation'
REPORT=ROOT/'reports/cxr_online_skill_r50_cxr6_20261109'

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def put(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')

def main():
    assert read(PREP/'HEALTH_RECEIPT.json')['native_exit_code']==0
    assert read(PREP/'archive_delta.upload.completed.json')['native_transport_returned_zero'] is True
    assert read(PREP/'controller.launch.completed.json')['launch_command_returned_zero'] is True
    ready=read(PREP/'EXECUTION_REVIEW_READY.json');assert ready['verdict']=='ready'
    health=read(PREP/'health/complete.json')
    when=datetime.now(timezone.utc).astimezone().isoformat()
    current={'recorded_at':when,'controller_pid':3167009,'runner_pid':3167015,'arm':'M43-IM-GT-S50-CXR6',
      'dataset':'chexbench','last_actual_status':{'controller_alive':True,'runner_alive':True,'saved_predictions':0,
        'contexts':1,'main_sends':1,'main_responses':1,'feedback':0,'meta_sends':0},
      'source':'root actual deploy_cxr6_r50.py status native0 after actual queue launch native0',
      'formal_generation_started':True,'completed_or_scored_claim':False,'gpu':'1',
      'launch_started':read(PREP/'controller.launch.started.json'),'launch_completed':read(PREP/'controller.launch.completed.json')}
    put(PREP/'ACTUAL_PRODUCTION_LAUNCH.json',current)
    v=read(ROOT/'.aris/IMPROVEMENT_STATE.json');v.update(status='R50_formal_generation_running_R49_final_pushed',updated_at=when)
    v['R50'].update(status='FORMAL_GENERATION_RUNNING',generation_started=True,actual_model_load_checks_completed=True,
      current_controller_pid=3167009,current_runner_pid=3167015,current_dataset='chexbench',actual_launch=current,
      formal_main_sends_observed=1,formal_main_responses_observed=1,
      health={'status':'DONE_CONSUMED','native_session':50422,'native_exit':0,'owner':'r50_env_doc_check',
        'three_new_tools_completed_healthy':True,'old_three_reprobed':False,'main_META_embedding_calls':0,
        'tool_elapsed_s':{k:round(r['elapsed_s'],4) for k,r in health['records'].items()},'production_result_reuse':False},
      archive_delta={'status':'DONE_CONSUMED','native_session':25880,'native_exit':0,'verdict':'ready','scope_complete':True,
        'actual_review_metadata':'local_assets/r50_cxr6_preparation/ARCHIVE_DELTA_METADATA.json','production_support_delta_deployed':True,
        'upload_native_transport_exit':0,'tests':'3new synthetic passed; first fixture-only __file__ omission retained',
        'limitation':'request-before-start crash can stop on existing strict request write; no silent/automatic resend; original reply retained'})
    v['next']='R50 formal848 now RUNNING: controller3167009/CheXrunner3167015, first actual main request returned, all3 new health50422DONE0 and code+archive-delta reviews99479/25880DONE0, no more reviews/probes/stage/queue/old sessions. Use only lightweight deploy_cxr6_r50.py status and current raw failure logs if exit!=0. Producer code frozen; do not rewrite existing predictions or reissue unknown sends. Implement local postprocessing from fixed pre-generation EVALUATION_PROTOCOL during generation; full per-dataset output and raw runner0 gates before one pull/score per dataset. R49 FINALPUSH already complete3ab0a927526e0910328b8db2503ac0fdc0e10036; no repeat score/pulls/reviews/push/remote verification (user waived). Keep existingmedrax-r47 monitor active in current chat through R50 full results/publication.'
    (ROOT/'.aris/IMPROVEMENT_STATE.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    protocol={'arm':'M43-IM-GT-S50-CXR6','status':'formal_generation_started_not_completed','datasets':{'chexbench':618,'slake':114,'vqarad':116},
      'serial_order':['chexbench','slake','vqarad'],'tools':['medgemma','llava_rad','chest_xray_expert','llava_med_qa','xray_phrase_grounding','medvlm_r1'],
      'method_changes':['six_model_tool_menu','nonempty_skill_candidates_always_prescreen_allow_empty_result'],
      'inherited_controls':'late-R49 ordinary MUTATE field/ANALYZE uniqueness/MAIRA EOS guard uniform from start; no old failed-cache repair registrations imported',
      'main_and_META':{'model':'qwen3.7-plus','temperature':.2,'top_p':.95,'max_output_tokens':2048,'enable_thinking':False},
      'embedding':{'model':'text-embedding-v4','dimension':1024},'window':30,'trajectory_buffer':20,'top_k':6,
      'fixed_main_or_tool_total_call_limit':None,'no_progress_stops':'unchanged existing3invalid/3identical-action rules',
      'feedback':'own prediction and event saved before own annotation; prior same-image feedback permitted; no current/future unreleased label',
      'per_dataset_initial_state':'empty Skill and same-image memory; no cross-dataset import',
      'warm_environment':'reused existing pinned local models/interpreters on physicalGPU1; no reinstall/rebuild/hash validation',
      'health':'new3 exactly once each on training_xmlab120; all healthy/native0; old3 not reprobed; no health output in production caches/Skill/scores',
      'evaluation_frozen_before_generation':read(PREP/'EVALUATION_PROTOCOL.json'),
      'claim_limits':'combination plus onlineGT/budgets/prompts/EOS/time and overlap confounds; no Skill-only causality, clinical capability or closed-test/official SOTA',
      'full_evidence_publication':'after complete raw0/one scoring per dataset; explicit allowlist excluding keys/weights/unrelated/user open_questions'}
    put(REPORT/'PROTOCOL.json',protocol);put(REPORT/'INITIAL_ACTUAL_LAUNCH.json',current)
    text='''# R50 CXR6 — running experiment

The actual user requested inspecting and running the supplied R50 CXR6 plan.
The single arm `M43-IM-GT-S50-CXR6` has now started: CheXbench618 → SLAKE114
→ VQA-RAD116, serially, each with empty Skill and same-image state.
This is a running record; complete-denominator scores are not available yet.

The six-model dynamic tool menu and nonempty-pool applicability prescreen are
a combined intervention. Existing late-R49 ordinary schema/EOS controls apply
uniformly from start. Main/META sampling, post-prediction online annotation
feedback, window30/buffer20/topk6 and no fixed total Agent/tool call ceiling
are retained. Health probes are separate and never reused as scored answers.

Actual new3 health checks each completed once with native0 on GPU1. The full
execution code review and one bounded tool-I/O archive-delta continuation are
complete; the exact tool request, raw stdout/stderr and available timeout logs
are now archived. Previous sources, synthetic fixture failure, reviewer
limitations and actual model/time/cost metadata are preserved.

R49 is archived and published at commit
`3ab0a927526e0910328b8db2503ac0fdc0e10036`. Its predictions, private scores,
transfers and result review are reused. The user waived post-push remote
verification. No R50 result is claimed from its targets or from enabling tools.

Fixed details: [protocol](PROTOCOL.json), [actual initial launch](INITIAL_ACTUAL_LAUNCH.json).
Results will retain full denominators, negative outcomes, all failures and
unknown costs, with onlineGT/budget/prompt/EOS/dataset-overlap confounds.
'''
    with (REPORT/'README.md').open('x',encoding='utf-8') as f:f.write(text)
    header=f'''## R50 FORMAL GENERATION STARTED ({when})

Actual root queue completed native0; remotecontroller3167009 alive/CheXrunner3167015 alive. First real main send1/response1/context1 observed; no prediction/feedback at that initial status. Unique ARM M43-IM-GT-S50-CXR6,618→114→116, GPU1, all848fresh. Producer code now frozen. All3new health50422DONE0 once, ownerenvagentdone, no old3probes; full initialcode review99479DONE0/ready and narrownewI/O delta25880DONE0/ready, uploaded only NEW CODE support+gate actual0. Do NOT repeat oldreviews/health/stage/queue/native sessions. Archive request-before-start crash limit explicitlyretained; unknown sendsstop, no auto resend. Use current helperstatus lightly. Local postprocessing still needs implementation from pre-generation EVALUATION_PROTOCOL, no scores yet; one full dataset pull/score only after complete and originalrunnerraw0. Active medrax-r47 monitors current chat. R49 finalpush already3ab0a927526e0910328b8db2503ac0fdc0e10036/user waivedfinalverify; no R49 work to repeat. Latest .aris overrides older text below.

'''
    for rel in ('local_assets/R50_NEW_CHAT_HANDOFF.md','local_assets/cxr_vqa_handoff.md'):
        p=ROOT/rel;p.write_text(header+p.read_text(encoding='utf-8-sig'),encoding='utf-8')
    ledger=ROOT/'.aris/compute/ssh-medrax-tools.md'
    with ledger.open('a',encoding='utf-8') as f:
        f.write('\n## R50 CXR6 actual warm reuse / fresh doc-following witness\n\n')
        f.write('No new environment/weights/install/hash. PhysicalGPU1. Fresh doc validator r50_env_doc_check executed the documented health command verbatim once, native50422exit0, no doc-vs-reality divergence. Only3added backends tested; old3warm history reused. Health did not enter Skill/cache/scores or make main/META/embedding calls.\n\n')
        for name,r in health['records'].items():
            f.write(f"- {name}: completed_healthy, native{r['native_exit_code']}, {r['elapsed_s']:.4f}s, revision{r['revision']}, one actual completed generate event; pinned existing donor interpreter.\n")
        f.write('\nExact raw evidence local_assets/r50_cxr6_preparation/health; deployment source and controls/reviews in same preparation namespace. New MAIRA wrapper was not re-probed; first actual production invocation exercises its unchanged inherited EOS assertions. Productioncontroller3167009 launched after actual3healthy/code+I/O reviews, main response1 observed.\n')
    print(json.dumps({'recorded_formal_launch':True,'controller':3167009,'runner':3167015,'current_first_main_responses':1,'R49_final_commit':'3ab0a927526e0910328b8db2503ac0fdc0e10036'}))

if __name__=='__main__':main()
