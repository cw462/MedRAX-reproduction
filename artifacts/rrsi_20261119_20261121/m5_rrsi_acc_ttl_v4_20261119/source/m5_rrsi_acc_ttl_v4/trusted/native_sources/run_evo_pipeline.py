"""Sequential M1 launch; one private stdin key, separate child stdin pipes."""
import argparse
import subprocess
import sys
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--resume',action='store_true');p.add_argument('--api-key-stdin',action='store_true');a=p.parse_args()
    key=sys.stdin.buffer.readline().strip() if a.api_key_stdin else b''
    if not key:raise ValueError('missing_private_stdin_key')
    root=a.out.resolve();here=Path(__file__).resolve().parent
    commands=[[sys.executable,'-u',str(here/'build_evo_seed.py'),'--config',str(a.config),'--out',str(root/'seed'),'--resume','--api-key-stdin'],
              [sys.executable,'-u',str(here/'run_evo_memory.py'),'--config',str(a.config),'--seed',str(root/'seed'),'--out',str(root/'stream'),'--resume','--api-key-stdin']]
    for command in commands:
        result=subprocess.run(command,input=key+b'\n')
        if result.returncode:return result.returncode
    return 0


if __name__=='__main__':raise SystemExit(main())
