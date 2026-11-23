import paramiko, time
HOST, PORT, USER, PW = "connect.weste.seetacloud.com", 32922, "root", "thGEPB3RC7f1cx5E/y5/6LMMk3KEqFxA"
def one(cmd, timeout=120, retries=4):
    last=None
    for a in range(retries):
        c=None
        try:
            c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(HOST, port=PORT, username=USER, password=PW, timeout=25, banner_timeout=45)
            _,so,se=c.exec_command(cmd,timeout=timeout)
            return so.read().decode("utf-8","replace") + (("\nERR:"+se.read().decode("utf-8","replace")[:200]) )
        except Exception as e:
            last=e; time.sleep(3+a*3)
        finally:
            if c:
                try: c.close()
                except Exception: pass
    return f"FAILED {repr(last)[:100]}"
for cmd in [
  "curl -s -m 15 -o /dev/null -w 'modelscope:%{http_code} time:%{time_total}\\n' https://modelscope.cn",
  "curl -s -m 15 -o /dev/null -w 'huggingface:%{http_code}\\n' https://huggingface.co",
  "curl -s -m 20 -o /dev/null -w 'speed:%{speed_download} B/s\\n' 'https://modelscope.cn/api/v1/models/microsoft/maira-2/repo?Revision=master&FilePath=model-00001-of-00006.safetensors' -r 0-100000000",
  "python -c 'import torch;print(torch.__version__, torch.cuda.is_available())' 2>&1 | tail -1",
  "which conda; ls /root/miniconda3/envs 2>/dev/null | head",
]:
    print("$", cmd); print(one(cmd)); print()
