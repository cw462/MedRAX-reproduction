import paramiko, sys

HOST, PORT, USER, PW = "connect.weste.seetacloud.com", 26853, "root", "4prHrQuYi9oBdcV9S41hlM8WyGI2dHR5"

def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PW, timeout=30, banner_timeout=40, auth_timeout=30)
    return c

def run(c, cmd, timeout=120):
    si, so, se = c.exec_command(cmd, timeout=timeout)
    out = so.read().decode("utf-8", "replace")
    err = se.read().decode("utf-8", "replace")
    return out, err

c = connect()
for cmd in ["hostname; nvidia-smi -L 2>&1 | head -3",
            "df -h / /root/autodl-tmp 2>/dev/null | tail -3",
            "du -sh /root/autodl-tmp/* 2>/dev/null | sort -h | tail -15",
            "du -sh /root/* 2>/dev/null | sort -h | tail -10"]:
    out, err = run(c, cmd)
    print("$", cmd)
    print(out.strip()[:1500])
    if err.strip(): print("ERR:", err.strip()[:200])
    print()
c.close()
