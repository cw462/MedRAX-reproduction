"""R6: detect contradictory claims between two tools on the same image.

The paper's case studies describe MedRAX "resolving conflicting tool
suggestions". Today the agent sees raw tool outputs and is never told that two
tools disagree, so any resolution is accidental. This module makes the conflict
explicit so the runner can put it in front of the model.

Scope and honesty
-----------------
* The classifier emits operating-point-normalised scores, which are NOT
  calibrated disease probabilities (see reports/classifier-score-semantics.md).
  Turning them into a claim therefore needs an explicit operating point; the
  threshold here is a declared heuristic and is recorded in the rendered block.
* Report text is parsed with negation rules, not NLP. Unparsed text yields no
  claim, never a guessed one: absence of a claim is reported as unknown.
* A detected conflict is not a clinical label. It only says "these two tool
  outputs pull in opposite directions", which is exactly what the model is being
  asked to adjudicate.
"""

from __future__ import annotations

import re

# torchxrayvision's 18 output labels, plus the words radiologists actually write.
PATHOLOGIES = {
    "atelectasis": ("atelectasis", "collapse", "volume loss"),
    "cardiomegaly": ("cardiomegaly", "enlarged heart", "cardiac enlargement", "heart is enlarged"),
    "consolidation": ("consolidation", "consolidative"),
    "edema": ("edema", "pulmonary edema", "interstitial edema"),
    "effusion": ("effusion", "pleural fluid"),
    "emphysema": ("emphysema", "hyperinflation"),
    "fibrosis": ("fibrosis", "fibrotic"),
    "hernia": ("hernia", "hiatal"),
    "infiltration": ("infiltrate", "infiltration", "infiltrates"),
    "mass": ("mass", "masses"),
    "nodule": ("nodule", "nodules", "nodular"),
    "pleural_thickening": ("pleural thickening", "pleural capping"),
    "pneumonia": ("pneumonia", "infectious", "airspace disease"),
    "pneumothorax": ("pneumothorax", "pneumothoraces", "lung collapse"),
    "fracture": ("fracture", "fractures", "fractured"),
    "lung_lesion": ("lung lesion", "lesion", "lesions"),
    "enlarged_cardiomediastinum": ("widened mediastinum", "mediastinal widening", "cardiomediastinal"),
    "normal": ("no acute", "unremarkable", "normal chest"),
}

NEGATION_RE = re.compile(
    r"\b(?:no|not|without|negative\s+for|free\s+of|clear\s+of|denies|resolved|absent|"
    r"unremarkable)\b", re.IGNORECASE)
# Checked before negation: "cannot exclude X" contains "not", and a naive
# substring test would invert an uncertain finding into a denial.
UNCERTAIN_RE = re.compile(
    r"cannot\s+(?:exclude|be\s+excluded)|can\s+not\s+exclude|possible|may\s+represent|"
    r"questionable|suspicious\s+for|probable|likely", re.IGNORECASE)


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.;:])\s+|\n+", text or "") if s.strip()]


def report_claims(text, window=90):
    """pathology -> 'present' | 'uncertain' | 'absent' from free report text.

    When several sentences mention the same finding, the strongest verdict wins:
    present > uncertain > absent. That precedence is a declared rule, not a
    clinical judgement.
    """
    rank = {"absent": 0, "uncertain": 1, "present": 2}
    lowered = (text or "").lower()
    claims = {}
    for pathology, variants in PATHOLOGIES.items():
        verdict = None
        for sentence in _sentences(lowered):
            for variant in variants:
                index = sentence.find(variant)
                if index < 0:
                    continue
                prefix = sentence[max(0, index - window):index]
                suffix = sentence[index:index + window]
                if UNCERTAIN_RE.search(prefix) or UNCERTAIN_RE.search(suffix):
                    candidate = "uncertain"
                elif NEGATION_RE.search(prefix):
                    candidate = "absent"
                else:
                    candidate = "present"
                if verdict is None or rank[candidate] > rank[verdict]:
                    verdict = candidate
        if verdict is not None:
            claims[pathology] = verdict
    return claims


def classifier_claims(scores, threshold=0.6):
    """pathology -> 'present' | 'absent' from operating-point-normalised scores.

    `scores` maps pathology name to a score in [0, 1]. The threshold is a
    declared operating point, not a probability cut. Scores inside the
    ambiguous band produce no claim at all rather than a guess.
    """
    if not 0.5 < threshold <= 1.0:
        raise ValueError("threshold must be in (0.5, 1.0] so the ambiguous band is empty or real")
    claims = {}
    for pathology, score in (scores or {}).items():
        key = pathology.strip().lower().replace(" ", "_")
        if key not in PATHOLOGIES:
            continue
        try:
            value = float(score)
        except (TypeError, ValueError):
            continue
        if value >= threshold:
            claims[key] = "present"
        elif value <= 1.0 - threshold:
            claims[key] = "absent"
    return claims


def find_conflicts(claims_a, claims_b, label_a="chest_xray_classifier",
                   label_b="chest_xray_report_generator"):
    """Pairs where one side says present and the other says absent."""
    conflicts = []
    for pathology in sorted(set(claims_a) & set(claims_b)):
        a, b = claims_a[pathology], claims_b[pathology]
        if {a, b} == {"present", "absent"}:
            conflicts.append({"pathology": pathology, "present_in": label_a if a == "present" else label_b,
                              "absent_in": label_b if a == "present" else label_a,
                              "verdict": "contradiction"})
    return conflicts


def render_review(conflicts, threshold, max_items=4):
    """A compact block for the model, or '' when there is nothing to review."""
    if not conflicts:
        return ""
    lines = ["[TOOL CONFLICT - resolve explicitly before answering]"]
    for item in conflicts[:max_items]:
        lines.append(f"- {item['pathology']}: {item['present_in']} reports present, "
                     f"while {item['absent_in']} reports absent.")
    if len(conflicts) > max_items:
        lines.append(f"- (+{len(conflicts) - max_items} further conflicting findings)")
    lines.append(f"(classifier claims use the declared operating point {threshold:.2f}; "
                 "scores are not calibrated probabilities)")
    return "\n".join(lines)
