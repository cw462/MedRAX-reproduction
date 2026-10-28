"""Private stdio bridge for isolated real MedRAX tool workers; no HTTP service.

The bridge does not implement medical predictions. It transports unchanged
Python JSON-compatible result values (including tuple/list distinction), and
raises real execution errors when a child cannot return an audited result.
Exactly one large-model worker may be active per pool/GPU lock.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
import uuid

PROTOCOL = 1
MAX_LINE = 8 * 1024 * 1024
KINDS = {"llava": "llava_med_qa", "maira": "xray_phrase_grounding", "chexagent": "chest_xray_expert"}
REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{1,120}\Z")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _constant(value):
    raise ValueError("Nonfinite JSON number is forbidden")


def parse_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError("Duplicate JSON object key")
            result[key] = value
        return result
    return json.loads(raw, parse_constant=_constant, object_pairs_hook=pairs)


def encode_value(value, depth=0):
    """Tagged tree prevents tuple/list drift and sentinel-key collisions."""
    if depth > 32:
        raise ValueError("Transport nesting is too deep")
    if value is None: return ["null", None]
    if type(value) is bool: return ["bool", value]
    if type(value) is int: return ["int", value]
    if type(value) is float:
        if not math.isfinite(value): raise ValueError("Nonfinite output cannot be transported")
        return ["float", value]
    if type(value) is str: return ["str", value]
    if type(value) in (list, tuple):
        return ["tuple" if type(value) is tuple else "list", [encode_value(x, depth + 1) for x in value]]
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise ValueError("Only string dictionary keys are supported")
        return ["dict", [[key, encode_value(item, depth + 1)] for key, item in value.items()]]
    raise ValueError("Unsupported tool return type; no lossy coercion is permitted")


def decode_value(node, depth=0):
    if depth > 32 or type(node) is not list or len(node) != 2 or type(node[0]) is not str:
        raise ValueError("Invalid typed transport node")
    kind, value = node
    types = {"null": type(None), "bool": bool, "int": int, "float": float, "str": str}
    if kind in types:
        if type(value) is not types[kind] or (kind == "float" and not math.isfinite(value)):
            raise ValueError("Typed scalar does not match its declared type")
        return value
    if kind in ("list", "tuple"):
        if type(value) is not list: raise ValueError("Invalid sequence node")
        items = [decode_value(x, depth + 1) for x in value]
        return tuple(items) if kind == "tuple" else items
    if kind == "dict":
        if type(value) is not list: raise ValueError("Invalid mapping node")
        result = {}
        for pair in value:
            if type(pair) is not list or len(pair) != 2 or type(pair[0]) is not str or pair[0] in result:
                raise ValueError("Invalid or duplicate dictionary key")
            result[pair[0]] = decode_value(pair[1], depth + 1)
        return result
    raise ValueError("Unknown transport node type")


def write_private(path, value, *, exclusive=True):
    raw = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode() + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
    fd = os.open(Path(path), flags, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw); handle.flush(); os.fsync(handle.fileno())


class WorkerFailure(RuntimeError):
    def __init__(self, category, details=None):
        self.category = category
        self.details = details or {}
        super().__init__("Real tool worker failed: " + category)


class _GpuLock:
    def __init__(self, path):
        self.path, self.handle = Path(path).resolve(), None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                if not handle.read(1): handle.write(b"0"); handle.flush()
                handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            raise WorkerFailure("gpu_slot_already_locked") from None
        self.handle = handle

    def close(self):
        if self.handle is None: return
        try:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0); msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close(); self.handle = None


@dataclass(frozen=True)
class WorkerSpec:
    kind: str
    python: str
    repo: str
    cache_dir: str | None = None
    snapshot: str | None = None
    vision_snapshot: str | None = None
    asset_manifest: str | None = None

    def validate(self):
        if self.kind not in KINDS or not Path(self.python).is_file() or not Path(self.repo).is_dir():
            raise ValueError("Invalid worker kind/interpreter/official checkout")
        needed = (self.snapshot, self.vision_snapshot, self.asset_manifest) if self.kind == "chexagent" else (self.cache_dir,)
        if any(type(value) is not str or not Path(value).exists() for value in needed):
            raise ValueError("Required local worker assets are missing")


def validate_cases(cases):
    if type(cases) is not dict or not cases:
        raise ValueError("A nonempty frozen case-image allowlist is required")
    clean = {}
    for case, images in cases.items():
        if type(case) is not str or not case or type(images) is not dict or not images:
            raise ValueError("Invalid case image allowlist")
        clean[case] = {}
        for image, sha in images.items():
            path = str(Path(image).resolve())
            if type(image) is not str or type(sha) is not str or not re.fullmatch(r"[0-9a-f]{64}", sha):
                raise ValueError("Images require a pre-recorded SHA256")
            if path in clean[case]: raise ValueError("Duplicate canonical image path")
            clean[case][path] = sha
    return clean


def validate_request(kind, params, allowed):
    """Enforce tool policy before any ML work; no labels or extra fields accepted."""
    if kind not in KINDS or type(params) is not dict or type(allowed) is not dict:
        raise ValueError("Invalid tool request")
    required = {"image_paths", "prompt"} if kind == "chexagent" else {"image_path", "question" if kind == "llava" else "phrase"}
    optional = set() if kind == "llava" else {"max_new_tokens"}
    if not required <= set(params) or not set(params) <= required | optional:
        raise ValueError("Missing or extra tool arguments")
    text_key = "prompt" if kind == "chexagent" else "question" if kind == "llava" else "phrase"
    text = params[text_key]
    if (type(text) is not str or not text.strip() or len(text) > (512 if kind == "chexagent" else 4096) or "\x00" in text or
            any(tag in text.lower() for tag in ("<|", "|>", "<image", "<img", "</img", "[img]"))):
        raise ValueError("Invalid text or image/control-token injection")
    # Images are read only through explicit, case-authorized path fields.
    paths = params["image_paths"] if kind == "chexagent" else [params["image_path"]]
    if type(paths) is not list or not paths or any(type(path) is not str for path in paths):
        raise ValueError("Invalid image paths")
    # First bridge deliberately retains the audited single-image CheXagent smoke.
    if kind == "chexagent" and len(paths) != 1:
        raise ValueError("This bridge's CheXagent adapter is audited for one image only")
    resolved = [str(Path(path).resolve()) for path in paths]
    if len(set(resolved)) != len(resolved): raise ValueError("Repeated image path")
    for path in resolved:
        if path not in allowed or not Path(path).is_file() or file_digest(path) != allowed[path]:
            raise ValueError("Image is not a byte-verified member of the current case")
    if kind != "llava":
        limit = 512 if kind == "chexagent" else 300
        value = params.get("max_new_tokens", limit)
        if type(value) is not int or not 1 <= value <= limit:
            raise ValueError("Tool output token limit is outside the frozen execution policy")
        # Current MAIRA audit instruments exactly the original default 300.
        if kind == "maira" and value != 300:
            raise ValueError("This MAIRA variant retains the original 300-token setting")
    result = dict(params)
    result["image_paths" if kind == "chexagent" else "image_path"] = resolved if kind == "chexagent" else resolved[0]
    return result, resolved


def _child_environment(gpu):
    names = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "LANG", "LC_ALL",
             "LD_LIBRARY_PATH", "CUDA_HOME", "CUDA_PATH", "CONDA_PREFIX", "VIRTUAL_ENV"}
    env = {key: value for key, value in os.environ.items() if key.upper() in names}
    env.update(CUDA_VISIBLE_DEVICES=str(gpu), PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1",
               HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", MPLBACKEND="Agg")
    return env


class _Child:
    def __init__(self, argv, *, env, stderr, timeout):
        self.stderr = Path(stderr).open("xb")
        kwargs = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "stderr": self.stderr,
                  "env": env, "shell": False, "close_fds": True}
        if os.name == "nt": kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            self.process = subprocess.Popen(argv, **kwargs)
        except Exception:
            self.stderr.close(); raise
        self.incoming = queue.Queue()
        def reader():
            try:
                while True:
                    raw = self.process.stdout.readline(MAX_LINE + 1)
                    self.incoming.put(raw)
                    if not raw or len(raw) > MAX_LINE: break
            except Exception:
                self.incoming.put(None)
        self.reader = threading.Thread(target=reader, daemon=True); self.reader.start()
        self.timeout = timeout

    def send(self, value):
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode() + b"\n"
        if len(raw) > MAX_LINE: raise WorkerFailure("request_too_large")
        try:
            self.process.stdin.write(raw); self.process.stdin.flush()
        except (BrokenPipeError, OSError):
            raise WorkerFailure("child_death", {"returncode": self.process.poll()}) from None

    def receive(self, timeout=None):
        try:
            raw = self.incoming.get(timeout=self.timeout if timeout is None else timeout)
        except queue.Empty:
            raise WorkerFailure("timeout") from None
        if not raw: raise WorkerFailure("child_death", {"returncode": self.process.poll()})
        if len(raw) > MAX_LINE or not raw.endswith(b"\n"):
            raise WorkerFailure("response_too_large_or_unframed")
        try:
            parsed = parse_json(raw.decode("utf-8"))
        except (ValueError, UnicodeError):
            raise WorkerFailure("invalid_json_transport") from None
        if type(parsed) is not dict or parsed.get("protocol") != PROTOCOL:
            raise WorkerFailure("invalid_protocol")
        return parsed

    def close(self, *, graceful=True, timeout=10):
        forced = False
        if self.process.poll() is None and graceful:
            try: self.send({"protocol": PROTOCOL, "op": "shutdown"})
            except WorkerFailure: pass
        if self.process.poll() is None:
            try: self.process.wait(timeout=timeout if graceful else 0.01)
            except subprocess.TimeoutExpired:
                forced = True; self.process.terminate()
                try: self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill(); self.process.wait(timeout=5)
        result = {"pid": self.process.pid, "returncode": self.process.returncode,
                  "exited_before_replacement": self.process.poll() is not None, "forced": forced}
        for stream in (self.process.stdin, self.process.stdout):
            try: stream.close()
            except OSError: pass
        self.stderr.close()
        return result


class WorkerPool:
    """One large model active; calls are serial and never automatically retried."""
    def __init__(self, specs, *, cases, run_root, gpu_lock, gpu="1", timeout=600, startup_timeout=120,
                 worker_script=None):
        self.specs = {KINDS[spec.kind]: spec for spec in specs}
        if len(self.specs) != len(specs) or not self.specs: raise ValueError("Distinct worker specs required")
        for spec in specs: spec.validate()
        self.cases = validate_cases(cases)
        self.root = Path(run_root).resolve(); self.root.mkdir(mode=0o700, parents=True, exist_ok=False)
        (self.root / ".gitignore").write_text("*\n", encoding="utf-8")
        self.script = Path(worker_script or Path(__file__).with_name("medical_tool_worker.py")).resolve()
        if not self.script.is_file(): raise ValueError("Worker script is missing")
        self.timeout, self.startup_timeout, self.gpu = timeout, startup_timeout, str(gpu)
        self.lock = _GpuLock(gpu_lock); self.lock.acquire()
        self.active, self.active_name, self.active_descriptor = None, None, None
        self.descriptors, self.lifecycle, self.case_id = {}, [], None
        self.closed, self.busy = False, threading.Lock()
        self.source_sha256 = file_digest(self.script)
        self.bridge_sha256 = file_digest(__file__)

    def __enter__(self): return self
    def __exit__(self, *args): self.close()

    def policy_snapshot(self):
        """Immutable path-free restrictions to freeze in the experiment manifest."""
        return {"protocol": PROTOCOL, "worker_script_sha256": self.source_sha256,
                "bridge_sha256": self.bridge_sha256, "case_image_allowlist_sha256": digest(self.cases),
                "tool_names": sorted(self.specs), "visible_gpu_slot": self.gpu,
                "source_hash_policy": "record_only",
                "one_active_large_worker": True, "automatic_retries": False,
                "startup_timeout_seconds": self.startup_timeout, "call_timeout_seconds": self.timeout,
                "max_protocol_line_bytes": MAX_LINE, "parent_and_child_image_hash_checks": True,
                "original_schema_preserved": True, "execution_policy_stricter_than_original_schema": True,
                "llava": {"explicit_image_required": True, "max_new_tokens": 500, "max_question_characters": 4096},
                "maira": {"sync_only": True, "max_new_tokens_exact": 300, "reject_constant_grayscale": True,
                          "max_phrase_characters": 4096},
                "chexagent": {"single_image_only": True, "max_new_tokens_range": [1, 512],
                              "max_prompt_characters": 512, "reloads_each_call": True},
                "control_tag_text_rejected": True, "private_journals_contain_raw_tool_results": True}

    def set_case(self, case_id):
        if not self.busy.acquire(blocking=False): raise WorkerFailure("case_change_during_call")
        try:
            if case_id not in self.cases: raise ValueError("Case is outside the frozen image allowlist")
            self.case_id = case_id
        finally:
            self.busy.release()

    def _launch(self, name, *, describe):
        if self.closed: raise WorkerFailure("pool_closed")
        # Hashes identify the source used for this launch; they are not immutable gates.
        self.source_sha256 = file_digest(self.script)
        self.bridge_sha256 = file_digest(__file__)
        spec = self.specs[name]
        folder = self.root / ("worker_" + uuid.uuid4().hex); folder.mkdir(mode=0o700)
        config = {"protocol": PROTOCOL, "spec": asdict(spec), "cases": self.cases,
                  "cases_sha256": digest(self.cases), "private_root": str(folder),
                  "worker_script_sha256": self.source_sha256, "bridge_sha256": self.bridge_sha256}
        path = folder / "config.private.json"; write_private(path, config)
        argv = [spec.python, "-B", str(self.script), "--config", str(path), "--config-sha256", file_digest(path)]
        if describe: argv.append("--describe")
        child = _Child(argv, env=_child_environment("" if describe else self.gpu),
                       stderr=folder / "stderr.private.log", timeout=self.timeout)
        try:
            ready = child.receive(self.startup_timeout)
            if (ready.get("event") != "ready" or ready.get("tool_name") != name or
                    ready.get("cases_sha256") != digest(self.cases) or type(ready.get("descriptor")) is not dict):
                raise WorkerFailure("invalid_ready_handshake")
            self.source_sha256 = ready.get("worker_script_sha256", self.source_sha256)
            desc = ready["descriptor"]
            if (desc.get("name") != name or type(desc.get("description")) is not str or
                    type(desc.get("parameters")) is not dict or desc.get("schema_sha256") != digest(desc["parameters"])):
                raise WorkerFailure("invalid_official_schema_descriptor")
            capability_fields = ("name", "description", "parameters", "return_direct")
            if name in self.descriptors and any(self.descriptors[name].get(key) != desc.get(key) for key in capability_fields):
                raise WorkerFailure("official_capabilities_changed")
            self.descriptors[name] = desc
            return child, desc
        except Exception:
            self.lifecycle.append(child.close(graceful=False)); raise

    def describe(self, name):
        if name not in self.specs: raise ValueError("Unknown tool")
        if name not in self.descriptors:
            child, descriptor = self._launch(name, describe=True)
            self.lifecycle.append(child.close(graceful=False))
        return dict(self.descriptors[name])

    def _stop_active(self, *, graceful=True):
        if self.active is not None:
            self.lifecycle.append(self.active.close(graceful=graceful))
        self.active, self.active_name, self.active_descriptor = None, None, None

    def invoke(self, name, params, *, request_id=None):
        if not self.busy.acquire(blocking=False): raise WorkerFailure("parallel_large_model_call_denied")
        started = time.monotonic()
        request_id = request_id or uuid.uuid4().hex
        sent, journal = False, None
        try:
            if self.closed or name not in self.specs or self.case_id not in self.cases:
                raise WorkerFailure("inactive_or_unscoped_tool")
            if type(request_id) is not str or not REQUEST_ID.fullmatch(request_id):
                raise ValueError("Invalid logical tool request ID")
            clean, images = validate_request(self.specs[name].kind, params, self.cases[self.case_id])
            request = {"protocol": PROTOCOL, "op": "invoke", "request_id": request_id,
                       "case_id": self.case_id, "tool_name": name, "params": clean,
                       "params_sha256": digest(clean), "case_images_sha256": digest(self.cases[self.case_id])}
            # Durable request intent before startup/inference; duplicate IDs never rerun.
            journal = self.root / ("request_" + request_id + ".private.json")
            try: write_private(journal, {"status": "intent", "request": request})
            except FileExistsError: raise WorkerFailure("duplicate_request_id") from None
            if self.active_name != name or self.active is None or self.active.process.poll() is not None:
                self._stop_active()
                self.active, self.active_descriptor = self._launch(name, describe=False)
                self.active_name = name
            sent = True
            self.active.send(request)
            response = self.active.receive()
            if response.get("request_id") != request_id or response.get("tool_name") != name or response.get("params_sha256") != request["params_sha256"]:
                raise WorkerFailure("response_identity_mismatch")
            if response.get("event") == "error":
                error = response.get("error_type")
                if type(error) is not str or not re.fullmatch(r"[A-Za-z0-9_]{1,80}", error): error = "UntrustedErrorType"
                raise WorkerFailure("worker_execution_error", {"error_type": error})
            if response.get("event") != "result" or type(response.get("audit")) is not dict:
                raise WorkerFailure("invalid_result_envelope")
            if response.get("result_sha256") != digest(response.get("result_tree")):
                raise WorkerFailure("result_digest_mismatch")
            result = decode_value(response["result_tree"])
            # Transport does not summarize or replace failed original tool returns.
            write_private(self.root / ("result_" + request_id + ".private.json"), response)
            safe = {"request_id": request_id, "tool_name": name, "params_sha256": request["params_sha256"],
                    "result_sha256": response["result_sha256"], "image_sha256": [self.cases[self.case_id][p] for p in images],
                    "worker_audit": response["audit"], "transport_seconds": time.monotonic() - started,
                    "clinical_evidence": "unknown", "step_credit": None, "raw_content_logged": False,
                    "raw_content_logged_scope": "safe_audit_only", "private_result_journal_contains_raw_content": True}
            if self.specs[name].kind == "chexagent": self._stop_active()
            return result, safe
        except Exception as exc:
            # An interrupted request is unknown, never silently replayed.
            self._stop_active(graceful=False)
            if journal is not None and journal.exists():
                failure_path = self.root / ("failure_" + request_id + "_" + uuid.uuid4().hex + ".private.json")
                write_private(failure_path, {"request_id": request_id, "category":
                    exc.category if isinstance(exc, WorkerFailure) else "request_validation_or_transport_failure",
                    "error_type": type(exc).__name__, "execution_may_have_started": sent,
                    "elapsed_seconds": time.monotonic() - started, "automatically_retried": False})
            if isinstance(exc, WorkerFailure): raise
            raise WorkerFailure("request_validation_or_transport_failure", {"error_type": type(exc).__name__}) from None
        finally:
            self.busy.release()

    def close(self):
        if self.closed: return
        self._stop_active(); self.lock.close(); self.closed = True
        write_private(self.root / "lifecycle.private.json", self.lifecycle)


def official_function_schema(descriptor):
    """Use directly with model.bind_tools; schema is the worker's official JSON."""
    return {"type": "function", "function": {"name": descriptor["name"],
        "description": descriptor["description"], "parameters": descriptor["parameters"]}}


