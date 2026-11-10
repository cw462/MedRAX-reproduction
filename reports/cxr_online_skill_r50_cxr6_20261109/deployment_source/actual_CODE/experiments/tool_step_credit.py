"""V4 E: turn paired tool-step replays into a step-contribution estimate.

`delta_step = mean(score_do_action - score_skip_or_alternate)` per (task, capability),
with a shrinkage factor `n/(n+k)` so one lucky state cannot dominate. Unknown
contribution stays neutral rather than negative: absence of evidence is not
evidence of harm.

This is not `memory_credit.py`. That module removed retrieved *memory entries*
from an injected block and measured the answer flip. Here the object is a real
* tool action* executed from a rebuilt visible prefix, and the score comes from
the replay pair.

Nothing in this module claims causality from a single repetition, and it refuses
to emit a credit for a branch pair whose denominator is zero.
"""

from __future__ import annotations

from collections import defaultdict

K_SHRINK = 5.0


def delta_step(do_scores, other_scores):
    """Mean paired difference, plus the pair count actually used."""
    n = min(len(do_scores), len(other_scores))
    if n == 0:
        return None, 0
    diffs = [float(do_scores[i]) - float(other_scores[i]) for i in range(n)]
    return sum(diffs) / n, n


def shrink(delta, n, k=K_SHRINK):
    """Shrink toward zero when only a few states support the estimate."""
    if delta is None or n <= 0:
        return None
    return delta * n / (n + k)


def aggregate(replays):
    """Group replay results by (task_type, capability) and estimate contribution.

    `replays` items: {task_type, capability, do_scores: [...], other_scores: [...],
                      branch, cost_cny, tokens, seconds}
    """
    groups = defaultdict(lambda: {"do": [], "other": [], "n_states": 0,
                                  "cost_cny": 0.0, "tokens": 0, "seconds": 0.0})
    for item in replays:
        if item.get("branch") not in ("do_action", "skip_action", "alternate_action"):
            continue
        key = (str(item.get("task_type") or "unknown"), str(item.get("capability") or "unknown"))
        bucket = groups[key]
        bucket["n_states"] += 1
        bucket["cost_cny"] += float(item.get("cost_cny") or 0.0)
        bucket["tokens"] += int(item.get("tokens") or 0)
        bucket["seconds"] += float(item.get("seconds") or 0.0)
        if item["branch"] == "do_action":
            bucket["do"].extend(item.get("scores") or [])
        else:
            bucket["other"].extend(item.get("scores") or [])

    out = []
    for (task_type, capability), bucket in sorted(groups.items()):
        delta, n_pairs = delta_step(bucket["do"], bucket["other"])
        out.append({
            "task_type": task_type,
            "capability": capability,
            "n_states": bucket["n_states"],
            "n_pairs": n_pairs,
            "delta_step": None if delta is None else round(delta, 4),
            "delta_shrunk": None if delta is None else round(shrink(delta, n_pairs), 4),
            "weight": None if delta is None else round(shrink(delta, n_pairs), 4),
            "status": "estimated" if n_pairs > 0 else "insufficient_pairs",
            "cost_cny": round(bucket["cost_cny"], 4),
            "tokens": bucket["tokens"],
            "seconds": round(bucket["seconds"], 1),
            "limitations": ("paired difference under the given state and follow-up policy; "
                            "not an exact causal truth and not a medical validation"),
        })
    return out


def credit_for(capability, table, default=0.0):
    """Lookup used by arm E: unknown contribution is neutral, not negative."""
    for row in table:
        if row.get("capability") == capability and row.get("weight") is not None:
            return float(row["weight"])
    return default
