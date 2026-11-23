"""Prepare the common native tool environment for the v6 paired pilot."""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from urllib.request import Request, urlopen

from integration.native_gateway import control_request, validate_binding

from .data import public_case
from .io import ProtocolError, read_json, run_lock, write_json


NATIVE_RUNTIME = Path("/root/autodl-tmp/medrax_r55_top4_full848")


def _live_gateway(receipt, entry, config_path):
    cmdline = Path("/proc") / str(receipt["pid"]) / "cmdline"
    try:
        args = cmdline.read_bytes().split(b"\0")
    except FileNotFoundError:
        return False
    return os.fsencode(entry) in args and os.fsencode(config_path) in args


def _start_gateway(entry, config_path, old_config_path, config, wire, log):
    source = Path(config["source_dir"])
    interpreter = NATIVE_RUNTIME / "env" / "modern" / "bin" / "python"
    pythonpath = [entry.parent.parent, entry.parent, old_config_path.parent, source, NATIVE_RUNTIME / "bin"]
    environment = dict(os.environ)
    inherited = environment.get("PYTHONPATH")
    search_path = [str(path) for path in pythonpath]
    if inherited:
        search_path.append(inherited)
    environment.update(
        PYTHONPATH=os.pathsep.join(search_path),
        PYTHONDONTWRITEBYTECODE="1",
        CUDA_VISIBLE_DEVICES="0",
        R55_MEMEVOLVE_GPU="0",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        TOKENIZERS_PARALLELISM="false",
        MPLBACKEND="Agg",
        OMP_NUM_THREADS="4",
        MKL_NUM_THREADS="4",
    )
    with log.open("ab") as output:
        process = subprocess.Popen(
            [str(interpreter), "-B", str(entry), "--config", str(config_path)],
            cwd=source, env=environment, stdin=subprocess.DEVNULL, stdout=output,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
    deadline = time.monotonic() + 60
    try:
        while not wire.is_socket():
            if process.poll() is not None:
                raise ProtocolError(f"v6 gateway exited during startup. See {log}.")
            if time.monotonic() >= deadline:
                raise TimeoutError(f"v6 gateway did not open its control socket. See {log}.")
            time.sleep(0.25)
        session = control_request(wire, {
            "action": "register", "operation": "check", "seed": 42, "limits": config["limits"],
        })
        control_request(wire, {"action": "close", "session": session["session"]})
    except Exception:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        if wire.is_socket():
            wire.unlink()
        raise
    return process.pid


def _smoke_roi(wire, config, trusted, sample_case, case_metadata, pid):
    case = public_case(sample_case)
    receipt_path = trusted / "roi_smoke.json"
    if receipt_path.is_file():
        receipt = read_json(receipt_path)
        if receipt["gateway_pid"] == pid and receipt["case_id"] == case["id"]:
            return
    meta = read_json(case_metadata)[case["id"]]
    state = tempfile.mkdtemp(prefix="roi-", dir=trusted)
    binding = {k: meta[k] for k in ("native_row", "order_item", "ordinal", "image_annotations")}
    session = control_request(wire, {
        "action": "register", "operation": "predict", "seed": 42, "case": case,
        "state_dir": state, "limits": config["limits"], **binding,
    })
    try:
        action = {"tool": "roi_crop", "args": {"box": [0.25, 0.25, 0.75, 0.75], "zoom": 2}}
        payload = {"row": binding["native_row"], "action": action, "ordinal": 1}
        request = Request(
            session["gateway_url"] + "/tool", data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urlopen(request, timeout=90) as reply:
            result = json.load(reply)
    finally:
        usage = control_request(wire, {"action": "close", "session": session["session"]})
    tool = result["result"]["observation"]
    images = result["result"]["images"]
    if tool["status"] != "completed" or not images:
        raise ProtocolError(f"v6 ROI crop failed: {tool.get('error', tool['status'])}.")
    if not usage["authoritative"] or usage["tool_calls"] != 1 or usage["model_calls"] or usage["embedding_calls"]:
        raise ProtocolError("v6 ROI smoke did not close exactly one tool operation.")
    write_json(receipt_path, {
        "gateway_pid": pid, "case_id": case["id"], "status": tool["status"],
        "derived_images": len(images), "usage": usage, "observed_epoch": time.time(),
    })


def prepare_backend(v5_run: Path, out: Path, sample_case: dict, case_metadata: Path) -> dict:
    """Start the v6 gateway with the existing model residents and verify ROI."""
    v5_run, out = Path(v5_run).resolve(), Path(out).resolve()
    case_metadata = Path(case_metadata).resolve()
    if out.is_relative_to(v5_run) or v5_run.is_relative_to(out):
        raise ProtocolError("v6 requires a separate run directory.")
    runtime = read_json(v5_run / "dev" / "config.json")["runtime"]
    old_config_path = Path(runtime["gateway_config"]).resolve()
    config = read_json(old_config_path)
    if not config["resident_control"] or not out.is_relative_to(Path(config["run_root"]).resolve()):
        raise ProtocolError("v6 must use the existing residents within the MedRAX experiment root.")

    trusted = out / "trusted"
    trusted.mkdir(parents=True, exist_ok=True, mode=0o700)
    config_path = trusted / "gateway.json"
    marker = trusted / "gateway.launched.json"
    wire = out / "v6g.sock"
    log = trusted / "gateway.log"
    entry = Path(__file__).resolve().parents[1] / "integration" / "native_gateway.py"
    with run_lock(trusted / "gateway.lock"):
        previous = read_json(marker) if marker.is_file() else None
        if previous and wire.is_socket() and _live_gateway(previous, entry, config_path):
            pid = previous["pid"]
            config = read_json(config_path)
        else:
            if wire.exists():
                with socket.socket(socket.AF_UNIX) as connection:
                    try:
                        connection.connect(str(wire))
                    except ConnectionRefusedError:
                        wire.unlink()
                    else:
                        raise ProtocolError(f"An untracked v6 gateway owns {wire}.")
            with socket.socket() as available:
                available.bind(("127.0.0.1", 0))
                port = available.getsockname()[1]
            config.update(
                listen_host="127.0.0.1", listen_port=port, public_url=f"http://127.0.0.1:{port}",
                control_socket=str(wire), audit_dir=str(out / "gateway_audit"), run_root=str(out),
            )
            validate_binding(config)
            write_json(config_path, config)
            pid = _start_gateway(entry, config_path, old_config_path, config, wire, log)
            write_json(marker, {
                "pid": pid, "control_socket": str(wire), "config": str(config_path),
                "gateway_url": config["public_url"], "resident_control": config["resident_control"],
                "log": str(log), "started_epoch": time.time(),
            })
        _smoke_roi(wire, config, trusted, sample_case, case_metadata, pid)
    return {
        "control_socket": str(wire), "gateway_url": config["public_url"],
        "gateway_config": str(config_path), "case_metadata": str(case_metadata),
    }
