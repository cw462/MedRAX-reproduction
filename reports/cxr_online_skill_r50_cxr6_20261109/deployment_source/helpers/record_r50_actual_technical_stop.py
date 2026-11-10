"""Record the observed original stop and one explicitly launched tool retry."""
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PREP=ROOT/'local_assets/r50_cxr6_preparation'
FAIL=PREP/'failures/001_chex_104';when=datetime.now(timezone.utc).astimezone().isoformat()
p=ROOT/'.aris/IMPROVEMENT_STATE.json';state=json.loads(p.read_text(encoding='utf-8-sig'))
assert state['R50']['last_lightweight_actual_status']['snapshot']['controller']['exit']=='1'
failure=json.loads((FAIL/'actual_failure.json').read_text(encoding='utf-8'))
value={'utc':when,'status':'explicit_single_tool_retry_running_not_adopted','original_controller_pid':3167009,
 'original_runner_pid':3167015,'original_controller_exit':1,'original_runner_exit':1,'saved_prefix':104,
 'question_id':failure['question_id'],'ordinal':105,'tool_selection_ordinal':5,'tool':'medvlm_r1',
 'original_failure':'tokenizer load: Token `ViewChild` out of vocabulary; masked by absent protobuf ImportError',
 'original_actual_model_events':[],'underlying_reason_for_health_success_vs_load_failure':'unknown; identical configured paths/runtime and old tokenizer mtimes, no hash or identity attestation',
 'original_diagnostic_copies':26,'failure_archive':'local_assets/r50_cxr6_preparation/failures/001_chex_104',
 'explicit_retry_launch_native_exit':0,'explicit_retry_pid':3238018,
 'explicit_retry_remote':'runs/online_skill_r50_cxr6_20261109/technical_recovery/001_medvlm_tokenizer_load',
 'max_explicit_tool_retries':1,'automatic_retry':False,'adopted_into_production':False,'queue_restarted':False,
 'main_META_embedding_calls_during_diagnosis_and_tool_retry':0,
 'model_environment_or_producer_or_predictions_modified':False,'new_hashes_or_weight_checks':False,
 'health_actual_duration_note':'saved completed.json is MedVLM-R1 15.362778s; older heartbeat115.36s was a text typo, no new health run',
 'external_primary_code_consulted':'https://raw.githubusercontent.com/huggingface/tokenizers/v0.22.2/tokenizers/src/models/bpe/model.rs',
 'next':'wait/read only this actual attempt. If unsuccessful preserve both failures and stop retries. If healthy, design explicit technical adoption/continuation with original exit1 retained; never overwrite original exits or saved104 predictions; final reporting gates must distinguish actual continuation0 from original1.'}
with (FAIL/'ACTUAL_TECHNICAL_STOP.json').open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
state['updated_at']=when;state['status']='R50_technical_stop_original1_single_tool_retry_running'
state['R50']['current_technical_recovery']=value
state['next']='R50 ACTUAL TECHNICAL STOP CheX104/618, controller3167009/runner3167015 originalexit1; medvlm tokenizer load failed before any generate. Explicit one tool retry3238018 running, NOT adopted/noqueue restart. Read actual completed/attempt.exitcode; no retry launch/health/probe/oldreview repeat. Preserve all actual failure receipts. '+value['next']
p.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
header=f'''## R50 ACTUAL TECHNICAL STOP / ONE EXPLICIT TOOL RETRY RUNNING ({when})

Original controller3167009 and CheXrunner3167015 are DEAD, each original rawexit1;104predictions/104feedback/105contexts,305main sends and305responses saved,60META/3windows. SLAKE/VQA not started. Actual failed question chexbench_rad_restruct_0227 ordinal105/toolselection5 medvlm_r1. Original stderr first shows Token `ViewChild` out of vocabulary in TokenizerFast.from_file; subsequent absentprotobuf ImportError masks it. actual_model_events=[] proves no generate for this failed worker. Failed current question has no prediction or ownGT feedback.26exact original job/context/call/selection/cache files captured once in failures/001_chex_104; this was a bounded actual-failure archive, not formal dataset pull/score.

Health and failed production runtime objects equal and same jyj interpreter/model path. Tokenizer metadata mtimes predate health, Python JSON contains ViewChild; underlying reason for inconsistent native load remains unknown. No environment installation/model/tokenizer/weight modification, hash or generation probe performed. Saved actual MedVLMhealth completed.json duration15.362778s; older heartbeat115.36s is a typo, not a second probe. Existing unhealthy/gibberish health answer remains as actual output.

ONE explicit technical tool retry ACTUALLY LAUNCHED native0, remote wrapper3238018, RUN/technical_recovery/001_medvlm_tokenizer_load. Exact original image/question/model args/env/GPU1, only new outputartifact dir. Original failed cache andselection untouched. Separate actual stdout/stderr/process/worker.exitcode/result/completed/attempt.exitcode. At mostthisone attempt; no automatic retry. It is NOT adopted and formal queue is NOT restarted. Read actual outcome only; do not launch another tool/model/health call. If it fails stop retries and preserve raw sources. If healthy, must implement explicit technical adoption+continuation with originalexit1 retained and finalcollection/export/writer gates extended honestly; do NOT overwrite original job exits as0 or104saved predictions. No favorableanswer check or ownGT read. All failures/recovery costs/time/source must enter final actual complete-result review/publication.

Latest .aris current_technical_recovery overrides all older RUNNING/strict originalraw0-only text below. Existing once-postprocessing code is prepared, not executed; actual final pipeline needs retained-original1 plus genuine attributed continuation0, never fake initial success.

'''
for relative in ('local_assets/R50_NEW_CHAT_HANDOFF.md','local_assets/cxr_vqa_handoff.md'):
 f=ROOT/relative;f.write_text(header+f.read_text(encoding='utf-8-sig'),encoding='utf-8')
print(json.dumps({'recorded_actual_original_exit1':True,'single_tool_retry_pid':3238018,'actual_adoption_or_queue_restart':False}))
