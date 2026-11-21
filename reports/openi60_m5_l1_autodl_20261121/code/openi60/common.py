from __future__ import annotations
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

class ExperimentError(RuntimeError):
    pass

def require(condition: bool, message: str) -> None:
    if not condition:
        raise ExperimentError(message)

def read_json(path: Path) -> Any:
    with Path(path).open(encoding="utf-8-sig") as stream:
        return json.load(stream)

def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)

def object_hash(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def write_once(path: Path, value: Any) -> None:
    """Atomic, immutable JSON, including protection against concurrent publishers."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(read_json(path) == value, f"Immutable file differs: {path}")
        return
    fd, name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        try:
            os.link(tmp, path)
        except FileExistsError:
            require(read_json(path) == value, f"Concurrent immutable file differs: {path}")
    finally:
        tmp.unlink(missing_ok=True)

def write_text_once(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)

def safe_qid(value: Any) -> str:
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.-]+", value) is not None
            and value not in {".", ".."}, f"Unsafe question id: {value!r}")
    return value

def relative_path(value: str) -> Path:
    require(isinstance(value, str), "Image path must be text")
    p = Path(value.replace("\\", "/"))
    require(not p.is_absolute() and ".." not in p.parts and ":" not in str(p)
            and str(p) not in {".", ""}, f"Unsafe relative path: {value}")
    return p

def resolve_path(value: str, base: Path) -> Path:
    p = Path(os.path.expandvars(value)).expanduser()
    require("${" not in str(p), f"Unexpanded environment variable in path: {value}")
    return (p if p.is_absolute() else base / p).resolve()
