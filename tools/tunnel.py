#!/usr/bin/env python3
"""Local TCP forwarder: 127.0.0.1:<local_port> -> (via AutoDL box) -> host:22.

Lets this machine use git over SSH against github.com even though the local
network cannot reach it: the AutoDL instance can, and we tunnel through it.
The private key never leaves this machine.
"""
import json
import pathlib
import selectors
import socket
import sys

import paramiko

HERE = pathlib.Path(__file__).resolve().parent
CREDS = json.loads((HERE.parent / ".creds.json").read_text(encoding="utf-8"))

LISTEN = ("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 2222)
TARGET = (sys.argv[2] if len(sys.argv) > 2 else "github.com", 22)


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(CREDS["host"], port=int(CREDS["port"]), username=CREDS["user"],
              password=CREDS["password"], timeout=25, look_for_keys=False, allow_agent=False)
    tr = c.get_transport()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(LISTEN)
    srv.listen(8)
    print(f"tunnel {LISTEN[0]}:{LISTEN[1]} -> {TARGET[0]}:{TARGET[1]} via {CREDS['host']}",
          flush=True)

    sel = selectors.DefaultSelector()
    sel.register(srv, selectors.EVENT_READ)

    def pump(a, b):
        while True:
            try:
                data = a.recv(65536)
            except Exception:
                break
            if not data:
                break
            try:
                b.sendall(data)
            except Exception:
                break
        try:
            b.shutdown(socket.SHUT_WR)
        except Exception:
            pass

    while True:
        try:
            conn, _ = srv.accept()
        except KeyboardInterrupt:
            break
        try:
            ch = tr.open_channel("direct-tcpip", TARGET, conn.getpeername())
        except Exception as exc:  # noqa: BLE001
            print("open_channel failed:", exc, flush=True)
            conn.close()
            continue

        import threading
        t1 = threading.Thread(target=pump, args=(conn, ch), daemon=True)
        t2 = threading.Thread(target=pump, args=(ch, conn), daemon=True)
        t1.start()
        t2.start()

    srv.close()
    c.close()


if __name__ == "__main__":
    main()
