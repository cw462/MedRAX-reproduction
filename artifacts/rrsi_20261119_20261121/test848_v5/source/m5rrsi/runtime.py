"""Narrow runtime boundary. Generated source executes in a separate Docker container.
The container must use a trusted, budget-enforcing medical tool/model gateway.
Neither the reference file nor the host run directory is mounted.
"""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import tempfile
import time
import uuid
from .io import ProtocolError, command, read_json, write_json, tree_hash, file_hash


def require_prediction(result):
    if not isinstance(result, dict) or not isinstance(result.get("answer"), str):
        raise ProtocolError("native predict must return answer text")
    if "trace" not in result or not isinstance(result["trace"], (list, dict)):
        raise ProtocolError("native predict must return a real execution trace")
    u = result.get("usage", {})
    for k in ("total_tokens", "model_calls", "tool_calls"):
        if not isinstance(u.get(k), (int, float)) or u[k] < 0:
            raise ProtocolError(f"missing/invalid runtime usage: {k}")
    return result


def scoped_case(case, metadata):
    """Limit trusted same-image dependencies to the current empty-start replay."""
    if "replay_previous_ids" not in case:
        return case, metadata
    public = dict(case)
    previous = set(public.pop("replay_previous_ids"))
    item = metadata["order_item"]
    return public, {**metadata, "order_item": {**item, "previous_ids": [
        qid for qid in item["previous_ids"] if qid in previous
    ]}}


