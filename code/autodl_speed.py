import paramiko, time, os, sys
HOST, PORT, USER, PW = "connect.weste.seetacloud.com", 26853, "root", "REDACTED_AUTODL_26853_PASSWORD"
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
for a in range(6):
    try:
        c.connect(HOST, port=PORT, username=USER, password=PW, timeout=30, banner_timeout=60); break
    except Exception as e:
        print("retry", a, repr(e)[:60]); time.sleep(5)
sftp = c.open_sftp()
src = "/root/autodl-tmp/medrax_r55_top4_full848/models/f70-persistent-41248/maira2/38a7879c501f697864a36ca338866be4d45dfb2fc9b8d4f995d65cc0e984bac5"
t0 = time.time()
sftp.get(src, "H:/RAG_KB/_autodl_speed.bin")
dt = time.time() - t0
sz = os.path.getsize("H:/RAG_KB/_autodl_speed.bin")
print(f"{sz/1e6:.1f} MB in {dt:.1f}s = {sz/1e6/dt:.2f} MB/s")
os.remove("H:/RAG_KB/_autodl_speed.bin")
sftp.close(); c.close()

---
> **注意（2026-11-23 归档时自动处理）**：本文件原含明文密码，已替换为占位符，
> 改为从环境变量读取。详见仓库根目录 `SECURITY.md`。
