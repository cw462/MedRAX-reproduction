"""Idempotent, immutable state transitions used by primary stream and replay."""
from __future__ import annotations
from pathlib import Path
from .io import ProtocolError, digest, tree_hash, copy_tree, write_json, write_once, read_json
from .runtime import require_prediction


def transition(runtime, harness, before, root, op, *, case=None, prediction=None, feedback=None, seed=0):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    before_hash = tree_hash(before) if before is not None else "EMPTY"
    expected = {"op": op, "harness": tree_hash(harness), "before": before_hash,
                "case": case, "prediction": prediction, "feedback": feedback, "seed": seed}
    record = root / "locked.json"
    if record.exists():
        rec = read_json(record)
        if rec["request_hash"] != digest(expected): raise ProtocolError("resume inputs changed")
        if tree_hash(rec["state"]) != rec["state_hash"]: raise ProtocolError("locked state mutated")
        return rec
    write_once(root / "intent.json", expected)
    state = root / "state"
    if before is None:
        import shutil
        if state.exists(): shutil.rmtree(state)
        state.mkdir()
    else: copy_tree(before, state)
    result = runtime.call(harness, state, op, case=case, prediction=prediction,
                          feedback=feedback, seed=seed)
    if op == "predict": require_prediction(result)
    rec = {"request_hash": digest(expected), "result": result,
           "state": str(state.resolve()), "state_hash": tree_hash(state),
           "before_hash": before_hash, "harness_hash": expected["harness"]}
    # The response is locked before scoring; later calls only reuse it.
    write_json(record, rec)
    if before is not None and tree_hash(before) != before_hash:
        raise ProtocolError("runtime mutated immutable source state")
    return rec