def make_proxy(pool, name):
    """Build a BaseTool whose schema is checked against the official worker class.

    The simple input types cover these three official tools. No general schema
    interpretation or model output coercion is attempted. The pool must be
    scoped with set_case() by the trusted caller before invoke.
    """
    from typing import List, Optional
    from pydantic import BaseModel, Field, PrivateAttr, create_model
    from langchain_core.tools import BaseTool
    descriptor = pool.describe(name)
    schema = descriptor["parameters"]
    if set(schema) - {"title", "description", "properties", "required", "type"} or schema.get("type") != "object":
        raise ValueError("Unsupported official input schema shape")
    def annotation(node):
        if "anyOf" in node:
            nonnull = [part for part in node["anyOf"] if part != {"type": "null"}]
            if len(nonnull) != 1 or len(node["anyOf"]) != 2: raise ValueError("Unsupported optional schema")
            return Optional[annotation(nonnull[0])]
        if node.get("type") == "string": return str
        if node.get("type") == "integer": return int
        if node.get("type") == "array" and node.get("items") == {"type": "string"}: return List[str]
        raise ValueError("Unsupported official field type")
    fields = {}
    for key, item in schema["properties"].items():
        if set(item) - {"title", "description", "type", "items", "anyOf", "default"}:
            raise ValueError("Unsupported official field validation")
        default = ... if key in schema.get("required", []) else item.get("default", None)
        fields[key] = (annotation(item), Field(default, title=item.get("title"), description=item.get("description")))
    inputs = create_model(schema.get("title", "OfficialWorkerInput"), __base__=BaseModel,
                          __doc__=schema.get("description"), **fields)
    if digest(inputs.model_json_schema()) != descriptor["schema_sha256"]:
        raise ValueError("Main-process Pydantic schema differs from the official worker schema")
    class Proxy(BaseTool):
        _pool: object = PrivateAttr()
        _last_audit: object = PrivateAttr(default=None)

        def __init__(self):
            super().__init__(name=descriptor["name"], description=descriptor["description"], args_schema=inputs,
                             return_direct=descriptor.get("return_direct", False))
            self._pool = pool

        def _run(self, **params):
            self._last_audit = None
            result, self._last_audit = self._pool.invoke(self.name, params)
            return result

        def invoke(self, input, config=None, **kwargs):
            # BaseTool's ordinary Pydantic parsing may drop extra keys or coerce
            # booleans into ints. Validate the raw requested arguments first.
            self._last_audit = None
            if type(input) is not dict or kwargs:
                raise WorkerFailure("invalid_proxy_invoke_arguments")
            return self._run(**input)

        @property
        def last_worker_audit(self): return self._last_audit

        async def _arun(self, **params):
            raise WorkerFailure("synchronous_worker_invocation_required")
    proxy = Proxy()
    if digest(proxy.args_schema.model_json_schema()) != descriptor["schema_sha256"]:
        raise ValueError("Proxy schema drift")
    return proxy
