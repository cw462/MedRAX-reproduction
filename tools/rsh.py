#!/usr/bin/env python3
"""Remote helper for the AutoDL instance: run commands / push / pull files.

Usage:
  python rsh.py run  <script.sh>        # run a local bash script remotely
  python rsh.py cmd  "bash string"      # run a one-liner
  python rsh.py put  <local> <remote>   # sftp upload
  python rsh.py get  <remote> <local>   # sftp download
  python rsh.py ping                    # connectivity + host key

Credentials come from ../.creds.json (host/port/user/password).
"""
import json
import pathlib
import sys

import paramiko

# Windows console defaults to GBK; force UTF-8 so remote output never crashes us.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = pathlib.Path(__file__).resolve().parent
CREDS = json.loads((HERE.parent / ".creds.json").read_text(encoding="utf-8"))


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(
        CREDS["host"],
        port=int(CREDS["port"]),
        username=CREDS["user"],
        password=CREDS["password"],
        timeout=25,
        banner_timeout=40,
        auth_timeout=40,
        look_for_keys=False,
        allow_agent=False,
    )
    return c


def run(cmd, timeout=600):
    c = connect()
    try:
        _, out, err = c.exec_command(cmd, timeout=timeout, get_pty=False)
        o = out.read().decode("utf-8", "replace")
        e = err.read().decode("utf-8", "replace")
        rc = out.channel.recv_exit_status()
    finally:
        c.close()
    sys.stdout.write(o)
    if e.strip():
        sys.stderr.write("\n--- stderr ---\n" + e)
    sys.stdout.write(f"\n[exit {rc}]\n")
    return rc


def put(local, remote):
    c = connect()
    try:
        s = c.open_sftp()
        s.put(local, remote)
        s.close()
        print(f"put {local} -> {remote} ({pathlib.Path(local).stat().st_size} bytes)")
    finally:
        c.close()


def get(remote, local):
    c = connect()
    try:
        s = c.open_sftp()
        s.get(remote, local)
        s.close()
        print(f"get {remote} -> {local} ({pathlib.Path(local).stat().st_size} bytes)")
    finally:
        c.close()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    op = sys.argv[1]
    if op == "ping":
        c = connect()
        k = c.get_transport().get_remote_server_key()
        import hashlib
        print("connected", c.get_transport().remote_version)
        print("fingerprint SHA256:" + hashlib.sha256(k.asbytes()).hexdigest())
        c.close()
        return 0
    if op == "run":
        return run(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
    if op == "cmd":
        return run(sys.argv[2])
    if op == "put":
        return put(sys.argv[2], sys.argv[3]) or 0
    if op == "get":
        return get(sys.argv[2], sys.argv[3]) or 0
    print("unknown op", op)
    return 1


if __name__ == "__main__":
    sys.exit(main())
