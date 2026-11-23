from __future__ import annotations
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

class ProtocolError(RuntimeError):
    """Stop rather than silently changing the experiment protocol."""


def canonical(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(obj) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def file_hash(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, obj) -> None:
    """Atomic replace, fsync file and parent directory (POSIX)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=p.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(canonical(obj) + b"\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
        d = os.open(p.parent, os.O_RDONLY)
        try: os.fsync(d)
        finally: os.close(d)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def write_once(path, obj) -> None:
    p = Path(path)
    if p.exists():
        if read_json(p) != obj:
            raise ProtocolError(f"immutable record differs: {p}")
        return
    write_json(p, obj)


def tree_manifest(path) -> dict:
    root = Path(path).resolve()
    if not root.is_dir(): raise ProtocolError(f"missing directory: {root}")
    result = {}
    for p in sorted(root.rglob("*")):
        if p.is_symlink(): raise ProtocolError(f"symlink is not allowed in artifact tree: {p}")
        if p.is_file():
            result[str(p.relative_to(root))] = file_hash(p)
        elif not p.is_dir():
            raise ProtocolError(f"special file is not allowed: {p}")
    return result


def tree_hash(path) -> str:
    return digest(tree_manifest(path))


def copy_tree(src, dst) -> None:
    """Fresh independent bytes; never share writable DBs or follow symlinks."""
    tree_manifest(src)
    dst = Path(dst)
    if dst.exists(): shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        command(["cp", "--reflink=auto", "-a", str(Path(src).resolve()), str(dst.resolve())])
    else:
        shutil.copytree(src, dst, symlinks=False)


def command(argv, *, cwd=None, input_data=None, timeout=600, env=None):
    r = subprocess.run([str(x) for x in argv], cwd=cwd, input=input_data,
                       text=True, capture_output=True, timeout=timeout, env=env)
    if r.returncode:
        raise ProtocolError(f"command failed ({r.returncode}): {argv[0]}\n{r.stderr[-3000:]}")
    return r.stdout


def git(repo, *args):
    return command(["git", "-c", "user.name=M5 TTL", "-c", "user.email=m5-ttl@localhost", *args], cwd=repo).strip()


def code_export(repo, commit, out) -> Path:
    """Export only the committed editable harness, not repo, labels, or logs."""
    out = Path(out)
    marker = out.parent / (out.name + ".export.json")
    full = git(repo, "rev-parse", commit)
    if marker.exists():
        old = read_json(marker)
        if old["commit"] != full or tree_hash(out) != old["tree"]:
            raise ProtocolError("changed exported harness")
        return out
    import tarfile
    rel = "domains/med_m5/harness"
    out.mkdir(parents=True, exist_ok=True)
    tmp = out.parent / (out.name + ".tar")
    with open(tmp, "wb") as f:
        subprocess.run(["git", "archive", full, rel], cwd=repo, stdout=f, check=True)
    try:
        with tarfile.open(tmp) as tf:
            for m in tf.getmembers():
                if m.isdir(): continue
                if not m.isfile() or not m.name.startswith(rel + "/"):
                    raise ProtocolError("unsafe git archive member")
                name = m.name[len(rel) + 1:]
                p = out / name
                if ".." in Path(name).parts: raise ProtocolError("unsafe archive path")
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(tf.extractfile(m).read())
        write_json(marker, {"commit": full, "tree": tree_hash(out)})
    finally:
        tmp.unlink(missing_ok=True)
    return out


@contextlib.contextmanager
def run_lock(path):
    """One coordinator per run. Not a distributed lock."""
    import fcntl
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a+") as f:
        try: fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e: raise ProtocolError("another coordinator owns this run") from e
        try: yield
        finally: fcntl.flock(f.fileno(), fcntl.LOCK_UN)
