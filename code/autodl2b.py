import paramiko, time
HOST, PORT, USER, PW = "connect.weste.seetacloud.com", 32922, "root", "thGEPB3RC7f1cx5E/y5/6LMMk3KEqFxA"
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
for a in range(5):
    try:
        c.connect(HOST, port=PORT, username=USER, password=PW, timeout=30, banner_timeout=60); break
    except Exception: time.sleep(5)
def run(cmd, t=240):
    _, so, se = c.exec_command(cmd, timeout=t)
    return so.read().decode("utf-8","replace")
print(run("du -sh /root/autodl-tmp/medrax_r55_top4_full848 2>/dev/null; ls /root/autodl-tmp/medrax_r55_top4_full848 2>/dev/null | head"))
print(run("ls -lh /root/autodl-tmp/medrax_r55_top4_full848/models/f70-persistent-41248/maira2/ 2>/dev/null | head"))
print(run("find /root/autodl-tmp -maxdepth 5 -type d -iname '*maira*' 2>/dev/null | head"))
print(run("du -sh /root/autodl-tmp/* 2>/dev/null | sort -h | tail -5"))
c.close()
