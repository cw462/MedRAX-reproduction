"""Explicit once-only adoption/continuation for the actually observed load failure.

Original producer modules, completed predictions and original nonzero job exits
are immutable. The known failed cache/selection move to an explicit failure
archive; the actual successful retry materializes the active cache once.
"""
import ast,contextlib,io,json
from datetime import datetime,timezone
from deploy_cxr6_r50 import connect,remote_python,script,PREP,RUN,CODE,PYTHON,ARM,DATASETS,COUNTS,program,TRANSPORT_HOME
from recover_r50_medvlm_pre_generation_once import Q,KEY,NAME

LOCAL=PREP/'failures/001_chex_104'
CONTROLLER=r'''
from pathlib import Path
import fcntl,json,os,subprocess,sys,time,shutil
r=Path(RUN);jobs=r/'jobs';tag='recovery001'
lock=(jobs/'.controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert (jobs/'controller.exitcode').read_text().strip()=='1'
assert json.loads((r/'generation/chexbench/technical_recovery.json').read_text())['adopted_retry_id']==NAME
main_key=sys.stdin.buffer.readline();embedding_key=sys.stdin.buffer.readline().strip().decode()
assert main_key.strip() and embedding_key
def state(v):
 v.update(technical_continuation=tag,original_controller_exit=1,original_chexbench_exit=1)
 path=jobs/'queue_status.recovery001.json';temporary=path.with_suffix('.tmp')
 temporary.write_text(json.dumps(v,indent=2)+'\n');temporary.replace(path)
for ds in DATASETS:
 job=ds+'_recovery001' if ds=='chexbench' else ds
 assert not (jobs/(job+'.pid')).exists(),'continuation_dataset_already_invoked'
 while True:
  mem=int(subprocess.check_output(['nvidia-smi','--id=1','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip())
  state({'state':'waiting_gpu1' if mem>=500 else 'starting_dataset','dataset':ds,'gpu1_used_mib':mem,'other_jobs_modified':False})
  if mem<500:break
  time.sleep(60)
 assert shutil.disk_usage(r).free>3*1024**3,'insufficient_free_disk'
 env=dict(os.environ,R50_EMBEDDING_API_KEY=embedding_key,LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false')
 for flag in ('CUDA_LAUNCH_BLOCKING','TORCH_SHOW_CPP_STACKTRACES'):env.pop(flag,None)
 with (jobs/(job+'.log')).open('xb',buffering=0) as log:
  p=subprocess.Popen(PROGRAMS[ds]+['--execute','--api-key-stdin'],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,env=env)
  (jobs/(job+'.pid')).write_text(str(p.pid));state({'state':'running_dataset','dataset':ds,'pid':p.pid})
  p.communicate(main_key)
 rc=p.returncode
 with (jobs/(job+'.exitcode')).open('x') as f:f.write(str(rc)+'\n')
 out=r/'generation'/ds;name='generation.recovery001.exitcode' if ds=='chexbench' else 'generation.exitcode'
 if out.is_dir():
  with (out/name).open('x') as f:f.write(str(rc)+'\n')
 if rc:
  state({'state':'dataset_failed_stop_queue','dataset':ds,'exit_code':rc,'pid':p.pid});raise SystemExit(rc)
 complete=json.loads((out/'complete.json').read_text())
 assert complete['status']=='generation_complete' and complete['questions']==COUNTS[ds] and complete['arm']==ARM
state({'state':'all_three_datasets_exited_zero','datasets':DATASETS,'arm':ARM})
'''

