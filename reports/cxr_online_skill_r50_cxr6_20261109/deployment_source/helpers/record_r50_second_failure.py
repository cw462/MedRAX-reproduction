"""Record this new actual stop without changing the prior consumed recovery."""
import json,sys
from datetime import datetime,timezone
from pathlib import Path

root=Path(__file__).resolve().parents[1];prep=root/'local_assets/r50_cxr6_preparation'
folder=prep/'failures/002_chex_183';when=datetime.now(timezone.utc).astimezone().isoformat()
status=json.loads(sys.argv[1]);assert status['controller']['pid']=='3240536' and status['controller']['exit']=='1'
failure=json.loads((folder/'actual_failure.json').read_text(encoding='utf-8'))
launch=json.loads((folder/'technical_retry.launch.completed.json').read_text(encoding='utf-8'))
value={'utc':when,'status':'second_actual_stop_explicit_retry_pending_not_adopted','failure_id':'002_medgemma_tokenizer_load',
 'question_id':failure['question_id'],'ordinal':184,'saved_prefix':183,'tool':'medgemma','selection_ordinal':1,
 'original_controller_and_CheX_exits':1,'first_continuation_controller_and_CheX_exits':1,
 'failure':'TokenizerFast.from_file JSON parse expected comma or closing bracket at line1814948 column7',
 'failed_actual_model_events':[],'underlying_common_native_loader_reason':'unknown; different model and interpreter from first stop',
 'bounded_original_files_copied_once':18,'explicit_retry_pid':launch['pid'],'explicit_retry_launch_native_exit':0,
 'max_explicit_attempts_for_this_failure':1,'adopted':False,'queue_restarted':False,
 'first_failure_retry_consumed':True,'prior_helpers_not_reexecuted':True,
 'new_main_META_embedding_calls':0,'completed_predictions_producer_model_environment_modified':False,
 'latest_original_status':status,
 'next':'Read only new attempt3275049 outcome; do not launch it again. If unsuccessful stop further retries. If healthy, explicit second adoption/continuation must preserve original1 and recovery0011, use distinct recovery002 native files and retain all183predictions. Update only local reporting gates for these two actual events; no scoring or model review now.'}
with (folder/'ACTUAL_SECOND_TECHNICAL_STOP.json').open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
p=root/'.aris/IMPROVEMENT_STATE.json';state=json.loads(p.read_text(encoding='utf-8-sig'));r=state['R50']
history=r.setdefault('technical_recovery_events',[])
if not history:history.append(r['current_technical_recovery'])
history.append(value);r['current_technical_recovery']=value
state['status']='R50_second_actual_tool_load_stop_one_new_retry_pending'
state['updated_at']=when;state['next']='R50 second ACTUAL STOP atCheX183/618; recovery001 controller3240536/runner3240544 originalexit1 retained. medgemma tokenizer load before generate failed at184. '+value['next']
p.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
header=f'''## R50 SECOND ACTUAL TOOL LOAD STOP / NEW ONCE RETRY PENDING ({when})

Recovery001 controller3240536/CheXrunner3240544 both DEAD/raw1 after183saved/183feedback/184contexts,469main sends andresponses,105META/6windows. Initial controller/CheX1 also retained. New failed q chexbench_slake_0068 ordinal184/toolselection1 medgemma, TokenizerFast.from_file native JSON parse error expected comma/closing bracket line1814948 column7; actual_model_events=[], no current prediction/ownGT read. Different model/interpreter than first MedVLMstop; common underlying native load problem UNKNOWN.18exact new failure files captured once under failures/002_chex_183. No model/env/config/producer/prediction modification, hashes or extra generate probes.

NEW one explicit tool retry ACTUALLY launched remote3275049 under RUN/technical_recovery/002_medgemma_tokenizer_load, native launch0, not yet adopted/queue restart. Exact original image/args/model/environment/GPU1, only new outputdir; at mostthisone attempt, no autoretry. Read actual completed/attempt.exitcode and preserve all raw stdout/stderr. Prior001 retry/adoption/helpers are still CONSUMED and were NOT executed again. If new retry fails stop further retries. If healthy, explicit recovery002 must keep both original and recovery001 exit1 and all183existing predictions, add distinct native files/jobmap/registry, and extend ONLY local postprocessing/evidence gates/resource accounting to both real events. Never overwrite failure as0 or retry legal wrong/poor text. No actual dataset score/transfer/export/public repro/review now.

This actual stop supersedes older ACTIVE statements below. Current .aris current_technical_recovery and receipts take precedence; update active state only from actual new outcome. Existing automation remains sole owner, no duplicate monitor.

'''
for relative in ('local_assets/R50_NEW_CHAT_HANDOFF.md','local_assets/cxr_vqa_handoff.md'):
 f=root/relative;f.write_text(header+f.read_text(encoding='utf-8-sig'),encoding='utf-8')
print(json.dumps({'second_actual_stop_recorded':True,'new_retry_pid':launch['pid'],'adopted':False,'prior_consumed_retry_reexecuted':False}))
