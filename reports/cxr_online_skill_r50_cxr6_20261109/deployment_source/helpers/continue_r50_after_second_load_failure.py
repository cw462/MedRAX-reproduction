"""Explicit second continuation, reusing recorded orchestration source only.

The consumed first helper's main() is never invoked. Its preserved launch source
is specialized to this second observed failure and a distinct recovery002 job.
"""
import ast,contextlib,io,json
from datetime import datetime,timezone
from pathlib import Path
from deploy_cxr6_r50 import connect,remote_python,script,PREP,RUN,CODE,PYTHON,ARM,DATASETS,COUNTS,program,TRANSPORT_HOME
from continue_r50_after_known_tool_failure import CONTROLLER as FIRST_CONTROLLER
from recover_r50_medgemma_load_once import Q,KEY,NAME

LOCAL=PREP/'failures/002_chex_183'

def second_sources():
    old=ast.parse(Path(__file__).with_name('continue_r50_after_known_tool_failure.py').read_text(encoding='utf-8'))
    assignments=[n for n in ast.walk(old) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='launch' for t in n.targets)]
    assert len(assignments)==1
    launch=assignments[0].value.args[0].value
    # No invocation/side effects from the original main; all new job names differ.
    launch=launch.replace('recovery001','recovery002')
    launch=launch.replace("'/proc/3167009'","'/proc/3240536'").replace("'/proc/3167015'","'/proc/3240544'")
    launch=launch.replace("==104","==183").replace("'original_saved_prefix':104","'original_saved_prefix':183")
    launch=launch.replace("/Q/'5.json'","/Q/'1.json'")
    launch=launch.replace("'ordinal':105,'selection_ordinal':5","'ordinal':184,'selection_ordinal':1")
    launch=launch.replace("'tool':'medvlm_r1'","'tool':'medgemma'")
    launch=launch.replace("'r50_known_medvlm_pre_generate_recovery_v1'","'r50_known_medgemma_pre_generate_recovery_v2'")
    launch=launch.replace("'r50_explicit_technical_continuation_v1'","'r50_explicit_technical_continuation_v2'")
    launch=launch.replace("g/'technical_recovery.json'","g/'technical_recovery002.json'")
    launch=launch.replace("'original_generation_exit':1,","'original_generation_exit':1,'prior_generation_exit_file':'generation.recovery001.exitcode','prior_continuation_exit':1,'parent_recovery_id':'001_medvlm_tokenizer_load',")
    launch=launch.replace("'original_controller_exit':1,'original_chexbench_exit':1,'original_failed_records_retained':True,",
      "'original_controller_exit':1,'original_chexbench_exit':1,'prior_controller_exit':1,'prior_chexbench_exit':1,'parent_recovery_id':'001_medvlm_tokenizer_load','original_failed_records_retained':True,")
    launch=launch.replace("assert (g/'generation.exitcode').read_text().strip()=='1'",
      "assert (g/'generation.exitcode').read_text().strip()=='1'\nassert (g/'generation.recovery001.exitcode').read_text().strip()=='1'\nassert (jobs/'controller_recovery001.exitcode').read_text().strip()=='1' and (jobs/'chexbench_recovery001.exitcode').read_text().strip()=='1'")
    controller=FIRST_CONTROLLER.replace('recovery001','recovery002').replace("r/'generation/chexbench/technical_recovery.json'","r/'generation/chexbench/technical_recovery002.json'")
    controller=controller.replace("original_chexbench_exit=1)","original_chexbench_exit=1,prior_continuation_exit=1)")
    ast.parse(launch);ast.parse(controller)
    return launch,script(controller,RUN=RUN,ARM=ARM,DATASETS=DATASETS,COUNTS=COUNTS,NAME=NAME,PROGRAMS={ds:program(ds) for ds in DATASETS})

def main():
    done=json.loads((LOCAL/'explicit_retry/completed.json').read_text(encoding='utf-8'))
    assert done['status']=='completed_healthy' and done['tool']=='medgemma' and done['native_worker_exit_code']==0
    assert (LOCAL/'explicit_retry/attempt.exitcode').read_text().strip()=='0'
    source,controller=second_sources()
    with (LOCAL/'continuation.launch.started.json').open('x',encoding='utf-8') as f:json.dump({
      'utc':datetime.now(timezone.utc).isoformat(),'scope':'second observed pre-generation load failure only',
      'first_helpers_not_reexecuted':True,'existing183predictions_and_original_producer_preserved':True},f,indent=2)
    launch=script(source,RUN=RUN,CODE=CODE,PYTHON=PYTHON,ARM=ARM,Q=Q,KEY=KEY,NAME=NAME,CONTROLLER=controller)
    keys=(TRANSPORT_HOME/'.secrets/token_plan_api.key').read_bytes().strip()+b'\n'+(TRANSPORT_HOME/'.secrets/qwen_api.key').read_bytes().strip()+b'\n'
    output=io.StringIO()
    with connect() as client,contextlib.redirect_stdout(output):remote_python(client,launch,timeout=30,input_bytes=keys)
    result=json.loads(output.getvalue())
    with (LOCAL/'continuation.launch.completed.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))

if __name__=='__main__':main()
