"""V7: recovery experiment. P0 -> P1/PB/PC -> GB/GC on the same real prefix.

Design (from the V7 plan):

  P0  the no-memory agent answers normally. Its checkpointer thread holds the real
      multimodal prefix: question text, images (as data URLs), every tool call and
      observation, in order.
  P1  same prefix, no cross-case memory: one more targeted verification pass.
  PB  same prefix + the B-style structural-memory block, same budget as P1.
  PC  same prefix + the C-style skill block, same budget as P1.
  GB/GC  a gate call that sees P0's answer, the candidate answer, the attributes that
      differ, and the branch's new observations; it may only accept or retain.

Every branch is a new thread seeded with a copy of P0's message list, so no branch can
contaminate another and none of them re-pays for the prefix.

This module deliberately does not re-implement tool tracking: it borrows
`BudgetedModel`, `TrackedTool`, `CaseBudget` and `initial_messages` from
`memory_agent_eval`, so cost accounting and image authorisation stay in one place.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next((p for p in (HERE.parent, HERE.parent.parent)
             if (p / "data" / "memory_v1").exists() or (p / "source" / "MedRAX").exists()),
            HERE.parent)
sys.path.insert(0, str(HERE))


def load_config(path):
    cfg = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            cfg[key] = [v.strip() for v in value[1:-1].split(",") if v.strip()]
        elif value.lower() in ("true", "false"):
            cfg[key] = value.lower() == "true"
        else:
            try:
                cfg[key] = int(value)
            except ValueError:
                try:
                    cfg[key] = float(value)
                except ValueError:
                    cfg[key] = value
    return cfg


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()]


def options_of(question):
    out, current = {}, None
    for line in question.splitlines():
        m = re.match(r"^([A-F])\)\s*(.*)$", line.strip())
        if m:
            current = m.group(1)
            out[current] = m.group(2).strip()
        elif current and line.strip():
            out[current] += " " + line.strip()
    return out


def letter_of(text):
    from diagnostic_eval import smoke
    return smoke.answer_letter(text), smoke.summarize(text)


# --------------------------------------------------------------------------- context
def new_ctx(question_id, thread_id, paths, runtime, args, trace, max_tool, max_model):
    """The subset of run_arm's context that BudgetedModel/TrackedTool/CaseBudget need."""
    import diagnostic_eval as diag
    ctx = {'question_id': question_id, 'arm': 'agent', 'thread_id': thread_id,
           'run_id': 'bc_recovery', 'phase': 0, 'issues': set(), 'usage_records': [],
           'ledger_settlements': [], 'actual_model_calls': 0, 'actual_tool_attempts': 0,
           'validated_tool_returns': 0, 'failed_tool_returns': 0, 'repeated_tool_calls': 0,
           'allowed_images': set(paths), 'tool_fingerprints': set(), 'stop_run': False,
           'last_finish_reason': None, 'max_output_tokens': args.max_output_tokens,
           'allowed_tool_names': set(runtime.tools),
           'tool_counts': {name: dict(requested=0, attempted=0, validated_returns=0,
                                      failed_returns=0, exceptions=0, repeated=0)
                           for name in runtime.tools}}
    ctx['trace'] = diag.TaggedTrace(trace, ctx)
    ctx['semantic_writer'] = None
    ctx['budget'] = diag.smoke.CaseBudget(max_tool, max_model, args.max_case_seconds, ctx['trace'])
    ctx['budget'].case_hash = diag.hash_value(question_id)
    ctx['budget'].thread_id = thread_id
    return ctx


def make_agent(runtime, ledger, ctx, profile, model_override=None):
    from memory_agent_eval import BudgetedModel, TrackedTool
    agent = runtime.Agent(runtime.model, tools=list(runtime.tools.values()),
                          checkpointer=runtime.MemorySaver(),
                          system_prompt=runtime.agent_system, log_tools=False)
    agent.model = BudgetedModel(agent.model, ledger, ctx, profile)
    agent.tools = {name: TrackedTool(tool, runtime.tool_provenance[name], ctx)
                   for name, tool in runtime.tools.items()}
    return agent


