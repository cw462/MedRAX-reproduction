"""One serial artifact/source capture after the explicit user stop, without inference."""
import json
from datetime import datetime, timezone
from pathlib import Path
import stat

from deploy_cxr6_r50 import LOCAL, RUN, CODE, connect

PREP = LOCAL / 'local_assets/r50_user_stop_publication_20261110'
MIRROR = Path('D:/MedRAX_Experiment_Artifacts/online_skill_r50_user_stopped_20261110')
STRONG_RUN = '/home/imss/cw/MedRAX_reproduction_20261027/runs/deepseek_flash_skill_formation_v2_20261110'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def once(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def main():
    stopped = read(PREP / 'stop.completed.json')
    assert stopped['status'] == 'USER_STOPPED_INCOMPLETE' and stopped['counts']['predictions'] == 435
    assert stopped['no_live_attributed_runner_descendants'] and not stopped['automatic_resume']
    MIRROR.mkdir()
    once(PREP / 'collection.started.json', {'utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'User-stopped incomplete R50 raw artifacts, actual code and controls; once serial inventory, no retry.',
        'mirror': str(MIRROR), 'formal_full_dataset_collector_consumed': False})
    inventory = []
    code_files = []
    try:
        with connect() as client, client.open_sftp() as sftp:
            def take(remote, local, kind):
                info = sftp.stat(remote)
                assert stat.S_ISREG(info.st_mode), remote
                assert local.suffix.lower() not in {'.safetensors', '.pt', '.pth', '.pem', '.key', '.ckpt'}, remote
                local.parent.mkdir(parents=True, exist_ok=True)
                partial = local.with_name(local.name + '.download_part')
                assert not local.exists() and not partial.exists(), str(local)
                sftp.get(remote, str(partial), prefetch=False)
                partial.replace(local)
                inventory.append({'remote': remote, 'local': local.relative_to(MIRROR).as_posix(),
                    'bytes': info.st_size, 'remote_mtime': info.st_mtime, 'kind': kind})
                if len(inventory) % 100 == 0:
                    (MIRROR / 'inventory.partial.json').write_text(json.dumps(inventory), encoding='utf-8')
                    print(json.dumps({'copied_files': len(inventory), 'bytes': sum(item['bytes'] for item in inventory)}), flush=True)
            def tree(remote, local, kind):
                for entry in sftp.listdir_attr(remote):
                    if entry.filename.startswith('.') or entry.filename in ('__pycache__', 'hf_modules'):
                        continue
                    source = remote + '/' + entry.filename
                    target = local / entry.filename
                    if stat.S_ISDIR(entry.st_mode):
                        tree(source, target, kind)
                    elif stat.S_ISREG(entry.st_mode):
                        take(source, target, kind)
            for folder in ('generation', 'jobs', 'configs'):
                tree(RUN + '/' + folder, MIRROR / folder, 'stopped_run_' + folder)
            for entry in sftp.listdir_attr(RUN):
                if stat.S_ISREG(entry.st_mode) and (entry.filename.startswith(('queue_controller', 'health_controller', 'protocol_amendment', 'amendment003'))
                    or entry.filename in ('EXECUTION_REVIEW_READY.json', 'EVALUATION_PROTOCOL.json')):
                    take(RUN + '/' + entry.filename, MIRROR / entry.filename, 'run_control')
            for entry in sftp.listdir_attr(CODE + '/experiments'):
                name = entry.filename
                if stat.S_ISREG(entry.st_mode) and name.endswith('.py') and 'credential' not in name.lower() and Path(name).stem.lower() not in ('settings', 'keys'):
                    relative = 'experiments/' + name
                    take(CODE + '/' + relative, MIRROR / 'actual_code_source' / relative, 'actual_CODE')
                    code_files.append(relative)
            relative = 'configs/cxr_vqa_tool_worker_gpu.json'
            take(CODE + '/' + relative, MIRROR / 'actual_code_source' / relative, 'actual_CODE')
            code_files.append(relative)
            take('/home/imss/cw/MedRAX_reproduction_20261027/runs/cxr_vqa_backend_readiness/training_xmlab120.jpg',
                MIRROR / 'health_input/training_xmlab120.jpg', 'exact_existing_health_input')
            # The revised pair never started; preserve its actual hold/exit as history.
            for entry in sftp.listdir_attr(STRONG_RUN + '/jobs'):
                if stat.S_ISREG(entry.st_mode) and entry.filename.endswith(('.json', '.pid', '.log', '.exitcode')):
                    take(STRONG_RUN + '/jobs/' + entry.filename, MIRROR / 'held_comparison/jobs' / entry.filename, 'held_zero_request_comparison')
        once(MIRROR / 'inventory.json', inventory)
        record = {'status': 'completed', 'utc': datetime.now(timezone.utc).isoformat(),
            'files': len(inventory), 'bytes': sum(item['bytes'] for item in inventory),
            'actual_code_files': sorted(code_files), 'actual_code_count': len(code_files),
            'mirror': str(MIRROR), 'user_stopped': True, 'new_model_calls': 0,
            'old_dataset_downloads_or_scores': 0, 'automatic_retry': False,
            'weight_or_byte_attestation': False, 'final_full_cohort_receipts_consumed': False}
        once(PREP / 'collection.completed.json', record)
        print(json.dumps(record))
    except Exception as error:
        once(MIRROR / 'inventory.failure.json', inventory)
        once(PREP / 'collection.failure.json', {'utc': datetime.now(timezone.utc).isoformat(),
            'error': repr(error), 'files_copied': len(inventory), 'partial_originals_retained': True,
            'automatic_retry': False, 'native_stderr': 'original exec transcript'})
        raise


if __name__ == '__main__':
    main()
