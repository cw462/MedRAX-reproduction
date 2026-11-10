"""Materialize only an actually completed, scoped, selected execution review."""
import json
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
PREP=ROOT/'local_assets/r50_cxr6_preparation'
TRACE=ROOT/'.aris/traces/experiment-bridge/run_20261109_r50_cxr6_001/001-code'
ARM='M43-IM-GT-S50-CXR6'


def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))


def put(p,value):
    with p.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')


def verdict(text):
    found=[];decoder=json.JSONDecoder()
    for pos,c in enumerate(text):
        if c!='{':continue
        try:value,end=decoder.raw_decode(text[pos:])
        except ValueError:continue
        if isinstance(value,dict) and {'scope_complete','verdict','audit_scope','blockers'}<=set(value):found.append(value)
    assert len(found)==1,'one_actual_structured_final_review_verdict_required'
    return found[0]


def main():
    assert not (PREP/'CODE_REVIEW_METADATA.json').exists(),'review_result_already_materialized_inspect'
    assert read(TRACE/'exit.json')['exit_code']==0
    raw=read(TRACE/'stdout.json');meta=read(TRACE/'metadata.json');started=read(TRACE/'started.json')
    assert not raw.get('is_error') and raw.get('result')
    assert meta['session_id']==started['session_id'] and started['fresh'] is True
    assert meta.get('duration_ms',0)>0 and meta.get('turns',0)>0
    assert meta.get('modelUsage') and all('deepseek' in m.lower() for m in meta['modelUsage'])
    result=verdict(raw['result'])
    assert result['scope_complete'] is True
    assert {'method_and_leakage','runtime_GPU_and_health','launch_and_archiving'}<=set(result['audit_scope'])
    meta.update(result=result,scope_complete=True,audit_scope=result['audit_scope'],arm=ARM,
      code_review_completed=True,readiness_scope='code deployment and mandatory new3 health only; production requires actual healthy receipt',
      new_model_health_already_completed=False,provider_invoice=False)
    put(PREP/'CODE_REVIEW_METADATA.json',meta);put(PREP/'CODE_REVIEW_RAW_CLI.json',raw)
    with (PREP/'CODE_REVIEW.md').open('x',encoding='utf-8') as f:f.write(raw['result']+'\n')
    with (ROOT/'refine-logs/EXPERIMENT_CODE_REVIEW_R50_CXR6_20261109.md').open('x',encoding='utf-8') as f:f.write(raw['result']+'\n')
    if result['verdict']=='ready' and not result['blockers']:
        put(PREP/'EXECUTION_REVIEW_READY.json',{**meta,'utc':datetime.now(timezone.utc).isoformat(),
          'verdict':'ready','scope_complete':True,'native_review_session':99479,
          'production_queue_requires_three_new_tools_healthy':True})
    print(json.dumps({'actual_code_review_verdict':result['verdict'],'scope_complete':True,
      'blockers':result['blockers'],'health_or_generation_started':False,'session_id':meta['session_id']}))


if __name__=='__main__':main()
