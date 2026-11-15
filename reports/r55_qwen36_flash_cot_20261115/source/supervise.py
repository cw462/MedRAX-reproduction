
import json
import os
import subprocess
import sys
import time
from pathlib import Path

run = Path(__file__).resolve().parent
base = run.parent
frozen = run / "frozen"
python = base / "env/modern/bin/python"

def record(name, data):
    file = run / name
    partial = file.with_suffix(".tmp")
    partial.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    partial.replace(file)

def identity(pid):
    return int((Path("/proc") / str(pid) / "stat").read_text().rsplit(") ", 1)[1].split()[19])

def main():
    key = sys.stdin.buffer.read()
    if not key.strip():
        raise ValueError("Token Plan credential missing from stdin")
    args = [str(python), "-B", "-u", str(run / "code/run_qwen_baselines.py"),
            str(frozen), str(run), "cot", "--workers", "6"]
    env = {**os.environ, "CUDA_VISIBLE_DEVICES": "", "OMP_NUM_THREADS": "2",
           "LANGCHAIN_TRACING_V2": "false", "LANGSMITH_TRACING": "false"}
    with (run / "runner.stdout.log").open("ab") as stdout, (run / "runner.stderr.log").open("ab") as stderr:
        process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, cwd=run, env=env)
        record("runner.started.json", {"pid": process.pid, "start_ticks": identity(process.pid), "epoch": time.time()})
        process.communicate(key)
    record("runner.exit.json", {"pid": process.pid, "exit": process.returncode, "epoch": time.time()})
    return process.returncode

if __name__ == "__main__":
    sys.exit(main())
