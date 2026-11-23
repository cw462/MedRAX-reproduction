"""Load the six original model families sequentially for the new M5 run."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

root=Path(sys.argv[1]).resolve()
trusted=root/'trusted'
config_path=trusted/'gateway.json'
config=json.loads(config_path.read_text())
control=Path(config['resident_control'])
control.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(trusted))
from native_resident_pool import read,store,request_worker

families=[('chexagent','chest_xray_expert',18000),('maira','maira2_grounded_report',10000),
          ('llava-med','llava_med_qa',15000),('llava-rad','llava_rad',15000),
          ('medgemma','medgemma',10000),('medvlm-r1','medvlm_r1',6000)]
results={}

def gpu():
    raw=subprocess.check_output(['nvidia-smi','-i','0','--query-gpu=memory.used,memory.free,memory.total',
                                 '--format=csv,noheader,nounits'],text=True).strip()
    used,free,total=[int(x.strip()) for x in raw.split(',')]
    return {'used_mib':used,'free_mib':free,'total_mib':total}

def status(state,**details):
    store(control/'pool.status.json',{'state':state,'families':results,'gpu':gpu(),'time':time.time(),**details})

try:
    for family,tool,expected in families:
        marker=control/(family+'.ready.json')
        if marker.is_file():
            previous=read(marker)
            if Path('/proc',str(previous['pid'])).exists() and Path(previous['socket']).is_socket():
                pong=request_worker(previous['socket'],{})
                if pong['pid']==previous['pid']:
                    results[family]=previous
                    continue
            raise RuntimeError('Stale resident marker requires inspection: '+family)
        memory=gpu()
        if memory['free_mib']<expected+12*1024:
            raise RuntimeError('Insufficient GPU headroom for '+family+': '+str(memory))
        spec=config['runtime']['tools'][tool]
        environment=dict(os.environ)
        environment.update(spec.get('worker_env',{}))
        environment.update(CUDA_VISIBLE_DEVICES='0',R55_MEMEVOLVE_GPU='0',
                           HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',
                           MPLBACKEND='Agg',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4')
        environment['PYTHONPATH']=os.pathsep.join([str(trusted),config['source_dir'],
                        '/root/autodl-tmp/medrax_r55_top4_full848/bin'])
        log=control/(family+'.log')
        with log.open('ab') as output:
            process=subprocess.Popen([spec['python'],'-B','-u',str(trusted/'native_resident_pool.py'),
                   '--config',str(config_path),'--family',family],
                   cwd=config['runtime']['backend_config']['root'],env=environment,
                   stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
        store(control/(family+'.launched.json'),{'pid':process.pid,'log':str(log),'time':time.time()})
        status('loading',current_family=family,pid=process.pid)
        deadline=time.monotonic()+600
        while not marker.is_file():
            if process.poll() is not None:
                raise RuntimeError(f'{family} resident exited {process.returncode}; see {log}')
            if time.monotonic()>deadline:
                raise TimeoutError(f'{family} resident loading exceeded 600 seconds; see {log}')
            time.sleep(.5)
        ready=read(marker)
        if request_worker(ready['socket'],{})['pid']!=process.pid:
            raise RuntimeError('Resident socket PID differs from the loader')
        results[family]=ready
        status('loading_next',last_ready=family)
    status('ready',all_six_loaded=True)
except Exception as error:
    if 'family' in globals():
        store(control/(family+'.failed.json'),{'error':str(error),'time':time.time()})
    status('failed',error=str(error))
    raise
