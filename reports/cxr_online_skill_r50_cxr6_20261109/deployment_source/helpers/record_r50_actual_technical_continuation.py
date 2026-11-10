"""Persist actual continuation and local reporting changes, without experiment calls."""
import ast,json,sys
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];PREP=ROOT/'local_assets/r50_cxr6_preparation'
FAIL=PREP/'failures/001_chex_104';status=json.loads(sys.argv[1])
assert status['arm']=='M43-IM-GT-S50-CXR6' and status['controller']['pid']=='3240536'
launch=json.loads((FAIL/'continuation.launch.completed.json').read_text(encoding='utf-8'))
retry=json.loads((FAIL/'explicit_retry/completed.json').read_text(encoding='utf-8'))
result=json.loads((FAIL/'explicit_retry/result.json').read_text(encoding='utf-8'))
assert launch['explicit_continuation_launched'] is True and retry['status']=='completed_healthy'
assert (FAIL/'explicit_retry/attempt.exitcode').read_text().strip()=='0'
sources=['experiments/r50_recovery_evidence.py','experiments/score_online_skill_r50.py',
 'experiments/export_online_skill_r50.py','experiments/verify_public_online_skill_r50.py',
 'local_assets/deploy_cxr6_r50.py','local_assets/collect_and_score_r50_once.py',
 'local_assets/finalize_r50_report.py','local_assets/publish_cxr6_r50.py','local_assets/capture_r50_publication_sources.py',
 'local_assets/inspect_r50_chex_failure_20261110.py','local_assets/inspect_r50_medvlm_load_failure.py',
 'local_assets/recover_r50_medvlm_pre_generation_once.py','local_assets/inspect_r50_retry_outcome.py',
 'local_assets/record_r50_actual_technical_stop.py','local_assets/continue_r50_after_known_tool_failure.py',
 'local_assets/record_r50_actual_technical_continuation.py','tests/test_recovery_evidence_r50.py']
for relative in sources:ast.parse((ROOT/relative).read_text(encoding='utf-8'),filename=relative)
sys.path.insert(0,str(ROOT/'experiments'));from r50_recovery_evidence import REMOTE_GATE_SOURCE
ast.parse(REMOTE_GATE_SOURCE,filename='remote_completion_gate_generated')
when=datetime.now(timezone.utc).astimezone().isoformat()
value={'utc':when,'status':'actual_explicit_retry_consumed_and_continuation_launched',
 'original_controller_exit':1,'original_chexbench_exit':1,
 'explicit_tool_retry_native_exit':0,'explicit_tool_retry_generations':1,
 'explicit_tool_retry_elapsed_s':result['elapsed_s'],'explicit_tool_retry_output_tokens':result['observation']['backend_output_tokens'],
 'actual_retry_text_quality':'poor; retained without answer-quality filtering',
 'underlying_tokenizer_loader_intermittency_cause':'unknown','model_environment_or_generation_parameters_changed':False,
 'active_controller_pid':3240536,'active_chexbench_pid':3240544,
 'latest_actual_status':status,'known_retry_may_be_launched_again':False,
 'adoption':'original failed cache+selection preserved by rename under GEN/technical_failures/001_medvlm_tokenizer_load; actual retry copied under GEN/technical_recovery and materialized active cache; original producer modules and completed predictions unchanged',
 'original_native_files_not_overwritten':True,'final_generation_exit_file':'generation.recovery001.exitcode',
 'active_job_mapping':'jobs/technical_continuation001.json','active_queue_status':'jobs/queue_status.recovery001.json',
 'new_reporting_module':'experiments/r50_recovery_evidence.py','local_module_scope':15,'owned_test_scope':8,
 'new_synthetic_policy_tests_passed':3,'new_test_elapsed_s':0.119,
 'new_test_checks':'retain original1 with final0; reject unknown/unfinished/unknown-send recovery; count failed attempt and accept poor technically successful text',
 'AST_sources_passed':len(sources),'generated_remote_gate_AST_passed':True,
 'new_actual_private_scores_transfers_of_complete_datasets_exports_public_reproductions_or_model_reviews':0,
 'postprocessing_extension':'all completion gates require attributed final0 and retained original1; both physical tool attempts/time counted; source exporter and final report include exact failure/continuation controls and cases',
 'model_review_status':'new post-launch and recovery/reporting code await ONE final actual complete-result review, no repeated model review now'}
with (FAIL/'ACTUAL_TECHNICAL_CONTINUATION.json').open('x',encoding='utf-8') as f:
 json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
