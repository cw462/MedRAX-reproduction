"""Trusted in-container loader; only /harness is evolvable.
Copy alongside the completed native_bridge.py. Candidate code never receives
reference paths, future questions, full manifests, host run directories, or API keys.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys


def tree_hash(root):
    result = {}
    for p in sorted(Path(root).rglob("*")):
        if p.is_symlink(): raise RuntimeError("symlink in harness")
        if p.is_file(): result[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    raw = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def main():
    req = json.loads(Path("/request.json").read_text())
    before = tree_hash(Path("/harness"))
    if before != req["harness_sha256"]: raise RuntimeError("source mismatch")
    for p in Path("/harness").rglob("*.py"):
        compile(p.read_text(), str(p), "exec")
    from native_bridge import create_services
    services = create_services(req["gateway_url"], req["model"], req["limits"], req["seed"])
    spec = importlib.util.spec_from_file_location("m5_editable_agent", "/harness/agent.py")
    agent = importlib.util.module_from_spec(spec); sys.modules[spec.name] = agent
    spec.loader.exec_module(agent)
    for name in ("initialize", "predict", "observe", "migrate"):
        if not callable(getattr(agent, name, None)): raise RuntimeError(f"missing entrypoint {name}")
    state = Path("/state"); op = req["operation"]
    if op == "check": result = {"ok": True}
    elif op == "initialize": result = agent.initialize(state, services) or {}
    elif op == "migrate": result = agent.migrate(state, services) or {}
    elif op == "predict": result = agent.predict(req["case"], state, services)
    elif op == "observe":
        result = agent.observe(req["case"], req["prediction"], req["feedback"], state, services) or {}
    else: raise RuntimeError("invalid operation")
    if tree_hash(Path("/harness")) != before: raise RuntimeError("source changed during runtime")
    # Usage must come from a trusted gateway, not from candidate self-report.
    result["usage"] = services.usage_receipt()
    result["harness_sha256"] = before
    result["model"] = req["model"]
    Path("/out/result.json").write_text(json.dumps(result, ensure_ascii=False, allow_nan=False))

if __name__ == "__main__": main()
