"""Accuracy-only replacement for rrsi.loop.select_round; costs are logged, not rewarded."""
from __future__ import annotations
import math
from .io import ProtocolError


def check_pair(inc, cand, min_gain=0.0, nonnegative_repeats=True):
    errors = []
    if not inc.per_task or not cand.per_task:
        return False, ["empty replay panel"], []
    for key in ("panel_id", "replay_start_hash", "feedback_mode", "metric_id"):
        if not inc.extra.get(key) or inc.extra.get(key) != cand.extra.get(key):
            errors.append(f"incomparable {key}")
    if inc.k != cand.k or set(inc.per_task) != set(cand.per_task):
        errors.append("different task IDs or repeat count")
    if inc.missing or cand.missing: errors.append("missing trials")
    for ev in (inc, cand):
        if not math.isfinite(ev.S) or not 0 <= ev.S <= 1: errors.append("invalid accuracy")
        if ev.n_expected != len(ev.per_task) * ev.k: errors.append("incorrect denominator")
        for tr in ev.per_task.values():
            if len(tr.rewards) != ev.k or any(r not in (0, 1) for r in tr.rewards):
                errors.append("nonbinary or incomplete rewards")
    if errors: return False, errors, []
    gains = [sum(cand.per_task[i].rewards[j] - inc.per_task[i].rewards[j]
                 for i in inc.per_task) / len(inc.per_task) for j in range(inc.k)]
    if cand.S - inc.S <= min_gain + 1e-12: errors.append("no strictly positive accuracy gain")
    if nonnegative_repeats and any(g < -1e-12 for g in gains):
        errors.append("a repeat regressed")
    return not errors, errors, gains


def select_round(cands, incumbent, S_star, delta, cfg, incumbent_counts, guard_fn=None):
    # S_star from a previous TTL panel is NOT a valid comparison baseline.
    from rrsi.selection import Decision
    decisions = []
    for c in cands:
        if c.ev is None:
            decisions.append(Decision(c.variant, False, c.gate_failure or "not evaluated"))
            continue
        ok, reasons, gains = check_pair(incumbent, c.ev, min_gain=max(0.0, float(delta)))
        guards = guard_fn(incumbent, c.ev) if guard_fn else []
        ok = ok and not guards
        dC = ((c.ev.C - incumbent.C) / incumbent.C
              if incumbent.C and c.ev.C is not None else 0.0)
        decisions.append(Decision(c.variant, ok,
            "accuracy_only: " + (f"paired gains={gains}" if ok else "; ".join(reasons + guards)),
            S=c.ev.S, C=c.ev.C, delta_S=c.ev.S - incumbent.S, delta_C=dC,
            novelty=0, guards=guards))
    eligible = [(c, d) for c, d in zip(cands, decisions) if d.admissible]
    if not eligible: return None, decisions
    # Stable candidate order breaks exact ties; neither novelty nor cheapness promotes a tie.
    return max(eligible, key=lambda x: x[1].S)[0], decisions
