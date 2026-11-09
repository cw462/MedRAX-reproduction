"""V4 C: distill semantic skills from real training trajectories.

Input is what `semantic_trace.py` recorded during a real run: for each case, the
question, the ordered tool calls with their observed facts, and the independent
task outcome. Output is one JSON skill per source trajectory (the plan's default
until representation and data changes are separated).

Ground rules taken from the plan:
  * a skill must be conditional and actionable ("trigger -> action -> check"),
    never "analyse carefully" or "use appropriate tools";
  * answer letters, option text and the source patient's final diagnosis are not
    instructions for future patients;
  * final correctness is not evidence of medical correctness, so
    `evidence_status` stays "unverified_clinical_contribution" and
    `step_credit` stays null at distillation time;
  * capability aliases must map to tools that are actually deployed.

Everything is recorded with its source trace id so a skill can be audited back to
the real run it came from.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# capability -> deployed tool names that can actually provide it
CAPABILITIES = {
    "image_classification": ["chest_xray_classifier"],
    "report_generation": ["chest_xray_report_generator"],
    "chest_xray_vqa": ["chest_xray_expert"],
    "biomedical_vqa": ["llava_med_qa"],
    "visual_localization": ["xray_phrase_grounding"],
    "segmentation_or_measurement": ["chest_xray_segmentation"],
    "image_display_or_crop": ["image_visualizer"],
    "dicom_conversion": ["dicom_processor"],
}

TASK_TYPES = ["detection", "classification", "localization", "comparison",
              "relationship", "diagnosis", "characterization"]

SYSTEM_PROMPT = """You summarize reusable tool-use skills from observed training trajectories.
Return JSON with a concrete trigger, required information, actionable operations,
checkpoints, fallback branches, stop conditions, and provenance.
Separate observed facts, task outcomes, and hypotheses about why an action helped.
Do not copy answer letters, option-specific conclusions, identities, or the source
patient's final diagnosis as an instruction for future patients.
Do not infer medical correctness or step contribution from final correctness alone.
If a failure cause is uncertain, mark it as a hypothesis and suggest an observable check.
Write in concise English for consistency with the benchmark prompts."""

USER_TEMPLATE = """One observed trajectory from a chest X-ray tool-using agent.

QUESTION (may be truncated):
{question}

TRACE (ordered; each line is a tool call and the semantic content it returned):
{trace}

INDEPENDENT TASK OUTCOME: {outcome}

