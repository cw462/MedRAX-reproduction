"""Record observed review/stage/health ownership without starting work."""
import json
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parents[1];prep=root/'local_assets/r50_cxr6_preparation'
path=root/'.aris/IMPROVEMENT_STATE.json';v=json.loads(path.read_text(encoding='utf-8-sig'))
when=datetime.now(timezone.utc).astimezone().isoformat()
push=json.loads((root/'local_assets/r49_publication/push_completed.json').read_text())
review=json.loads((prep/'CODE_REVIEW_METADATA.json').read_text())
assert push['commit']=='3ab0a927526e0910328b8db2503ac0fdc0e10036'
v.update(status='R49_final_pushed_R50_new3_health_and_bounded_archive_delta_review_running',updated_at=when,
  published_commit=push['commit'],report_url=push['report_url'],overall_objective_complete=False)
v['R49']['final_publication']={**push,'native_session':27508,'actual_native_exit':0,'git_index_paths':45,
  'all_original_scores_exports_result_review_reused':True,'user_post_push_remote_verification_waiver_honored':True}
v['R49']['final_followup_live']={'status':'DONE_CONSUMED','prepare_session':41511,'prepare_native_exit':0,
  'final_check_stage_push_session':27508,'final_check_stage_push_native_exit':0,'commit':push['commit']}
r=v['R50'];r.update(status='new3_health_running_bounded_tool_archive_delta_review_running',
  generation_started=False,actual_model_load_checks_completed=False,stage_completed=True,
  semantic_dryruns={'chexbench':{'n':618,'groups':488,'followups':130},'slake':{'n':114,'groups':30,'followups':84},'vqarad':{'n':116,'groups':58,'followups':58},'network_and_reference_file_opens':0},
  initial_actual_code_review={'native_session':99479,'native_exit':0,'verdict':'ready','scope_complete':True,
    'session_id':review['session_id'],'turns':review['turns'],'duration_ms':review['duration_ms'],
    'CLI_estimated_USD':review['CLI_estimated_USD'],'provider_invoice':False,'blockers':[]},
  health={'status':'RUNNING','native_session':50422,'remote_controller_pid':3163320,'owner':'r50_env_doc_check',
    'invocation':'python -X utf8 local_assets/deploy_cxr6_r50.py health','new_tools_only':True,
    'main_META_embedding_calls':0,'no_production_cache_Skill_or_score_reuse':True,'do_not_root_poll_or_repeat_agent_owned_session':True},
  archive_delta={'native_session':25880,'status':'RUNNING','trace':'.aris/traces/experiment-bridge/run_20261109_r50_cxr6_001/002-archive-delta',
    'same_CLI_session_as_initial_review':True,'source':'support/run_cxr_vqa_toolsets.py Tools.observe',
    'reason':'persist actual tool request, raw stdout and available timeout partial logs; declare existing MAIRA policy metadata',
    'new_synthetic_cases_passed':3,'synthetic_native_attempts':2,
    'first_fixture_only_error':'AST test namespace omitted __file__; no backend mock/real calls before error; fixture fixed only',
    'production_support_delta_deployed':False,'local_execution_ready_marker':'pending_archive_delta','original_ready_preserved':True})
v['next']='R49 COMPLETED actual ordinary final push27508exit0 commit3ab0a9; do not repeat publication/reviews/exports/private scores/pulls or final remote verification (user waived). R50 initial code review99479 DONE0/ready40turns. Stage DONE0/all3 label/network-blind dryruns. Agent r50_env_doc_check owns ONLY health50422/controller3163320 and consuming it; root must not duplicate/poll that session. Root ONLY live bounded archive delta review25880 (same reviewer thread), local support not deployed and local ready pending; after actual scope-ready upload only isolated support+updated gate, then wait real all3 health0 before queue ONCE. No formal848 generation yet. Read primary failure artifacts if needed, no unchanged retry/old3 probes/GPU0/CT/hashes.'
path.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
heading=f'''## LATEST ACTUAL OWNER STATE ({when})

R49 final follow-up PUSHED native27508exit0, commit3ab0a927526e0910328b8db2503ac0fdc0e10036,45changed paths, report {push['report_url']}. Final review10526/writer84164/public reproduction already complete. User waived final remote verification; none performed. No R49 work remains to repeat. Previous prepare93625/82168 stopped exactPIDs and raw1/1 retained; final prepare41511passed0/all3gates, final delta content45files/11070MDlinks passed. No new R49 inference/private score/pull/export/model-review.

R50 actual initial new code review99479 DONE0, freshCLI53d8f871-7ad7-4c18-b8d6-fc7b623c7a1a,scope_complete/ready/no blockers,40turns1174294ms,CLIestimatedUSD3.398147(notinvoice). Independent CODE/RUN stage DONE0/all3blinddryruns, no formal848calls. Agent r50_env_doc_check owns ONLY actual new3 health native50422/remotecontroller3163320/GPU1, still running. Root must not repeat or poll its native session. Agent will return actual native results and original failure artifacts. Original support reviewed/staged; health invokes genericworker directly and is unaffected by the next delta.

Root separately found actual tool request/rawstdout archival gap. Local isolated support Tools.observe now adds request-before-intent/stdout/available timeout logs and existing MAIRA policy metadata, no generation/cache/args/call changes. Original source preserved. New3synthetic archive tests passed. First fixture attempt omitted __file__ in AST namespace (0backend calls); corrected fixture only and second suite3passed0.143s. ONLY live bounded continuation review25880 in same reviewer CLI, trace002-archive-delta; NOT a new full unchanged review. Local ready marker pending_archive_delta blocksqueue, initial ready preserved, modified support NOT deployed. After actual delta scope-ready/root review, upload only newCODE support and updated actual gate. Then require agent all3health0 and launch formal helper queue once. Do not stageagain, reprobeold3, repeathealth, touchR49outputs/useropen_questions, add controls/seeds/CXR11, or claim generation already started. Latest .aris state overrides all older pending text below.

'''
for relative in ('local_assets/R50_NEW_CHAT_HANDOFF.md','local_assets/cxr_vqa_handoff.md'):
    p=root/relative;p.write_text(heading+p.read_text(encoding='utf-8-sig'),encoding='utf-8')
print(json.dumps({'R49_final_pushed_commit':push['commit'],'R50_health_owner':'r50_env_doc_check','bounded_delta_review_native':25880,'production_started':False}))
