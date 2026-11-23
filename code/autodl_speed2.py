import paramiko, time
HOST, PORT, USER, PW = "connect.weste.seetacloud.com", 32922, "root", "thGEPB3RC7f1cx5E/y5/6LMMk3KEqFxA"
def one(cmd, timeout=120, retries=6):
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
print(one("curl -s -m 60 -o /tmp/t.bin -w 'http:%{http_code} size:%{size_download} speed:%{speed_download}\\n' -r 0-200000000 'https://modelscope.cn/api/v1/models/microsoft/maira-2/repo?Revision=master&FilePath=model-00006-of-00006.safetensors'; ls -lh /tmp/t.bin 2>/dev/null"))
print(one("/root/miniconda3/bin/python -c 'import torch,transformers;print(torch.__version__, torch.cuda.is_available(), transformers.__version__)' 2>&1 | tail -2"))
print(one("df -h /root/autodl-tmp | tail -1; du -sh /root/autodl-tmp/medrax_m5_rrsi_acc_ttl_v4_20261119 2>/dev/null"))
