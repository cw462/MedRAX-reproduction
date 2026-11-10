"""One serial remaining-file stream after preserving the intentionally stopped SFTP attempt.

Existing complete files are reused by ordinary size/member checks; no hashes,
inference, overwritten partials, second live queue or duplicate downloaded files.
"""
import contextlib
import io
import json
from pathlib import Path
import shlex
import shutil
import tarfile
from datetime import datetime, timezone

from deploy_cxr6_r50 import connect, remote_python, script, PYTHON, ROOT as REMOTE_ROOT
from collect_r50_user_stop_once import PREP, MIRROR, RUN, CODE, STRONG_RUN, once, read


def main():
    assert not (PREP / 'collection.completed.json').exists()
    once(PREP / 'collection_transport_handoff.json', {'utc': datetime.now(timezone.utc).isoformat(),
        'original_native_session': 27877, 'original_native_exit': 1, 'original_native_chunk': 'bbfbc2',
        'intentional_local_capture_termination_pid': 51728,
        'reason': 'High per-file SFTP latency. Preserve original4700+complete files and partials; use one serial remaining-file tar stream.',
        'original_attempt_claimed_success': False, 'new_inference_calls': 0,
        'original_remote_run_or_producer_modified': False})
    once(PREP / 'collection002.started.json', {'utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'One immutable inventory, reuse completed local members, stream only missing files.', 'automatic_retry': False})
    inventory_source = script(r'''
import os,stat,json
from pathlib import Path
items=[];code=[]
def add(src,dest,kind):
 st=os.stat(src);assert stat.S_ISREG(st.st_mode)
 assert Path(src).suffix.lower() not in ('.pt','.pth','.safetensors','.pem','.key','.ckpt')
 items.append({'remote':str(src),'local':dest,'bytes':st.st_size,'remote_mtime':st.st_mtime,'kind':kind})
def tree(src,dest,kind):
 for base,dirs,files in os.walk(src):
  dirs[:]=[n for n in dirs if not n.startswith('.') and n not in ('__pycache__','hf_modules')]
  for name in files:
   if name.startswith('.'):continue
   p=Path(base)/name
   if not p.is_symlink():add(p,str(Path(dest)/p.relative_to(src)),kind)
for folder in ('generation','jobs','configs'):tree(RUN+'/'+folder,folder,'stopped_run_'+folder)
for p in Path(RUN).iterdir():
 if p.is_file() and (p.name.startswith(('queue_controller','health_controller','protocol_amendment','amendment003')) or p.name in ('EXECUTION_REVIEW_READY.json','EVALUATION_PROTOCOL.json')):add(p,p.name,'run_control')
for p in (Path(CODE)/'experiments').glob('*.py'):
 if 'credential' not in p.name.lower() and p.stem.lower() not in ('settings','keys'):
  relative='experiments/'+p.name;add(p,'actual_code_source/'+relative,'actual_CODE');code.append(relative)
relative='configs/cxr_vqa_tool_worker_gpu.json';add(Path(CODE)/relative,'actual_code_source/'+relative,'actual_CODE');code.append(relative)
add(HEALTH,'health_input/training_xmlab120.jpg','exact_existing_health_input')
for p in (Path(STRONG_RUN)/'jobs').iterdir():
 if p.is_file() and p.suffix in ('.json','.pid','.log','.exitcode'):add(p,'held_comparison/jobs/'+p.name,'held_zero_request_comparison')
assert len({x['local'] for x in items})==len(items)
print(json.dumps({'files':items,'actual_code_files':sorted(code)}))
''', RUN=RUN, CODE=CODE, STRONG_RUN=STRONG_RUN,
        HEALTH=REMOTE_ROOT + '/runs/cxr_vqa_backend_readiness/training_xmlab120.jpg')
    try:
        with connect() as client:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                remote_python(client, inventory_source, timeout=45)
            inventory = json.loads(output.getvalue())
            once(MIRROR / 'inventory002.remote.json', inventory)
            missing = []
            reused = 0
            for item in inventory['files']:
                relative = Path(item['local'])
                assert not relative.is_absolute() and '..' not in relative.parts
                target = MIRROR / relative
                if target.is_file():
                    assert not target.is_symlink() and target.stat().st_size == item['bytes'], str(relative)
                    reused += 1
                else:
                    missing.append(item)
            once(PREP / 'collection002.plan.json', {'reused_complete_files': reused,
                'remaining_files': len(missing), 'remaining_bytes': sum(x['bytes'] for x in missing),
                'all_previous_partials_preserved': True})
            remote = 'import sys,tarfile,os\nitems=' + repr(missing) + '\n'
            remote += "with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as archive:\n for item in items:\n  assert os.stat(item['remote']).st_size==item['bytes']\n  archive.add(item['remote'],arcname=item['local'],recursive=False)\n"
            text = PREP / 'collection002.remote.py'
            text.write_text(remote, encoding='utf-8')
            stdin, stdout, stderr = client.exec_command(shlex.quote(PYTHON) + ' -u -', timeout=900)
            stdin.write(remote.encode('utf-8'));stdin.channel.shutdown_write()
            expected = {item['local']: item for item in missing}
            copied = []
            with tarfile.open(fileobj=stdout, mode='r|') as archive:
                for member in archive:
                    assert member.isfile() and member.name in expected and member.size == expected[member.name]['bytes']
                    target = MIRROR / member.name
                    assert not target.exists()
                    target.parent.mkdir(parents=True, exist_ok=True)
                    partial = target.with_name(target.name + '.tarstream002_part')
                    with partial.open('xb') as handle, archive.extractfile(member) as source:
                        shutil.copyfileobj(source, handle, length=1024*1024)
                    assert partial.stat().st_size == member.size
                    partial.replace(target);copied.append(member.name)
                    if len(copied) % 1000 == 0:
                        print(json.dumps({'streamed_remaining_files': len(copied), 'reused_complete_files': reused}), flush=True)
            error = stderr.read().decode('utf-8','replace')
            rc = stdout.channel.recv_exit_status()
            (PREP / 'collection002.remote.stderr.log').write_text(error, encoding='utf-8')
            once(PREP / 'collection002.remote.exit.json', {'native_exit': rc})
            assert rc == 0 and set(copied) == set(expected), error
        once(MIRROR / 'inventory.json', inventory['files'])
        record = {'status': 'completed', 'utc': datetime.now(timezone.utc).isoformat(),
            'files': len(inventory['files']), 'bytes': sum(item['bytes'] for item in inventory['files']),
            'actual_code_files': inventory['actual_code_files'], 'actual_code_count': len(inventory['actual_code_files']),
            'mirror': str(MIRROR), 'reused_previous_complete_files': reused, 'new_remaining_files': len(copied),
            'initial_capture_native_exit': 1, 'initial_capture_intentionally_superseded': True,
            'new_model_calls': 0, 'no_repeated_dataset_files': True, 'automatic_retry': False,
            'weight_or_byte_attestation': False, 'final_full_cohort_receipts_consumed': False}
        once(PREP / 'collection002.completed.json', record)
        once(PREP / 'collection.completed.json', record)
        print(json.dumps(record))
    except Exception as error:
        once(PREP / 'collection002.failure.json', {'utc': datetime.now(timezone.utc).isoformat(),
            'error': repr(error), 'partial_originals_retained': True, 'automatic_retry': False})
        raise


if __name__ == '__main__':main()