class DockerRuntime:
    def __init__(self, config, audit_dir):
        self.cfg = config
        self.audit = Path(audit_dir).resolve(); self.audit.mkdir(parents=True, exist_ok=True)
        self.runtime_dir = Path(config["runtime_dir"]).resolve()
        self.case_metadata = read_json(config["case_metadata"])
    def preflight(self):
        c = self.cfg
        image = c["image"]
        import re
        if not re.fullmatch(r"(?:[^\s]+@)?sha256:[0-9a-f]{64}", image):
            raise ProtocolError("pin the native Docker image by digest")
        command(["docker", "image", "inspect", c["image"]])
        if c["network"] in ("host", "bridge", "none", "default"):
            raise ProtocolError("use a dedicated INTERNAL network with a restricted model/tool gateway")
        net = json.loads(command(["docker", "network", "inspect", c["network"]]))[0]
        if not net.get("Internal"): raise ProtocolError("candidate Docker network must have Internal=true")
        if not (self.runtime_dir / "worker.py").exists() or not (self.runtime_dir / "native_bridge.py").exists():
            raise ProtocolError("native worker/bridge is not installed")
        if any("<" in str(v) or "REPLACE" in str(v) for v in (c["image"], c["gateway_url"])):
            raise ProtocolError("runtime configuration is still a template")
    def call(self, harness, state, op, *, case=None, prediction=None, feedback=None, seed=0):
        if op not in {"initialize", "predict", "observe", "migrate", "check"}:
            raise ProtocolError("unknown native operation")
        if op != "observe" and feedback is not None:
            raise ProtocolError("feedback is only passed to observe")
        harness = Path(harness).resolve(); state = Path(state).resolve()
        h = tree_hash(harness)
        work = self.audit / uuid.uuid4().hex; work.mkdir()
        out = work / "out"; out.mkdir()
        req = {"operation": op, "seed": seed, "harness_sha256": h,
               "model": self.cfg["model"], "limits": self.cfg["limits"],
               "gateway_url": self.cfg["gateway_url"]}
        mounts = []
        if case is not None:
            case, native = scoped_case(case, self.case_metadata[case["id"]])
            q = copy.deepcopy(case)
            for n, im in enumerate(q["images"]):
                source = Path(im["path"]).resolve()
                if file_hash(source) != im["sha256"]: raise ProtocolError("original image bytes changed")
                target = f"/case_images/{n}{source.suffix}"
                mounts += ["--mount", f"type=bind,src={source},dst={target},readonly"]
                im["path"] = target
            req["case"] = q
        if prediction is not None: req["prediction"] = prediction
        if feedback is not None: req["feedback"] = feedback
        from integration.native_gateway import control_request
        native_cache = state / "native_services"
        if op in ("predict", "observe"):
            native_cache.mkdir(exist_ok=True)
        registration = {"action": "register", "operation": op, "seed": seed,
                        "limits": self.cfg["limits"], "state_dir": str(state)}
        if case is not None:
            registration.update(case=case, native_row=native["native_row"],
                                order_item=native["order_item"], ordinal=native["ordinal"],
                                image_annotations=native["image_annotations"])
        session = control_request(self.cfg["control_socket"], registration)
        req["gateway_url"] = session["gateway_url"]
        write_json(work / "request.json", req)
        # No host environment is forwarded into the candidate container.
        name = "m5ttl-" + uuid.uuid4().hex
        argv = ["docker", "run", "--rm", "--name", name, "--read-only",
                "--user", f"{os.getuid()}:{os.getgid()}", "--cap-drop=ALL",
                "--security-opt=no-new-privileges", "--pids-limit=128",
                "--memory", self.cfg.get("memory_limit", "8g"), "--cpus", str(self.cfg.get("cpus", 4)),
                "--network", self.cfg["network"], "--tmpfs", "/tmp:rw,nosuid,nodev,size=1g",
                "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "PYTHONPATH=/runner:/harness",
                "--mount", f"type=bind,src={harness},dst=/harness,readonly",
                "--mount", f"type=bind,src={state},dst=/state",
                "--mount", f"type=bind,src={self.runtime_dir},dst=/runner,readonly",
                "--mount", f"type=bind,src={work / 'request.json'},dst=/request.json,readonly",
                "--mount", f"type=bind,src={out},dst=/out", *mounts,
                *(["--mount", f"type=bind,src={native_cache},dst=/state/native_services,readonly"]
                  if native_cache.exists() else []),
                self.cfg["image"], "python", "/runner/worker.py"]
        start = time.monotonic()
        try:
            stdout = command(argv, timeout=self.cfg.get("timeout_seconds", 600))
            (work / "stdout.log").write_text(stdout, encoding="utf-8")
        except Exception as exc:
            write_json(work / "receipt.json", {"op": op, "status": "failed", "error_type": type(exc).__name__,
                "seconds": time.monotonic() - start, "usage": None, "harness_sha256": h,
                "retained_state": str(state)})
            # A killed docker client can leave its container alive; explicitly stop it.
            try: command(["docker", "rm", "-f", name], timeout=20)
            except Exception: pass
            raise
        finally:
            usage = control_request(self.cfg["control_socket"],
                                    {"action": "close", "session": session["session"]})
            write_json(work / "gateway_receipt.json", usage)
        result = read_json(out / "result.json")
        if usage.get("authoritative") is not True:
            raise ProtocolError("native gateway did not return authoritative usage")
        result["usage"] = usage
        if result.get("harness_sha256") != h or tree_hash(harness) != h:
            raise ProtocolError("executed harness hash mismatch")
        if result.get("model") != self.cfg["model"]: raise ProtocolError("native model configuration changed")
        result["wall_seconds"] = time.monotonic() - start
        write_json(work / "receipt.json", {"op": op, "seconds": result["wall_seconds"],
                   "usage": result.get("usage"), "harness_sha256": h, "retained_state": str(state)})
        if op == "predict": require_prediction(result)
        return result


class NativeScorer:
    """Trusted host adapter to the existing frozen scorer; never an editable module."""
    def __init__(self, argv, metric_id):
        if not argv or not metric_id: raise ProtocolError("native scorer is not configured")
        self.argv, self.metric_id = argv, metric_id
    def score(self, case, prediction, reference):
        payload = {"id": case["id"], "dataset": case["dataset"], "options": case["options"],
                   "answer": prediction["answer"], "reference": reference,
                   "terminal_raw": prediction.get("terminal_raw")}
        out = json.loads(command(self.argv, input_data=json.dumps(payload, ensure_ascii=False), timeout=120))
        if out.get("metric_id") != self.metric_id or out.get("correct") not in (0, 1, False, True):
            raise ProtocolError("native scorer contract mismatch")
        return int(out["correct"])
