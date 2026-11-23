import paramiko, time
HOST, PORT, USER, PW = "connect.weste.seetacloud.com", 26853, "root", "4prHrQuYi9oBdcV9S41hlM8WyGI2dHR5"
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
for a in range(4):
    try:
        c.connect(HOST, port=PORT, username=USER, password=PW, timeout=30, banner_timeout=60); break
    except Exception: time.sleep(6)
def run(cmd, t=240):
    _, so, se = c.exec_command(cmd, timeout=t)
    return so.read().decode("utf-8","replace")
print(run("du -sh /root/autodl-tmp/medrax_r55_top4_full848/models/* 2>/dev/null | sort -h | tail -10"))
print(run("find /root/autodl-tmp -maxdepth 6 -type f -size +1G 2>/dev/null | grep -i -E 'maira|sam|medsam' | head -10"))
print(run("ls /root/autodl-tmp/medrax_r55_top4_full848/env 2>/dev/null | head; du -sh /root/autodl-tmp/medrax_r55_top4_full848/env/* 2>/dev/null | head"))
print(run("ls /root/autodl-tmp/medrax_r55_top4_full848/chexagent8 2>/dev/null | head -5"))
c.close()
