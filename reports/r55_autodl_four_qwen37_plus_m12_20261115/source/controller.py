
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
ARM = sys.argv[1]
JOB = ROOT / 'jobs' / ARM
PLAN = json.loads((ROOT / 'plan.json').read_bytes())
PYTHON = str(ROOT / 'env/modern/bin/python')
SCRIPT = str(ROOT / 'bin/run_top4_priority.py')
ENVS = {
    **os.environ, 'CUDA_VISIBLE_DEVICES': '0', 'R55_MEMEVOLVE_GPU': '0',
    'OMP_NUM_THREADS': '2', 'MKL_NUM_THREADS': '2', 'PYTHONDONTWRITEBYTECODE': '1',
    'R55_REQUIRE_CHEXAGENT8': '1', 'R55_CHEXAGENT8_SNAPSHOT': PLAN['chexagent8_snapshot'],
    'LANGCHAIN_TRACING_V2': 'false', 'LANGSMITH_TRACING': 'false',
}

def read(path):
    return json.loads(path.read_bytes())

def save(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    tmp.replace(path)

def run_child(folder, phase, args, secret=None):
    with (folder / (phase+'.stdout.log')).open('ab') as so, (folder / (phase+'.stderr.log')).open('ab') as se:
        proc = subprocess.Popen([PYTHON,'-B','-u',*args],stdin=subprocess.PIPE if secret else subprocess.DEVNULL,
                                stdout=so,stderr=se,cwd=ROOT,env=ENVS)
        save(folder / (phase+'.started.json'), {'pid':proc.pid,'epoch':time.time()})
        proc.communicate(secret)
    save(folder / (phase+'.exit.json'), {'exit':proc.returncode,'pid':proc.pid,'epoch':time.time()})
    if proc.returncode:
        raise RuntimeError(f'{phase} exited {proc.returncode} in {folder.relative_to(ROOT)}')

def fresh_attempt(stage):
    attempt = stage / f'attempt-{time.time_ns()}'
    attempt.mkdir(parents=True)
    return attempt

def validate_score(summary, label, dataset, count):
    if (summary['arm'],summary['dataset'],summary['questions']) != (label,dataset,count):
        raise RuntimeError(f'Score identity mismatch for {label}/{dataset}')
    return summary

def memory(key):
    boundary=ROOT/'verification'/ARM/'slake'/'verified.json'
    base_args=[SCRIPT,'verify',str(ROOT),ARM,'--dataset','slake']
    if not boundary.is_file():
        run_child(fresh_attempt(JOB/'preflight'),'verify',base_args)
    verified=read(boundary)
    assert verified['new_external_model_requests']==0 and verified['bound_questions']==114
    results={}
    for ds,n in PLAN['datasets'].items():
        target=ROOT/'generation'/ARM/ds
        scored=target/'analysis/summary.json'
        if not (JOB/ds/'complete.json').is_file():
            a=fresh_attempt(JOB/ds)
            for phase in ('dataset','score'):
                if phase=='dataset' and (target/'generation.exitcode').is_file() and (target/'generation.exitcode').read_text().strip()=='0':
                    continue
                run_child(a,phase,[SCRIPT,phase,str(ROOT),ARM,'--dataset',ds],
                          key+b'\n'+key+b'\n' if phase=='dataset' else None)
                if phase=='dataset':
                    (target/'generation.exitcode').write_text('0\n')
            summary=validate_score(read(scored),'R55-'+ARM,ds,n)
            save(JOB/ds/'complete.json',{'score':summary,'verified_exit':0,'epoch':time.time()})
        summary=read(JOB/ds/'complete.json')['score']
        results[ds]=validate_score(summary,'R55-'+ARM,ds,n)
    return results

def react(key):
    out=ROOT/'flash_react'
    a=fresh_attempt(JOB)
    run_child(a,'runner',[str(out/'code/run_qwen_baselines.py'),str(ROOT),str(out),'react','--workers','3','--r55-11-tools'],key+b'\n')
    return {ds:validate_score(read(out/'react'/ds/'summary.json'),'react',ds,n) for ds,n in PLAN['datasets'].items()}

def main():
    key=sys.stdin.buffer.read().strip()
    if not key or key.startswith(b'sk-ws-'):
        raise ValueError('Existing Token Plan key is required')
    with (JOB/'controller.lock').open('a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            scores=react(key) if ARM=='ReAct' else memory(key)
        except Exception as exc:
            save(JOB/'terminal.json',{'exit':1,'error':f'{type(exc).__name__}: {exc}','epoch':time.time()})
            raise
        save(JOB/'terminal.json',{'exit':0,'arm':ARM,'datasets':scores,'epoch':time.time(),
                                 'questions':sum(d['questions'] for d in scores.values()),
                                 'correct':sum(d['correct'] for d in scores.values())})

if __name__=='__main__':
    main()
