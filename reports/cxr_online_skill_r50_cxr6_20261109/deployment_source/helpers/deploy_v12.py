"""Private V12 transport; never prints or publishes credentials.

Usage: python local_assets/deploy_v12.py deploy|prepare|status|launch|fetch
Deployment contains source only. Launch is deliberately single-use: an existing
PID marker requires explicit recovery outside this helper, even after exit.
"""
from pathlib import Path, PurePosixPath
import argparse
import json
import shlex
import stat
import sys
import tarfile

TRANSPORT_HOME = Path(r'C:\Users\cheng\Documents\deepseek-harness\default-workspace\medrax_work')
sys.path.insert(0, str(TRANSPORT_HOME))
from remote import connect, ROOT

LOCAL = Path(__file__).resolve().parents[1]
CODE = ROOT + '/code_v12'
OUT = ROOT + '/runs/v12_ab60'
LOG_BASE = ROOT + '/logs/v12_ab60'
PYTHON = ROOT + '/.venv/bin/python'
LOCK = OUT + '/.launch.lock'
CONFIG = 'configs/v12_ab60.json'
RUNNER = 'experiments/run_v12_ab.py'
SERVER = 'experiments/server/run_v12.sh'
REQUIRED = (RUNNER, SERVER, CONFIG, 'experiments/v12_metrics.py',
            'experiments/v12_evidence.py', 'experiments/v12_retrieval.py')


def execute(client, command, timeout=90, input_bytes=None):
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    if input_bytes is not None:
        stdin.write(input_bytes)
        stdin.flush()
    stdin.channel.shutdown_write()
    data = stdout.read().decode('utf-8', 'replace')
    errors = stderr.read().decode('utf-8', 'replace')
    if data:
        print(data, end='', flush=True)
    if errors:
        print(errors[-6000:], file=sys.stderr, flush=True)
    rc = stdout.channel.recv_exit_status()
    if rc:
        raise RuntimeError('remote_operation_failed_exit_' + str(rc))


def remote_python(client, source, timeout=90, input_bytes=None):
    execute(client, shlex.quote(PYTHON) + ' -c ' + shlex.quote(source), timeout, input_bytes)


def preamble():
    return ('import fcntl,json,os,subprocess,sys\nfrom pathlib import Path\n'
            f'root=Path({ROOT!r}); code=Path({CODE!r}); out=Path({OUT!r})\n'
            f'python={PYTHON!r}; logbase=Path({LOG_BASE!r})\n'
            "out.mkdir(parents=True,exist_ok=True); logbase.parent.mkdir(parents=True,exist_ok=True)\n")


def acquire_launch_lock():
    # Every mutating transport action uses this lock. The launch wrapper inherits
    # its open file description and holds it until generation AND scoring exit.
    return ("launch_lock=(out/'.launch.lock').open('a')\n"
            "try: fcntl.flock(launch_lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)\n"
            "except BlockingIOError: raise SystemExit('V12 operation already active; inspect status')\n")


def acquire_generation_lock():
    # This also detects a runner started directly, outside this transport.
    return ("generation_lock=(out/'.generation.lock').open('a')\n"
            "try: fcntl.flock(generation_lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)\n"
            "except BlockingIOError: raise SystemExit('V12 generation already active; inspect status')\n")


def deploy(client):
    for name in REQUIRED:
        if not (LOCAL / name).is_file():
            raise FileNotFoundError('required V12 source missing: ' + name)
    target = LOCAL / 'local_assets/v12_code.tar.gz'
    target.parent.mkdir(parents=True, exist_ok=True)
    paths = []
    # No data, labels, reports, assets, secret directories, or model files.
    for dirname in ('experiments', 'runner', 'memory_core', 'memory_pipeline', 'data_tools'):
        paths.extend(p for p in (LOCAL / dirname).rglob('*.py')
                     if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts)
    paths.extend(LOCAL / name for name in (CONFIG, SERVER))
    resume_server=LOCAL/'experiments/server/run_v12_resume.sh'
    if resume_server.exists():paths.append(resume_server)
    with tarfile.open(target, 'w:gz') as archive:
        for path in sorted(set(paths)):
            archive.add(path, arcname='code_v12/' + path.relative_to(LOCAL).as_posix(), recursive=False)
    # Upload to a unique filename; extraction itself is protected by both locks.
    import uuid
    remote_archive = ROOT + '/.v12_code_' + uuid.uuid4().hex + '.tar.gz'
    try:
        with client.open_sftp() as sftp:
            sftp.put(str(target), remote_archive)
            sftp.chmod(remote_archive, 0o600)
        script = preamble() + acquire_launch_lock() + acquire_generation_lock()
        script += f"subprocess.run(['tar','-xzf',{remote_archive!r},'-C',str(root)],check=True)\n"
        script += "print(json.dumps({'deployed':str(code),'content':'allowlisted_source_and_V12_config_only'}))\n"
        remote_python(client, script)
    finally:
        with client.open_sftp() as sftp:
            try:
                sftp.remove(remote_archive)
            except FileNotFoundError:
                pass


