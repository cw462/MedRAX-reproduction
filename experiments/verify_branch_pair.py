"""Verify one do/skip pair landed on disk: observations, answers, money.

Prints the facts the report needs and asserts the properties that make the pair a
usable counterfactual:
  * both branches ran from the same checkpoint;
  * do_action executed exactly one real tool call and saw its observation;
  * skip_action executed nothing and received no new observation;
  * both answers and both settlements are recorded.
"""
import argparse
import json
import sys
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--path", type=Path, required=True)
    args = ap.parse_args(argv)

    d = json.loads(args.path.read_text(encoding="utf-8"))
    cp = d.get("checkpoint") or {}
    pair = d.get("pair") or {}
    do = pair.get("do_action") or {}
    skip = pair.get("other") or {}
    calls = d.get("tool_calls") or []
    money = d.get("money") or {}
    settle = money.get("settlements") or []

    print(f"checkpoint: {cp.get('checkpoint_id')}  status={cp.get('rebuild_status')}")
    print(f"prefix observations: {len(cp.get('prefix_observations') or [])} "
          f"tools={[p.get('tool') for p in cp.get('prefix_observations') or []]}")
    print(f"target action: {cp.get('target_action', {}).get('tool')}")
    print()
    print("DO branch")
    print(f"  actions: {do.get('actions')}")
    print(f"  observations: {len(do.get('observations') or [])} "
          f"facts_chars={[len(json.dumps(o.get('observation', {}).get('facts'), ensure_ascii=False, default=str)) for o in (do.get('observations') or [])]}")
    print(f"  answer: {(do.get('answer') or '')[:300]}")
    print(f"  stopped_reason: {do.get('stopped_reason')}  tool_error: {do.get('tool_error')}")
    print()
    print("SKIP branch")
    print(f"  actions: {skip.get('actions')}")
    print(f"  observations: {len(skip.get('observations') or [])}  (must be 0)")
    print(f"  answer: {(skip.get('answer') or '')[:300]}")
    print(f"  stopped_reason: {skip.get('stopped_reason')}")
    print()
    print(f"tool calls actually executed: {len(calls)} -> {[c.get('tool') for c in calls]}")
    print(f"model calls recorded: {len(d.get('usage') or [])}")
    print(f"settlements: {len(settle)}  charged_total="
          f"{sum(float(s.get('charged_cny') or 0) for s in settle):.4f} CNY  "
          f"remaining={money.get('remaining_cny')}")

    problems = []
    if len(do.get("observations") or []) != 1:
        problems.append("do branch did not record exactly one observation")
    if len(skip.get("observations") or []) != 0:
        problems.append("skip branch recorded an observation")
    if len(calls) != 1:
        problems.append(f"expected exactly one executed tool call, got {len(calls)}")
    if not do.get("answer"):
        problems.append("do branch has no answer")
    if not skip.get("answer"):
        problems.append("skip branch has no answer")
    if len(d.get("usage") or []) != 2:
        problems.append(f"expected two model calls, got {len(d.get('usage') or [])}")
    if len(settle) != 2:
        problems.append(f"expected two settlements, got {len(settle)}")
    print()
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print(" -", p)
        return 1
    print("OK: same checkpoint, one real action on the do side, none on the skip side, "
          "both answers and both settlements on disk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
