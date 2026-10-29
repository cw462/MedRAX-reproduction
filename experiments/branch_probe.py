"""Wire `skill_branch_runner` to the real eight-tool runtime, for one checkpoint.

This is the glue the V4 plan asks for at S3/S4: take a checkpoint recorded by a real
run, execute the two branches from the *same* prefix, and land the observations,
answers and money on disk. The control flow stays in `skill_branch_runner`; this
module only supplies `call_tool` (validated, tracked tool invocation) and
`ask_model` (the same ChatOpenAI profile, settled through the same ledger).

Two honest constraints:

* the do branch re-executes the recorded tool call with the recorded arguments -
  the observation may legitimately differ from the one in the trace, and it is the
  new one that the model sees;
* the skip branch executes nothing and shows no new observation. Nothing is
  fabricated for it.

Use `--plan-only` to build and print the checkpoint without loading a model, any
GPU or any API call.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = next((p for p in (HERE.parent, HERE.parent.parent)
             if (p / "data" / "memory_v1").exists() or (p / "source" / "MedRAX").exists()),
            HERE.parent)

sys.path.insert(0, str(HERE))


def read_jsonl(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_checkpoint(run_dir, input_path, question_index=0, checkpoint_index=None):
    """Rebuild one checkpoint from the run's semantic trace."""
    import tool_step_replay as replay

    traces = read_jsonl(Path(run_dir) / "semantic_trace.jsonl")
    grouped = replay.group_by_question(traces)
    qids = sorted(grouped)
    if not qids:
        raise SystemExit(f"no semantic trace rows in {run_dir}")
    if question_index >= len(qids):
        raise SystemExit(f"question-index {question_index} outside {len(qids)} traced questions")
    qid = qids[question_index]

    wanted = {r["question_id"]: r for r in read_jsonl(input_path)}
    if qid not in wanted:
        raise SystemExit(f"question {qid} is not in {input_path}")
    source = wanted[qid]

    rows = grouped[qid]
    candidates = [i for i, r in enumerate(rows)
                  if (r.get("observation") or {}).get("execution_status")
                  and (r.get("observation") or {}).get("execution_status") != "failed"]
    if not candidates:
        raise SystemExit(f"no executed call to replay for {qid}")
    index = candidates[0] if checkpoint_index is None else int(checkpoint_index)
    checkpoint = replay.build_checkpoint(rows, index, question=source["question"],
                                         images=source["images"])
    checkpoint["source_run"] = str(run_dir)
    checkpoint["candidates"] = candidates
    return checkpoint


