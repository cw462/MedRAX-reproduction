"""Record actual recovery002, its preserved failed launch and local evidence code."""
import ast,json,sys
from datetime import datetime,timezone
from pathlib import Path

root=Path(__file__).resolve().parents[1];prep=root/'local_assets/r50_cxr6_preparation'
folder=prep/'failures/002_chex_183';status=json.loads(sys.argv[1])
assert status['controller']['pid']=='3277341' and status['technical_continuation']['recovery_id']=='002_medgemma_tokenizer_load'
launch=json.loads((folder/'continuation_corrected.launch.completed.json').read_text(encoding='utf-8'))
retry=json.loads((folder/'explicit_retry/completed.json').read_text(encoding='utf-8'))
result=json.loads((folder/'explicit_retry/result.json').read_text(encoding='utf-8'))
assert retry['status']=='completed_healthy' and (folder/'explicit_retry/attempt.exitcode').read_text().strip()=='0'
sources=['experiments/r50_recovery_evidence.py','experiments/export_online_skill_r50.py',
 'local_assets/deploy_cxr6_r50.py','local_assets/collect_and_score_r50_once.py','local_assets/finalize_r50_report.py',
 'local_assets/publish_cxr6_r50.py','local_assets/capture_r50_publication_sources.py','tests/test_recovery_evidence_r50.py',
 'local_assets/inspect_r50_chex_second_failure_once.py','local_assets/recover_r50_medgemma_load_once.py',
 'local_assets/record_r50_second_failure.py','local_assets/inspect_r50_second_retry_outcome_once.py',
 'local_assets/continue_r50_after_second_load_failure.py','local_assets/continue_r50_second_load_corrected_once.py',
 'local_assets/record_r50_second_continuation.py']
for relative in sources:ast.parse((root/relative).read_text(encoding='utf-8'),filename=relative)
sys.path.insert(0,str(root/'experiments'));from r50_recovery_evidence import REMOTE_GATE_SOURCE
ast.parse(REMOTE_GATE_SOURCE,filename='second_actual_native_completion_gate')
when=datetime.now(timezone.utc).astimezone().isoformat()
value={'utc':when,'status':'second_explicit_retry_adopted_consumed_and_recovery002_running',
 'known_retry_may_be_launched_again':False,'adopted':True,'queue_restarted':True,
 'explicit_tool_retry_pid':3275049,'explicit_tool_retry_native_exit':0,'explicit_tool_retry_generations':1,
 'explicit_tool_retry_elapsed_s':result['elapsed_s'],'explicit_tool_retry_output_tokens':result['observation']['backend_output_tokens'],
 'answer_quality_or_GT_used_to_choose_retry':False,'completed_predictions_modified':False,'saved_prefix_preserved':183,
 'original_producer_model_environment_or_generation_parameters_changed':False,
 'underlying_native_tokenizer_loading_cause':'unknown across two models/interpreters',
 'active_controller_pid':3277341,'active_chexbench_pid':status['datasets']['chexbench']['pid'],
 'original_controller_and_CheX_exits':1,'first_continuation_controller_and_CheX_exits':1,
 'active_jobs':'controller_recovery002/chexbench_recovery002','active_queue_status':'queue_status.recovery002.json',
 'immutable_active_mapping':'jobs/technical_continuation002.json','generation_exit_file':'generation.recovery002.exitcode',
 'first_second_continuation_helper_native_exit':1,'helper_failure_stage':'old technical_continuation001 filename guard before cache adoption or queue launch',
 'failed_helper_source_and_marker_preserved':True,'corrected_launch_native_exit':0,'corrected_launch_reused_successful_tool_result':True,
 'new_targeted_synthetic_tests_passed':1,'new_targeted_test_elapsed_s':0.051,'older3policytests_repeated':False,
 'AST_changed_sources_passed':len(sources),'generated_remote_gate_AST_passed':True,
 'publication_scope':'15local modules/8owned test files/4R50 marker-only indexes/report; original11remote producer unchanged',
 'actual_private_scores_whole_dataset_pulls_exports_public_reproductions_or_model_reviews':0,
 'latest_actual_status':status,
 'completion_contract':'Keep original and recovery001 raw1; require corresponding real recovery002 final0 and full cohort before once collection/score. Exact known two failure/retry histories and their physical time count, no unknown registrations or silent resends.',
 'final_review_contract':'ONE fresh complete-results DeepSeek review must include both actual load failures, both once retries, native helper guard failure/correction, all local postprocessing/publication code and real resource/time unknowns'}
