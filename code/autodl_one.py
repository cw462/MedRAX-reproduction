import paramiko, time
HOST, PORT, USER, PW = "connect.weste.seetacloud.com", 32922, "root", "REDACTED_AUTODL_32922_PASSWORD"

def one(cmd, timeout=120, retries=4):
    last = None
    for a in range(retries):
        c = None
        try:
            c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(HOST, port=PORT, username=USER, password=PW, timeout=25, banner_timeout=45, auth_timeout=25)
            _, so, se = c.exec_command(cmd, timeout=timeout)
            out = so.read().decode("utf-8","replace")
            err = se.read().decode("utf-8","replace")
            return out + (("\nERR:" + err[:200]) if err.strip() else "")
        except Exception as e:
            last = e; time.sleep(3 + a*3)
        finally:
            if c: 
                try: c.close()
                except Exception: pass
    return f"FAILED {repr(last)[:120]}"

cmds = [
 "du -sh /root/autodl-tmp/medrax_r55_top4_full848 2>/dev/null",
 "ls /root/autodl-tmp/medrax_r55_top4_full848/models 2>/dev/null | head",
 "ls -lh /root/autodl-tmp/medrax_r55_top4_full848/models/f70-persistent-41248/maira2/ 2>/dev/null | head -6",
 "find /root/autodl-tmp -maxdepth 4 -type d -iname '*maira*' 2>/dev/null | head -5",
 "du -sh /root/autodl-tmp/* 2>/dev/null | sort -h | tail -4",
]
for cmd in cmds:
    print("$", cmd)
    print(one(cmd))
    print()

---
> **注意（2026-11-23 归档时自动处理）**：本文件原含明文密码，已替换为占位符，
> 改为从环境变量读取。详见仓库根目录 `SECURITY.md`。
