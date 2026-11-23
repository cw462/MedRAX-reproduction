"""Launch or inspect the four authorized Qwen3.7-Plus arms on Linux."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from uuid import uuid4

from .data import digest, read, write
from .native import DEEPSEEK_KEY, QWEN_KEY, native_paths
from .search import ARMS
from .workflow import config_file, native_binding


PLUS = {"plus": "qwen3.7-plus"}
PRIVATE_SLOTS = Path("/root/.config/medrax-autodl-r55/memory_resume.keys")


class Blocked(RuntimeError):
    """An unmet prerequisite safe to record."""


def now():
    return datetime.now(timezone.utc).isoformat()


def phases():
    yield "preflight", ["preflight"]
    yield "smoke", ["smoke", "--backbone", "plus"]
    for arm in ARMS:
        yield f"search.{arm}", ["search", "--backbone", "plus", "--arm", arm]
    yield "freeze", ["freeze"]
    for arm in ARMS:
        for phase in ("warmup", "evaluate"):
            yield f"{phase}.{arm}", [phase, "--backbone", "plus", "--arm", arm]
    yield "report", ["report"]


def credentials(env):
    qwen, memory = env.get(QWEN_KEY), env.get(DEEPSEEK_KEY)
    if not (qwen and memory):
        try:
            with PRIVATE_SLOTS.open("rb") as source:
                mode = os.fstat(source.fileno()).st_mode
                if not stat.S_ISREG(mode) or mode & 0o077:
                    raise Blocked("Existing R55 credentials must be in a private regular file")
                rows = source.read().splitlines()
        except OSError:
            raise Blocked("No inherited credential pair or readable R55 credential slots") from None
        if len(rows) != 2:
            raise Blocked("Existing R55 credential file does not contain two slots")
        try:
            saved_qwen, saved_memory = (slot.decode("ascii") for slot in rows)
        except UnicodeError:
            raise Blocked("Existing R55 credential slots have an invalid format") from None
        qwen, memory = qwen or saved_qwen, memory or saved_memory
    if (not qwen.startswith("sk-sp-") or not memory.startswith("sk-")
            or memory.startswith(("sk-sp-", "sk-ws-"))
            or any(char.isspace() for secret in (qwen, memory) for char in secret)):
        raise Blocked("Credential slots do not match the Qwen Token Plan and DeepSeek routes")
    return {QWEN_KEY: qwen, DEEPSEEK_KEY: memory}


def launcher_environment():
    return dict(os.environ, CUDA_VISIBLE_DEVICES="0", R55_MEMEVOLVE_GPU="0",
                R55_REQUIRE_CHEXAGENT8="1", OMP_NUM_THREADS="2", MKL_NUM_THREADS="2",
                PYTHONDONTWRITEBYTECODE="1", LANGCHAIN_TRACING_V2="false", LANGSMITH_TRACING="false")


def bind_runtime(config, env):
    paths = native_paths(native_binding(config, "plus"))
    template = read(paths["template"])
    snapshot = Path(template["runtime"]["backend_config"]["chexagent8_snapshot"])
    if not snapshot.is_dir():
        raise Blocked(f"Staged CheXagent-8B snapshot unavailable: {snapshot}")
    python_paths = {Path(config.get("native_python") or sys.executable)}
    python_paths.update(Path(tool["python"]) for tool in template["runtime"]["tools"].values() if tool.get("python"))
    missing = sorted(str(path) for path in python_paths if not path.is_file() or not os.access(path, os.X_OK))
    if missing:
        raise Blocked("Missing native Python executables: " + ", ".join(missing))
    env["R55_CHEXAGENT8_SNAPSHOT"] = str(snapshot)


def current(control):
    file = control / "controller.json"
    return read(file) if file.is_file() else {"status": "not_started"}


def lock_active(control):
    import fcntl

    try:
        with (control / "controller.lock").open("rb") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
    except FileNotFoundError:
        pass
    return False


def status(control):
    live = lock_active(control)
    value = current(control)
    if value["status"] in {"starting", "running"} and not live:
        value["status"] = "interrupted"
    value["lock_active"] = live
    value["model"] = PLUS["plus"]
    value["completed_phases"] = [name for name, _ in phases() if checkpoint(control, name).is_file()]
    return value


def checkpoint(control, phase):
    return control / "completed" / f"{phase}.json"


def write_state(control, state, **update):
    state = {**state, **update, "updated_at": now()}
    write(control / "controller.json", state)
    return state


def invoke(config, config_path, control, attempt, lock_fd, env, phase, args):
    folder = control / "attempts" / attempt / phase
    folder.mkdir(parents=True, exist_ok=True)
    stdout_path, stderr_path = folder / "stdout.log", folder / "stderr.log"
    receipt = {"phase": phase, "attempt": attempt, "started_at": now(),
               "stdout": str(stdout_path), "stderr": str(stderr_path)}
    write(folder / "started.json", receipt)
    cmd = [sys.executable, "-B", "-u", "-m", "experiments.m5_rsi", *args, "--config", str(config_path)]
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        result = subprocess.run(cmd, cwd=config["project_root"], env=env, stdin=subprocess.DEVNULL,
                                stdout=stdout, stderr=stderr, pass_fds=(lock_fd,), check=False)
    receipt.update(returncode=result.returncode, ended_at=now(),
                   status="complete" if result.returncode == 0 else "failed")
    write(folder / "exit.json", receipt)
    return receipt


def run(config, config_path, control, state, lock_fd):
    state = write_state(control, state, status="running", pid=os.getpid())
    claim = control / "execution_scope.json"
    scope = {"config_sha256": digest(config_path), "models": PLUS, "arms": list(ARMS)}
    if claim.is_file() and read(claim) != scope:
        raise Blocked("Staged configuration differs from the scope of the existing run")
    env = launcher_environment()
    env.update(credentials(env))
    for phase, args in phases():
        if phase != "preflight" and checkpoint(control, phase).is_file():
            continue
        state = write_state(control, state, phase=phase)
        receipt = invoke(config, config_path, control, state["attempt"], lock_fd, env, phase, args)
        if receipt["returncode"]:
            write_state(control, state, status="failed", phase_exit=receipt)
            return 1
        if phase == "preflight":
            preflight = read(Path(config["artifacts"]) / "preflight.json")
            if preflight["status"] != "preflight_passed_awaiting_live_smoke":
                write_state(control, state, status="blocked", phase_exit=receipt,
                            blockers=preflight.get("blockers", [preflight["status"]]))
                return 1
            bind_runtime(config, env)
            if not claim.is_file():
                write(claim, scope)
        write(checkpoint(control, phase), receipt)
    write_state(control, state, status="complete", phase="report")
    return 0


def run_recorded(config, config_path, control, state, lock_fd):
    try:
        return run(config, config_path, control, state, lock_fd)
    except Blocked as exc:
        write_state(control, current(control), status="blocked", blockers=[str(exc)])
        return 1
    except (Exception, KeyboardInterrupt) as exc:
        write_state(control, current(control), status="failed", error_type=type(exc).__name__)
        raise


def begin(config, config_path, control, requested, resume, lock_fd):
    previous = current(control)["status"]
    if previous == "complete":
        return current(control), 0
    if previous != "not_started" and not resume:
        return {**current(control), "next": "Inspect the last phase before restarting with --resume"}, 1
    state = write_state(control, {"attempt": uuid4().hex, "started_at": now(), "models": PLUS},
                        status="starting", phase="preflight")
    if requested == "run":
        code = run_recorded(config, config_path, control, state, lock_fd)
        return current(control), code
    log = control / "attempts" / state["attempt"] / "launcher.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-B", "-u", "-m", "experiments.m5_rsi.run_plus", "run",
           "--config", str(config_path), "--_lock-fd", str(lock_fd)]
    with log.open("wb") as stdout:
        try:
            child = subprocess.Popen(cmd, cwd=config["project_root"], stdin=subprocess.DEVNULL,
                                     stdout=stdout, stderr=subprocess.STDOUT, start_new_session=True,
                                     pass_fds=(lock_fd,))
        except OSError as exc:
            write_state(control, state, status="failed", error_type=type(exc).__name__)
            raise
    return {**state, "pid": child.pid, "launcher_log": str(log)}, 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "start", "run"))
    parser.add_argument("--config", type=Path, default=Path("configs/m5_rsi.yaml"))
    parser.add_argument("--resume", action="store_true", help="Continue after inspecting the prior attempt")
    parser.add_argument("--_lock-fd", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    config_path = args.config.resolve(strict=True)
    config = config_file(config_path)
    if config["models"] != PLUS:
        parser.error("This controller requires an active matrix containing only qwen3.7-plus")
    import fcntl

    control = Path(config["artifacts"]).resolve() / "control" / "plus"
    if args.command == "status":
        print(json.dumps(status(control)))
        return 0
    control.mkdir(parents=True, exist_ok=True)
    lock_path = control / "controller.lock"
    if args._lock_fd is not None:
        if args.command != "run" or not os.path.samestat(os.fstat(args._lock_fd), lock_path.stat()):
            parser.error("Invalid detached launcher lock")
        with os.fdopen(args._lock_fd, "rb") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            state = current(control)
            if state["status"] != "starting":
                parser.error("Missing detached launcher start record")
            code = run_recorded(config, config_path, control, state, handle.fileno())
            print(json.dumps(current(control)))
            return code
    with lock_path.open("a+b") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"status": "already_running", "control": str(control)}))
            return 0
        result, code = begin(config, config_path, control, args.command, args.resume, handle.fileno())
        print(json.dumps(result))
        return code


if __name__ == "__main__":
    raise SystemExit(main())
