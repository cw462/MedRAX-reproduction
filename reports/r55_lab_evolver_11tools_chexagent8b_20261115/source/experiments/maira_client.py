"""Client side of the MAIRA-2 worker (runs in the main Agent environment).

Spawns `.venv-maira/bin/python maira_worker_server.py` once, loads the model once,
and forwards each grounding call over stdin/stdout JSONL. The main process never
loads MAIRA weights, so the two transformers versions cannot collide.

Failure handling is deliberately strict: a timeout, a dead child or a malformed
line raises `MairaWorkerError`. It is never converted into a medical answer, and
there is no silent retry - a failed call stays failed in the trace.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


class MairaWorkerError(RuntimeError):
    pass


class MairaClient:
    def __init__(self, python_executable, repo, model_path, cache_dir=None,
                 temp_dir=None, device="cuda", startup_timeout=300.0, call_timeout=180.0,
                 log_path=None):
        self.repo = Path(repo)
        self.python_executable = str(python_executable)
        self.model_path = str(model_path)
        self.cache_dir = str(cache_dir) if cache_dir else None
        self.temp_dir = str(temp_dir) if temp_dir else None
        self.device = device
        self.startup_timeout = startup_timeout
        self.call_timeout = call_timeout
        self.log_path = str(log_path) if log_path else os.devnull
        self._process = None
        self._describe = {}

    # --- process lifecycle ------------------------------------------------
    def start(self):
        if self._process is not None and self._process.poll() is None:
            return self._describe
        env = dict(os.environ)
        env["MEDRAX_REPO"] = str(self.repo)
        env["MAIRA_WORKER_LOG"] = self.log_path
        env.setdefault("HF_HUB_OFFLINE", "1")
        env.setdefault("TOKENIZERS_PARALLELISM", "false")
        self._process = subprocess.Popen(
            [self.python_executable, str(HERE / "maira_worker_server.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, cwd=str(HERE), env=env)
        info = self._request({"cmd": "load", "model_path": self.model_path,
                              "cache_dir": self.cache_dir, "temp_dir": self.temp_dir,
                              "device": self.device}, timeout=self.startup_timeout)
        self._describe = {"tool_version": info.get("tool_version"),
                          "model_dtype": info.get("model_dtype"),
                          "vram_gib": info.get("vram_gib")}
        return self._describe

    def stop(self):
        if self._process is None:
            return
        try:
            if self._process.poll() is None:
                self._process.stdin.write(json.dumps({"cmd": "shutdown"}) + "\n")
                self._process.stdin.flush()
                self._process.wait(timeout=15)
        except Exception:
            pass
        finally:
            if self._process.poll() is None:
                self._process.kill()
            self._process = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()

    # --- protocol ---------------------------------------------------------
    def _request(self, payload, timeout):
        if self._process is None or self._process.poll() is not None:
            raise MairaWorkerError("worker process is not running")
        try:
            self._process.stdin.write(json.dumps(payload) + "\n")
            self._process.stdin.flush()
        except (BrokenPipeError, ValueError) as error:
            raise MairaWorkerError(f"worker pipe closed: {error}") from error
        line = self._readline(timeout)
        try:
            reply = json.loads(line)
        except json.JSONDecodeError as error:
            raise MairaWorkerError(f"worker sent a non-JSON line: {line[:120]!r}") from error
        if not reply.get("ok"):
            tail = (reply.get("traceback") or "").strip().splitlines()
            detail = tail[-1] if tail else ""
            raise MairaWorkerError(f"{reply.get('error')} {detail}".strip())
        return reply

    def _readline(self, timeout):
        """Blocking read with a deadline; raises instead of hanging forever."""
        deadline = time.monotonic() + timeout
        process = self._process
        while True:
            if process.poll() is not None:
                err = process.stderr.read()[-800:] if process.stderr else ""
                raise MairaWorkerError(f"worker exited early: {err}")
            line = process.stdout.readline()
            if line:
                return line.strip()
            if time.monotonic() > deadline:
                raise MairaWorkerError(f"worker timed out after {timeout:.0f}s")
            time.sleep(0.05)

    # --- public API -------------------------------------------------------
    def describe(self):
        return dict(self._describe)

    def ground(self, image_path, phrase, max_new_tokens=300):
        reply = self._request({"cmd": "ground", "image_path": str(image_path),
                               "phrase": str(phrase), "max_new_tokens": int(max_new_tokens)},
                              timeout=self.call_timeout)
        return reply["result"]