def stream_once(agent, ctx, batch, thread_id, recursion_limit, events):
    """Run the graph one batch and return the last assistant text."""
    final = None
    for step in agent.workflow.stream({'messages': batch},
                                      {'configurable': {'thread_id': thread_id},
                                       'recursion_limit': recursion_limit}):
        for node, values in step.items():
            for message in values.get('messages', []):
                if node == 'process' and not (getattr(message, 'tool_calls', None) or []):
                    final = message.content
                elif node == 'execute':
                    events.append({'tool_name': getattr(message, 'name', None),
                                   'tool_call_id': getattr(message, 'tool_call_id', None)})
    return final


# --------------------------------------------------------------------------- prompts
P1_PROMPT = (
    "Before you finalize: re-examine the single finding your answer depends on most. "
    "You may make at most {tool_budget} tool call(s) to check it on this case's images. "
    "Then give your final answer letter again. If the new evidence does not settle it, "
    "keep your earlier answer; do not change it just to change it."
)

# Same willingness to name a candidate as PROPOSE_PROMPT, so P1 and PB/PC differ only in
# whether the experience is present.
PROPOSE_P1 = (
    "Before you finalize: re-examine the single finding your answer depends on most. You may "
    "make at most {tool_budget} tool call(s) to check it on this case's images. Then state the "
    "single option letter you would answer if that re-check is right, even when it differs "
    "from your earlier answer. If nothing new is visible, keep your earlier answer. End with "
    "the letter alone."
)

MEMORY_PROMPT = (
    "Operating experience from other training cases is below. It is not evidence about "
    "this patient; it only suggests what is worth checking. If it applies, use it to pick "
    "at most {tool_budget} targeted check(s) on this case's images, then give your final "
    "answer letter. You may ignore it; if the new evidence does not settle the answer, "
    "keep your earlier answer.\n\n{block}"
)

# The conservative prompt above asks the model to keep its answer unless the new evidence
# settles the question, so the branch is a weak intervention. This variant asks for an
# explicit candidate instead: the model must say whether the experience points at a
# different option, and the gate - not the model - decides whether to take it.
PROPOSE_PROMPT = (
    "Operating experience from other training cases is below. It is not evidence about "
    "this patient. Use it only to decide what to check: you may make at most {tool_budget} "
    "tool call(s) on this case's images.\n\n{block}\n\n"
    "After checking, state the single option letter you would answer if this experience is "
    "right, even when it differs from your earlier answer. If the experience does not apply "
    "to this case, say so and keep your earlier answer. End with the letter alone."
)

