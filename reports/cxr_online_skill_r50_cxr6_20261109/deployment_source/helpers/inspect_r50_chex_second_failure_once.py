"""Once-only archive of the second actual stop; does not invoke prior helpers."""
import json
from datetime import datetime,timezone
from deploy_cxr6_r50 import connect,RUN,ARM,PREP

DEST=PREP/'failures/002_chex_183'

def main():
    DEST.mkdir(parents=True,exist_ok=False);files=[]
    def put(name,value):
        with (DEST/name).open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
    put('inspection.started.json',{'utc':datetime.now(timezone.utc).isoformat(),'scope':'second actual stopped question/cache/jobs only; no label or model calls'})
    with connect() as client,client.open_sftp() as s:
        def capture(relative):
            path=DEST/'originals'/relative
            if path.exists():return path
            path.parent.mkdir(parents=True,exist_ok=True);info=s.stat(RUN+'/'+relative)
            with s.open(RUN+'/'+relative,'rb') as a,path.open('xb') as b:
                while True:
                    body=a.read(1024*1024)
                    if not body:break
                    b.write(body)
            files.append({'relative':relative,'remote_size':info.st_size,'remote_mtime':info.st_mtime});return path
        def parsed(relative):return json.loads(capture(relative).read_text(encoding='utf-8'))
        for job in ('controller_recovery001','chexbench_recovery001'):
            for suffix in ('.log','.pid','.exitcode'):capture('jobs/'+job+suffix)
        capture('jobs/queue_status.recovery001.json')
        base='generation/chexbench/'
        preds={x[:-5] for x in s.listdir(RUN+'/'+base+'predictions/'+ARM) if x.endswith('.json')}
        contexts={x[:-5] for x in s.listdir(RUN+'/'+base+'contexts') if x.endswith('.json')}
        pending=contexts-preds
        if len(preds)!=183 or len(pending)!=1:raise ValueError('unexpected_second_failure_prefix')
        q=pending.pop();ctx=parsed(base+'contexts/'+q+'.json')
        for ordinal in s.listdir(RUN+'/'+base+'services/calls/R50-AGENT/'+q):
            relative=base+'services/calls/R50-AGENT/'+q+'/'+ordinal
            for name in s.listdir(RUN+'/'+relative):capture(relative+'/'+name)
        selections=[]
        for name in s.listdir(RUN+'/'+base+'services/tool_selections/R50-AGENT/'+q):
            relative=base+'services/tool_selections/R50-AGENT/'+q+'/'+name;record=parsed(relative)
            if record.get('status')!='completed':selections.append({'relative':relative,'record':record})
        if len(selections)!=1:raise ValueError('exact_second_failed_selection_required')
        failure=selections[0];cache=base+'services/tool_cache/'+failure['record']['cache_key']
        for name in s.listdir(RUN+'/'+cache):
            if name!='artifacts':capture(cache+'/'+name)
        value={'question_id':q,'ordinal':ctx['ordinal'],'saved_prefix':183,'failed_selection':failure,'tool_cache':cache,
            'original_attempt_and_first_continuation_exits_retained':True,'no_prediction_or_own_feedback_for_failed_question':True}
        put('actual_failure.json',value)
    put('inspection.completed.json',{'status':'completed','utc':datetime.now(timezone.utc).isoformat(),'files':files,'count':len(files),'new_model_score_or_mutation_calls':0})
    cache_dir=DEST/'originals'/cache
    print(json.dumps({'failure':value,'backend_original_tails':{p.name:p.read_text(encoding='utf-8',errors='replace').splitlines()[-70:] for p in cache_dir.glob('*.log')},'captured_original_files':len(files)},ensure_ascii=False))

if __name__=='__main__':main()