p=ROOT/'.aris/IMPROVEMENT_STATE.json';state=json.loads(p.read_text(encoding='utf-8-sig'));state['updated_at']=when
state['status']='R50_explicit_technical_continuation_running_original_failures_retained'
state['R50']['current_technical_recovery'].update(value)
state['R50']['active_continuation']=launch
post=state['R50']['postprocessing'];post['actual_technical_recovery_extension']=value
post['publisher_owned_scope_latest']='explicit15localR50modules+8ownedtests+4R50marker-only indexes+newreport; original11producer remain unchanged and actual_CODE snapshot separate'
state['next']='R50 actual known technical continuation controller3240536/CheX3240544; use ONLY updated deploy_cxr6_r50.py status. Original controller3167009/CheX3167015 exit1 retained. Explicit retry3238018 DONE0/onegenerate/26.1349s/poor text retained, already ADOPTED/CONSUMED; NEVER launch again or repeat health/review. Underlying loader intermittency cause unknown. Frozen producer modules and104completed predictions preserved; main saved responses replayed locally. Updated collector/native evidence gates now accept ONLY exact known original1 + attributed final0; each full dataset pull+private score ONCE after actual final runner0. all3+controller final0 then final-controls/actual-source/export/repro/sourcepackage/ONE fresh complete-result review/finalwriter/explicit normalpush. New3 policy synthetic tests0.119s and17sourceAST+generatedgateAST passed; no old tests or actual private/public scores/exports/reviews. All recovery code/cost/time/failures in final model review. Source/publication scope now15localmodules+8tests; actual remote11producer unchanged. Do not touch user open_questions or repeat completedR49; pre-push base guard/no force, user waived postpush remote check.'
p.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
header=f'''## R50 ACTUAL TECHNICAL CONTINUATION ACTIVE / RETRY CONSUMED ({when})

Explicit once tool retry3238018 COMPLETED raw0, one actual MedVLM-R1 generate,26.1348517s/106outputtokens, poor text RETAINED without quality filtering. It is ADOPTED/CONSUMED; do NOT rerun retry/recovery helpers, health, probes or model reviews. Underlying reason for native tokenizer-load intermittency remains UNKNOWN. No install/rebuild/model/environment/generation-parameter change. Original frozen producer11modules unchanged.

Actual continuation controller3240536/CheXrunner3240544 launched with identical original runner/config. Saved prefix104 kept; existing paid responses reused, no unknown sends reissued or ownGT read before adoption. Original failed cache+selection renamed under GEN/technical_failures/001_medvlm_tokenizer_load; real successful retry+logs mirrored under GEN/technical_recovery/001_medvlm_tokenizer_load and materialized activecache. Original jobs/controller.exitcode,chexbench.exitcode and GEN/generation.exitcode remain1. New jobs/controller_recovery001,chexbench_recovery001 have distinct PID/log/exit files; GEN/generation.recovery001.exitcode will be written when that runner actually exits. SLAKE/VQA still serial and original job names. Immutable jobs/technical_continuation001.json selects active jobs; queue_status.recovery001.json is current. Updated deploy_cxr6_r50.py status reads this map and also shows original failures. Latest actual counts/liveness in .aris override launch count. Do NOT overwrite original1 as0.

Local reporting/collection code extended for THIS actual failure only, no original protocol tuning. New postprocessing-only experiments/r50_recovery_evidence.py gates original1 plus real attributed final0, rejects unknown recovery/unknown sends, validates actual failed/healthy attempt bindings without hashes/labels. Scorer counts both physical attempts and elapsed time; successful poor text is not redone. Export/verifier carry original/final raw exits, exact failed/successful records and job controls. Finalwriter case/report/resources disclose failure and continuation; publisher/source-map require new controller and native history. Current explicit scope15LOCALmodules+8ownedtests+4R50-only indexes+report. New module is not in original remote implementation_files/actual11producer; required actual_CODE source/count still exactly matches eventual source receipt. Source assembler includes all new helpers and bounded failure archive, never private credentials or weights.

New3 synthetic recovery-policy tests passed0.119s (retained initial1 vs final0; unknown/incomplete/unknown-send refusal; failed time counted and poor successful text accepted).17unique source AST and generated remote-gate AST passed. No old tests/reviews/probes repeated, no private R50 scores/whole-dataset transfers/export/public reproduction. All these new/reporting/recovery sources still await ONE actual full-result DeepSeek review AFTER848+once scores/public evidence; do not claim model-reviewed or publish now. Future collector commands remain same once-only CLI, but updated gates require genuine final0 AND retain first1; older handoff strict original0 text is superseded by this actual failure record.

Full raw private actual failure/diagnostics/retry/continuation receipts: local_assets/r50_cxr6_preparation/failures/001_chex_104. Initial bounded archive26files and actualretry17files are already copied once; do not pull them again. Formal completed-dataset mirror will later contain the explicitly preserved GEN failure/recovery records as part of its one allowed full transfer. Original startup MedVLMhealth was15.362778s, not old115.36s text typo. Existing automation continues sole-owner here; notify on this real recovery, then routine increments stay local.

'''
for relative in ('local_assets/R50_NEW_CHAT_HANDOFF.md','local_assets/cxr_vqa_handoff.md'):
 f=ROOT/relative;f.write_text(header+f.read_text(encoding='utf-8-sig'),encoding='utf-8')
with (ROOT/'reports/cxr_online_skill_r50_cxr6_20261109/TESTS.md').open('a',encoding='utf-8') as f:
 f.write('\n- Actual production failure: after104 CheX predictions, MedVLM-R1 tokenizer load failed before any generate event; original controller/runner raw1 retained. One explicit unchanged technical tool retry completed one generate (26.1348517s,106outputtokens), and its poor output was retained. Original frozen producer/completed predictions were preserved; saved API replies replayed for continuation. The underlying intermittent loader cause remains unknown. Separate original/final exits and both physical attempts/timing will be published. New3 recovery-policy synthetic tests passed0.119s;17unique source AST plus generated native-gate AST passed. No old tests, model review, private scores or actual public reproduction repeated. New local reporting module brings explicit publication scope to15modules/8tests, distinct from original11 deployed producer modules.\n')
print(json.dumps({'actual_continuation_recorded':True,'original_nonzero_exits_retained':True,'new_policy_tests':3,'AST_sources':len(sources),'actual_dataset_scores_or_model_reviews':0}))
