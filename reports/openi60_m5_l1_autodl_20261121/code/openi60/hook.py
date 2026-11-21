"""Main-solver-only system suffix, at the verified R55 Services.call boundary."""
from __future__ import annotations
import copy
import functools
import inspect
from pathlib import Path
from typing import Any
from .common import require, safe_qid, object_hash, write_once

BEGIN = "[OPENI60_L1_SOLVER_POLICY_BEGIN]"
END = "[OPENI60_L1_SOLVER_POLICY_END]"
MAIN_SLOT = "R49-AGENT"

def patched_messages(messages: list[dict], patch: str) -> tuple[list[dict], str, str]:
    require(isinstance(messages, list), "messages must be a list")
    systems = [i for i, m in enumerate(messages) if m.get("role") == "system"]
    require(len(systems) == 1, "Expected exactly one system message at main solver boundary")
    i = systems[0]
    before = messages[i].get("content")
    require(isinstance(before, str) and before, "Expected textual solver system message")
    require(BEGIN not in before and END not in before, "Policy already injected; refusing duplicate hook")
    if not patch:
        return messages, before, before  # B0 passes the very same object to native call.
    after = before + "\n\n" + BEGIN + "\n" + patch.strip() + "\n" + END
    result = list(messages)
    result[i] = dict(messages[i], content=after)
    return result, before, after

def make_services(base: type, patch: str, arm: str, qids: set[str]) -> type:
    """The native runner imports this class through skill_services_r55.Services."""
    require(arm in {"B0", "L1"}, "Unknown arm")
    require(bool(patch) == (arm == "L1"), "Only L1 may have the suffix")
    signature = inspect.signature(base.call)
    require(list(signature.parameters)[:5] == ["self", "row", "arm", "ordinal", "messages"],
            f"Unsupported Services.call signature: {signature}; inspect native code first")
    original = base.call
    class AuditedSolverServices(base):
        @functools.wraps(original)
        def call(self, row, arm, ordinal, messages):
            if arm != MAIN_SLOT:
                return original(self, row, arm, ordinal, messages)
            qid = safe_qid(row["question_id"])
            require(qid in qids and type(ordinal) is int and ordinal > 0,
                    "Unexpected solver question or call ordinal")
            outgoing, before, after = patched_messages(messages, patch)
            # Record text seen by the native sender, not merely a config flag.
            audit = {
                "question_id": qid, "call_ordinal": ordinal,
                "slot": MAIN_SLOT, "experiment_arm": arm_name,
                "patch_applied": bool(patch), "patch_sha256": object_hash(patch),
                "base_system_sha256": object_hash(before), "effective_system_sha256": object_hash(after),
                "base_system": before, "effective_system": after,
                "only_system_suffix_changed": all(
                    m1 == m2 for m1, m2 in zip(messages, outgoing) if m1.get("role") != "system"),
            }
            write_once(Path(self.out).parent / "prompt_audit" / qid / f"{ordinal}.json", audit)
            return original(self, row, arm, ordinal, outgoing)
    arm_name = arm
    AuditedSolverServices.__name__ = "OpenI60" + arm + "Services"
    return AuditedSolverServices
