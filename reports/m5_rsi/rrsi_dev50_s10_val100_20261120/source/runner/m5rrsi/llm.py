"""Drop-in rrsi.llm.generate via a Qwen-compatible chat-completions endpoint.
No provider SDK; no hard-coded credentials; no silent alternate model.
"""
from __future__ import annotations
import copy
import json
import os
import threading
import time
import urllib.request
import urllib.error
from pathlib import Path
from .io import ProtocolError, digest

_CONFIG = {}
_LOCK = threading.Lock()

def configure(config, log_path):
    global _CONFIG
    with _LOCK:
        _CONFIG = {**copy.deepcopy(config), "log_path": str(log_path)}


def extract_json(text):
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines(); t = "\n".join(lines[1:-1]).strip()
    # Reject unparseable output; the official proposer can request a correction.
    try: return json.dumps(json.loads(t), ensure_ascii=False)
    except json.JSONDecodeError: return t


def _audit(rec, config):
    p = Path(config["log_path"]); p.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK, p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def generate(prompt, system=None, max_retries=6, json_only=False, model=None,
             max_tokens=20000, cache_prefix=None):
    with _LOCK:
        config = copy.deepcopy(_CONFIG)
    if not config: raise ProtocolError("search client was not configured")
    key = os.environ.get(config["api_key_env"], "")
    base = os.environ.get(config["base_url_env"], "").rstrip("/")
    if not key or not base: raise ProtocolError("missing Qwen credentials/base URL environment")
    if not base.startswith("https://") and not config.get("allow_http_local", False):
        raise ProtocolError("search endpoint must use HTTPS")
    mdl = model or config["model"]
    if mdl != config["model"]: raise ProtocolError("unregistered search model")
    sys = (system or "") + ("\nReturn exactly one valid JSON object, without markdown." if json_only else "")
    text = (cache_prefix + "\n\n" if cache_prefix else "") + prompt
    body = {"model": mdl, "messages": [{"role": "system", "content": sys},
                                          {"role": "user", "content": text}],
            "temperature": config.get("temperature", 0),
            "max_tokens": min(max_tokens, config["max_tokens"]),
            **config.get("extra_body", {})}
    if body["model"] != mdl or body["messages"][1]["content"] != text:
        raise ProtocolError("extra_body must not override model/messages")
    n = min(max_retries, config.get("retries", 3))
    for attempt in range(n):
        start = time.monotonic()
        req = urllib.request.Request(base + "/chat/completions", data=json.dumps(body).encode(),
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=config.get("timeout_seconds", 180)) as r:
                data = json.load(r)
            choice = data["choices"][0]
            answer = choice["message"].get("content")
            usage = data.get("usage")
            _audit({"event": "search_call", "model_requested": mdl, "model_returned": data.get("model"),
                    "request_hash": digest(body), "usage": usage,
                    "finish_reason": choice.get("finish_reason"), "seconds": time.monotonic() - start}, config)
            if not isinstance(answer, str) or not answer.strip(): raise ProtocolError("empty search response")
            if not isinstance(usage, dict) or "total_tokens" not in usage:
                raise ProtocolError("usage missing; stop rather than claiming zero search cost")
            return extract_json(answer) if json_only else answer
        except urllib.error.HTTPError as e:
            _audit({"event": "search_http_error", "status": e.code, "attempt": attempt}, config)
            if e.code not in (429, 500, 502, 503, 504) or attempt + 1 == n: raise
        except (urllib.error.URLError, TimeoutError) as e:
            _audit({"event": "search_transport_error", "type": type(e).__name__, "attempt": attempt}, config)
            if attempt + 1 == n: raise
        time.sleep(min(2 ** attempt, 8))
    raise ProtocolError("search retries exhausted")
