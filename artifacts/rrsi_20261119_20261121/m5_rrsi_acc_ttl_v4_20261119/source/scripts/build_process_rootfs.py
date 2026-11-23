"""Build the candidate CPU rootfs from the existing native Python environment."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


def build(python, destination):
    destination = Path(destination).resolve()
    if destination.exists():
        raise RuntimeError('Use a new rootfs directory')
    query = "import sys,sysconfig,json,importlib.metadata as m;print(json.dumps({'executable':sys.executable,'stdlib':sysconfig.get_path('stdlib'),'purelib':sysconfig.get_path('purelib'),'version':sys.version,'packages':{n:m.version(n) for n in ('numpy','scipy','scikit-learn','joblib','threadpoolctl','pillow')}}))"
    native = json.loads(subprocess.check_output([python, '-c', query], text=True))
    destination.mkdir(parents=True)
    pending = []

    def copy_file(source, target):
        shutil.copy2(source, target)
        with open(source, 'rb') as stream:
            if stream.read(4) == b'\x7fELF':
                pending.append(Path(source))
        return target

    prefix = destination / 'usr/local'
    (prefix / 'bin').mkdir(parents=True)
    copy_file(Path(native['executable']).resolve(), prefix / 'bin/python')
    stdlib = Path(native['stdlib'])
    targetlib = prefix / 'lib' / stdlib.name
    shutil.copytree(stdlib, targetlib, copy_function=copy_file,
                    ignore=shutil.ignore_patterns('site-packages', '__pycache__', 'test', 'tests'))
    packages = targetlib / 'site-packages'
    packages.mkdir()
    source = Path(native['purelib'])
    included = []
    for pattern in ('numpy', 'numpy.libs', 'scipy', 'scipy.libs', 'sklearn', 'scikit_learn.libs',
                    'joblib', 'threadpoolctl.py', 'PIL', 'pillow.libs', 'packaging'):
        path = source / pattern
        if path.is_dir():
            shutil.copytree(path, packages / path.name, copy_function=copy_file,
                            ignore=shutil.ignore_patterns('__pycache__', 'test', 'tests'))
            included.append(path.name)
        elif path.is_file():
            copy_file(path, packages / path.name)
            included.append(path.name)
    copied = set()
    while pending:
        binary = pending.pop()
        result = subprocess.run(['ldd', str(binary)], capture_output=True, text=True)
        for item in re.findall(r'(?:=>\s*)?(/[^\s()]+)', result.stdout):
            path = Path(item)
            if not path.is_file() or str(path) in copied:
                continue
            copied.add(str(path))
            # Conda's relocated extensions resolve their shared libraries here.
            if path.is_relative_to(source):
                target = packages / path.relative_to(source)
            elif path.is_relative_to(stdlib):
                target = targetlib / path.relative_to(stdlib)
            elif '/miniconda' in str(path):
                target = prefix / 'lib' / path.name
            else:
                target = destination / str(path).lstrip('/')
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path.resolve(), target)
                pending.append(path)
    for name in ('harness', 'runner', 'state', 'case_images', 'out', 'tmp', 'etc'):
        (destination / name).mkdir(exist_ok=True)
    (destination / 'etc/hosts').write_text('127.0.0.1 localhost\n')
    native.update(rootfs=str(destination), included_cpu_packages=included,
                  runtime_python='/usr/local/bin/python', python_home='/usr/local',
                  pythonpath='/runner:/harness:/usr/local/lib/' + stdlib.name + '/site-packages',
                  network='shared host network; no Docker internal-network namespace',
                  candidate_uid=62055, gpu_devices=False, proc_mounted=False)
    (destination / 'process_runtime_spec.json').write_text(json.dumps(native, indent=2) + '\n')
    for path in destination.rglob('*'):
        os.chown(path, 0, 0)
        executable = path.is_dir()
        if path.is_file():
            with path.open('rb') as stream:
                executable = stream.read(4) == b'\x7fELF'
        os.chmod(path, 0o555 if executable else 0o444)
    os.chmod(destination, 0o555)
    return native


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', required=True)
    parser.add_argument('--dest', required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.python, args.dest)))
