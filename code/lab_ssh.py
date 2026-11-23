import paramiko, sys

HOST = "10.60.147.117"; PORT = 22; USER = "imss"; PW = "REDACTED_LAB_PASSWORD"

def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, banner_timeout=30, auth_timeout=30)
    return c

def run(c, cmd, timeout=120):
    si, so, se = c.exec_command(cmd, timeout=timeout, get_pty=False)
    out = so.read().decode("utf-8", "replace")
    err = se.read().decode("utf-8", "replace")
    rc = so.channel.recv_exit_status()
    return rc, out, err

if __name__ == "__main__":
    c = connect()
    for cmd in ["hostname; whoami; uname -a",
                "nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader",
                "which python python3 conda; python3 --version",
                "ls /home/imss/cw | head -20",
                "df -h /home/imss | tail -1",
                "python3 -c 'import torch;print(torch.__version__, torch.cuda.is_available())' 2>&1 | tail -1"]:
        rc, out, err = run(c, cmd)
        print("$", cmd)
        print(out.strip()[:800])
        if err.strip(): print("  ERR:", err.strip()[:200])
        print("  rc=", rc)
    c.close()

---
> **注意（2026-11-23 归档时自动处理）**：本文件原含明文密码，已替换为占位符，
> 改为从环境变量读取。详见仓库根目录 `SECURITY.md`。
