
from pathlib import Path
from online_memory_r49 import read,save_once

class VerifyUnavailable(RuntimeError):
    pass

def timeout(path):
    path=Path(path)
    if path.parent.parent.name!='R55-VERIFY' or path.name!='1':
        return None
    if not all((path/name).is_file() for name in ('request.json','started.json','result.json','endpoint.json')):
        return None
    if (path/'response.json').exists():
        return None
    receipt=read(path/'result.json')
    if (receipt.get('error')=='TimeoutError' and receipt.get('response_received') is False
            and receipt.get('request_id')==read(path/'started.json').get('request_id')):
        return receipt
    return None

def mark_timeout(path):
    receipt=timeout(path)
    if receipt is None:
        raise ValueError('not_a_saved_r55_verify_timeout')
    save_once(path/'unavailable.recovery001.json',{'request_id':receipt['request_id'],
        'response_received':False,'provider_execution_unknown':True,
        'disposition':'no_usable_observation','resent':False})

def accounted_timeout(path):
    receipt=timeout(path)
    sidecar=path/'unavailable.recovery001.json'
    return bool(receipt and sidecar.is_file() and read(sidecar)=={'request_id':receipt['request_id'],
        'response_received':False,'provider_execution_unknown':True,
        'disposition':'no_usable_observation','resent':False})
