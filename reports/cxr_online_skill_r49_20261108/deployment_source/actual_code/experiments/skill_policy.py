"""V4 C/D: skill retrieval and explicit state-driven action selection.

Two responsibilities, kept apart:

1. `SkillIndex` - retrieve the skills whose trigger matches the current question.
   Used by arm C, where the only change from B is the representation (semantic
   skill instead of structural memory), so the retrieval budget and top-k stay the
   same.

2. `AgentState` + `decide` - the explicit intermediate state arm D needs:
   required information, observations, missing information, comparable conflicts,
   available actions, active skill branch, remaining budget. `decide` returns an
   operation, never free text, so a run can log *why* the next action was chosen.

Honesty notes:
  * a conflict is only recorded for the same finding and the same attribute;
    absence of an output is never treated as counter-evidence, and a classifier
    score cannot supply a laterality claim;
  * "local reinspection" is only proposed when a real box exists for the current
    case - it is never fabricated from a training case;
  * stopping with uncertainty is a valid, recorded outcome, not a failure.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field

STOPWORDS = set("""a an the of in on at to for with and or is are was were be been this that these those
which what how does do did can could would should may might will shall about into from as by it its
patient case image show shows shown seen following best answer choice option select""".split())


def tokenize(text):
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


# Concrete findings a question or a skill can be about. Used only to decide
# whether a skill is on-topic; it is not a label, it is read from visible text.
TOPICS = {
    "effusion": ("effusion", "pleural fluid"),
    "pneumothorax": ("pneumothorax",),
    "consolidation": ("consolidation", "consolidative"),
    "atelectasis": ("atelectasis", "collapse"),
    "nodule": ("nodule", "nodules", "nodular"),
    "mass": ("mass", "masses"),
    "opacity": ("opacity", "opacities", "infiltrate", "infiltration"),
    "cardiomegaly": ("cardiomegaly", "enlarged heart", "cardiac enlargement"),
    "edema": ("edema",),
    "fibrosis": ("fibrosis", "fibrotic"),
    "pneumonia": ("pneumonia",),
    "fracture": ("fracture",),
    "hernia": ("hernia",),
    "emphysema": ("emphysema", "hyperinflation"),
    "catheter_or_device": ("catheter", "pacemaker", "stent", "line", "tube", "device"),
}


def _topic_tags(text):
    lowered = (text or "").lower()
    return {name for name, variants in TOPICS.items() if any(v in lowered for v in variants)}


def _skill_text(skill):
    parts = [str(skill.get("trigger") or "")]
    parts += [str(x) for x in (skill.get("required_information") or [])]
    parts += [str(x) for x in (skill.get("required_capabilities") or [])]
    parts += [str(x) for x in (skill.get("task_types") or [])]
    parts += [str(x) for x in (skill.get("avoid") or [])]
    for action in (skill.get("actions") or []):
        if isinstance(action, dict):
            parts.append(str(action.get("operation") or ""))
            parts.append(str(action.get("capability") or ""))
    return " ".join(parts)


class SkillIndex:
    """BM25 over skill text, same shape as the memory retriever."""

    def __init__(self, skills, k1=1.5, b=0.75):
        self.skills = [s for s in skills if isinstance(s, dict)]
        self.k1, self.b = k1, b
        self._docs = [tokenize(_skill_text(s)) for s in self.skills]
        self._avg = (sum(len(d) for d in self._docs) / len(self._docs)) if self._docs else 0.0
        self._df = Counter()
        for doc in self._docs:
            for word in set(doc):
                self._df[word] += 1

    def search(self, question, top_k=3, min_score=0.0, topic_filter=False):
        """Rank skills for a question.

        `topic_filter=True` keeps only skills that share at least one concrete
        finding with the question. Measured need: without it, 6 of 29 frozen
        validation questions received a skill about a *different* finding
        (e.g. a nodule question got an "atelectasis/consolidation" skill),
        because BM25 matches the generic vocabulary in every trigger. A skill
        about the wrong finding is worse than no skill, so the default for the
        C arm should be to filter rather than to fill the slot.
        """
        if not self.skills:
            return []
        query = set(tokenize(question))
        question_topics = _topic_tags(question)
        n = len(self._docs)
        scored = []
        for skill, doc in zip(self.skills, self._docs):
            if topic_filter:
                if question_topics and not (question_topics & _topic_tags(_skill_text(skill))):
                    continue
            counts = Counter(doc)
            score = 0.0
            for word in query:
                count = counts[word]
                if not count:
                    continue
                idf = math.log(1 + (n - self._df[word] + 0.5) / (self._df[word] + 0.5))
                score += idf * count * (self.k1 + 1) / (
                    count + self.k1 * (1 - self.b + self.b * len(doc) / (self._avg or 1)))
            if score > 0 and score >= min_score:
                scored.append((score, skill))
        scored.sort(key=lambda pair: (-pair[0], pair[1].get("skill_id", "")))
        return [skill for _score, skill in scored[:top_k]]


# --------------------------------------------------------------------------- D
@dataclass
class AgentState:
    required_information: list = field(default_factory=list)
    observations: list = field(default_factory=list)          # {tool, attribute, value, source}
    missing_information: list = field(default_factory=list)
    comparable_conflicts: list = field(default_factory=list)  # {finding, attribute, a, b}
    available_actions: list = field(default_factory=list)     # capabilities still callable
    active_skill: dict | None = None
    applicable_branch: str | None = None
    remaining_tool_calls: int = 0
    remaining_seconds: float = 0.0

    def observe(self, tool, attribute, value, source="tool_statement"):
        self.observations.append({"tool": tool, "attribute": attribute,
                                  "value": value, "source": source})

    def refresh_gaps(self):
        """Recompute what is still missing from the required information list."""
        got = {str(o["attribute"]) for o in self.observations if o.get("value") is not None}
        self.missing_information = [r for r in self.required_information if str(r) not in got]


def detect_conflicts(observations):
    """Only same finding + same attribute can conflict; absence is not evidence."""
    by_key = {}
    for obs in observations:
        key = (str(obs.get("attribute")), str(obs.get("finding")))
        if obs.get("value") is None:
            continue
        by_key.setdefault(key, []).append(obs)
    conflicts = []
    for (attribute, finding), items in by_key.items():
        values = {str(i["value"]) for i in items}
        if len(values) > 1:
            conflicts.append({"finding": finding, "attribute": attribute,
                              "a": f"{items[0]['tool']}={items[0]['value']}",
                              "b": f"{items[-1]['tool']}={items[-1]['value']}"})
    return conflicts


def decide(state, capability_actions, has_roi_box=False):
    """Choose the next operation from the explicit state.

    `capability_actions` maps a capability to the tool that provides it and is
    still callable. Returns (operation, detail).
    """
    state.refresh_gaps()
    state.comparable_conflicts = detect_conflicts(state.observations)

    if state.remaining_tool_calls <= 0 or state.remaining_seconds <= 1.0:
        return "stop_with_uncertainty", {"reason": "budget_exhausted",
                                         "missing": list(state.missing_information)}
    if not state.missing_information:
        return "answer", {"reason": "required_information_satisfied"}
    if state.comparable_conflicts:
        # a real conflict on the required attribute: try an independent tool, else stop.
        alternative = _first_unused(state, capability_actions)
        if alternative:
            return "call_tool", {"reason": "resolve_conflict", "capability": alternative}
        return "stop_with_uncertainty", {"reason": "conflict_unresolved",
                                         "conflicts": state.comparable_conflicts}
    if has_roi_box and state.applicable_branch == "needs_local_review":
        return "local_reinspection", {"reason": "gap_is_local",
                                      "missing": list(state.missing_information)}
    alternative = _first_unused(state, capability_actions)
    if alternative:
        return "call_tool", {"reason": "fill_missing_information", "capability": alternative}
    return "stop_with_uncertainty", {"reason": "no_available_action_adds_information"}


def _first_unused(state, capability_actions):
    used = {str(o.get("tool")) for o in state.observations}
    for capability in sorted(capability_actions):
        tool = capability_actions[capability]
        if tool not in used:
            return capability
    return None


# ------------------------------------------------------- continuation prefix
PREFIX_HEADER = (
    "You are resuming a chest X-ray tool-using episode at a fixed point. "
    "Below are the observations already obtained in this episode, in order. "
    "Treat them as facts you observed yourself. Continue from here."
)


def render_prefix(prefix_observations, facts_chars=280):
    """The visible prefix as an ordered, quotable transcript."""
    lines = []
    for index, obs in enumerate(prefix_observations or [], 1):
        facts = json.dumps(obs.get("facts"), ensure_ascii=False, default=str)
        status = obs.get("execution_status")
        lines.append(f"{index}. {obs.get('tool')} [{status}] {facts[:facts_chars]}")
    return "\n".join(lines) if lines else "(no tool observation has been obtained yet)"


def branch_messages(question, prefix_observations, *, skill_block=None,
                    branch_observation=None, branch_note=None):
    """Chat messages for a replay continuation.

    `branch_observation` is the observation produced by the branch under test -
    present for do_action, absent for skip_action. It is appended, never
    invented: a branch that did not execute must not receive a fabricated
    observation.
    """
    sections = [PREFIX_HEADER, "", f"QUESTION: {question}", "",
                "OBSERVATIONS SO FAR:", render_prefix(prefix_observations)]
    if branch_observation is not None:
        sections += ["", "NEW OBSERVATION:",
                     f"{branch_observation.get('tool')} -> "
                     f"{json.dumps(branch_observation.get('facts'), ensure_ascii=False, default=str)[:400]}"]
    if branch_note:
        sections += ["", f"NOTE: {branch_note}"]
    if skill_block:
        sections += ["", skill_block]
    sections += ["", "Give your best answer to the question now, or say plainly what is still "
                     "unknown if the observations do not settle it."]
    return [{"role": "user", "content": "\n".join(sections)}]