def prepare(client):
    script = preamble() + acquire_launch_lock()
    # The runner owns its existing generation lock itself. Preparation makes no
    # API call and runs no unit tests, ledger scan, or reference-label reader.
    script += f"raise SystemExit(subprocess.call([python,{RUNNER!r},'--config',{CONFIG!r},'--out',str(out),'--prepare-only'],cwd=code))\n"
    remote_python(client, script, timeout=180)


def launch(client, resume=False, recovery_id='01_ledger_byte_check_removed'):
    import re
    if not re.fullmatch(r'[0-9]{2}_[a-z0-9_]+',recovery_id):
        raise ValueError('invalid_recovery_identifier')
    key = (TRANSPORT_HOME / '.secrets/qwen_api.key').read_bytes().strip()
    if not key or b'\n' in key or b'\r' in key:
        raise ValueError('invalid local API credential format')
    script = preamble() + acquire_launch_lock() + acquire_generation_lock()
    launch_server='experiments/server/run_v12_resume.sh' if resume else SERVER
    script += f'''
pidfile=Path(str(logbase)+'.pid')
resume={resume!r}
if pidfile.exists() and not resume: raise SystemExit('Existing V12 launch record; inspect status and recover explicitly')
if resume and pidfile.exists():
    try: os.kill(int(pidfile.read_text().strip()),0)
    except ProcessLookupError: pass
    else: raise SystemExit('Existing V12 process is still alive; no duplicate launch')
if not (out/'effective_config.json').exists(): raise SystemExit('Run prepare before launch')
state=json.loads((out/'status.json').read_text()) if (out/'status.json').exists() else {{}}
required_state='stopped' if resume else 'prepared'
if state.get('status')!=required_state: raise SystemExit('Launch requires '+required_state+' status')
if resume:
    import shutil
    history=out/'recovery_history'/{recovery_id!r}
    history.mkdir(parents=True,exist_ok=False)
    for original in [pidfile,Path(str(logbase)+'.exitcode'),Path(str(logbase)+'.log'),out/'fatal_error.json',out/'status.json']:
        if original.exists():shutil.copy2(original,history/original.name)
    exitfile=Path(str(logbase)+'.exitcode')
    if exitfile.exists():exitfile.unlink()
for name in {REQUIRED!r}:
    if not (code/name).is_file(): raise SystemExit('Missing deployed V12 source: '+name)
if not (code/{launch_server!r}).is_file():raise SystemExit('Missing V12 launch entry')
key=sys.stdin.buffer.readline().strip()
if not key: raise SystemExit('missing API credential on stdin')
secret=out/('.run_key_'+str(os.getpid()))
key_fd=None
try:
    fd=os.open(secret,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as handle: handle.write(key+b'\\n')
    key_fd=os.open(secret,os.O_RDONLY)
    secret.unlink()  # No pathname remains once the child can access the FD.
    del key
    wrapper='bash '+{shlex.quote(CODE + '/' + launch_server)!r}+'; result=$?; printf "%s\\n" "$result" > '+{shlex.quote(LOG_BASE + '.exitcode')!r}+'; exit "$result"'
    # Release the probe before the child takes the runner lock. The inherited
    # launch lock continues to exclude another transport launch/prepare/deploy.
    fcntl.flock(generation_lock.fileno(),fcntl.LOCK_UN); generation_lock.close()
    with Path(str(logbase)+'.log').open('ab',buffering=0) as log:
        process=subprocess.Popen(['bash','-c',wrapper],cwd=code,stdin=key_fd,
            stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
            pass_fds=(launch_lock.fileno(),))
    pidfile.write_text(str(process.pid)+'\\n')
    print(json.dumps({{'launched':True,'pid':process.pid,'run':str(out),'scoring':'server_after_generation'}}))
finally:
    if key_fd is not None: os.close(key_fd)
    if secret.exists(): secret.unlink()
'''
    remote_python(client, script, timeout=40, input_bytes=key + b'\n')


def resume(client, recovery_id='01_ledger_byte_check_removed'):
    launch(client,resume=True,recovery_id=recovery_id)


