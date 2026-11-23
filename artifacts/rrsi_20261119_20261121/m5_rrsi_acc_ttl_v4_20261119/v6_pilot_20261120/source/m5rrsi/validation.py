from pathlib import Path
from .io import ProtocolError, read_json, write_once, digest, file_hash, tree_hash, git
from .upstream import verify_lock
from .engine import primary_arms


def validate_config(cfg, template_ok=False):
    arms = primary_arms(cfg)
    if not template_ok and "REPLACE" in str(cfg): raise ProtocolError("config is still a server-integration template")
    if cfg["feedback_mode"] != "full_label":
        raise ProtocolError("v4 currently implements only full_label; do not silently change feedback strength")
    n = cfg["expected_questions"]
    s = cfg["search"]
    phase = cfg.get("phase")
    if phase is not None:
        if phase not in ("dev", "val", "test") or arms != ("rrsi_acc",):
            raise ProtocolError("v5 uses one isolated development, validation or test run per arm")
        allowed_arms = ("M", "RSI_selected") if phase == "test" else ("RSI",)
        if cfg.get("arm") not in allowed_arms:
            raise ProtocolError(f"invalid v5 {phase} arm")
        if phase == "val" and cfg.get("checkpoint") not in ("S0", "S50", "S100"):
            raise ProtocolError("validation needs a development checkpoint")
    max_rounds = s["max_rounds"]
    if type(max_rounds) is not int:
        raise ProtocolError("max_rounds must be an integer")
    if phase == "dev":
        if not 1 <= max_rounds <= n or s.get("replay_initial_memory") != "empty":
            raise ProtocolError("development needs an empty-start replay and a budget within the stream")
    elif phase in ("val", "test"):
        if max_rounds != 0:
            raise ProtocolError("validation and test require zero search rounds")
    elif not 1 <= max_rounds <= n-1:
        raise ProtocolError("legacy search requires a positive budget and skips the final question")
    for key in ("replay_window_cases", "repeats", "candidates", "edit_budget_min", "edit_budget_max", "stall_window"):
        if not isinstance(s[key], int) or isinstance(s[key], bool) or s[key] <= 0: raise ProtocolError(f"invalid {key}")
    if not 1 <= s["candidates"] <= 8: raise ProtocolError("official candidate label limit is 8")
    for key, bound in (("eval_parallel", s["candidates"]),
                       ("repeat_parallel", s["repeats"]),
                       ("draft_parallel", s["candidates"])):
        value = s.get(key, 1)
        if type(value) is not int or not 1 <= value <= bound:
            raise ProtocolError(f"{key} must be between 1 and {bound}")
    if s["edit_budget_min"] > s["edit_budget_max"]: raise ProtocolError("invalid edit budget interval")
    import math
    if not math.isfinite(s["min_gain"]) or s["min_gain"] < 0: raise ProtocolError("invalid min_gain")
    if phase not in ("val", "test") and cfg["runtime"]["model"] != cfg["search_llm"]["model"]:
        raise ProtocolError("this preregistered template uses the same Qwen model for actor/search")
    if not template_ok:
        limits = cfg["runtime"]["limits"]
        required = {"model_calls", "tool_calls", "output_tokens"}
        if not isinstance(limits, dict) or not required <= limits.keys():
            raise ProtocolError("copy all native M5 call and output limits before running")
        for key in ("model_calls", "tool_calls"):
            value = limits[key]
            if value is not None and (type(value) is not int or value <= 0):
                raise ProtocolError(f"{key} must be positive or null for native unlimited calls")
        if type(limits["output_tokens"]) is not int or limits["output_tokens"] <= 0:
            raise ProtocolError("output_tokens must be the positive native per-response token limit")
        if len(cfg["initial_commit"]) != 40: raise ProtocolError("use full initial H0 commit")
    return cfg


def budget(cfg):
    s = cfg["search"]; n = cfg["expected_questions"]
    r = min(s["max_rounds"], n if cfg.get("phase") == "dev" else n-1)
    windows = sum(min(i, s["replay_window_cases"]) for i in range(1, r+1))
    replay = windows * s["repeats"] * (1+s["candidates"])
    return {"primary_question_predictions": len(primary_arms(cfg))*n, "max_search_rounds": r,
            "max_initial_candidate_slots": r*s["candidates"],
            "max_sequential_replay_predictions_without_failures_or_retries": replay,
            "max_replay_observe_operations": replay,
            "additional_unpriced_calls": "official analyst/digester/proposer/critic/repair calls, migrate/smoke, failed or retried API calls",
            "note": "This is not a time/cost estimate. Window length is replay size, NOT trigger interval."}


