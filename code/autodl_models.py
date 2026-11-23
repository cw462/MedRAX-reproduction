import paramiko, time, sys
HOST, PORT, USER, PW = "connect.weste.seetacloud.com", 26853, "root", "4prHrQuYi9oBdcV9S41hlM8WyGI2dHR5"
c = None
last = None
for attempt in range(5):
    try:
        c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(HOST, port=PORT, username=USER, password=PW, timeout=30, banner_timeout=60, auth_timeout=30)
        print("connected on attempt", attempt+1); break
    except Exception as e:
        last = e; print("retry", attempt, repr(e)[:80]); time.sleep(5 + attempt*5)
if c is None:
    print("FAILED", repr(last)[:200]); sys.exit(1)
def run(cmd, t=180):
    _, so, se = c.exec_command(cmd, timeout=t)
    return so.read().decode("utf-8","replace"), se.read().decode("utf-8","replace")
for cmd in [
  "du -sh /root/autodl-tmp/*/ 2>/dev/null | sort -h | tail -8",
  "find /root /root/autodl-tmp -maxdepth 4 -type d -iname '*maira*' -o -maxdepth 4 -type d -iname '*chexagent*' 2>/dev/null | head",
  "find /root /root/autodl-tmp -maxdepth 5 -type f \\( -name '*.safetensors' -o -name '*.pth' \\) -size +1G 2>/dev/null | head -15",
  "du -sh /root/.cache/huggingface 2>/dev/null; ls /root/.cache/huggingface/hub 2>/dev/null | head",
]:
    out, err = run(cmd); print("$", cmd[:60]); print(out.strip()[:1200]); print()
c.close()
