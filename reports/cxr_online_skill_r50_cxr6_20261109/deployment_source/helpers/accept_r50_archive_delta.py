"""Accept only actual narrow continuation; keep production gated until upload."""
import json
from pathlib import Path
from accept_r50_execution_review import verdict

ROOT=Path(__file__).resolve().parents[1];PREP=ROOT/'local_assets/r50_cxr6_preparation'
TRACE=ROOT/'.aris/traces/experiment-bridge/run_20261109_r50_cxr6_001/002-archive-delta'

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def put(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')

def main():
    assert not (PREP/'ARCHIVE_DELTA_METADATA.json').exists()
    raw=read(TRACE/'stdout.json');meta=read(TRACE/'metadata.json');started=read(TRACE/'started.json')
    assert read(TRACE/'exit.json')['exit_code']==0 and not raw.get('is_error')
    assert meta['session_id']==read(PREP/'CODE_REVIEW_METADATA.json')['session_id'] and started['fresh'] is False
    assert meta.get('duration_ms',0)>0 and meta.get('turns',0)>0 and meta.get('modelUsage')
    assert all('deepseek' in m.lower() for m in meta['modelUsage'])
    result=verdict(raw['result']);assert result['scope_complete'] is True
    assert 'tool_request_and_stdout_archiving_delta' in result['audit_scope']
    meta.update(result=result,scope='narrow additional Tools.observe I/O archiving; original full-code review retained')
    put(PREP/'ARCHIVE_DELTA_METADATA.json',meta);put(PREP/'ARCHIVE_DELTA_RAW_CLI.json',raw)
    with (PREP/'ARCHIVE_DELTA_REVIEW.md').open('x',encoding='utf-8') as f:f.write(raw['result']+'\n')
    if result['verdict']=='ready' and not result['blockers']:
        health=read(PREP/'HEALTH_RECEIPT.json');assert health['native_exit_code']==0
        actual=read(PREP/'health/complete.json');assert actual['status']=='three_new_tools_healthy'
        next_ready=read(PREP/'EXECUTION_REVIEW_READY.initial.json')
        next_ready.update(verdict='ready',archive_delta_review_pending=False,archive_delta_actual_review=meta,
          actual_new3_health_completed=True,actual_health_native_session=50422,
          static_runtime_pending_flags='preserved as pre-health config; actual new3 readiness is the separate complete health receipt',
          original_full_code_review_not_repeated=True)
        put(PREP/'EXECUTION_REVIEW_READY.next.json',next_ready)
        put(PREP/'ARCHIVE_DELTA_READY.json',{'verdict':'ready','scope_complete':True,'session_id':meta['session_id'],
          'actual_health_completed':True,'production_support_upload_completed':False})
    print(json.dumps({'actual_delta_verdict':result['verdict'],'blockers':result['blockers'],'production_locally_gated_until_upload':True}))

if __name__=='__main__':main()
