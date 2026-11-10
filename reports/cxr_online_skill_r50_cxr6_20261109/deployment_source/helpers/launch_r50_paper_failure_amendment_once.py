"""Once-only approved A.4 continuation; no failed tool generation is retried."""
import ast
import contextlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

from deploy_cxr6_r50 import (connect, remote_python, script, PREP, RUN, CODE, PYTHON,
                             ARM, DATASETS, COUNTS, program, TRANSPORT_HOME)

LOCAL = Path(__file__).resolve().parents[1]
STATE = PREP / 'amendment003'
NAMES = ('r50_failure_observation.py', 'r50_services_amended.py', 'r50_run_amended.py')
POLICY_ID = '003_paper_tool_failure_observation'
Q = 'chexbench_openi_0078'
KEY = '65e65ea9f529a7ce811f54147a7c2326bf115aeaf0ddb2960ff9c3437d77626d'

CONTROLLER = r'''
from pathlib import Path
import fcntl,json,os,subprocess,sys,time,shutil
r=Path(RUN);jobs=r/'jobs';tag='amendment003'
lock=(jobs/'.controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
approval=json.loads((r/'amendment003_user_approval.json').read_text())
assert approval['approved'] is True and approval['user_reply']=='那按照论文中的同样来吧'
for phase in ('controller','controller_recovery001','controller_recovery002','chexbench','chexbench_recovery001','chexbench_recovery002'):
 assert (jobs/(phase+'.exitcode')).read_text().strip()=='1'
main_key=sys.stdin.buffer.readline();embedding_key=sys.stdin.buffer.readline().strip().decode()
assert main_key.strip() and embedding_key
def state(v):
 v.update(protocol_amendment=tag,policy_id=POLICY_ID,all_prior_CheX_controller_and_generation_raw_exits=1)
 path=jobs/'queue_status.amendment003.json';temporary=path.with_suffix('.tmp')
 temporary.write_text(json.dumps(v,indent=2)+'\n');temporary.replace(path)
for ds in DATASETS:
 job=ds+'_amendment003'
 assert not (jobs/(job+'.pid')).exists(),'amended_dataset_already_invoked'
 while True:
  mem=int(subprocess.check_output(['nvidia-smi','--id=1','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip())
  state({'state':'waiting_gpu1' if mem>=500 else 'starting_dataset','dataset':ds,'gpu1_used_mib':mem,'other_jobs_modified':False})
  if mem<500:break
  time.sleep(30)
 assert shutil.disk_usage(r).free>3*1024**3,'insufficient_free_disk'
 env=dict(os.environ,R50_EMBEDDING_API_KEY=embedding_key,LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false')
 for flag in ('CUDA_LAUNCH_BLOCKING','TORCH_SHOW_CPP_STACKTRACES'):env.pop(flag,None)
 with (jobs/(job+'.log')).open('xb',buffering=0) as log:
  p=subprocess.Popen(PROGRAMS[ds]+['--execute','--api-key-stdin'],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,env=env)
  with (jobs/(job+'.pid')).open('x') as f:f.write(str(p.pid))
  with (jobs/(job+'.started.json')).open('x') as f:json.dump({'utc':time.time(),'pid':p.pid,'dataset':ds,'policy_id':POLICY_ID,'command':PROGRAMS[ds]},f,indent=2)
  state({'state':'running_dataset','dataset':ds,'pid':p.pid})
  p.communicate(main_key)
 rc=p.returncode
 with (jobs/(job+'.exitcode')).open('x') as f:f.write(str(rc)+'\n')
 out=r/'generation'/ds
 with (out/'generation.amendment003.exitcode').open('x') as f:f.write(str(rc)+'\n')
 if rc:
  state({'state':'dataset_failed_stop_queue','dataset':ds,'exit_code':rc,'pid':p.pid});raise SystemExit(rc)
 complete=json.loads((out/'complete.json').read_text())
 assert complete['status']=='generation_complete' and complete['questions']==COUNTS[ds] and complete['arm']==ARM
 assert complete['execution_protocol_amendment']==POLICY_ID
state({'state':'all_three_datasets_exited_zero','datasets':DATASETS,'arm':ARM})
'''

