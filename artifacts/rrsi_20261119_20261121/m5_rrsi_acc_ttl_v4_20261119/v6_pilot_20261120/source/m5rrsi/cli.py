from __future__ import annotations
import argparse
import json
from pathlib import Path
from .io import ProtocolError, read_json
from .validation import validate_config, budget, freeze, verify_frozen
from .data import prepare, References
from .runtime import DockerRuntime, NativeScorer
from .engine import StreamEngine
from .report import report


def main():
    p = argparse.ArgumentParser(description="M5 TTL using actual official RRSI")
    sub = p.add_subparsers(dest="action", required=True)
    prep = sub.add_parser("prepare"); prep.add_argument("--inputs", required=True); prep.add_argument("--out", required=True)
    for name in ("budget", "validate", "freeze", "run"):
        a = sub.add_parser(name); a.add_argument("--config", required=True)
        if name == "run":
            a.add_argument("--stop-after", type=int); a.add_argument("--resume", action="store_true")
    a = sub.add_parser("report"); a.add_argument("--run-dir", required=True)
    args = p.parse_args()
    try:
        if args.action == "prepare": out = prepare(args.inputs, args.out); out = {k:v for k,v in out.items() if k != "cases"}
        elif args.action == "report": out = report(args.run_dir)
        else:
            cfg = read_json(args.config)
            validate_config(cfg, template_ok=args.action == "budget")
            if args.action == "budget": out = budget(cfg)
            else:
                kind = cfg["runtime"].get("kind", "docker")
                if kind == "restricted_process":
                    from .process_runtime import ProcessRuntime
                    runtime = ProcessRuntime(cfg["runtime"], Path(cfg["run_dir"]) / "runtime_audit")
                elif kind == "docker":
                    runtime = DockerRuntime(cfg["runtime"], Path(cfg["run_dir"]) / "runtime_audit")
                else:
                    raise ProtocolError("unknown native runtime kind")
                runtime.preflight()
                if args.action == "freeze": out = freeze(cfg)
                elif args.action == "validate":
                    from .validation import runtime_fingerprint
                    runtime_fingerprint(cfg); out = {"status": "validated", "note": "not a medical performance test"}
                else:
                    verify_frozen(cfg)
                    existing = (Path(cfg["run_dir"]) / "run_identity.json").exists()
                    if existing and not args.resume: raise ProtocolError("existing run: use --resume without changing inputs/code")
                    if args.resume and not existing: raise ProtocolError("no run to resume")
                    manifest = read_json(cfg["manifest"])
                    references = References(cfg["references"], [r["id"] for r in manifest["cases"]])
                    scorer = NativeScorer(cfg["scorer_command"], cfg["metric_id"])
                    from .search import OfficialSearch
                    search = OfficialSearch(cfg, runtime, scorer)
                    engine = StreamEngine(cfg, manifest, references, runtime, scorer, search)
                    out = engine.run(args.stop_after)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    except ProtocolError as e:
        p.exit(2, f"BLOCKED: {e}\n")

if __name__ == "__main__": main()
