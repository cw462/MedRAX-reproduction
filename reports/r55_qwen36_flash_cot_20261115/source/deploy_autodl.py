import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

BASE = Path("/root/autodl-tmp/medrax_r55_top4_full848")
PRIOR = BASE / "cot_repeat_20261115_001"
RUN = BASE / "qwen36_flash_cot_20261115_001"
MODEL = "qwen3.6-flash"
URL = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
DOC = "https://help.aliyun.com/zh/model-studio/qwen3-6-flash"
COUNTS = {"slake": 114, "vqarad": 116, "chexbench": 618}
SAMPLING = {"temperature": 0.2, "top_p": 0.95, "max_output_tokens": 2048, "enable_thinking": False}

def read(p):
    return json.loads(p.read_bytes())

def write(p, value):
    staging = p.with_suffix(".tmp")
    staging.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    staging.replace(p)

def change(source, old, new):
    if source.count(old) != 1:
        raise ValueError("Unexpected reference runner source")
    return source.replace(old, new, 1)

key = sys.stdin.buffer.read().strip()
if not key or key.startswith(b"sk-ws-") or b"\n" in key:
    raise ValueError("The existing Token Plan credential is required")
if RUN.exists():
    print(json.dumps({"state": "existing", "runner": read(RUN / "runner.started.json") if (RUN / "runner.started.json").is_file() else None,
                      "exit": read(RUN / "runner.exit.json") if (RUN / "runner.exit.json").is_file() else None}))
    sys.exit(0)
if read(PRIOR / "runner.exit.json")["exit"] != 0:
    raise ValueError("Reference CoT run has no successful exit")
runner = (PRIOR / "code/run_qwen_baselines.py").read_text(encoding="utf-8")
runner = change(runner, "experiment_id='cot_repeat_20261115_001'", "experiment_id=out.name")
runner = change(runner, "'model': 'qwen3.7-plus'", "'model': 'qwen3.6-flash'")
supervise = "\nimport json\nimport os\nimport subprocess\nimport sys\nimport time\nfrom pathlib import Path\n\nrun = Path(__file__).resolve().parent\nbase = run.parent\nfrozen = run / \"frozen\"\npython = base / \"env/modern/bin/python\"\n\ndef record(name, data):\n    file = run / name\n    partial = file.with_suffix(\".tmp\")\n    partial.write_text(json.dumps(data, indent=2) + \"\\n\", encoding=\"utf-8\")\n    partial.replace(file)\n\ndef identity(pid):\n    return int((Path(\"/proc\") / str(pid) / \"stat\").read_text().rsplit(\") \", 1)[1].split()[19])\n\ndef main():\n    key = sys.stdin.buffer.read()\n    if not key.strip():\n        raise ValueError(\"Token Plan credential missing from stdin\")\n    args = [str(python), \"-B\", \"-u\", str(run / \"code/run_qwen_baselines.py\"),\n            str(frozen), str(run), \"cot\", \"--workers\", \"6\"]\n    env = {**os.environ, \"CUDA_VISIBLE_DEVICES\": \"\", \"OMP_NUM_THREADS\": \"2\",\n           \"LANGCHAIN_TRACING_V2\": \"false\", \"LANGSMITH_TRACING\": \"false\"}\n    with (run / \"runner.stdout.log\").open(\"ab\") as stdout, (run / \"runner.stderr.log\").open(\"ab\") as stderr:\n        process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, cwd=run, env=env)\n        record(\"runner.started.json\", {\"pid\": process.pid, \"start_ticks\": identity(process.pid), \"epoch\": time.time()})\n        process.communicate(key)\n    record(\"runner.exit.json\", {\"pid\": process.pid, \"exit\": process.returncode, \"epoch\": time.time()})\n    return process.returncode\n\nif __name__ == \"__main__\":\n    sys.exit(main())\n"
compile(runner, "run_qwen_baselines.py", "exec")
compile(supervise, "supervise.py", "exec")
manifests = {}
for ds,n in COUNTS.items():
    manifest = read(BASE / "manifests/M2" / (ds + ".json"))
    if len(manifest["inputs"]) != n or len(manifest["reference_files"]) != n:
        raise ValueError(f"Unexpected frozen cohort for {ds}")
    if any(manifest["protocol"].get(k) != v for k,v in SAMPLING.items()):
        raise ValueError(f"Frozen sampling changed for {ds}")
    cfg, protocol = manifest["config"], manifest["protocol"]
    if cfg["credential_slot"] != "token_plan" or cfg["profile"]["base_url"] != URL:
        raise ValueError("Unexpected Token Plan endpoint")
    if protocol["budget"]["existing_shared_ledger"] is not False:
        raise ValueError("Reference CoT API accounting changed")
    cfg.update(model=MODEL, experiment_id=RUN.name)
    protocol.update(model=MODEL, experiment_id=RUN.name)
    if isinstance(cfg.get("protocol"), dict):
        cfg["protocol"].update(model=MODEL, experiment_id=RUN.name)
    cfg["profile"].update(model=MODEL, identity_prefixes=[MODEL],
                          input_cny_per_million="1.2", output_cny_per_million="7.2",
                          price_basis="beijing_public_list_price_reference_only_token_plan_credits_are_billed",
                          documentation=DOC, notes="Token Plan route. Actual Credits come from the service console.")
    manifests[ds] = manifest
RUN.mkdir(mode=0o700)
code = RUN / "code"
code.mkdir()
(code / "run_qwen_baselines.py").write_text(runner, encoding="utf-8")
shutil.copyfile(PRIOR / "code/r55_baseline_common.py", code / "r55_baseline_common.py")
(RUN / "supervise.py").write_text(supervise, encoding="utf-8")
frozen = RUN / "frozen"
(frozen / "manifests/M2").mkdir(parents=True)
for name in ("data", "refs", "code", "bin"):
    (frozen / name).symlink_to(BASE / name, target_is_directory=True)
for ds, manifest in manifests.items():
    write(frozen / "manifests/M2" / (ds + ".json"), manifest)
write(RUN / "launch.protocol.json", {
    "run": RUN.name, "comparison_run": PRIOR.name, "model": MODEL, "endpoint": URL,
    "transport": "token_plan", "cohorts": COUNTS, "dataset_order": list(COUNTS),
    "sampling": SAMPLING, "method": "prompted_cot", "workers": 6, "tools": [],
    "main_requests_per_question": 1, "score_after_full_dataset": True,
    "image_archive": "image_base64_content_addressed_v1", "launch_epoch": time.time(),
})
with (RUN / "supervisor.log").open("ab") as log:
    proc = subprocess.Popen([sys.executable, "-B", str(RUN / "supervise.py")],
                            stdin=subprocess.PIPE, stdout=log, stderr=log, cwd=RUN, start_new_session=True)
    proc.stdin.write(key + b"\n")
    proc.stdin.close()
write(RUN / "supervisor.started.json", {"pid": proc.pid, "epoch": time.time()})
print(json.dumps({"state": "launched", "run": str(RUN), "supervisor_pid": proc.pid,
                  "model": MODEL, "workers": 6, "cohorts": COUNTS}))
