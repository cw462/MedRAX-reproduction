"""Once-only read/copy of the actual R50 CheX failure; no model, GT or mutation."""
import json
from datetime import datetime,timezone
from pathlib import Path
from deploy_cxr6_r50 import connect,RUN,ARM,PREP

DEST=PREP/'failures/001_chex_104'

def main():
    DEST.mkdir(parents=True,exist_ok=False)
    files=[]
    def put(name,value):
        with (DEST/name).open('x',encoding='utf-8') as f:
            json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
    put('inspection.started.json',{'utc':datetime.now(timezone.utc).isoformat(),
        'scope':'actual failed question/cache/job originals only; no labels/probes or resend'})
    with connect() as client,client.open_sftp() as s:
        def capture(relative):
            remote=RUN+'/'+relative;target=DEST/'originals'/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():return target
            info=s.stat(remote)
            with s.open(remote,'rb') as a,target.open('xb') as b:
                while True:
                    chunk=a.read(1024*1024)
                    if not chunk:break
                    b.write(chunk)
            files.append({'relative':relative,'remote_size':info.st_size,'remote_mtime':info.st_mtime})
            return target
        def parsed(relative):return json.loads(capture(relative).read_text(encoding='utf-8'))
        for name in ('controller.log','controller.pid','controller.exitcode','chexbench.log','chexbench.pid','chexbench.exitcode','queue_status.json'):
            capture('jobs/'+name)
        base='generation/chexbench/'
        pred={v[:-5] for v in s.listdir(RUN+'/'+base+'predictions/'+ARM) if v.endswith('.json')}
        contexts={v[:-5] for v in s.listdir(RUN+'/'+base+'contexts') if v.endswith('.json')}
        unfinished=contexts-pred
        if len(pred)!=104 or len(unfinished)!=1:raise ValueError('unexpected_actual_failure_prefix')
        q=unfinished.pop();ctx=parsed(base+'contexts/'+q+'.json')
        for folder in s.listdir(RUN+'/'+base+'services/calls/R50-AGENT/'+q):
            remote=base+'services/calls/R50-AGENT/'+q+'/'+folder
            for name in s.listdir(RUN+'/'+remote):capture(remote+'/'+name)
        selections=[]
        for name in s.listdir(RUN+'/'+base+'services/tool_selections/R50-AGENT/'+q):
            relative=base+'services/tool_selections/R50-AGENT/'+q+'/'+name
            selection=parsed(relative);selections.append({'relative':relative,'record':selection})
        failed=[v for v in selections if v['record'].get('status')!='completed']
        if len(failed)!=1:raise ValueError('one_actual_failed_selection_required')
        cache=base+'services/tool_cache/'+failed[0]['record']['cache_key']
        for name in s.listdir(RUN+'/'+cache):
            if name!='artifacts':capture(cache+'/'+name)
        try:artifact_names=s.listdir(RUN+'/'+cache+'/artifacts')
        except FileNotFoundError:artifact_names=[]
        # Inventory only; no new image/model/file integrity checks.
        failure={'question_id':q,'ordinal':ctx['ordinal'],'saved_prefix':104,
            'failed_selection':failed[0],'tool_cache':cache,'artifact_names':artifact_names,
            'no_prediction_or_own_feedback_for_failed_question':True}
        put('actual_failure.json',failure)
    put('inspection.completed.json',{'status':'completed','utc':datetime.now(timezone.utc).isoformat(),
        'files':files,'count':len(files),'new_inference_or_mutation_or_reference_reads':0})
    cache_root=DEST/'originals'/cache
    tails={p.name:p.read_text(encoding='utf-8',errors='replace').splitlines()[-65:]
        for p in cache_root.glob('*.log')}
    print(json.dumps({'failure':failure,'backend_original_tails':tails,'captured_original_files':len(files)},ensure_ascii=False))

if __name__=='__main__':main()