LAUNCH = r'''
from pathlib import Path
import ast,fcntl,json,os,shlex,subprocess,sys,time,shutil
r=Path(RUN);jobs=r/'jobs';g=r/'generation/chexbench';code=Path(CODE)/'experiments'
lock=(jobs/'.amendment003.launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not Path('/proc/3277341').exists() and not Path('/proc/3277347').exists()
for phase in ('controller','controller_recovery001','controller_recovery002','chexbench','chexbench_recovery001','chexbench_recovery002'):
 assert (jobs/(phase+'.exitcode')).read_text().strip()=='1'
for filename in ('generation.exitcode','generation.recovery001.exitcode','generation.recovery002.exitcode'):
 assert (g/filename).read_text().strip()=='1'
assert not (jobs/'controller_amendment003.pid').exists() and not (jobs/'protocol_amendment003.json').exists()
assert not (r/'protocol_amendment003.json').exists() and not (r/'queue_controller_amendment003.py').exists()
assert len(list((g/'predictions'/ARM).glob('*.json')))==316
assert len(list((g/'feedback').glob('*.json')))==316 and len(list((g/'contexts').glob('*.json')))==317
for folder in ('predictions/'+ARM,'prediction_events','feedback'):
 assert not (g/folder/(Q+'.json')).exists()
selection=json.loads((g/'services/tool_selections/R50-AGENT'/Q/'1.json').read_text())
failed=json.loads((g/'services/tool_cache'/KEY/'result.json').read_text())
assert selection['status']=='failed' and selection['cache_key']==KEY and selection['tool']=='xray_phrase_grounding'
assert failed['status']=='failed' and failed.get('error')=='guard_policy_incomplete_or_non_eos_termination'
assert len(failed['actual_model_events'])==1 and failed['actual_model_events'][0]['status']=='completed'
assert failed['actual_model_events'][0]['elapsed_s']==48.27794743003324
assert all(selection.get(k)==v for k,v in failed.items())
assert json.loads((Path(CODE)/'configs/cxr_vqa_tool_worker_gpu.json').read_text())=={'cuda_visible_devices':'1'}
assert shutil.disk_usage(r).free>3*1024**3
assert APPROVAL['approved'] is True and APPROVAL['user_reply']=='那按照论文中的同样来吧'
sys.path.insert(0,str(code))
from cxr_online_primitives_r50 import assert_closed_sends
assert_closed_sends(g,require_receipts=True)
for ds in DATASETS:
 assert not (jobs/(ds+'_amendment003.pid')).exists()
 if ds!='chexbench':
  assert not (jobs/(ds+'.pid')).exists()
  assert not list((r/'generation'/ds/'predictions'/ARM).glob('*.json'))
for name,source in MODULES.items():
 assert not (code/name).exists();ast.parse(source)
assert all(not (r/'generation'/ds/'protocol_amendment.json').exists() for ds in DATASETS)
# All checks precede new execution-code/registry writes. Existing files stay in place.
for name,source in MODULES.items():
 with (code/name).open('x') as f:f.write(source)
with (r/'amendment003_user_approval.json').open('x') as f:json.dump(APPROVAL,f,ensure_ascii=False,indent=2)
policy={'schema':'r50_paper_tool_failure_observation_v1','policy_id':POLICY_ID,'arm':ARM,
 'explicit_user_approval':True,'user_reply':APPROVAL['user_reply'],'all_remaining_questions':True,
 'regenerate_failed_output':False,'modify_original_producers':False,'change_model_EOS_or_token_parameters':False,
 'original_exit1_records_retained':True,'held_question':Q,'held_cache_key':KEY,
 'new_execution_modules':list(MODULES),'paper_scope':'MedRAX appendix A.4 in the existing R50 JSON interface; not an exact original-paper evaluation reproduction',
 'failure_trajectory_learning':'Existing technical-failure exclusion remains; failed tool output is not healthy image evidence',
 'separate_evaluation_retry_policy':'No new automatic paid retries or unknown-send resends',
 'amendment_recorded_at':time.time()}
with (r/'protocol_amendment003.json').open('x') as f:json.dump(policy,f,ensure_ascii=False,indent=2)
for ds in DATASETS:
 folder=r/'generation'/ds;folder.mkdir(parents=True,exist_ok=True)
 with (folder/'protocol_amendment.json').open('x') as f:json.dump(dict(policy,dataset=ds,saved_prefix=316 if ds=='chexbench' else 0),f,ensure_ascii=False,indent=2)
mapping={'schema':'r50_explicit_protocol_amendment_v1','arm':ARM,'amendment_id':POLICY_ID,
 'active_controller':'controller_amendment003','active_queue_status':'queue_status.amendment003.json',
 'dataset_jobs':{ds:ds+'_amendment003' for ds in DATASETS},
 'generation_exit_files':{ds:'generation.amendment003.exitcode' for ds in DATASETS},
 'prior_mappings':['technical_continuation001.json','technical_continuation002.json'],
 'prior_controller_jobs':['controller','controller_recovery001','controller_recovery002'],
 'prior_chexbench_jobs':['chexbench','chexbench_recovery001','chexbench_recovery002'],
 'all_prior_native_exits':1,'original_11_producer_modules_modified':False,'execution_code_extended':True,
 'new_execution_modules':list(MODULES),'saved_predictions_modified':False,'failed_tool_regenerated':False}
with (jobs/'protocol_amendment003.json').open('x') as f:json.dump(mapping,f,indent=2)
with (r/'queue_controller_amendment003.py').open('x') as f:f.write(CONTROLLER)
main_key=sys.stdin.buffer.readline();embed_key=sys.stdin.buffer.readline();assert main_key.strip() and embed_key.strip()
rd,wr=os.pipe();os.write(wr,main_key+embed_key);os.close(wr)
command=shlex.join([PYTHON,'-u',str(r/'queue_controller_amendment003.py')])+'; rc=$?; printf "%s\\n" "$rc" > '+shlex.quote(str(jobs/'controller_amendment003.exitcode'))+'; exit "$rc"'
try:
 with (jobs/'controller_amendment003.log').open('xb',buffering=0) as log:
  process=subprocess.Popen(['bash','-c',command],stdin=rd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 with (jobs/'controller_amendment003.pid').open('x') as f:f.write(str(process.pid))
 with (jobs/'controller_amendment003.started.json').open('x') as f:json.dump({'utc':time.time(),'pid':process.pid,'policy_id':POLICY_ID,'arm':ARM,'gpu':'1'},f,indent=2)
 print(json.dumps({'approved_amendment_launched':True,'controller_pid':process.pid,'policy_id':POLICY_ID,
  'mapping':mapping,'failed_output_regenerated':False,'completed_predictions_modified':False,
  'original_11_producer_modules_modified':False,'new_execution_modules':list(MODULES)}))
finally:os.close(rd)
'''


