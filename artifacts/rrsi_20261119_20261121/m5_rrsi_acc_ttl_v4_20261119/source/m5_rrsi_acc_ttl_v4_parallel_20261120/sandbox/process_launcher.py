"""Trusted root launcher. Chroot, drop privileges, then exec candidate Python."""

import ctypes
import json
import os
from pathlib import Path
import resource
import sys


def main():
    root, settings = Path(sys.argv[1]).resolve(), json.loads(sys.argv[2])
    uid = settings['uid']
    if type(uid) is not int or uid < 10000 or os.geteuid() != 0:
        raise RuntimeError('Process runtime needs root launcher and a separate numeric UID')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    for kind, value in ((resource.RLIMIT_AS, settings['memory_bytes']),
                        (resource.RLIMIT_CPU, settings['cpu_seconds']),
                        (resource.RLIMIT_NOFILE, 256), (resource.RLIMIT_NPROC, 128)):
        resource.setrlimit(kind, (value, value))
    if hasattr(os, 'sched_setaffinity'):
        allowed = sorted(os.sched_getaffinity(0))
        os.sched_setaffinity(0, allowed[:settings['cpus']])
    os.chroot(root)
    os.chdir('/')
    os.setgroups([])
    os.setgid(uid)
    os.setuid(uid)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0):
        raise OSError(ctypes.get_errno(), 'PR_SET_NO_NEW_PRIVS')
    class Header(ctypes.Structure):
        _fields_ = [('version', ctypes.c_uint32), ('pid', ctypes.c_int)]
    class Data(ctypes.Structure):
        _fields_ = [('effective', ctypes.c_uint32), ('permitted', ctypes.c_uint32), ('inheritable', ctypes.c_uint32)]
    header, data = Header(0x20080522, 0), (Data * 2)()
    if libc.capset(ctypes.byref(header), ctypes.byref(data)):
        raise OSError(ctypes.get_errno(), 'capset')
    environment = {'PATH': '/usr/local/bin', 'HOME': '/tmp', 'TMPDIR': '/tmp',
                   'PYTHONHOME': '/usr/local', 'PYTHONPATH': settings['pythonpath'],
                   'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1',
                   'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': str(settings['cpus']),
                   'LD_LIBRARY_PATH': '/usr/local/lib:/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu'}
    os.execve('/usr/local/bin/python', ['python', settings['entrypoint']], environment)


if __name__ == '__main__':
    main()
