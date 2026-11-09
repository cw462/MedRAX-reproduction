"""Prepare a label-free validation30 protocol; this CLI NEVER executes models.

Only the offline plan and strict per-request stage-budget adapter are implemented.
The future runtime must use multi_tool_eval.run_arm, the six frozen slice plans,
and a locked existing MoneyGuard. There is deliberately no run/resume CLI yet.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from decimal import Decimal, localcontext
import importlib.metadata
import json
from pathlib import Path
import random
import subprocess
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import diagnostic_eval as diag
import multi_tool_eval as multi
from money_guard import MoneyGuard, BudgetExceeded, BudgetIntegrityError, RESERVATION_CNY, _decimal
from data_tools import audit_figures as files

CAPS = (512, 1024)
REPLICATES = (1, 2, 3)
ARMS = ("direct", "agent")
SEED = 20261027
KIND = "validation30_caps512_1024_three_repeats_direct_original_multitool_plan"


def code_repository_info():
    root = Path(__file__).resolve().parents[1]
    try:
        commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True, stderr=subprocess.DEVNULL).strip())
        return {"commit": commit, "working_tree_dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "working_tree_dirty": None, "source_file_hashes_are_authoritative": True}


class StageBudgetExceeded(BudgetExceeded):
    """Keep unstarted schedule items pending; never send this request."""


def stage_decision(origin, current_spent, cap, hard_remaining):
    if cap not in CAPS:
        raise ValueError("Only 512/1024 caps are specified")
    with localcontext() as context:
        context.prec = 80
        start = _decimal(origin["starting_committed_cny"])
        limit = _decimal(origin["stage_limit_cny"])
        spent, remaining = _decimal(current_spent), _decimal(hard_remaining)
        if spent < start or limit <= 0 or remaining < 0:
            raise BudgetIntegrityError("Stage origin/spending is inconsistent")
        required = RESERVATION_CNY * (1 if cap == 512 else 2)
        available = limit - (spent-start)
        reason = "stage_budget" if available < required else "budget" if remaining < required else None
        return {"allowed": reason is None, "stop_reason": reason,
                "required_reservation_cny": str(required), "stage_spent_cny": str(spent-start),
                "stage_remaining_cny": str(available), "hard_remaining_cny": str(remaining)}


class StageBudgetGuard:
    """Adapter for an ALREADY locked shared guard; never opens another ledger.

    For cap512 wrap the original MoneyGuard; for cap1024 wrap its existing
    ChunkedBudgetGuard(1024). A strict full logical-request preflight avoids both
    stage overshoot and a partially reserved two-block request on low balance.
    Actual runtime/journal integration is not implemented by this planning CLI.
    """
    def __init__(self, guard, origin, *, cap):
        if cap not in CAPS or not callable(getattr(guard, "reserve", None)) or not callable(getattr(guard, "settle", None)):
            raise ValueError("Use an existing compatible guarded request adapter")
        policy = guard.policy_snapshot()
        if policy != origin["monetary_policy"]:
            raise BudgetIntegrityError("Stage monetary policy changed")
        if cap == 1024:
            if not callable(getattr(guard, "chunk_policy_snapshot", None)) or guard.chunk_policy_snapshot()["effective_max_output_tokens"] != 1024:
                raise ValueError("1024 requires the existing two-block adapter")
        elif callable(getattr(guard, "chunk_policy_snapshot", None)):
            raise ValueError("512 must not use the two-block adapter")
        underlying = getattr(guard, "_guard", None) if cap == 1024 else guard
        if not isinstance(underlying, MoneyGuard) or underlying._state["ledger_id"] != origin["ledger_id"]:
            raise BudgetIntegrityError("Stage adapter must use the same existing locked ledger identity")
        _ = underlying.remaining
        self.guard, self.origin, self.cap = guard, deepcopy(origin), cap
        self.last_decision = None

    @property
    def remaining(self): return self.guard.remaining

    def policy_snapshot(self): return self.guard.policy_snapshot()

    def preflight(self):
        remaining = self.remaining
        with localcontext() as context:
            context.prec = 80
            spent = _decimal(self.policy_snapshot()["budget_cny"]) - remaining
        self.last_decision = stage_decision(self.origin, spent, self.cap, remaining)
        return deepcopy(self.last_decision)

    def reserve(self, *args, **kwargs):
        decision = self.preflight()
        if not decision["allowed"]:
            raise StageBudgetExceeded(decision["stop_reason"])
        return self.guard.reserve(*args, **kwargs)

    def settle(self, *args, **kwargs): return self.guard.settle(*args, **kwargs)


def load_validation(directory, split_directory, expected_count=30):
    directory, split_directory = Path(directory).resolve(), Path(split_directory).resolve()
    manifest = files.read_json(directory/"manifest.json")
    if manifest.get("status") != "frozen_ready_for_validation" or manifest.get("split") != "validation":
        raise ValueError("A frozen validation-only dataset is required")
    for name in ("inference.jsonl", "audit_manifest.json", "selection_plan.json"):
        if files.file_sha(directory/name) != manifest["artifact_sha256"][name]:
            raise ValueError("Frozen validation artifact hash mismatch")
    rows = diag.load_rows(directory/"inference.jsonl", planned_count=expected_count)
    selected = files.read_json(directory/"selection_plan.json")
    audit = files.read_json(directory/"audit_manifest.json")
    if (audit["inference_sha256"] != manifest["artifact_sha256"]["inference.jsonl"]
            or audit["selection_plan_sha256"] != manifest["artifact_sha256"]["selection_plan.json"]):
        raise ValueError("Validation audit hash chain differs")
    split_manifest = files.read_json(split_directory/"manifest.json")
    for name in ("audit_index.jsonl", "validation.inputs.jsonl"):
        if files.file_sha(split_directory/name) != split_manifest["artifact_sha256"][name]:
            raise ValueError("Original split artifact hash mismatch")
    if selected["source_provenance"]["split_manifest_sha256"] != files.file_sha(split_directory/"manifest.json"):
        raise ValueError("Selected validation belongs to another original split")
    index_rows = files.read_jsonl(split_directory/"audit_index.jsonl")
    index = {r["question_id"]: r for r in index_rows}
    if len(index) != len(index_rows): raise ValueError("Duplicate original audit question")
    original_rows = files.read_jsonl(split_directory/"validation.inputs.jsonl")
    original = {r["question_id"]: r for r in original_rows}
    mappings = {r["question_id"]: r for r in audit["records"]}
    ids = [r["question_id"] for r in rows]
    if (ids != selected["question_ids"] or set(ids) != set(mappings)
            or len(mappings) != len(audit["records"]) or len(original) != len(original_rows)):
        raise ValueError("Validation selection/index mapping differs")
    case_hashes = {}
    for row in rows:
        qid = row["question_id"]; mapping = mappings[qid]
        if (index[qid]["split"] != "validation" or mapping["split"] != "validation"
                or mapping["case_hash_audit_only"] != index[qid]["case_hash"]
                or row["question"] != original[qid]["question"]
                or [x["dataset_image_path"] for x in mapping["images"]] != original[qid]["images"]
                or [x["inference_image_path"] for x in mapping["images"]] != row["images"]
                or not row["images"]):
            raise ValueError("Selected question/case/complete-image source differs")
        if mapping.get("exact_cross_split_overlap_flag"):
            raise ValueError("Flagged validation overlap needs an explicit revised protocol")
        record, paths = diag.inspect_input(row, directory/"images")
        if record["preflight_issues"]:
            raise ValueError("Selected validation inputs are unavailable or exceed the current runner limits")
        for path, expected in zip(paths, mapping["images"]):
            if files.file_sha(path) != expected["sha256"] or path.stat().st_size != expected["bytes"]:
                raise ValueError("Image differs from frozen original bytes")
        case_hashes[qid] = index[qid]["case_hash"]
    if len(set(case_hashes.values())) != len(rows): raise ValueError("Repeated validation case")
    if manifest["question_count"] != len(rows) or manifest["distinct_case_count"] != len(rows):
        raise ValueError("Validation denominators differ")
    return rows, {"validation_manifest_sha256": files.file_sha(directory/"manifest.json"),
                  "artifact_sha256": manifest["artifact_sha256"],
                  "split_manifest_sha256": files.file_sha(split_directory/"manifest.json"),
                  "original_validation_sha256": split_manifest["artifact_sha256"]["validation.inputs.jsonl"],
                  "audit_index_sha256": split_manifest["artifact_sha256"]["audit_index.jsonl"],
                  "case_hashes_audit_only": case_hashes, "split": "validation", "labels_read": False}


def read_ledger(path, expected_id, policy):
    """Validate without constructing MoneyGuard, locking, recovering or writing."""
    path = Path(path).resolve()
    if not path.is_file(): raise ValueError("An existing original ledger is required; creation prohibited")
    raw = path.read_bytes(); state = files.decode(raw.decode("utf-8-sig"))
    validator = object.__new__(MoneyGuard)
    validator._policy = deepcopy(policy)
    validator._validate(state)
    if state["ledger_id"] != expected_id or state["blocked"]:
        raise BudgetIntegrityError("Ledger identity mismatch or permanently blocked")
    if any(item["status"] == "pending" for item in state["reservations"]):
        raise BudgetIntegrityError("Read-only planning refuses an unsettled live request")
    if path.read_bytes() != raw: raise BudgetIntegrityError("Ledger changed during read-only planning")
    return {"ledger_id": state["ledger_id"], "generation": state["generation"],
            "committed_cny": state["committed_cny"], "ledger_sha256": files.sha(raw),
            "monetary_policy": state["policy"], "locked_snapshot": False}


def stage_origin(path, snapshot, limit):
    """Return existing immutable origin or prepare (without writing) a new one."""
    path = Path(path)
    amount = _decimal(limit)
    if amount <= 0 or amount > Decimal("100"):
        raise ValueError("Stage limit must be positive and no more than the unchanged hard ceiling")
    if path.exists():
        origin = files.read_json(path)
        if (origin["ledger_id"] != snapshot["ledger_id"] or origin["monetary_policy"] != snapshot["monetary_policy"]
                or _decimal(origin["stage_limit_cny"]) != amount
                or _decimal(snapshot["committed_cny"]) < _decimal(origin["starting_committed_cny"])
                or snapshot["generation"] < origin["starting_ledger_generation"]):
            raise BudgetIntegrityError("Existing stage origin/limit/ledger cannot be reset or changed")
        return origin, False
    return {"schema_version": 1, "created_utc": diag.utc_now(), "ledger_id": snapshot["ledger_id"],
            "monetary_policy": snapshot["monetary_policy"], "starting_committed_cny": snapshot["committed_cny"],
            "starting_ledger_generation": snapshot["generation"], "starting_ledger_sha256": snapshot["ledger_sha256"],
            "stage_limit_cny": str(amount), "rule": "same-ledger cumulative charge plus full next-request reservation must fit; never reset origin"}, True


def schedule(ids, seed=SEED):
    if not ids or len(set(ids)) != len(ids): raise ValueError("Distinct planned question IDs required")
    generator, result = random.Random(seed), []
    for replicate in REPLICATES:
        for qid in ids:
            block = [(cap, arm) for cap in CAPS for arm in ARMS]
            generator.shuffle(block)
            for cap, arm in block:
                result.append({"schedule_index": len(result)+1, "slice_id": f"cap{cap}_rep{replicate}",
                               "cap": cap, "replicate": replicate, "question_id": qid, "arm": arm})
    return result


def build_plan(rows, data_provenance, args, origin, snapshot, prompt, registry, registry_source_hash):
    kinds = {item["kind"] for item in registry.values()}
    if kinds not in ({"classification", "report"}, {"classification", "report", "segmentation"}):
        raise ValueError("Freeze an actually available classifier/report set, optionally segmentation")
    if len(kinds) != len(registry) or any(item.get("mode") != "original" for item in registry.values()):
        raise ValueError("This cap comparison uses distinct original tool variants only")
    base = diag.build_plan(rows, args.validation_dir/"inference.jsonl", args.validation_dir/"images", args.repo,
                           args, snapshot["monetary_policy"], prompt)
    ids = [row["question_id"] for row in rows]; ordered = schedule(ids, args.schedule_seed)
    sources = dict(base["source_sha256"])
    for name in ("validation_protocol.py", "multi_tool_eval.py", "tool_variants.py", "report_smoke.py", "chunked_budget.py", "segmentation_smoke.py"):
        sources[name] = files.file_sha(Path(__file__).with_name(name))
    for kind in kinds:
        source = multi.variants._source(args.repo.resolve(), kind)
        recorded = next(item["source"] for item in registry.values() if item["kind"] == kind)
        if source["commit"] != recorded["commit"] or source["tool_lf_sha256"] != recorded["tool_lf_sha256"]:
            raise ValueError("Current official source differs from actual tool registry")
        sources["official_"+kind] = source["tool_sha256"]
    environment = {"python": sys.version, "planning_environment_only": True}
    for package in ("torch", "torchvision", "torchxrayvision", "transformers", "numpy", "Pillow"):
        try: environment[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError: environment[package] = None
    conditions = {}
    for cap in CAPS:
        for replicate in REPLICATES:
            slice_id = f"cap{cap}_rep{replicate}"
            plan = deepcopy(base)
            plan.update(kind=KIND+"_slice", slice_id=slice_id, cap=cap, replicate=replicate,
                        planned_question_count=len(rows), max_output_tokens=cap,
                        schedule=[{"question_id": item["question_id"], "arm": item["arm"]} for item in ordered if item["slice_id"] == slice_id],
                        tool_registry=deepcopy(registry), available_tool_names=sorted(registry),
                        source_sha256=sources, data_provenance=data_provenance, stage_origin=origin,
                        provider_seed=None, schedule_seed=args.schedule_seed,
                        request_accounting={"effective_max_output_tokens": cap, "reservation_blocks_per_request": cap//512,
                                            "guard": "MoneyGuard" if cap == 512 else "ChunkedBudgetGuard(1024)"},
                        cross_case_memory_enabled=False, protocol_repair_enabled=False,
                        protocol_deviations=["Prospective repeated validation development; not a heldout or full-paper result.",
                                             "Two-stage direct answer; fresh thread per question/arm/repeat.",
                                             "Original available tools are model-selected, never all forced.",
                                             "Same model/sampling/input/final-letter protocol; only output cap differs across cap conditions.",
                                             "Seed randomizes condition order only; no provider sampling seed.",
                                             "Four model requests and two total tool calls can limit complex behavior."])
            conditions[slice_id] = plan
    return {"schema_version": 1, "kind": KIND, "status": "prepared_not_executed",
            "runtime_implemented": False, "runtime_entrypoint": None, "model_calls_made": 0,
            "planned_question_count": len(rows), "planned_case_count": len(rows), "planned_arm_results": len(ordered),
            "question_ids": ids, "caps": list(CAPS), "replicates": list(REPLICATES), "arms": list(ARMS),
            "schedule_seed": args.schedule_seed, "provider_seed": None, "global_schedule": ordered,
            "global_schedule_sha256": diag.hash_value(ordered), "condition_plans": conditions,
            "source_sha256": sources, "data_provenance": data_provenance, "tool_registry": registry,
            "environment_at_planning": environment,
            "experiment_repository_at_planning": code_repository_info(),
            "tool_registry_manifest_sha256": registry_source_hash,
            "tool_availability_status": "provenance_from_prior_real_manifest_revalidation_required_before_runtime",
            "monetary_ledger_path": str(args.ledger.resolve()), "monetary_policy": snapshot["monetary_policy"],
            "ledger_snapshot_at_planning": snapshot, "stage_origin": origin,
            "frozen_engine": "multi_tool_eval.run_arm", "label_access": "none_in_planning_or_inference",
            "scoring_contract": {"independent_scorer_only": True, "per_slice_denominator": len(rows),
                                 "slice_arms": list(ARMS), "missing_error_invalid_count_as_not_correct": True,
                                 "paired_unit": "case", "repeat_aggregation": "average within case before paired bootstrap",
                                 "repeats_are_not_independent_cases": True,
                                 "requires_finalized_execution_journals": True}}


def prepare(args):
    if args.output.exists(): raise FileExistsError("A new protocol output directory is required")
    rows, provenance = load_validation(args.validation_dir, args.split_directory)
    source = files.read_json(args.tool_manifest)
    tool_plan = source["plan"]
    if source.get("plan_sha256") != diag.hash_value(tool_plan): raise ValueError("Tool source manifest hash mismatch")
    snapshot = read_ledger(args.ledger, args.expected_ledger_id, tool_plan["monetary_policy"])
    origin, create_origin = stage_origin(args.stage_state, snapshot, args.stage_soft_limit_cny)
    utils = diag.smoke.module_from_file("_validation_planning_official_utils", args.repo/"medrax/utils/utils.py")
    prompt = utils.load_prompts_from_file(str(args.repo/"medrax/docs/system_prompts.txt"))["MEDICAL_ASSISTANT"]
    plan = build_plan(rows, provenance, args, origin, snapshot, prompt, tool_plan["tool_registry"], files.file_sha(args.tool_manifest))
    args.output.mkdir(parents=True)
    (args.output/".gitignore").write_text("*\n", encoding="utf-8")
    if create_origin:
        args.stage_state.parent.mkdir(parents=True, exist_ok=True)
        files.write_json(args.stage_state, origin)
    manifest = {"created_utc": diag.utc_now(), "plan_sha256": diag.hash_value(plan), "plan": plan,
                "stage_state_sha256": files.file_sha(args.stage_state)}
    files.write_json(args.output/"manifest.json", manifest)
    files.write_json(args.output/"summary.json", {"status": "prepared_not_executed", "runtime_implemented": False,
                     "planned_arm_results": len(plan["global_schedule"]), "terminal_count": 0,
                     "question_results": [dict(item, status="pending_not_executed") for item in plan["global_schedule"]],
                     "stage_budget_preflight": {str(cap): stage_decision(origin, snapshot["committed_cny"], cap,
                        _decimal(snapshot["monetary_policy"]["budget_cny"])-_decimal(snapshot["committed_cny"])) for cap in CAPS}})
    for slice_id, slice_plan in plan["condition_plans"].items():
        target = args.output/slice_id; target.mkdir()
        files.write_json(target/"plan.json", {"plan_sha256": diag.hash_value(slice_plan), "plan": slice_plan})
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("validation-dir", "split-directory", "repo", "ledger", "tool-manifest", "stage-state", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--expected-ledger-id", required=True)
    parser.add_argument("--stage-soft-limit-cny", required=True, help="Strict full-request pre-reservation limit from one immutable stage origin")
    parser.add_argument("--base-url", default="https://api.apiyi.com/v1")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--image-detail", choices=("auto", "low", "high"), default="auto")
    parser.add_argument("--max-case-seconds", type=float, default=180)
    parser.add_argument("--request-timeout-seconds", type=float, default=60)
    parser.add_argument("--schedule-seed", type=int, default=SEED)
    args = parser.parse_args(argv)
    import math
    if any(not math.isfinite(value) or value <= 0 for value in (args.max_case_seconds, args.request_timeout_seconds)):
        parser.error("Timeouts must be finite and positive")
    url = urlsplit(args.base_url)
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
        parser.error("HTTPS API base URL without credentials/query/fragment required")
    args.arms, args.arm_order_seed = ARMS, args.schedule_seed
    result = prepare(args)
    print(json.dumps({"status": "prepared_not_executed", "runtime_implemented": False,
                      "planned_arm_results": result["plan"]["planned_arm_results"], "plan_sha256": result["plan_sha256"]}))


if __name__ == "__main__": main()
