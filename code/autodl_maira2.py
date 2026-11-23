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
print(run("ls /root/autodl-tmp/medrax_r55_top4_full848/models/hf_full/ | head -20"))
print(run("find /root/autodl-tmp/medrax_r55_top4_full848/models -maxdepth 4 -name 'config.json' 2>/dev/null | grep -i maira | head -5"))
print(run("find /root/autodl-tmp -maxdepth 6 -name 'modeling_maira2.py' 2>/dev/null | head -5"))
print(run("ls -la /root/autodl-tmp/medrax_r55_top4_full848/models/f70-persistent-41248/maira2/ | head"))
c.close()
