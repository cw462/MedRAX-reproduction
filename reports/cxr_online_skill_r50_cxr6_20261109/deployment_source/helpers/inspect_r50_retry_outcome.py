"""Read the one launched technical attempt; copy its raw files once after exit."""
import json,stat
from pathlib import Path
from deploy_cxr6_r50 import connect,RUN,PREP

REMOTE=RUN+'/technical_recovery/001_medvlm_tokenizer_load'
LOCAL=PREP/'failures/001_chex_104/explicit_retry'

def main():
    with connect() as client,client.open_sftp() as s:
        def raw(name):
            with s.open(REMOTE+'/'+name,'rb') as f:return f.read()
        try:exit_body=raw('attempt.exitcode')
        except FileNotFoundError:
            print(json.dumps({'status':'pending_existing_attempt_only','pid':raw('attempt.pid').decode().strip()}));return
        if LOCAL.exists():raise ValueError('retry_artifacts_already_captured_read_local_not_repeat')
        LOCAL.mkdir();files=[]
        def walk(remote,relative=''):
            for info in s.listdir_attr(remote):
                if info.filename.startswith('.'):continue
                child=(relative+'/' if relative else '')+info.filename
                if stat.S_ISDIR(info.st_mode):walk(remote+'/'+info.filename,child)
                elif stat.S_ISREG(info.st_mode):
                    dest=LOCAL/child;dest.parent.mkdir(parents=True,exist_ok=True)
                    with s.open(remote+'/'+info.filename,'rb') as a,dest.open('xb') as b:
                        while True:
                            chunk=a.read(1024*1024)
                            if not chunk:break
                            b.write(chunk)
                    files.append({'relative':child,'remote_size':info.st_size,'remote_mtime':info.st_mtime})
        walk(REMOTE)
    with (LOCAL/'capture_receipt.json').open('x',encoding='utf-8') as f:json.dump({'status':'completed','files':files,'count':len(files),'new_model_or_score_or_mutation_calls':0},f,indent=2)
    record=json.loads((LOCAL/'completed.json').read_text(encoding='utf-8'))
    result=json.loads((LOCAL/'result.json').read_text(encoding='utf-8')) if (LOCAL/'result.json').exists() else None
    print(json.dumps({'raw_attempt_exit':exit_body.decode(),'record':record,'result':result,
        'stderr_tail':(LOCAL/'backend.stderr.log').read_text(encoding='utf-8',errors='replace').splitlines()[-25:],
        'captured_files':len(files)},ensure_ascii=False))

if __name__=='__main__':main()
