import paramiko, time, sys

HOST, PORT, USER, PW = "connect.weste.seetacloud.com", 32922, "root", "thGEPB3RC7f1cx5E/y5/6LMMk3KEqFxA"

def connect(retries=6):
    last = None
    for a in range(retries):
        try:
            c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(HOST, port=PORT, username=USER, password=PW, timeout=30, banner_timeout=60, auth_timeout=30)
            return c
        except Exception as e:
            last = e; time.sleep(4 + a*3)
    raise RuntimeError(repr(last))

def run(c, cmd, timeout=180):
    _, so, se = c.exec_command(cmd, timeout=timeout)
    return so.read().decode("utf-8","replace"), se.read().decode("utf-8","replace")

if __name__ == "__main__":
    c = connect()
    for cmd in ["hostname; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>&1 | head -3",
                "df -h / /root/autodl-tmp | tail -3",
                "ls /root/autodl-tmp | head -10",
                "du -sh /root/autodl-tmp/*/ 2>/dev/null | sort -h | tail -8"]:
        out, err = run(c, cmd)
        print("$", cmd); print(out.strip()[:1000]); print()
    c.close()