# --------------------------------------------------------------------- runtime
class RealRuntime:
    """call_tool / ask_model backed by the real tools and the real provider."""

    def __init__(self, args, profile, key):
        import diagnostic_eval as diag
        import memory_agent_eval as mae
        from langchain_openai import ChatOpenAI
        import tool_registry_ext

        self.diag = diag
        self.mae = mae
        self.profile = profile
        self.temp = tempfile.TemporaryDirectory(prefix="branch-probe-")
        self.repo = Path(args.repo).resolve()
        self.tools, self.provenance = tool_registry_ext.build_tools(
            self.repo, cache_dir=args.model_cache,
            classifier_checkpoint=args.classifier_checkpoint,
            report_cache=args.report_cache,
            segmentation_checkpoint=args.segmentation_checkpoint,
            temp_dir=Path(self.temp.name))
        self.model = ChatOpenAI(model=profile.model, base_url=profile.base_url, api_key=key,
                                temperature=args.temperature, top_p=args.top_p,
                                max_tokens=args.max_output_tokens, max_retries=0,
                                timeout=args.request_timeout_seconds)
        self.ledger = None
        self.allowed_images = set()
        self.tool_calls = []
        self.usage_records = []
        self.settlements = []

    def set_checkpoint(self, checkpoint, images_root):
        self.allowed_images = {(Path(images_root) / p).resolve() for p in checkpoint.get("images") or []}
        self.checkpoint_id = checkpoint.get("checkpoint_id")
        self.model_calls = 0

    def call_tool(self, name, arguments):
        tool = self.tools.get(name)
        if tool is None:
            raise KeyError(f"tool {name!r} is not in the registry")
        kind = self.provenance[name]["kind"]
        clean, images = self.mae.validate_parameters(tool, kind, arguments or {},
                                                     self.allowed_images)
        started = time.monotonic()
        result = tool.invoke(clean)
        checked = self.mae.observe(kind, result,
                                   **({"artifact_dir": tool.temp_dir}
                                      if kind == "segmentation" and hasattr(tool, "temp_dir") else {}))
        record = {"tool": name, "kind": kind, "arguments": clean,
                  "execution_status": "returned", "valid": bool(checked.get("valid")),
                  "elapsed_ms": round((time.monotonic() - started) * 1000),
                  "image_count": len(images),
                  "response_chars": checked.get("response_chars")}
        self.tool_calls.append(record)
        return {"tool": name, "facts": self._facts(kind, result), "valid": checked.get("valid"),
                "execution_status": "returned"}

    def _facts(self, kind, result):
        """The same semantic facts the distiller sees, if the trace module can build them."""
        try:
            from semantic_trace import semantic_observation
            return (semantic_observation(kind, result) or {}).get("facts")
        except Exception:
            return {"note": "observation captured but not summarised"}

    def ask_model(self, messages):
        self.model_calls += 1
        request_id = f"branch-{uuid4_hex()}"
        estimate = max(1, sum(len(m.get("content", "")) for m in messages) // 3 + 2000)
        estimate = min(estimate, self.profile.max_input_tokens - 1000)
        reservation = self.ledger.reserve(request_id=request_id,
                                          estimated_input_tokens=estimate,
                                          max_output_tokens=self.args.max_output_tokens,
                                          model=self.profile.model)
        error = None
        response = None
        usage = None
        try:
            from langchain_core.messages import HumanMessage
            response = self.model.invoke([HumanMessage(content=m["content"]) for m in messages])
            usage = self.diag.smoke.numeric_usage(response)
            if usage:
                self.usage_records.append(usage)
            return getattr(response, "content", "") or ""
        except BaseException as exc:
            error = type(exc).__name__
            raise
        finally:
            billed = ({'prompt_tokens': usage['input_tokens'],
                       'completion_tokens': usage['output_tokens']}
                      if usage and all(k in usage for k in ('input_tokens', 'output_tokens'))
                      and error is None else None)
            settled = self.ledger.settle(reservation, usage=billed,
                                         response_received=response is not None,
                                         error_type=error)
            self.settlements.append(settled)

    def close(self):
        self.temp.cleanup()


def uuid4_hex():
    import uuid
    return uuid.uuid4().hex


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", type=Path, required=True, help="run dir holding semantic_trace.jsonl")
    ap.add_argument("--input", type=Path, required=True, help="the run's question input")
    ap.add_argument("--images-root", type=Path, required=True)
    ap.add_argument("--question-index", type=int, default=0)
    ap.add_argument("--checkpoint-index", type=int, help="call index; default first executed call")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--repo", type=Path, default=ROOT / "source" / "MedRAX")
    ap.add_argument("--api-key-stdin", action="store_true")
    ap.add_argument("--ledger", type=Path,
                    help="ledger for the paid call; not needed with --plan-only")
    ap.add_argument("--inherit-ledger", type=Path)
    ap.add_argument("--cap-cny", default="1000000")
    ap.add_argument("--profile", default="qwen3-vl-plus")
    ap.add_argument("--classifier-checkpoint", type=Path, required=False)
    ap.add_argument("--report-cache", type=Path, required=False)
    ap.add_argument("--segmentation-checkpoint", type=Path)
    ap.add_argument("--model-cache", type=Path)
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--top-p", type=float, default=0.95)
    ap.add_argument("--max-output-tokens", type=int, default=1024)
    ap.add_argument("--request-timeout-seconds", type=float, default=120.0)
    ap.add_argument("--branch", choices=("do_action", "skip_action", "alternate_action"),
                    default="do_action")
    args = ap.parse_args(argv)

    checkpoint = load_checkpoint(args.run, args.input, args.question_index, args.checkpoint_index)
    if args.plan_only:
        print(json.dumps(checkpoint, ensure_ascii=False, indent=1, default=str))
        return 0

    key = sys.stdin.readline().strip() if args.api_key_stdin else ""
    if not key:
        raise SystemExit("API key absent")
    from provider_profile import get_profile
    from provider_ledger import ProviderLedger
    from skill_branch_runner import continue_from_checkpoint

    profile = get_profile(args.profile)
    runtime = RealRuntime(args, profile, key)
    runtime.args = args
    runtime.set_checkpoint(checkpoint, args.images_root)
    out = {"checkpoint": checkpoint, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        with ProviderLedger(args.ledger, profile, cap_cny=args.cap_cny,
                            inherit_ledger_path=args.inherit_ledger) as ledger:
            runtime.ledger = ledger
            result = continue_from_checkpoint(checkpoint, call_tool=runtime.call_tool,
                                              ask_model=runtime.ask_model, branch=args.branch,
                                              remaining_tool_calls=2)
            out["result"] = result.to_dict()
            out["money"] = {"settlements": runtime.settlements,
                            "remaining_cny": str(ledger.remaining)}
    finally:
        out["tool_calls"] = runtime.tool_calls
        out["usage"] = runtime.usage_records
        runtime.close()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str) + "\n",
                            encoding="utf-8")
        print(json.dumps({"branch": out.get("result", {}).get("branch"),
                          "stopped_reason": out.get("result", {}).get("stopped_reason"),
                          "answer": (out.get("result", {}).get("answer") or "")[:200],
                          "tool_calls": len(out["tool_calls"]),
                          "out": str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
