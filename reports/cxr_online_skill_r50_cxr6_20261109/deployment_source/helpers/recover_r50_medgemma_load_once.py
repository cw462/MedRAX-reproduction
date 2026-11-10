"""One explicit retry for the second actually observed zero-generate failure.

Importing the first attempt's recorded source does not execute its consumed
main(). Only this new known MedGemma failure is eligible, once.
"""
import ast,contextlib,io,json
from datetime import datetime,timezone
from deploy_cxr6_r50 import connect,remote_python,script,PREP,RUN,CODE,PYTHON,ARM
from recover_r50_medvlm_pre_generation_once import ATTEMPT

Q='chexbench_slake_0068'
KEY='90fc56c698e79fe11b01dbef78553feedef1c3f5ea3a92447feca6b700fc86dc'
NAME='002_medgemma_tokenizer_load'
LOCAL=PREP/'failures/002_chex_183'

def main():
    failure=json.loads((LOCAL/'actual_failure.json').read_text(encoding='utf-8'))['failed_selection']['record']
    assert failure['tool']=='medgemma' and failure['actual_model_events']==[] and failure['status']=='failed'
    source=ATTEMPT.replace("runtime['tools']['medvlm_r1']","runtime['tools'][TOOL]")
    source=source.replace("'selection_ordinal':5,'tool':'medvlm_r1'","'selection_ordinal':1,'tool':TOOL")
    source=script(source,RUN=RUN,CODE=CODE,Q=Q,NAME=NAME,TOOL='medgemma')
    ast.parse(source)
    with (LOCAL/'technical_retry.launch.started.json').open('x',encoding='utf-8') as f:
        json.dump({'utc':datetime.now(timezone.utc).isoformat(),'known_zero_generate_failure':True,'automatic_retry':False,'max_explicit_attempts':1},f,indent=2)
    launch=script(r'''
from pathlib import Path
import json,os,subprocess,shlex,time
r=Path(RUN);g=r/'generation/chexbench';folder=r/'technical_recovery'/NAME
assert not Path('/proc/3240536').exists() and not Path('/proc/3240544').exists()
assert (r/'jobs/controller_recovery001.exitcode').read_text().strip()=='1'
assert (r/'jobs/chexbench_recovery001.exitcode').read_text().strip()=='1'
assert not (g/'predictions'/ARM/(Q+'.json')).exists() and not (g/'feedback'/(Q+'.json')).exists()
cache=g/'services/tool_cache'/KEY
failed=json.loads((cache/'result.json').read_text());selection=json.loads((g/'services/tool_selections/R50-AGENT'/Q/'1.json').read_text())
assert failed['status']=='failed' and failed['error_type']=='Exception' and failed.get('actual_model_events')==[]
assert failed['error']=='expected `,` or `]` at line 1814948 column 7'
assert selection['cache_key']==KEY and selection['tool']=='medgemma' and selection['status']=='failed'
assert 'TokenizerFast.from_file' in (cache/'backend.stderr.log').read_text()
used=int(subprocess.check_output(['nvidia-smi','--id=1','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip())
assert used<500,'GPU1_busy_no_restart'
folder.mkdir(parents=True,exist_ok=False)
for name,body in [('original_request.json',(cache/'request.json').read_text()),('original_result.json',(cache/'result.json').read_text()),('original_selection.json',json.dumps(selection))]:
 with (folder/name).open('x') as f:f.write(body)
with (folder/'attempt.py').open('x') as f:f.write(SOURCE)
with (folder/'started.json').open('x') as f:json.dump({'utc':time.time(),'question_id':Q,'selection_ordinal':1,
 'original_cache_key':KEY,'known_pre_generation_failure':True,'max_explicit_attempts':1,'automatic_retry':False,
 'original_model_environment_parameters_unchanged':True,'user_labels_or_completed_predictions_read':False},f,indent=2)
cmd=shlex.join([PYTHON,'-u',str(folder/'attempt.py')])+'; rc=$?; printf "%s\\n" "$rc" > '+shlex.quote(str(folder/'attempt.exitcode'))+'; exit "$rc"'
with (folder/'controller.log').open('xb',buffering=0) as out:p=subprocess.Popen(['bash','-c',cmd],stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
(folder/'attempt.pid').write_text(str(p.pid)+'\n')
print(json.dumps({'explicit_technical_attempt_launched':True,'pid':p.pid,'folder':str(folder),'tool':'medgemma','adopted_or_queue_restarted':False,'gpu':'1'}))
''',RUN=RUN,CODE=CODE,PYTHON=PYTHON,ARM=ARM,Q=Q,KEY=KEY,NAME=NAME,SOURCE=source)
    output=io.StringIO()
    with connect() as client,contextlib.redirect_stdout(output):remote_python(client,launch,timeout=30)
    result=json.loads(output.getvalue())
    with (LOCAL/'technical_retry.launch.completed.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))

if __name__=='__main__':main()