def main():
    outcome=json.loads((LOCAL/'explicit_retry/completed.json').read_text(encoding='utf-8'))
    assert outcome['status']=='completed_healthy' and outcome['native_worker_exit_code']==0
    assert (LOCAL/'explicit_retry/attempt.exitcode').read_text().strip()=='0'
    ast.parse(script(CONTROLLER,RUN=RUN,ARM=ARM,DATASETS=DATASETS,COUNTS=COUNTS,NAME=NAME,PROGRAMS={ds:program(ds) for ds in DATASETS}))
    with (LOCAL/'continuation.launch.started.json').open('x',encoding='utf-8') as f:json.dump({
        'utc':datetime.now(timezone.utc).isoformat(),'adoption':'known failed pre-generation tool only',
        'original_producer_source_and_predictions_unchanged':True,'automatic_retry':False},f,indent=2)
    launch=script(r'''
from pathlib import Path
import json,os,subprocess,shlex,shutil,fcntl,datetime
r=Path(RUN);jobs=r/'jobs';g=r/'generation/chexbench';retry=r/'technical_recovery'/NAME
lock=(jobs/'.continuation001.launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not Path('/proc/3167009').exists() and not Path('/proc/3167015').exists()
assert (jobs/'controller.exitcode').read_text().strip()=='1' and (jobs/'chexbench.exitcode').read_text().strip()=='1'
assert (g/'generation.exitcode').read_text().strip()=='1'
assert not (jobs/'controller_recovery001.pid').exists() and not (jobs/'technical_continuation001.json').exists()
assert len(list((g/'predictions'/ARM).glob('*.json')))==104
assert not (g/'predictions'/ARM/(Q+'.json')).exists() and not (g/'feedback'/(Q+'.json')).exists()
cache=g/'services/tool_cache'/KEY;selection=g/'services/tool_selections/R50-AGENT'/Q/'5.json'
failed=json.loads((cache/'result.json').read_text());old_selection=json.loads(selection.read_text())
result=json.loads((retry/'result.json').read_text());request=json.loads((retry/'request.json').read_text())
original_request=json.loads((cache/'request.json').read_text());done=json.loads((retry/'completed.json').read_text())
assert failed['status']=='failed' and failed.get('actual_model_events')==[] and old_selection['cache_key']==KEY
assert done['status']=='completed_healthy' and (retry/'attempt.exitcode').read_text().strip()=='0'
assert result['status']=='completed' and result['identity']==failed['identity']
assert request==dict(original_request,artifact_dir=str(retry/'artifacts'))
assert len(result['actual_model_events'])==1 and result['actual_model_events'][0]['status']=='completed'
assert not result['derived_images'],'this bounded recovery does not reinterpret derived assets'
archive=g/'technical_failures'/NAME;archive.mkdir(parents=True,exist_ok=False)
# Preserve originals by same-filesystem rename; no completed prediction touched.
cache.rename(archive/'tool_cache');selection.rename(archive/'selection.json')
shutil.copytree(retry,g/'technical_recovery'/NAME)
cache.mkdir()
for name in ('request.json','result.json','backend.stdout.log','backend.stderr.log'):
 shutil.copyfile(retry/name,cache/name)
shutil.copytree(retry/'artifacts',cache/'artifacts')
actual_start=json.loads((retry/'started.json').read_text())
started={'identity':result['identity'],'utc':datetime.datetime.fromtimestamp(actual_start['utc'],datetime.timezone.utc).isoformat(),
 'automatic_retry':False,'explicit_known_technical_retry':NAME,
 'materialized_from_actual_retry_started':'technical_recovery/'+NAME+'/started.json'}
with (cache/'started.json').open('x') as f:json.dump(started,f,indent=2)
registry={'schema':'r50_known_medvlm_pre_generate_recovery_v1','adopted_retry_id':NAME,
 'question_id':Q,'ordinal':105,'selection_ordinal':5,'cache_key':KEY,'tool':'medvlm_r1',
 'failed_archive':'technical_failures/'+NAME,'successful_attempt':'technical_recovery/'+NAME,
 'original_generation_exit':1,'final_generation_exit_file':'generation.recovery001.exitcode',
 'original_controller_exit':1,'original_runner_exit':1,'original_saved_prefix':104,
 'failed_attempt_model_events':[],'exact_image_args_revision_unchanged':True,
 'completed_predictions_modified':False,'unknown_sends_reissued':False,'own_GT_read_before_adoption':False,
 'model_environment_or_generation_parameters_changed':False,'underlying_loader_intermittency_cause':'unknown',
 'adoption_is_technical_not_answer_quality_selection':True,'successful_attempt_mirrored_for_publication':True}
with (g/'technical_recovery.json').open('x') as f:json.dump(registry,f,indent=2)
mapping={'schema':'r50_explicit_technical_continuation_v1','arm':ARM,'recovery_id':NAME,
 'original_controller':'controller','active_controller':'controller_recovery001',
 'active_queue_status':'queue_status.recovery001.json',
 'dataset_jobs':{'chexbench':'chexbench_recovery001','slake':'slake','vqarad':'vqarad'},
 'generation_exit_files':{'chexbench':'generation.recovery001.exitcode','slake':'generation.exitcode','vqarad':'generation.exitcode'},
 'original_controller_exit':1,'original_chexbench_exit':1,'original_failed_records_retained':True,
 'original_producer_modules_modified':False,'saved_predictions_modified':False,'automatic_retry':False}
with (jobs/'technical_continuation001.json').open('x') as f:json.dump(mapping,f,indent=2)
with (r/'queue_controller_recovery001.py').open('x') as f:f.write(CONTROLLER)
main_key=__import__('sys').stdin.buffer.readline();embed_key=__import__('sys').stdin.buffer.readline()
assert main_key.strip() and embed_key.strip()
rd,wr=os.pipe();os.write(wr,main_key+embed_key);os.close(wr)
cmd=shlex.join([PYTHON,'-u',str(r/'queue_controller_recovery001.py')])+'; rc=$?; printf "%s\\n" "$rc" > '+shlex.quote(str(jobs/'controller_recovery001.exitcode'))+'; exit "$rc"'
try:
 with (jobs/'controller_recovery001.log').open('xb',buffering=0) as out:
  p=subprocess.Popen(['bash','-c',cmd],stdin=rd,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
 (jobs/'controller_recovery001.pid').write_text(str(p.pid))
 with (jobs/'controller_recovery001.started.json').open('x') as f:json.dump({'utc':datetime.datetime.now(datetime.timezone.utc).timestamp(),
  'pid':p.pid,'arm':ARM,'original_controller_exit':1,'technical_recovery_id':NAME},f,indent=2)
 print(json.dumps({'explicit_continuation_launched':True,'controller_pid':p.pid,'original_controller_exit':1,
  'original_chexbench_exit':1,'saved_predictions_modified':False,'producer_modules_modified':False,
  'recovery_id':NAME,'mapping':mapping}))
finally:os.close(rd)
''',RUN=RUN,CODE=CODE,PYTHON=PYTHON,ARM=ARM,Q=Q,KEY=KEY,NAME=NAME,
CONTROLLER=script(CONTROLLER,RUN=RUN,ARM=ARM,DATASETS=DATASETS,COUNTS=COUNTS,NAME=NAME,PROGRAMS={ds:program(ds) for ds in DATASETS}))
    keys=(TRANSPORT_HOME/'.secrets/token_plan_api.key').read_bytes().strip()+b'\n'+(TRANSPORT_HOME/'.secrets/qwen_api.key').read_bytes().strip()+b'\n'
    output=io.StringIO()
    with connect() as client,contextlib.redirect_stdout(output):remote_python(client,launch,timeout=30,input_bytes=keys)
    result=json.loads(output.getvalue())
    with (LOCAL/'continuation.launch.completed.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))

if __name__=='__main__':main()
