import paramiko, time
HOST, PORT, USER, PW = "connect.weste.seetacloud.com", 32922, "root", "REDACTED_AUTODL_32922_PASSWORD"
def one(cmd, timeout=90, retries=5):
    last=None
    for a in range(retries):
        c=None
        try:
            c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(HOST, port=PORT, username=USER, password=PW, timeout=25, banner_timeout=45)
            _,so,se=c.exec_command(cmd,timeout=timeout)
            return so.read().decode("utf-8","replace").strip()
        except Exception as e:
            last=e; time.sleep(4+a*4)
        finally:
            if c:
                try: c.close()
                except Exception: pass
    return f"FAILED {repr(last)[:80]}"
for cmd in [
  "ls /root | head -15",
  "ls /root/miniconda3/bin/python* 2>/dev/null; ls /usr/bin/python* 2>/dev/null",
  "df -h /root/autodl-tmp; ls /root/autodl-tmp | wc -l",
  "curl -s -m 10 -o /dev/null -w 'baidu:%{http_code}\\n' https://www.baidu.com",
  "nvidia-smi --query-gpu=name,memory.used --format=csv,noheader",
]:
    print("$", cmd); print(one(cmd)); print()

---
> **注意（2026-11-23 归档时自动处理）**：本文件原含明文密码，已替换为占位符，
> 改为从环境变量读取。详见仓库根目录 `SECURITY.md`。
