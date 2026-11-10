"""V4 D/E: run one continuation from a replay checkpoint.

This is the piece that turns `tool_step_replay` checkpoints into actual paired
runs. It is written against two injected callables - `call_tool` and `ask_model` -
so the control flow can be tested offline with fakes and then wired to the real
eight-tool runtime without changing this logic.

Contract that matters for the counterfactual:

  * do_action executes the recorded target action and its observation is shown to
    the model;
  * alternate_action executes a different real tool;
  * skip_action executes nothing and therefore shows **no** new observation - a
    fabricated observation would silently turn "without this step" into a
    different experiment;
  * a tool failure is recorded as a failure and passed on as such, never retried
    silently and never replaced by a plausible-looking observation.

The answer comes back with whatever the model said; this module does not score it
and does not know whether it is correct.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from skill_policy import branch_messages


@dataclass
class ContinuationResult:
    checkpoint_id: str
    branch: str
    actions: list = field(default_factory=list)
    observations: list = field(default_factory=list)
    answer: str = ""
    stopped_reason: str = "answered"
    tool_error: str | None = None

    def to_dict(self):
        return {"checkpoint_id": self.checkpoint_id, "branch": self.branch,
                "actions": self.actions, "observations": self.observations,
                "answer": self.answer, "stopped_reason": self.stopped_reason,
                "tool_error": self.tool_error}


def continue_from_checkpoint(checkpoint, *, call_tool, ask_model, branch,
                            alternative_tool=None, skill_block=None,
                            remaining_tool_calls=1):
    """Run one branch of one checkpoint and return what happened."""
    if checkpoint.get("rebuild_status") != "usable":
        return ContinuationResult(checkpoint.get("checkpoint_id", "?"), branch,
                                  stopped_reason="checkpoint_unusable")
    if remaining_tool_calls <= 0 and branch != "skip_action":
        return ContinuationResult(checkpoint["checkpoint_id"], branch,
                                  stopped_reason="no_tool_budget")
    if branch not in ("do_action", "skip_action", "alternate_action"):
        raise ValueError(f"unknown branch {branch!r}")

    prefix = list(checkpoint.get("prefix_observations") or [])
    target = checkpoint.get("target_action") or {}
    result = ContinuationResult(checkpoint["checkpoint_id"], branch)
    branch_observation = None

    if branch == "do_action":
        tool, arguments = target.get("tool"), target.get("arguments") or {}
        result.actions.append({"branch": branch, "tool": tool})
        observation, error = _safe_call(call_tool, tool, arguments)
        result.tool_error = error
        result.observations.append({"tool": tool, "observation": observation, "error": error})
        branch_observation = {"tool": tool, "facts": (observation or {}).get("facts")} if observation else None
    elif branch == "alternate_action":
        tool = alternative_tool or target.get("tool")
        result.actions.append({"branch": branch, "tool": tool})
        observation, error = _safe_call(call_tool, tool, target.get("arguments") or {})
        result.tool_error = error
        result.observations.append({"tool": tool, "observation": observation, "error": error})
        branch_observation = {"tool": tool, "facts": (observation or {}).get("facts")} if observation else None
    else:
        result.actions.append({"branch": "skip_action", "tool": None})

    messages = branch_messages(checkpoint.get("question", ""), prefix,
                               skill_block=skill_block,
                               branch_observation=branch_observation)
    try:
        result.answer = ask_model(messages) or ""
    except Exception as exc:                       # recorded, not swallowed as an answer
        result.answer = ""
        result.stopped_reason = f"model_error: {type(exc).__name__}"
        return result
    if result.tool_error:
        result.stopped_reason = "answered_after_tool_error"
    return result


def _safe_call(call_tool, tool, arguments):
    try:
        return call_tool(tool, arguments), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def run_replay_pair(checkpoint, *, call_tool, ask_model, skill_block=None,
                    other_branch="skip_action", alternative_tool=None):
    """Both sides of one paired comparison, from the same checkpoint."""
    do_result = continue_from_checkpoint(
        checkpoint, call_tool=call_tool, ask_model=ask_model, branch="do_action",
        skill_block=skill_block)
    other_result = continue_from_checkpoint(
        checkpoint, call_tool=call_tool, ask_model=ask_model, branch=other_branch,
        alternative_tool=alternative_tool, skill_block=skill_block)
    return {"checkpoint_id": checkpoint.get("checkpoint_id"),
            "do_action": do_result.to_dict(),
            "other": other_result.to_dict(),
            "other_branch": other_branch}