with (folder/'ACTUAL_SECOND_TECHNICAL_CONTINUATION.json').open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
p=root/'.aris/IMPROVEMENT_STATE.json';state=json.loads(p.read_text(encoding='utf-8-sig'));r=state['R50']
r['current_technical_recovery'].update(value);r['technical_recovery_events'][-1].update(value)
r.setdefault('continuation_history',[r['active_continuation']]).append(launch);r['active_continuation']=launch
r['postprocessing']['second_actual_recovery_extension']=value
state['status']='R50_recovery002_running_original_and_recovery001_failures_retained';state['updated_at']=when
state['next']='R50 recovery002 controller3277341/CheX3277347 actualrunning; use only updated helper status, latest counts in.aris. Original3167009/3167015 and recovery0013240536/3240544 all originalexit1 retained. Both explicit tool retries3275049(second24.0388s254tokens) and3238018(first26.1349s106tokens) DONE0/onegenerateeach/ADOPTED/CONSUMED; never rerun any consumed helpers/reviews/health. Second initial launch helper failed guard beforeadoption native1, original source retained, correctedlaunch0 reused tool result. Native tokenizer intermittency rootcause UNKNOWN; no env/model/producer/pred edits. Prepared local gates now enforce exact two actual failures, both physical attempts/time, original1+recovery0011+actualfinal recovery0020; no earlycollect/score. Each complete dataset pull+score ONCE with native sessionIDs/serialSFTP; finalcontrols/source afterall3+controller final0; publicexport/repro/sourcepackage thenONE fresh fullresult DeepSeek review inclall failures/reportcode, finalwriter, explicit normalpush. New1 targeted synthetic .051s/15changedAST+generatedgateAST passed; old tests/reviews not repeated. All private scores/wholeGEN pulls/publicexport/repro/Git stillpending. Scope15localmodules8tests actual11producerunchanged; no useropen_questions, weights/keys/extraarms orpostpushremoteverify.'
p.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
header=f'''## R50 RECOVERY002 ACTUALLY RUNNING / BOTH TOOL RETRIES CONSUMED ({when})

Latest active controller3277341/CheXrunner3277347, immutable jobs/technical_continuation002.json, current queue_status.recovery002.json. Original controller/CheX and recovery001 controller/CheX are ALL rawexit1/dead, retained without overwrite. New final native files controller_recovery002/chexbench_recovery002 and GEN/generation.recovery002.exitcode are distinct and pending real completion. SLAKE/VQA remain serial original job names. Use ONLY updated deploy_cxr6_r50.py status; it reports active/original/prior states. Actual count/liveness in.aris wins over stale text.

Second actual failure after183saved was chexbench_slake_0068 ordinal184/toolselection1 medgemma tokenizer JSON parse, actual_model_events=[]/no prediction or ownGT.18exact raw originals captured once under failures/002_chex_183. One NEW explicit unchanged tool retry3275049 COMPLETED0/onegenerate/24.0387727s/254outputtokens,17new retry files copied once, nowADOPTED/CONSUMED. First MedVLMretry3238018 is alsoDONE/CONSUMED. Never rerun either tool/health/helper or duplicate captures. Both tool outputs retained without answer-quality/GT filtering. Underlying native tokenizer loading intermittency across two different environments/models remains UNKNOWN. No model/env/params/install/rebuild/producer edit or hashcheck.183savedpredictions preserved, paid replies reused locally.

First recovery002 launch helper continue_r50_after_second_load_failure.py actually FAILED native1 at generated remote line19, old technical_continuation001.json guard retained by mistake. This was before cache adoption/queue launch (first such mutation line32); only a lockfile opened. Original helper/marker and continuation.failed.generated.py/failure.json preserved. Corrected helper continue_r50_second_load_corrected_once.py changed ONLY new002 mapping/lock filename, launched native0 while reusing the already completed tool result. No extra tool/API generation from this guard correction. Full original native stderr is in actual exec transcript; no false separate raw-byte stderr claim.

Local evidence module/scorer accounting/export/verifier/collector/writer/publisher/sourceassembler now support EXACTLY these two actual failures, not arbitrary repair registrations. Both GEN/technical_recovery.json (001) and technical_recovery002.json retained; GEN/technical_failures and technical_recovery each contain001+002. Original generation.exitcode1 and generation.recovery001.exitcode1 retained; final generation.recovery002.exitcode must actually0. Jobs controls/oldnative1/currentnative0/evidence/resources/affectedcasepages/sourcepackage all carry both histories and failed+healthy physical attempts/time. No adapter/metrics formula change. Explicit scope remains15LOCALmodules+8owned test files+4R50-only indexes+report, actualremote11producer unchanged. New helpers and all bounded failure artifacts included in sourceassembler.

Only ONE new targeted synthetic test passed0.051s: original1+firstcontinuation1+final0020 retained, first failure cannot be replaced with0, corresponding native job attribution matches. Older3 recovery-policy tests NOT rerun.15changed source AST plus generatedremotegate AST passed. No actual private R50score/whole-dataset transfer/export/public reproduction/Git or model review. Actual once pipelines wait genuine complete cohort/final0, then all3 controls/source/public evidence/sourcepackage/ONE actual fresh complete-result DeepSeek review (include this actual helper failure/correction and all postprocessing/resource code), finalwriter/allowlistednormalpush. Negative results, poor text, onlineGT/prompt/EOS/budget/time/overlap confounds remain.

Latest.aris overrides all older RUNNING/raw0-only/001-only statements below. Existing sole-owner monitor continues here; ordinary increments only local, real failures/complete group scores/finalpush notify. No automatic R51 or additional arms. User open_questions untouched; pre-push mainchangeSTOP/noforce and user post-push remotecheck waived.

'''
for relative in ('local_assets/R50_NEW_CHAT_HANDOFF.md','local_assets/cxr_vqa_handoff.md'):
 f=root/relative;f.write_text(header+f.read_text(encoding='utf-8-sig'),encoding='utf-8')
with (root/'reports/cxr_online_skill_r50_cxr6_20261109/TESTS.md').open('a',encoding='utf-8') as f:
 f.write('\n- Second actual production stop after183 CheX predictions: MedGemma native tokenizer JSON loading failed before generate. Original and recovery001 raw1 retained. One unchanged explicit tool retry3275049 completed one generate (24.0387727s,254outputtokens), then recovery002 resumed using frozen producer, saved predictions and paid replies. The first recovery002 launch helper had an actual old-filename guard failure/native1 before adoption/launch; its source/marker/generated program/failure receipt remain. Corrected launch reused the existing successful tool result, no new generation. Underlying loader cause unknown. ONE new targeted multi-failure/native attribution synthetic test passed0.051s; old3tests not rerun.15changed AST plus generatedremotegate AST passed. All actual final scoring/export/review/publication remains pending.\n')
print(json.dumps({'actual_recovery002_recorded':True,'active_controller':3277341,'native_failure_histories_retained':True,'new_targeted_tests':1,'changed_AST_sources':len(sources),'new_model_reviews_private_scores_or_Git':0}))
