"""V4 E: build paired tool-step replay checkpoints from a recorded trajectory.

A checkpoint is the *visible prefix* before a chosen tool action: the question,
the images, the observations already obtained, the active skill, and the
remaining budget. Replaying from it with and without the action estimates that
action's contribution.

This module only builds the plan. It never fabricates a prefix it cannot rebuild
from the recorded trace: if an observation was not captured, the checkpoint says
so and the state is marked unusable instead of being silently reconstructed.

The plan's warning is important here: skipping an action and then letting the
policy call the same tool again is a *compensated* action, not a strict deletion,
and it must be recorded as such.
"""

from __future__ import annotations

CHECKPOINT_FIELDS = ("checkpoint_id", "question_id", "question", "images",
                     "prefix_observations", "active_skill_id", "remaining_tool_calls",
                     "remaining_seconds", "target_action", "rebuild_status")


def group_by_question(rows):
    out = {}
    for row in rows:
        out.setdefault(row["question_id"], []).append(row)
    return out


def build_checkpoint(rows, index, *, question="", images=(), active_skill_id=None,
                     remaining_tool_calls=12, remaining_seconds=240.0,
                     observations_before=None):
    """Checkpoint at `index` (0-based) of the ordered calls for one question."""
    if index < 0 or index >= len(rows):
        raise ValueError("index outside the recorded calls")
    target = rows[index]
    prefix = rows[:index] if observations_before is None else observations_before
    usable = all((row.get("observation") or {}).get("execution_status") for row in prefix)
    checkpoint = {
        "checkpoint_id": f"{target['question_id']}#{index}",
        "question_id": target["question_id"],
        "question": question,
        "images": list(images),
        "prefix_observations": [
            {"tool": row.get("tool_name"),
             "facts": (row.get("observation") or {}).get("facts"),
             "execution_status": (row.get("observation") or {}).get("execution_status")}
            for row in prefix],
        "active_skill_id": active_skill_id,
        "remaining_tool_calls": remaining_tool_calls,
        "remaining_seconds": remaining_seconds,
        "target_action": {
            "tool": target.get("tool_name"),
            "arguments": target.get("arguments"),
            "facts": (target.get("observation") or {}).get("facts"),
            "execution_status": (target.get("observation") or {}).get("execution_status"),
        },
        "rebuild_status": "usable" if usable else "unusable_missing_observation",
    }
    return checkpoint


def branches_for(checkpoint, alternative_tools=()):
    """do_action plus skip_action, plus alternate_action where a real alternative exists."""
    if checkpoint.get("rebuild_status") != "usable":
        return []
    base = {"checkpoint_id": checkpoint["checkpoint_id"],
            "question_id": checkpoint["question_id"]}
    target_tool = (checkpoint.get("target_action") or {}).get("tool")
    out = [dict(base, branch="do_action", tool=target_tool),
           dict(base, branch="skip_action", tool=None,
                compensation_note="skipped; if the policy moves the same tool later it is "
                                  "recorded as a compensated action, not a strict deletion")]
    for tool in alternative_tools:
        if tool and tool != target_tool:
            out.append(dict(base, branch="alternate_action", tool=tool))
    return out


def plan_replays(rows_by_question, *, max_states=20, alternative_tools=(),
                 keep_per_question=1):
    """Pick the checkpoints to replay, one per question by default.

    The plan asks for states that are actually informative - localisation review,
    tool substitution, an extra VQA - not simply the first call. So candidate
    indices are ordered by a priority on the target tool, then by position.

    A checkpoint is only chosen when the target call actually returned something,
    because replaying a failed call measures the failure, not the action.
    """
    priority = {"xray_phrase_grounding": 0, "chest_xray_expert": 1, "llava_med_qa": 2,
                "chest_xray_report_generator": 3, "chest_xray_segmentation": 4,
                "chest_xray_classifier": 5}
    plans = []
    for question_id in sorted(rows_by_question):
        rows = rows_by_question[question_id]
        candidates = []
        for index, row in enumerate(rows):
            status = (row.get("observation") or {}).get("execution_status")
            if not status or status == "failed":
                continue
            candidates.append((priority.get(row.get("tool_name"), 9), index))
        candidates.sort()
        chosen = 0
        for _rank, index in candidates:
            checkpoint = build_checkpoint(rows, index)
            branch_list = branches_for(checkpoint, alternative_tools)
            if not branch_list:
                continue
            plans.append({"checkpoint": checkpoint, "branches": branch_list})
            chosen += 1
            if chosen >= keep_per_question:
                break
        if len(plans) >= max_states:
            break
    return plans
