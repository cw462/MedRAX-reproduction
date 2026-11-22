"""Original GPU tool loaders resident behind this run's private sockets."""
import argparse
from datetime import datetime, timezone
from contextlib import redirect_stdout
import fcntl
import json
import os
from pathlib import Path
import socket
import socketserver
import sys
import time


def read(path):
    return json.loads(Path(path).read_text())

def store(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix('.pending')
    pending.write_text(json.dumps(value, ensure_ascii=False)+'\n')
    pending.replace(path)

def utc():
    return datetime.now(timezone.utc).isoformat()

def request_worker(path, payload):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(590)
        connection.connect(str(path))
        connection.sendall(json.dumps(payload).encode())
        connection.shutdown(socket.SHUT_WR)
        return json.load(connection.makefile('rb'))

def family_for(backend):
    from r55_resident_tools import FAMILIES
    return FAMILIES.get(backend)

def dispatch(config, request):
    family = family_for(request['backend'])
    control = Path(config['resident_control'])
    artifacts = Path(request['artifact_dir']).resolve()
    if not artifacts.is_relative_to(Path(config['run_root']).resolve()):
        raise RuntimeError('Resident request is outside this experiment')
    marker = control/(family+'.ready.json')
    deadline = time.monotonic()+570
    while not marker.is_file():
        if (control/(family+'.failed.json')).is_file():
            raise RuntimeError('Native resident failed to load: '+family)
        if time.monotonic()>deadline:
            raise TimeoutError('Native resident is not ready: '+family)
        time.sleep(.25)
    ready = read(marker)
    with (control/'gpu.lock').open('a') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        reply = request_worker(ready['socket'], {'request':request})
    if reply['pid'] != ready['pid']:
        raise RuntimeError('Resident reply came from a different process')
    store(artifacts.parent/'backend_route.json', {
        'family':family, 'worker_pid':reply['pid'], 'socket':ready['socket'],
        'resident':True, 'server_seconds':reply['seconds']})
    return reply

def tools_factory(native_tools, config):
    class ResidentTools(native_tools):
        def observe(self, name, spec, args, image, identity, folder, saved):
            if family_for(spec['backend']) is None:
                return super().observe(name,spec,args,image,identity,folder,saved)
            cache_hit = saved.exists()
            if cache_hit:
                result = read(saved)
            elif (folder/'started.json').exists():
                result = {'status':'started_unknown','observation':None,'automatic_retry':False}
            else:
                request = {'tool':name,'backend':spec['backend'],'args':args,'image':str(image),
                           'artifact_dir':str(folder/'artifacts'),'runtime':self.runtime['backend_config']}
                store(folder/'request.json',request)
                store(folder/'started.json',{'identity':identity,'utc':utc()})
                started = time.monotonic()
                try:
                    reply = dispatch(config,request)
                    result = reply['result']
                    (folder/'backend.stdout.log').write_text('CXR_VQA_RESULT='+json.dumps(result,ensure_ascii=False))
                    (folder/'backend.stderr.log').write_text(reply['stderr'])
                    store(folder/'backend.exit.json',{'returncode':0})
                except Exception as error:
                    result = {'status':'failed','observation':None,
                              'error_type':type(error).__name__,'error':str(error)[:300]}
                result.update(elapsed_s=time.monotonic()-started,backend=spec['backend'],
                              identity=identity,utc=utc())
                store(saved,result)
            return result,cache_hit
    return ResidentTools

def serve(config_path, family):
    config = read(config_path)
    sys.path.insert(0,config['source_dir'])
    from r55_resident_tools import Resident
    control = Path(config['resident_control'])
    wire = control/'sockets'/(family+'.sock')
    wire.parent.mkdir(parents=True,exist_ok=True)
    with (control/'gpu.lock').open('a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX)
        started = time.monotonic()
        with redirect_stdout(sys.stderr):
            model = Resident(family,config['runtime']['backend_config'],control)
            import torch
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
        free,total = torch.cuda.mem_get_info()
        ready = {'family':family,'pid':os.getpid(),'socket':str(wire),'python':sys.executable,
                 'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),
                 'loader_seconds':time.monotonic()-started,'gpu_free_bytes':free,
                 'gpu_total_bytes':total,'model_allocated_bytes':torch.cuda.memory_allocated()}
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            payload = json.load(self.rfile)
            result = model.run(payload['request']) if 'request' in payload else {'pid':os.getpid(),'family':family}
            self.wfile.write(json.dumps(result,ensure_ascii=False).encode())
    with socketserver.UnixStreamServer(str(wire),Handler) as server:
        os.chmod(wire,0o600)
        store(control/(family+'.ready.json'),ready)
        print(json.dumps(ready),flush=True)
        server.serve_forever()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--family',required=True)
    args=parser.parse_args()
    serve(args.config,args.family)