def status(client):
    # Metadata plus a bounded last terminal: no labels, ledger, full-result scan,
    # raw log/error text, answers, or patient evidence is sent back.
    script = ('import json,os,re,subprocess,time\nfrom pathlib import Path\n'
              f'out=Path({OUT!r}); base=Path({LOG_BASE!r})\n')
    script += '''
def metadata(path):
    if not path.exists(): return {'exists':False}
    s=path.stat(); return {'exists':True,'bytes':s.st_size,'mtime_epoch':s.st_mtime,'age_seconds':round(time.time()-s.st_mtime,1)}
def error_type(value):
    if not value: return None
    name=str(value).split(':',1)[0].strip()
    return name if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]{0,79}',name) else 'unclassified_error'
def last_terminal(path,initial=False):
    limit=256*1024
    if not path.exists(): return None
    with path.open('rb') as handle:
        handle.seek(0,os.SEEK_END); size=handle.tell(); start=max(0,size-limit)
        handle.seek(start); tail=handle.read(limit)
    lines=tail.splitlines()
    if start and lines: lines=lines[1:]  # May be the middle of a long JSON record.
    skipped=0
    for line in reversed(lines):
        if not line.strip(): continue
        try:
            record=json.loads(line)
            if not isinstance(record,dict): raise ValueError('not_object')
        except (ValueError,UnicodeDecodeError):
            skipped+=1; continue
        timing=record.get('timing') or {}
        account=record.get('accounting') or {}
        result={'status':record.get('status'),'error_type':error_type(record.get('error')),
            'accounting':{k:account.get(k) for k in ('model_calls','tool_calls')},
            'elapsed_s':timing.get('elapsed_s'),
            'timing':{k:timing.get(k) for k in ('started_utc','ended_utc','elapsed_s')},
            'tail_bytes_read':len(tail),'trailing_unparsed_records':skipped}
        if initial:
            result['first_answer_present']=bool(record.get('first_answer'))
        else:
            result.update(group=record.get('group'),error_phase=record.get('error_phase'),
                fallback_to_initial=bool(record.get('fallback_to_initial')),
                candidate_present=bool(record.get('candidate_answer')),
                solver_present=bool(record.get('solver_answer')))
        result['needs_attention']=bool(result['error_type'] or result['status']!='completed'
            or result.get('fallback_to_initial') or (not initial and not result['solver_present']))
        return result
    return {'record_found':False,'tail_bytes_read':len(tail),'trailing_unparsed_records':skipped,
            'needs_attention':bool(size),'reason':'no_complete_terminal_in_bounded_tail' if size else 'empty_file'}
p=out/'status.json'
raw=json.loads(p.read_text()) if p.exists() else {}
safe={k:raw[k] for k in ('status','updated_utc','planned_n','initial_completed','branch_completed','group_completed','stage','active_question','active_started_utc') if k in raw}
if raw.get('error'): safe['error_type']=error_type(raw['error'])
pidpath=Path(str(base)+'.pid'); pid=int(pidpath.read_text().strip()) if pidpath.exists() else None
process=None
if pid:
    check=subprocess.run(['ps','-p',str(pid),'-o','pid=,ppid=,stat=,etime=,comm='],capture_output=True,text=True)
    process=check.stdout.strip() or 'not_running'
exitpath=Path(str(base)+'.exitcode')
print(json.dumps({'status':safe or {'status':'not_started'},'pid':pid,'process':process,
 'exitcode':exitpath.read_text().strip() if exitpath.exists() else None,
 'latest_branch':last_terminal(out/'branch_results.jsonl'),
 'latest_initial':last_terminal(out/'initial_results.jsonl',initial=True),
 'files':{name:metadata(path) for name,path in {
   'status':p,'log':Path(str(base)+'.log'),'trace':out/'execution.trace.jsonl',
   'initial':out/'initial_results.jsonl','branches':out/'branch_results.jsonl',
   'metrics':out/'metrics.json','fatal_error':out/'fatal_error.json'}.items()}},ensure_ascii=False))
'''
    remote_python(client, script, timeout=40)


def fetch(client):
    target = LOCAL / 'local_assets/v12_ab60'
    target.mkdir(parents=True, exist_ok=True)
    extensions = {'.json', '.jsonl', '.md', '.txt', '.csv', '.png', '.jpg', '.jpeg', '.webp'}
    count = 0
    with client.open_sftp() as sftp:
        def copy_tree(remote_dir, relative=PurePosixPath()):
            nonlocal count
            for item in sftp.listdir_attr(remote_dir):
                name = item.filename
                if name.startswith('.') or name in {'.', '..'}:
                    continue
                child = relative / name
                if stat.S_ISLNK(item.st_mode):
                    continue
                if stat.S_ISDIR(item.st_mode):
                    copy_tree(remote_dir + '/' + name, child)
                elif stat.S_ISREG(item.st_mode) and child.suffix.lower() in extensions:
                    local_path = target.joinpath(*child.parts)
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    sftp.get(remote_dir + '/' + name, str(local_path))
                    count += 1
        copy_tree(OUT)
        for suffix in ('.log', '.pid', '.exitcode'):
            try:
                sftp.get(LOG_BASE + suffix, str(target / ('launcher' + suffix)))
                count += 1
            except FileNotFoundError:
                pass
    print(json.dumps({'fetched_files':count,'private_target':str(target),'publication':'not_performed'}))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('deploy', 'prepare', 'status', 'launch', 'resume', 'fetch'))
    parser.add_argument('--recovery-id',default='01_ledger_byte_check_removed')
    args = parser.parse_args(argv)
    with connect() as client:
        if args.mode=='resume':resume(client,recovery_id=args.recovery_id)
        else:globals()[args.mode](client)


if __name__ == '__main__':
    main()