Produce ONE skill as a JSON object with exactly these keys:
skill_id (leave "TBD"), task_types (subset of {task_types}),
trigger (a concrete observable condition, not "the question is hard"),
required_information (list), required_capabilities (subset of {capabilities}),
actions (list of objects with action_id, operation, capability),
checkpoints (list of checks that decide whether the action actually produced the
needed information), fallbacks (list of objects with when and operation),
stop_conditions (list), avoid (list of specific mistakes this trajectory shows),
source_trace_ids (["{qid}"]), evidence_status ("unverified_clinical_contribution"),
step_credit (null).
Do not invent tools outside the capability list. Do not restate the question's
options. If the trajectory shows no reusable lesson, say so in "trigger" by
returning the single string "NO_REUSABLE_SKILL" for skill_id."""

BANNED = ("analize carefully", "analyze carefully", "use appropriate tools",
          "think step by step", "carefully examine", "use the right tool")


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()]


def compact_trace(rows, limit=6, facts_chars=280):
    lines = []
    for index, row in enumerate(rows[:limit], 1):
        obs = row.get("observation") or {}
        facts = json.dumps(obs.get("facts"), ensure_ascii=False)
        lines.append(f"{index}. {row['tool_name']} [{obs.get('execution_status')}] {facts[:facts_chars]}")
    if len(rows) > limit:
        lines.append(f"... {len(rows) - limit} further calls omitted")
    return "\n".join(lines) if lines else "(no tool calls recorded)"


def validate_skill(skill):
    """Reject vague or ungrounded output rather than storing it."""
    problems = []
    if not isinstance(skill, dict):
        return ["not a JSON object"]
    trigger = str(skill.get("trigger", "")).strip()
    if len(trigger) < 20:
        problems.append("trigger too short")
    if any(bad in trigger.lower() for bad in BANNED):
        problems.append("trigger is generic advice")
    caps = skill.get("required_capabilities")
    if not isinstance(caps, list) or not caps:
        problems.append("no required_capabilities")
    else:
        unknown = [c for c in caps if c not in CAPABILITIES]
        if unknown:
            problems.append(f"unknown capabilities {unknown}")
    actions = skill.get("actions")
    if not isinstance(actions, list) or not actions:
        problems.append("no actions")
    else:
        for action in actions:
            if not isinstance(action, dict) or action.get("capability") not in CAPABILITIES:
                problems.append("action capability not deployed")
                break
    if not isinstance(skill.get("checkpoints"), list) or not skill["checkpoints"]:
        problems.append("no checkpoints")
    if skill.get("evidence_status") != "unverified_clinical_contribution":
        problems.append("evidence_status must stay unverified_clinical_contribution")
    if skill.get("step_credit") is not None:
        problems.append("step_credit must be null at distillation")
    return problems


def assign_task_types(question, declared):
    """Use the model's labels but keep only known ones; record if empty."""
    kept = [t for t in (declared or []) if t in TASK_TYPES]
    return kept or ["detection"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--outcomes", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--inherit-ledger", type=Path, required=True)
    parser.add_argument("--profile", default="qwen3-vl-plus")
    parser.add_argument("--cap-cny", default="1000000")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--api-key-stdin", action="store_true")
    args = parser.parse_args(argv)

    traces = defaultdict(list)
    for row in load_jsonl(args.traces):
        traces[row["question_id"]].append(row)
    outcome_of = {o["question_id"]: o["task_outcome"]
                  for o in json.loads(args.outcomes.read_text(encoding="utf-8"))["outcomes"]}
    question_of = {row["question_id"]: row["question"] for row in load_jsonl(args.questions)}

    qids = [q for q in traces if q in outcome_of]
    qids.sort(key=lambda q: (outcome_of[q] != "correct", q))   # successes first, per plan 6.1
    if args.limit:
        qids = qids[:args.limit]
    print(f"cases with traces: {len(traces)} | scored: {len(outcome_of)} | distilling: {len(qids)}")

    key = sys.stdin.readline().strip() if args.api_key_stdin else ""
    if not key:
        raise SystemExit("api key required on stdin")
    import os
    os.environ["OPENAI_API_KEY"] = key

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from langchain_openai import ChatOpenAI
    import provider_ledger
    from provider_profile import get_profile

    profile = get_profile(args.profile)
    ledger = provider_ledger.ProviderLedger(args.ledger, profile, cap_cny=args.cap_cny,
                                            inherit_ledger_path=args.inherit_ledger)
    model = ChatOpenAI(model=profile.model, base_url=profile.base_url, api_key=key,
                       temperature=0.2, max_tokens=900)

    skills, rejected = [], []
    with ledger:
        for qid in qids:
            prompt = USER_TEMPLATE.format(
                question=question_of.get(qid, "")[:900],
                trace=compact_trace(traces[qid]),
                outcome=outcome_of[qid],
                task_types=TASK_TYPES,
                capabilities=sorted(CAPABILITIES),
                qid=qid)
            try:
                reply = model.invoke([("system", SYSTEM_PROMPT), ("human", prompt)])
                text = reply.content if isinstance(reply.content, str) else str(reply.content)
                match = re.search(r"\{.*\}", text, re.S)
                if not match:
                    rejected.append({"question_id": qid, "reason": "no JSON in reply"})
                    continue
                skill = json.loads(match.group(0))
            except Exception as exc:
                rejected.append({"question_id": qid, "reason": f"{type(exc).__name__}: {exc}"})
                continue
            if skill.get("skill_id") == "NO_REUSABLE_SKILL":
                rejected.append({"question_id": qid, "reason": "model judged no reusable skill"})
                continue
            problems = validate_skill(skill)
            if problems:
                rejected.append({"question_id": qid, "reason": "; ".join(problems)})
                continue
            skill["skill_id"] = f"S{len(skills) + 1:03d}"
            skill["task_types"] = assign_task_types(question_of.get(qid, ""), skill.get("task_types"))
            skill["source_trace_ids"] = [qid]
            skill["source_outcome"] = outcome_of[qid]
            skill["skill_version"] = "v0"
            skills.append(skill)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "skill_version": "v0",
        "source_run": str(args.traces.parent.name),
        "source_traces": len(traces),
        "distilled": len(skills),
        "rejected": len(rejected),
        "rejection_reasons": dict(Counter(r["reason"].split(":")[0] for r in rejected)),
        "skills": skills,
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"distilled {len(skills)} skills, rejected {len(rejected)} -> {args.out}")
    print("rejection reasons:", payload["rejection_reasons"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
