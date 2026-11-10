"""Correct only the actually failed pre-adoption continuation filename guard.

The original failed helper/source/marker remain. No additional tool/API call.
"""
import ast,contextlib,io,json
from datetime import datetime,timezone
from continue_r50_after_second_load_failure import second_sources,LOCAL,Q,KEY,NAME
from deploy_cxr6_r50 import connect,remote_python,script,RUN,CODE,PYTHON,ARM,TRANSPORT_HOME

def main():
    original,controller=second_sources()
    old_source=script(original,RUN=RUN,CODE=CODE,PYTHON=PYTHON,ARM=ARM,Q=Q,KEY=KEY,NAME=NAME,CONTROLLER=controller)
    with (LOCAL/'continuation.failed.generated.py').open('x',encoding='utf-8') as f:f.write(old_source)
    with (LOCAL/'continuation.launch.failure.json').open('x',encoding='utf-8') as f:json.dump({
      'status':'failed','native_exit':1,'stage':'pre-adoption guard, generated remote source line19',
      'error':'AssertionError: consumed technical_continuation001.json exists; wrong old filename retained',
      'earliest_adoption_mutation_source_line':32,'actual_adoption_or_queue_launch_or_new_model_calls':0,
      'remote_only_created_or_opened_launch_lock':True,'original_failed_helper_and_marker_retained':True,
      'native_trace_available':'original exec tool output; no claim of separately captured raw-byte stderr'},f,indent=2)
    corrected=original.replace('technical_continuation001.json','technical_continuation002.json').replace('.continuation001.launch.lock','.continuation002.launch.lock')
    assert corrected!=original and 'technical_continuation001.json' not in corrected
    ast.parse(corrected)
    with (LOCAL/'continuation_corrected.launch.started.json').open('x',encoding='utf-8') as f:json.dump({
      'utc':datetime.now(timezone.utc).isoformat(),'corrected_scope':'distinct recovery002 mapping/lock filename only',
      'reuses_already_completed_tool_result':True,'no_new_tool_main_META_embedding_calls':True},f,indent=2)
    launch=script(corrected,RUN=RUN,CODE=CODE,PYTHON=PYTHON,ARM=ARM,Q=Q,KEY=KEY,NAME=NAME,CONTROLLER=controller)
    keys=(TRANSPORT_HOME/'.secrets/token_plan_api.key').read_bytes().strip()+b'\n'+(TRANSPORT_HOME/'.secrets/qwen_api.key').read_bytes().strip()+b'\n'
    output=io.StringIO()
    with connect() as client,contextlib.redirect_stdout(output):remote_python(client,launch,timeout=30,input_bytes=keys)
    result=json.loads(output.getvalue())
    with (LOCAL/'continuation_corrected.launch.completed.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))

if __name__=='__main__':main()
