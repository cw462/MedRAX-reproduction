"""Upload one reviewed archive-only support delta into NEW CODE, before launch."""
import json
from datetime import datetime,timezone
from pathlib import Path
from deploy_cxr6_r50 import connect,remote_python,PREP,CODE,RUN,read,write_new

def main():
    assert not (PREP/'archive_delta.upload.started.json').exists(),'delta_upload_already_invoked_inspect'
    assert read(PREP/'ARCHIVE_DELTA_READY.json')['verdict']=='ready'
    assert read(PREP/'EXECUTION_REVIEW_READY.json')['verdict']=='pending_archive_delta'
    write_new(PREP/'archive_delta.upload.started.json',{'utc':datetime.now(timezone.utc).isoformat(),'CODE':CODE,'RUN':RUN})
    with connect() as c:
        remote_python(c,'CODE='+repr(CODE)+'\nRUN='+repr(RUN)+'\n'+r'''
from pathlib import Path
import json,shutil
r=Path(RUN);target=Path(CODE)/'experiments/run_cxr_vqa_toolsets.py';backup=target.with_name('run_cxr_vqa_toolsets.before_request_archive.py')
assert not (r/'jobs/controller.pid').exists() and not (r/'jobs/controller.started.json').exists()
assert json.loads((r/'health/complete.json').read_text())['status']=='three_new_tools_healthy'
assert target.is_file() and not backup.exists()
shutil.copyfile(target,backup)
print(json.dumps({'original_reviewed_support_preserved':True,'formal_queue_not_started':True}))
''',timeout=30)
        with c.open_sftp() as s:
            s.put(str(PREP/'support/run_cxr_vqa_toolsets.py'),CODE+'/experiments/run_cxr_vqa_toolsets.py.archive_delta_upload')
            s.put(str(PREP/'EXECUTION_REVIEW_READY.next.json'),RUN+'/EXECUTION_REVIEW_READY.json.archive_delta_upload')
        remote_python(c,'CODE='+repr(CODE)+'\nRUN='+repr(RUN)+'\n'+r'''
from pathlib import Path
import ast,json
target=Path(CODE)/'experiments/run_cxr_vqa_toolsets.py';pending=target.with_name(target.name+'.archive_delta_upload')
ast.parse(pending.read_text());pending.replace(target)
r=Path(RUN);ready=json.loads((r/'EXECUTION_REVIEW_READY.json.archive_delta_upload').read_text())
assert ready['scope_complete'] is True and ready['verdict']=='ready' and ready['archive_delta_review_pending'] is False
assert ready['archive_delta_actual_review']['result']['verdict']=='ready'
(r/'EXECUTION_REVIEW_READY.json.archive_delta_upload').replace(r/'EXECUTION_REVIEW_READY.json')
print(json.dumps({'reviewed_tool_request_stdout_archive_delta_deployed':True,'AST':'passed','new_model_API_calls':0,'formal_queue_not_started':True}))
''',timeout=30)
    (PREP/'EXECUTION_REVIEW_READY.json').write_text((PREP/'EXECUTION_REVIEW_READY.next.json').read_text(encoding='utf-8'),encoding='utf-8')
    write_new(PREP/'archive_delta.upload.completed.json',{'utc':datetime.now(timezone.utc).isoformat(),
      'status':'reviewed_archive_delta_uploaded','native_transport_returned_zero':True,'model_API_calls':0,'production_started':False})
    print(json.dumps({'archive_delta_deployment':'completed','production_started':False}))

if __name__=='__main__':main()