def sources():
    programs={ds:program(ds) for ds in DATASETS}
    for command in programs.values():
        assert command[2]==CODE+'/experiments/run_online_skill_r50.py'
        command[2]=CODE+'/experiments/r50_run_amended.py'
    controller=script(CONTROLLER,RUN=RUN,ARM=ARM,DATASETS=DATASETS,COUNTS=COUNTS,
                      POLICY_ID=POLICY_ID,PROGRAMS=programs)
    approval=json.loads((STATE/'USER_APPROVAL.json').read_text(encoding='utf-8'))
    modules={name:(LOCAL/'experiments'/name).read_text(encoding='utf-8') for name in NAMES}
    launch=script(LAUNCH,RUN=RUN,CODE=CODE,PYTHON=PYTHON,ARM=ARM,DATASETS=DATASETS,
                  POLICY_ID=POLICY_ID,Q=Q,KEY=KEY,MODULES=modules,APPROVAL=approval,CONTROLLER=controller)
    ast.parse(controller);ast.parse(launch)
    return controller,launch


def main():
    controller,launch=sources()
    for name,source in (('controller.generated.py',controller),('launch.generated.py',launch)):
        with (STATE/name).open('x',encoding='utf-8') as f:f.write(source)
    with (STATE/'launch.started.json').open('x',encoding='utf-8') as f:
        json.dump({'utc':datetime.now(timezone.utc).isoformat(),'explicit_approval':True,
                   'scope':'paper A.4 terminal failure delivery; no backend retry'},f,indent=2)
    keys=(TRANSPORT_HOME/'.secrets/token_plan_api.key').read_bytes().strip()+b'\n'+(TRANSPORT_HOME/'.secrets/qwen_api.key').read_bytes().strip()+b'\n'
    output=io.StringIO()
    try:
        with connect() as client,contextlib.redirect_stdout(output):
            remote_python(client,launch,timeout=45,input_bytes=keys)
        result=json.loads(output.getvalue())
    except Exception as error:
        with (STATE/'launch.failure.json').open('x',encoding='utf-8') as f:
            json.dump({'utc':datetime.now(timezone.utc).isoformat(),'error':repr(error),
                       'native_stderr':'original exec transcript; inspect before any correction or repeat',
                       'generated_source_and_partial_remote_artifacts_retained':True},f,indent=2)
        print(output.getvalue());raise
    with (STATE/'launch.completed.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    statepath=LOCAL/'.aris/IMPROVEMENT_STATE.json';state=json.loads(statepath.read_text(encoding='utf-8'))
    state['R50']['status']='RUNNING_AMENDED_PAPER_TOOL_FAILURE_OBSERVATION'
    state['R50']['protocol_amendment003'].update(state='launched',launch=result,
        launch_native_exit=0,new_targeted_synthetic_tests=3,new_tests_elapsed_s=0.692,
        old_tests_repeated=False,new_model_review_calls=0)
    state['R50']['current_controller_pid']=result['controller_pid']
    state['status']='R50_amended_A4_actual_continuation_launched'
    statepath.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
