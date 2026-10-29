"""V4 orchestrator: drive S0-S4 stages in order, resumable, no silent skipping.

Usage:
  python experiments/run_skill_validation.py --config configs/skill_validation_v4.yaml \
      --stage all --resume

Stages
  collect  run the semantic-trace collection arms (S1)
  distill  turn the collected traces into skills v0 (C representation)
  validate run A/B/C on the fixed validation questions (S0 pilot, then S2)
  replay   build tool-step replay checkpoints and branch plans (S4 planning)
  report   write reports/skill_v4_validation.md from what actually finished

A stage that is not implemented yet fails loudly with the reason instead of
reporting success, and `--resume` skips only stages whose output artefact already
exists. Heldout (S5) is refused here: the config disables it until the user
authorises that spend separately.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # .../MedRAX_reproduction_20261027
CODE = ROOT / "code"
EXPERIMENTS = CODE / "experiments"
RUNS = ROOT / "runs"
REPORTS = ROOT / "reports"


# ----------------------------------------------------------------- config
def load_flat_yaml(path):
    """Tiny loader for the flat `key: value` / `key: [a, b]` config used here."""
    config = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            config[key] = [v.strip() for v in inner.split(",") if v.strip()] if inner else []
        elif value.lower() in ("true", "false"):
            config[key] = value.lower() == "true"
        else:
            try:
                config[key] = int(value)
            except ValueError:
                try:
                    config[key] = float(value)
                except ValueError:
                    config[key] = value
    return config


# ----------------------------------------------------------------- helpers
def run(cmd, log_path, label):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n=== {label}: {' '.join(str(c) for c in cmd)}\n")
        log.flush()
        proc = subprocess.run([str(c) for c in cmd], stdout=log, stderr=subprocess.STDOUT)
    return proc.returncode


def stage_done(marker):
    return Path(marker).exists()


# ----------------------------------------------------------------- stages
def stage_collect(config, resume):
    run_dir = RUNS / "v4_collect60"
    if resume and stage_done(run_dir / "summary.json"):
        return "skipped (already collected)"
    script = CODE / "v4_collect60.sh"
    if not script.exists():
        return "MISSING CODE: v4_collect60.sh"
    code = run(["bash", script], ROOT / "logs/v4_orchestrator.log", "collect")
    return "ok" if code == 0 else f"failed with exit {code}"


def stage_distill(config, resume):
    skills = RUNS / "skills_v0" / "skills.json"
    if resume and stage_done(skills):
        return "skipped (skills v0 already distilled)"
    traces = RUNS / "v4_collect60" / "semantic_trace.jsonl"
    outcomes = RUNS / "v4_collect60_scored" / "outcomes.json"
    questions = ROOT / "data/memory_v1/inputs/memory_train_subset_v1.jsonl"
    if not traces.exists() or not outcomes.exists():
        return "blocked: collection or scoring not finished"
    repo_py = subprocess.run([str(ROOT / ".venv/bin/python"), "--version"],
                             capture_output=True, text=True)
    if repo_py.returncode != 0:
        return "blocked: server venv python not found"
    key_path = Path("/tmp/.qwen_key")
    if not key_path.exists():
        return "blocked: /tmp/.qwen_key missing"
    cmd = (f"cat /tmp/.qwen_key | {ROOT}/.venv/bin/python {EXPERIMENTS}/skill_distill.py "
           f"--traces {traces} --outcomes {outcomes} --questions {questions} "
           f"--out {skills} --ledger {REPORTS}/api_budget_qwen_100cny_v8.json "
           f"--inherit-ledger {REPORTS}/api_budget_qwen_100cny_v7.json --api-key-stdin")
    code = run(["bash", "-lc", cmd], ROOT / "logs/v4_orchestrator.log", "distill")
    return "ok" if code == 0 else f"failed with exit {code}"


def stage_validate(config, resume):
    skills = RUNS / "skills_v0" / "skills.json"
    if not skills.exists():
        return "blocked: no skills v0 yet"
    # The validated arms need the multi-arm runner, which is not written yet; do not pretend.
    return ("NOT IMPLEMENTED: the A/B/C validation runner for a fixed 60-case set is not written "
            "yet. Existing per-arm shell entry points can run one arm at a time, but there is no "
            "orchestrator that fixes the case list, randomises arm order and repeats 3 rounds.")


def stage_replay(config, resume):
    traces = RUNS / "v4_collect60" / "semantic_trace.jsonl"
    if not traces.exists():
        return "blocked: no traces yet"
    sys.path.insert(0, str(EXPERIMENTS))
    import tool_step_replay as replay          # noqa: E402
    rows = [json.loads(line) for line in traces.read_text(encoding="utf-8").splitlines() if line.strip()]
    plans = replay.plan_replays(replay.group_by_question(rows),
                                max_states=int(config.get("credit_states", 20)))
    out = RUNS / "v4_replay_plan.json"
    out.write_text(json.dumps({"planned_states": len(plans), "plans": plans}, ensure_ascii=False,
                              indent=1) + "\n", encoding="utf-8")
    return (f"planned {len(plans)} checkpoints -> {out}. Executing do/skip/alternate replays needs a "
            "continuation runner that is not written yet; the plan file is real, the executions are not.")


def stage_report(config, resume):
    lines = ["# V4 skill validation", "",
             "Status is generated from finished artefacts only.", ""]
    rows = []
    for name, label in (("v4_collect60", "S1 collection"),
                        ("val8b_r0", "A baseline (released budget)"),
                        ("val8b_r1", "B frozen retriever"),
                        ("val8b_r5", "R5 text retriever"),
                        ("val8b_r57", "R5+R7")):
        score = RUNS / f"{name}_scored" / "score.json"
        if score.exists():
            data = json.loads(score.read_text(encoding="utf-8"))
            rows.append((label, data.get("graded_denominator"),
                         round((data.get("accuracy_among_all_planned") or 0) * 29)))
        else:
            rows.append((label, "-", "-"))
    lines.append("| run | graded | correct (of 29) |")
    lines.append("|---|---:|---:|")
    for label, graded, correct in rows:
        lines.append(f"| {label} | {graded} | {correct} |")
    skills = RUNS / "skills_v0" / "skills.json"
    lines.append("")
    if skills.exists():
        payload = json.loads(skills.read_text(encoding="utf-8"))
        lines.append(f"Skills v0: {payload.get('distilled')} distilled, "
                     f"{payload.get('rejected')} rejected of {payload.get('source_traces')} traces.")
        lines.append("")
        lines.append("NOTE: C/D/E arms have not run, so this table is not a method comparison.")
    else:
        lines.append("Skills v0: not distilled yet.")
    lines.append("")
    lines.append("Heldout (S5) is deliberately not run.")
    out = REPORTS / "skill_v4_validation.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f"wrote {out}"


STAGES = [("collect", stage_collect), ("distill", stage_distill),
          ("validate", stage_validate), ("replay", stage_replay),
          ("report", stage_report)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--stage", default="all",
                    choices=["all"] + [name for name, _ in STAGES])
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args(argv)

    config = load_flat_yaml(args.config)
    if config.get("heldout_enabled") is True:
        raise SystemExit("refusing to run: this orchestrator does not implement heldout (S5)")
    print(f"config: {args.config} -> {len(config)} keys")
    chosen = STAGES if args.stage == "all" else [s for s in STAGES if s[0] == args.stage]
    results = {}
    for name, fn in chosen:
        try:
            results[name] = fn(config, args.resume)
        except Exception as exc:                      # record, never swallow silently
            results[name] = f"error: {type(exc).__name__}: {exc}"
        print(f"[{name}] {results[name]}")
    summary = REPORTS / "skill_v4_stage_log.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    failed = [k for k, v in results.items() if not str(v).startswith(("ok", "skipped", "planned", "wrote"))]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