GATE_PROMPT = (
    "You are the acceptance gate for a tentative answer change.\n\n"
    "QUESTION OPTIONS:\n{options}\n\n"
    "INITIAL ANSWER (P0): {p0}\n"
    "TENTATIVE ANSWER: {cand}\n\n"
    "ATTRIBUTES THAT DIFFER between these two options:\n{diff}\n\n"
    "NEW OBSERVATIONS gathered since P0:\n{observations}\n\n"
    "Decide only between these two: reply 'ACCEPT' if the tentative answer is better "
    "supported by the visible evidence, or 'RETAIN' if the initial answer should stand. "
    "Do not produce a third answer. Then one sentence of reason."
)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=0, help="0 = all questions")
    ap.add_argument("--question", help="single question_id, for smoke runs")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--api-key-stdin", action="store_true")
    ap.add_argument("--stage", default="all", choices=["all", "smoke"])
    ap.add_argument("--repo", type=Path)
    ap.add_argument("--images-root", type=Path)
    ap.add_argument("--input", type=Path)
    ap.add_argument("--ledger", type=Path)
    ap.add_argument("--inherit-ledger", type=Path)
    ap.add_argument("--cap-cny", default="1000000")
    ap.add_argument("--profile", default="qwen3-vl-plus")
    ap.add_argument("--classifier-checkpoint", type=Path)
    ap.add_argument("--report-cache", type=Path)
    ap.add_argument("--segmentation-checkpoint", type=Path)
    ap.add_argument("--model-cache", type=Path)
    ap.add_argument("--temperature", type=float)
    ap.add_argument("--top-p", type=float)
    ap.add_argument("--max-output-tokens", type=int)
    ap.add_argument("--max-case-seconds", type=float)
    ap.add_argument("--request-timeout-seconds", type=float, default=120.0)
    ap.add_argument("--tool-budget", type=int)
    ap.add_argument("--model-budget", type=int)
    ap.add_argument("--recursion-limit", type=int)
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    args.repo = Path(args.repo or ROOT / cfg.get("repo", "source/MedRAX"))
    args.images_root = Path(args.images_root or ROOT / cfg.get("images_root", "data/memory_v1/images"))
    args.input = Path(args.input or ROOT / cfg.get("input", "runs/v4_validation60/inputs.jsonl"))
    args.ledger = Path(args.ledger or ROOT / cfg.get("ledger", "reports/api_budget_qwen_100cny_v9.json"))
    if args.inherit_ledger is None and cfg.get("inherit_ledger"):
        args.inherit_ledger = ROOT / cfg["inherit_ledger"]
    args.cap_cny = str(cfg.get("cap_cny", args.cap_cny))
    args.profile = cfg.get("profile", args.profile)
    args.classifier_checkpoint = Path(args.classifier_checkpoint or ROOT / cfg["classifier_checkpoint"])
    args.report_cache = Path(args.report_cache or ROOT / cfg["report_cache"])
    if args.segmentation_checkpoint is None and cfg.get("segmentation_checkpoint"):
        args.segmentation_checkpoint = ROOT / cfg["segmentation_checkpoint"]
    args.model_cache = Path(args.model_cache or ROOT / cfg.get("model_cache", "models/hf_full"))
    args.temperature = float(cfg.get("temperature", args.temperature if args.temperature is not None else 0.2))
    args.top_p = float(cfg.get("top_p", args.top_p if args.top_p is not None else 0.95))
    args.max_output_tokens = int(cfg.get("max_output_tokens", args.max_output_tokens or 1024))
    args.max_case_seconds = float(cfg.get("max_case_seconds", args.max_case_seconds or 180))
    args.tool_budget = int(cfg.get("branch_tool_budget", args.tool_budget or 2))
    args.model_budget = int(cfg.get("branch_model_budget", args.model_budget or 4))
    args.recursion_limit = int(cfg.get("recursion_limit", args.recursion_limit or 20))
    # build_runtime/initial_messages read these from the args namespace
    args.tools = cfg.get("tools") or None
    args.image_detail = cfg.get("image_detail", "auto")

    key = sys.stdin.readline().strip() if args.api_key_stdin else ""
    if not key:
        raise SystemExit("API key absent")

    import diagnostic_eval as diag
    import memory_agent_eval as mae
    from provider_ledger import ProviderLedger
    from provider_profile import get_profile
    from skill_render import render_block
    from memory_pipeline.injection import build_memory_block
    from langchain_core.messages import HumanMessage

    profile = get_profile(args.profile)
    rows = mae.load_rows(args.input, 0)
    if args.question:
        rows = [r for r in rows if r["question_id"] == args.question]
    elif args.limit:
        rows = rows[: args.limit]
    if not rows:
        raise SystemExit("no questions selected")

    pool = json.loads((ROOT / cfg["pool"]).read_text(encoding="utf-8"))["payload"]["records"]
    pool_by_id = {rec["memory_id"]: rec for rec in pool}
    skills = json.loads((ROOT / cfg["skills"]).read_text(encoding="utf-8"))["skills"]
    skills_by_id = {s["skill_id"]: s for s in skills}

    # The B/C blocks are rebuilt from the S2 run logs, not re-retrieved: the branch must
    # see exactly the memory the original arm saw, otherwise PB/PC is a different treatment.
    from memory_pipeline.core import _context
    b_rows = {r["question_id"]: r for r in reversed(
        read_jsonl(ROOT / cfg["b_retrieval"]))}
    c_rows = {r["question_id"]: r for r in reversed(
        read_jsonl(ROOT / cfg["c_retrieval"]))}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    trace_path = args.out.with_suffix(".trace.jsonl")
    # Incremental: every finished question is appended immediately, and a rerun skips the
    # ones already on disk. A crash must not cost the questions that were already paid for.
    done = set()
    if args.out.exists():
        for line in args.out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    done.add(json.loads(line)["question_id"])
                except Exception:
                    continue
    rows = [r for r in rows if r["question_id"] not in done]
    print(f"{len(rows)} question(s) to run, {len(done)} already done", flush=True)
    results = []
    out_handle = args.out.open("a", encoding="utf-8")

    def emit(record):
        out_handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        out_handle.flush()
        results.append(record)
    with ProviderLedger(args.ledger, profile, cap_cny=args.cap_cny,
                        inherit_ledger_path=args.inherit_ledger) as ledger, \
            open(trace_path, "a", encoding="utf-8") as trace, \
            tempfile.TemporaryDirectory(prefix="bc-recovery-") as temp:
        utils = diag.smoke.module_from_file("_bc_utils", args.repo / "medrax/utils/utils.py")
        system_prompt = utils.load_prompts_from_file(
            str(args.repo / "medrax/docs/system_prompts.txt"))["MEDICAL_ASSISTANT"]
        with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
            runtime = mae.build_runtime(args, profile, key, system_prompt, Path(temp))
        for row in rows:
            qid = row["question_id"]
            record, paths = mae.inspect_input(row, args.images_root.resolve())
            if record["preflight_issues"]:
                emit({"question_id": qid, "status": "preflight_failed",
                                "issues": record["preflight_issues"]})
                continue
            started = time.monotonic()
            p0_thread = str(uuid.uuid4())
            ctx0 = new_ctx(qid, p0_thread, paths, runtime, args, trace,
                           cfg.get("p0_tool_calls", 12), cfg.get("p0_model_calls", 16))
            agent = make_agent(runtime, ledger, ctx0, profile)
            events = []
            messages = mae.initial_messages(row, paths, "auto", None)
            stage = {}
            try:
                final1 = stream_once(agent, ctx0, messages, p0_thread, args.recursion_limit, events)
                final2 = stream_once(agent, ctx0, [HumanMessage(content=diag.smoke.FOLLOWUP)],
                                     p0_thread, args.recursion_limit, events)
                p0_letter, p0_summary = letter_of(final2)
                state = agent.workflow.get_state({"configurable": {"thread_id": p0_thread}})
                prefix = list(state.values["messages"])
                stage["p0"] = {"letter": p0_letter, "chars": p0_summary.get("bytes"),
                               "prefix_messages": len(prefix), "model_calls": ctx0["actual_model_calls"],
                               "tool_calls": ctx0["actual_tool_attempts"]}
            except Exception as exc:
                emit({"question_id": qid, "status": "p0_failed",
                                "error": f"{type(exc).__name__}: {exc}"})
                continue
            options = options_of(row["question"])

            # Rebuild exactly what B and C were shown for this question.
            b_block, b_meta = "", {}
            brow = b_rows.get(qid)
            if brow and brow.get("memory_ids"):
                hits = [{"memory_id": mid, "score": sc, "context": _context(pool_by_id[mid])}
                        for mid, sc in zip(brow["memory_ids"], brow["scores"])
                        if mid in pool_by_id]
                b_block, b_audit = build_memory_block(hits, max_chars=cfg.get("memory_max_chars", 1400))
                b_meta = {"returned": b_audit["returned"], "rendered": b_audit["rendered"],
                          "chars": len(b_block), "matches_run": len(b_block) == brow.get("injected_chars")}
            c_block, c_meta = "", {}
            crow = c_rows.get(qid)
            if crow and crow.get("skills"):
                c_hits = [skills_by_id[sid] for sid in crow["skills"] if sid in skills_by_id]
                c_block = render_block(c_hits, max_chars=cfg.get("skill_max_chars", 1400))
                c_meta = {"skills": crow["skills"], "chars": len(c_block),
                          "matches_run": len(c_block) == crow.get("skill_chars")}
            stage["b_block"] = b_meta
            stage["c_block"] = c_meta

            branches = {}
            style = cfg.get("branch_style", "keep")
            mem_prompt = PROPOSE_PROMPT if style == "propose" else MEMORY_PROMPT
            p1_prompt = PROPOSE_P1 if style == "propose" else P1_PROMPT
            for name, prompt, block in (
                    ("P1", p1_prompt.format(tool_budget=args.tool_budget), None),
                    ("PB", mem_prompt.format(tool_budget=args.tool_budget, block=b_block), b_block),
                    ("PC", mem_prompt.format(tool_budget=args.tool_budget, block=c_block), c_block)):
                thread = str(uuid.uuid4())
                ctx = new_ctx(qid, thread, paths, runtime, args, trace,
                              args.tool_budget, args.model_budget)
                agent_b = make_agent(runtime, ledger, ctx, profile)
                branch_events = []
                exceeded = None
                try:
                    stream_once(agent_b, ctx, prefix + [HumanMessage(content=prompt)],
                                thread, args.recursion_limit, branch_events)
                except Exception as exc:
                    # A branch that runs out of its tool budget is not a lost case: it still
                    # has to answer from what it saw. Recorded, not hidden.
                    exceeded = f"{type(exc).__name__}: {exc}"
                try:
                    # Same second phase the arms use, so the branch ends with a bare letter.
                    final = stream_once(agent_b, ctx, [HumanMessage(content=diag.smoke.FOLLOWUP)],
                                        thread, args.recursion_limit, branch_events)
                    letter, summary = letter_of(final)
                    branches[name] = {"letter": letter, "chars": summary.get("bytes"),
                                      "model_calls": ctx["actual_model_calls"],
                                      "tool_calls": ctx["actual_tool_attempts"],
                                      "tool_names": [e["tool_name"] for e in branch_events if e.get("tool_name")],
                                      "issues": sorted(ctx["issues"]),
                                      "budget_exceeded": exceeded,
                                      "answer_text": (final or "")[:400]}
                except Exception as exc:
                    branches[name] = {"letter": None, "error": f"{type(exc).__name__}: {exc}",
                                      "budget_exceeded": exceeded}

            # gate on the two memory branches
            gates = {}
            for name in ("PB", "PC"):
                cand = branches.get(name) or {}
                if not cand.get("letter") or cand["letter"] == p0_letter:
                    gates[name] = {"decision": "no_change"}
                    continue
                diff_lines = mae_options_diff(options, p0_letter, cand["letter"])
                prompt = GATE_PROMPT.format(
                    options="\n".join(f"{k}) {v}" for k, v in sorted(options.items())),
                    p0=f"{p0_letter}) {options.get(p0_letter, '')}",
                    cand=f"{cand['letter']}) {options.get(cand['letter'], '')}",
                    diff="\n".join(diff_lines[:8]) or "(no textual difference found)",
                    observations="\n".join(cand.get("tool_names") or []) or "(no new tool calls)")
                thread = str(uuid.uuid4())
                ctx = new_ctx(qid, thread, paths, runtime, args, trace, 0, 2)
                agent_g = make_agent(runtime, ledger, ctx, profile)
                try:
                    text = stream_once(agent_g, ctx, [HumanMessage(content=prompt)], thread,
                                       args.recursion_limit, [])
                    decision = "ACCEPT" if re.search(r"\bACCEPT\b", (text or "").upper()) else "RETAIN"
                    gates[name] = {"decision": decision, "reason": (text or "")[:300],
                                   "model_calls": ctx["actual_model_calls"]}
                except Exception as exc:
                    gates[name] = {"decision": "gate_error", "error": f"{type(exc).__name__}: {exc}"}

            final_letters = {"P0": p0_letter}
            for name, branch in branches.items():
                if not branch.get("letter"):
                    continue
                gate = gates.get(name) or {}
                accepted = gate.get("decision") == "ACCEPT"
                final_letters[name] = branch["letter"]
                final_letters[f"G{name[1]}"] = branch["letter"] if accepted else p0_letter
            emit({"question_id": qid, "status": "ok", "elapsed_s": round(time.monotonic() - started, 1),
                            "p0": stage["p0"], "stage": stage,
                            "b_block_chars": len(b_block), "c_block_chars": len(c_block),
                            "branches": branches, "gates": gates, "letters": final_letters,
                            "options": options, "p0_text": (final2 or "")[:400]})
            print(json.dumps({"qid": qid, "p0": p0_letter, "P1": branches.get("P1", {}).get("letter"),
                              "PB": branches.get("PB", {}).get("letter"),
                              "PC": branches.get("PC", {}).get("letter"),
                              "GB": final_letters.get("GB"), "GC": final_letters.get("GC"),
                              "cny": str(ledger.remaining)}, ensure_ascii=False), flush=True)
    out_handle.close()
    print(f"wrote {args.out} ({len(results)} questions this run)")
    return 0


def mae_options_diff(options, a, b):
    """Readable attribute differences between two option texts."""
    import difflib
    left, right = options.get(a, ""), options.get(b, "")
    out = []
    tok = re.compile(r"[A-Za-z]+|\d+(?:\.\d+)?%?|[\u4e00-\u9fff]")
    ta, tb = tok.findall(left), tok.findall(right)
    sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        l, r = "".join(ta[i1:i2]).strip(), "".join(tb[j1:j2]).strip()
        if l or r:
            out.append(f"{a}: '{l}' -> {b}: '{r}'")
    return out


if __name__ == "__main__":
    raise SystemExit(main())
