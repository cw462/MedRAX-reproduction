
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
    'R55_BASELINE_SHARED_GPU_ROOT': str(ROOT),
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


def baseline(keys):
    method = ARM.lower()
    out = ROOT/'flash_react'
    attempt = fresh_attempt(JOB)
    args = [str(out/'code_deepseek_methods/run_qwen_baselines.py'),str(ROOT),str(out),method,
            '--workers','3','--r55-11-tools']
    if method == 'reflexion':
        args.append('--wait-for-react')
    run_child(attempt,'runner',args,keys)
    return {ds:validate_score(read(out/method/ds/'summary.json'),method,ds,n)
            for ds,n in PLAN['datasets'].items()}


def main():
    keys = sys.stdin.buffer.read().splitlines()
    if len(keys) != 2 or not all(keys):
        raise ValueError('Two official DeepSeek role credentials are required')
    with (JOB/'controller.lock').open('a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            scores=baseline(b'\n'.join(keys)+b'\n')
        except Exception as exc:
            save(JOB/'terminal.json',{'exit':1,'error':f'{type(exc).__name__}: {exc}','epoch':time.time()})
            raise
        save(JOB/'terminal.json',{'exit':0,'arm':ARM,'datasets':scores,'epoch':time.time(),
                                'questions':sum(s['questions'] for s in scores.values()),
                                'correct':sum(s['correct'] for s in scores.values())})


if __name__ == '__main__':
    main()
