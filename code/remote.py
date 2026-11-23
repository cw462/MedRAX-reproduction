"""Minimal paramiko helper for the IMSS lab server (private, not for the repo).

The campus network routes SSH through the WLAN interface; a Meta TUN can hijack the
default route. Bind the socket to the live WLAN interface index (never hard-coded),
fall back to a direct connection, and retry with backoff.

Usage:
  python remote.py run <local-script.sh> [timeout]
  python remote.py put <local> <remote>
  python remote.py get <remote> <local>
  python remote.py cmd "<shell command>" [timeout]
"""
from __future__ import annotations

import socket
import struct
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

import paramiko

sys.path.insert(0, r"C:\Users\cheng")
import _ssh_helper as prior  # noqa: E402

ROOT = "/home/imss/cw/MedRAX_reproduction_20261027"


def _wlan_index():
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "(Get-NetIPInterface -AddressFamily IPv4 -InterfaceAlias WLAN).InterfaceIndex"],
            text=True, timeout=30).strip()
        return int(out) if out else None
    except Exception:
        return None


def _connect_once(index):
    kwargs = dict(username=prior.USER, password=prior.PWD, timeout=30, banner_timeout=45,
                  auth_timeout=20, look_for_keys=False, allow_agent=False)
    client = paramiko.SSHClient()
    client.load_host_keys(r"C:\Users\cheng\_ssh_known_hosts_imss")
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    sock = None
    if index is not None:
        sock = socket.socket()
        sock.settimeout(30)
        sock.setsockopt(socket.IPPROTO_IP, 31, struct.pack("!I", index))
        sock.connect((prior.HOST, 22))
        kwargs["sock"] = sock
    try:
        client.connect(prior.HOST, **kwargs)
    except Exception:
        if sock is not None:
            sock.close()
        raise
    # On success paramiko owns the socket; closing it here would kill the session.
    return client


def connect(retries=6):
    index = _wlan_index()
    last = None
    for attempt in range(retries):
        for use in ([index, None] if index is not None else [None]):
            if use is None and index is None:
                continue
            try:
                return _connect_once(use)
            except Exception as exc:  # noqa: BLE001
                last = exc
        time.sleep(min(30, 2 ** attempt))
    raise RuntimeError(f"SSH connect failed after {retries} attempts: {last!r}")


def _check(remote):
    path = PurePosixPath(remote)
    if ".." in path.parts or not path.is_relative_to("/home/imss/cw"):
        raise ValueError("Path must stay under /home/imss/cw")


def main():
    action = sys.argv[1]
    client = connect()
    try:
        if action == "run":
            script = Path(sys.argv[2]).read_bytes()
            timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 3600
            stdin, out, err = client.exec_command("bash -s", timeout=timeout)
            stdin.write(script)
            stdin.channel.shutdown_write()
            for line in out:
                sys.stdout.write(line)
                sys.stdout.flush()
            text = err.read().decode("utf-8", "replace")
            if text:
                sys.stderr.write(text)
            raise SystemExit(out.channel.recv_exit_status())
        if action == "cmd":
            timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 600
            _, out, err = client.exec_command(sys.argv[2], timeout=timeout)
            sys.stdout.write(out.read().decode("utf-8", "replace"))
            text = err.read().decode("utf-8", "replace")
            if text:
                sys.stderr.write(text[:4000])
            raise SystemExit(out.channel.recv_exit_status())
        remote = sys.argv[3] if action == "put" else sys.argv[2]
        _check(remote)
        with client.open_sftp() as sftp:
            if action == "put":
                sftp.put(sys.argv[2], sys.argv[3])
            elif action == "get":
                sftp.get(sys.argv[2], sys.argv[3])
            else:
                raise SystemExit("unknown action")
        print(action, "ok")
    finally:
        client.close()


if __name__ == "__main__":
    main()
