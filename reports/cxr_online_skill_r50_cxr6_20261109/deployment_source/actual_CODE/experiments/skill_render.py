"""V4 C: render distilled skills compactly for injection.

Storage keeps the full skill; injection must be small. The block mirrors the
existing memory block convention so B and C can be compared on the same
character budget (the plan's 1400-character default).

Nothing here adds advice that is not in the skill: an empty field is omitted
rather than filled with generic encouragement.
"""

from __future__ import annotations

CAPABILITY_TOOLS = {
    "image_classification": "chest_xray_classifier",
    "report_generation": "chest_xray_report_generator",
    "chest_xray_vqa": "chest_xray_expert",
    "biomedical_vqa": "llava_med_qa",
    "visual_localization": "xray_phrase_grounding",
    "segmentation_or_measurement": "chest_xray_segmentation",
    "image_display_or_crop": "image_visualizer",
    "dicom_conversion": "dicom_processor",
}


def render_skill(skill):
    """One skill as a few dense lines."""
    parts = [f"[SKILL {skill.get('skill_id', '?')}]"]
    if skill.get("task_types"):
        parts[0] += f" tasks={','.join(skill['task_types'])}"
    if skill.get("trigger"):
        parts.append(f"trigger: {skill['trigger']}")
    if skill.get("required_information"):
        parts.append("need: " + "; ".join(str(x) for x in skill["required_information"]))
    actions = []
    for action in (skill.get("actions") or []):
        cap = action.get("capability")
        tool = CAPABILITY_TOOLS.get(cap)
        if tool:
            actions.append(f"{action.get('operation', 'select')} -> {tool}")
        else:
            actions.append(str(action.get("operation")))
    if actions:
        parts.append("do: " + "; ".join(actions))
    if skill.get("checkpoints"):
        parts.append("check: " + "; ".join(str(x) for x in skill["checkpoints"]))
    fallbacks = []
    for fallback in (skill.get("fallbacks") or []):
        if isinstance(fallback, dict):
            fallbacks.append(f"if {fallback.get('when')}: {fallback.get('operation')}")
    if fallbacks:
        parts.append("fallback: " + "; ".join(fallbacks))
    if skill.get("stop_conditions"):
        parts.append("stop: " + "; ".join(str(x) for x in skill["stop_conditions"]))
    if skill.get("avoid"):
        parts.append("avoid: " + "; ".join(str(x) for x in skill["avoid"]))
    parts.append("(skill recorded from training trajectories; clinical contribution unverified)")
    return "\n".join(parts)


def render_block(skills, max_chars=1400):
    """Several skills as one bounded block, richest first, never truncated midline."""
    if not skills:
        return ""
    header = ("[REUSABLE TOOL SKILLS - operating experience, not verified clinical rules]\n"
              "Apply only when the stated trigger matches the current case.\n")
    budget = max_chars - len(header)
    if budget <= 0:
        return ""
    chosen, used = [], 0
    for skill in skills:
        text = render_skill(skill)
        if used + len(text) + 2 > budget:
            continue
        chosen.append(text)
        used += len(text) + 2
    if not chosen:
        # even one skill does not fit: emit a hard-trimmed single skill rather than nothing
        text = render_skill(skills[0])[:budget]
        return header + text
    return header + "\n\n".join(chosen)


def skill_features(skill):
    """Coarse retrieval features for a skill, matching the memory feature style."""
    features = set(skill.get("task_types") or [])
    for capability in (skill.get("required_capabilities") or []):
        features.add(str(capability))
    for action in (skill.get("actions") or []):
        if isinstance(action, dict) and action.get("capability"):
            features.add(str(action["capability"]))
    return sorted(features)