def source_hashes():
    root = Path(__file__).parent
    return {p.name: file_hash(p) for p in sorted(root.glob("*.py"))}


def runtime_fingerprint(cfg):
    import os
    endpoint = None
    if cfg.get("phase") not in ("val", "test"):
        endpoint = os.environ.get(cfg["search_llm"]["base_url_env"], "").rstrip("/")
        if not endpoint:
            raise ProtocolError("set the registered search endpoint before freezing")
        if not os.environ.get(cfg["search_llm"]["api_key_env"]):
            raise ProtocolError("set the search API key via environment; never store it in config")
    manifest = read_json(cfg["manifest"])
    if manifest["n"] != cfg["expected_questions"] or digest(manifest["cases"]) != manifest["cases_hash"]:
        raise ProtocolError("wrong question count or changed manifest")
    for row in manifest["cases"]:
        for im in row["images"]:
            if file_hash(im["path"]) != im["sha256"]: raise ProtocolError("original image changed")
    lock = verify_lock(cfg["upstream_repo"], cfg["upstream_lock"])
    if git(cfg["upstream_repo"], "rev-parse", cfg["initial_commit"]) != cfg["initial_commit"]:
        raise ProtocolError("initial commit not found")
    # A clean initial main checkout prevents uncommitted harness changes being ignored.
    if git(cfg["upstream_repo"], "status", "--porcelain", "--untracked-files=no"):
        raise ProtocolError("upstream/native checkout has uncommitted tracked changes")
    reports = {}
    required_checks = {
        "h0_parity_report": {"original_images", "native_tool_trace", "native_memory_writer", "source_tree_execution"},
        "native_scorer_report": {"same_parser", "same_denominator", "invalid_answer_policy"},
        "sandbox_gateway_report": {"no_future_files", "no_other_arm_state", "model_pinned", "tool_versions_pinned", "gateway_enforces_limits", "authoritative_usage"},
        "upstream_contract_report": {"real_Run_round", "official_proposal_path", "accuracy_patch", "version_inheritance"},
    }
    for key, required in required_checks.items():
        path = cfg["evidence"][key]; r = read_json(path)
        if r.get("status") != "passed" or not required <= set(r.get("passed_checks", [])):
            raise ProtocolError(f"required server evidence has not passed: {key}")
        if not r.get("evidence_files"):
            raise ProtocolError(f"report must point to actual test artifacts: {key}")
        hashes = {}
        for p in r["evidence_files"]:
            fp = Path(p); fp = fp if fp.is_absolute() else Path(path).parent / fp
            hashes[str(fp.resolve())] = file_hash(fp)
        reports[key] = {"report": file_hash(path), "artifacts": hashes}
    return {"config_hash": digest(cfg), "search_endpoint": endpoint, "manifest_hash": file_hash(cfg["manifest"]),
            "references_hash": file_hash(cfg["references"]), "upstream_lock": lock,
            "initial_commit": cfg["initial_commit"], "overlay_sources": source_hashes(),
            "trusted_runtime": tree_hash(cfg["runtime"]["runtime_dir"]),
            "scorer_files": {str(Path(x).resolve()): file_hash(x)
                             for x in [x for x in cfg["scorer_command"] if Path(x).is_file()]
                             + cfg.get("scorer_source_files", [])},
            "native_binding_files": {key: file_hash(cfg["runtime"][key])
                                     for key in ("case_metadata", "gateway_config")
                                     if key in cfg["runtime"]},
            "evidence": reports, "budget": budget(cfg)}


def freeze(cfg):
    validate_config(cfg)
    f = runtime_fingerprint(cfg)
    p = Path(cfg["run_dir"]) / "frozen.json"
    write_once(p, f)
    return f


def verify_frozen(cfg):
    current = runtime_fingerprint(cfg)
    p = Path(cfg["run_dir"]) / "frozen.json"
    if not p.exists() or read_json(p) != current:
        raise ProtocolError("configuration/code/evidence changed or not frozen; create a new run")
