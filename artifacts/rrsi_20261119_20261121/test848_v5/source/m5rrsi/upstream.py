"""Load and verify actual google-research/rrsi. No substitute implementation.
The server installer resolves a full commit and freezes every core file hash.
"""
from __future__ import annotations
import ast
import importlib
import inspect
import sys
from pathlib import Path
from .io import ProtocolError, file_hash, read_json, git, tree_manifest

REQUIRED = {
    "rrsi/loop.py": {"Run": {"__init__", "round", "frontier", "save_frontier", "checkout"}},
    "rrsi/config.py": {"RRSIConfig": {"dump"}},
    "rrsi/evaluate.py": {"EvalResult": {"save", "load"}, "TaskResult": set()},
    "rrsi/history.py": {"History": {"records", "render", "has", "append_candidate"}},
    "rrsi/propose.py": {"Workspace": {"read", "edit", "write", "_safe"}},
}


def source_contract(repo):
    repo = Path(repo)
    for filename, classes in REQUIRED.items():
        tree = ast.parse((repo / filename).read_text())
        found = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
        for cls, methods in classes.items():
            if cls not in found: raise ProtocolError(f"upstream API changed: missing {cls}")
            have = {n.name for n in found[cls].body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            if not methods <= have: raise ProtocolError(f"upstream API changed: {cls} methods")
    for name in ("analyst", "critic", "components", "digester", "gitops", "schedule", "selection", "llm", "calibrate"):
        if not (repo / "rrsi" / (name + ".py")).is_file(): raise ProtocolError("incomplete official checkout")


def verify_lock(repo, lock_path):
    repo = Path(repo).resolve(); lock = read_json(lock_path)
    if lock["repository"] != "https://github.com/google-research/rrsi.git":
        raise ProtocolError("unrecognized upstream repository")
    git(repo, "cat-file", "-e", lock["commit"] + "^{commit}")
    for rel, h in lock["core_sha256"].items():
        if file_hash(repo / rel) != h: raise ProtocolError(f"frozen upstream core changed: {rel}")
    actual = {str(p.relative_to(repo)) for p in (repo / "rrsi").rglob("*.py")}
    if actual != set(lock["core_sha256"]): raise ProtocolError("unexpected/missing rrsi core file")
    source_contract(repo)
    return lock


def load(repo, lock_path):
    repo = Path(repo).resolve(); lock = verify_lock(repo, lock_path)
    old = sys.modules.get("rrsi")
    if old and Path(old.__file__).resolve().parent != repo / "rrsi":
        raise ProtocolError("a different rrsi package is already imported")
    sys.path.insert(0, str(repo))
    loop = importlib.import_module("rrsi.loop")
    if Path(loop.__file__).resolve() != repo / "rrsi" / "loop.py":
        raise ProtocolError("not loading the locked official loop")
    expected = ["self", "t", "dry_run"]
    if list(inspect.signature(loop.Run.round).parameters) != expected:
        raise ProtocolError("Run.round signature changed; inspect before upgrading")
    return loop, lock


def safe_path(root, rel):
    root = Path(root).resolve(); p = (root / rel).resolve()
    if p != root and root not in p.parents: raise ValueError("path escapes rendered traces")
    return p


def patch_roles(loop, client, run, patch_log, replay_initial_memory=None):
    """Explicit process-local hooks, official files remain byte-for-byte unchanged."""
    from .selection import select_round
    from .io import write_json
    names = ["llm", "analyst", "digester", "propose", "critic"]
    mods = {name: importlib.import_module("rrsi." + name) for name in names}
    for m in mods.values(): m.generate = client.generate
    critic = mods["critic"]
    original = getattr(critic, "_m5_original_system", critic.SYSTEM_TMPL)
    critic._m5_original_system = original
    a, b = "5. RUNTIME MEMORY / SKILL LEAKAGE:", "6. UNBOUNDED WORK:"
    if a not in original or b not in original: raise ProtocolError("critic template changed; patch requires review")
    start, end = original.index(a), original.index(b)
    replay_start = ("Replay must start each trial from empty memory. "
                    if replay_initial_memory == "empty"
                    else "Replay must start from its historical pre-window state. ")
    critic.SYSTEM_TMPL = original[:start] + (
        "5. TTL MEMORY BOUNDARY: This domain intentionally learns across questions. "
        "Runtime memories written by observe() from PREVIOUSLY RELEASED feedback are allowed, "
        "including related-question experience. REJECT hard-coded question-answer tables in source, "
        "future or current-unlocked labels, unauthorized scorer/data access, and cross-arm state. "
        f"{replay_start}Do not reject ordinary authorized "
        "M5 memory accumulation merely because it persists across completed questions.\n"
    ) + original[end:]
    prop = mods["propose"]
    original_p = getattr(prop, "_m5_original_system", prop.SYSTEM_TMPL)
    prop._m5_original_system = original_p
    if "The policy LLM is frozen and is a DIFFERENT\nmodel from you" not in original_p:
        raise ProtocolError("proposer template changed; review the same-model patch before upgrading")
    if "entities, names or values anywhere in code, prompts or state; every edit" not in original_p:
        raise ProtocolError("proposer memory boundary changed; review before upgrading")
    prop.SYSTEM_TMPL = original_p.replace(
        "The policy LLM is frozen and is a DIFFERENT\nmodel from you: do not assume it shares your capabilities, habits or judgment.",
        "The policy LLM is frozen. It may share the same Qwen model as the search roles,\nbut uses different inputs and tools; judge its actual trajectories, not your assumptions.")
    prop.SYSTEM_TMPL = prop.SYSTEM_TMPL.replace(
        "entities, names or values anywhere in code, prompts or state; every edit",
        "entities, names or answer tables embedded in code or prompts; authorized past-feedback memory is allowed; every edit")
    # The original digester exposes a read-only shell; a read-only shell can still read
    # arbitrary host label files. Remove that tool and strengthen file path containment.
    mods["digester"]._bash_ok = lambda cmd: False
    mods["digester"]._safe = safe_path
    loop.select_round = select_round
    from rrsi.history import stall_flag as official_stall
    def ttl_stall(_trajectory, t, w, delta):
        # Panels change over time. Use per-round accepted paired gains, counted ONCE
        # per candidate, not absolute scores or once for each edit in a bundle.
        by_round = {}
        for r in run.history.records():
            if r.get("accepted") and r.get("delta_S") is not None and int(r["t"]) < t:
                by_round[int(r["t"])] = max(by_round.get(int(r["t"]), 0.0), float(r["delta_S"]))
        series = [0.0]
        for i in range(t): series.append(series[-1] + by_round.get(i, 0.0))
        return official_stall(series, t, w, delta)
    loop.stall_flag = ttl_stall
    write_json(patch_log, {"official_loop": str(Path(loop.__file__).resolve()),
        "official_round_reused": True, "runtime_hooks": ["qwen_generate", "accuracy_only_select_round",
        "TTL_critic_memory_boundary", "same_model_proposer_wording", "digester_no_shell_and_path_containment",
        "stall_on_paired_accepted_gains"], "upstream_core_files_modified": False})
