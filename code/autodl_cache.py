import paramiko, time
HOST, PORT, USER, PW = "connect.weste.seetacloud.com", 32922, "root", "REDACTED_AUTODL_32922_PASSWORD"
def one(cmd, timeout=90, retries=6):
    last=None
    for a in range(retries):
        c=None
        try:
            c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(HOST, port=PORT, username=USER, password=PW, timeout=25, banner_timeout=45)
            _,so,se=c.exec_command(cmd,timeout=timeout)
            return so.read().decode("utf-8","replace").strip()
        except Exception as e:
            last=e; time.sleep(4+a*3)
        finally:
            if c:
                try: c.close()
                except Exception: pass
    return f"FAILED {repr(last)[:80]}"
for cmd in [
  "ls -la /root/medrax_r55_top4_model_cache | head",
  "du -sh /root/medrax_r55_top4_model_cache 2>/dev/null",
  "find /root/medrax_r55_top4_model_cache -maxdepth 3 -iname '*maira*' 2>/dev/null | head",
  "du -sh /root/autodl-tmp/* 2>/dev/null | sort -h | tail -5",
]:
    print("$", cmd); print(one(cmd)); print()

---
> **注意（2026-11-23 归档时自动处理）**：本文件原含明文密码，已替换为占位符，
> 改为从环境变量读取。详见仓库根目录 `SECURITY.md`。
