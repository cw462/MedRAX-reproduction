from __future__ import annotations
from pathlib import Path
from .io import ProtocolError, read_json, write_json, write_once, digest, tree_hash, code_export, git, run_lock, file_hash
from .data import public_case
from .steps import transition

ARMS = ("fixed_m5", "rrsi_acc")


def primary_arms(config):
    arms = config.get("primary_arms", list(ARMS))
    if (not isinstance(arms, list) or not arms
            or any(arm not in ARMS for arm in arms)
            or len(set(arms)) != len(arms) or "rrsi_acc" not in arms):
        raise ProtocolError("primary_arms must list rrsi_acc and optionally fixed_m5, without duplicates")
    return tuple(arms)


class StreamEngine:
    def __init__(self, config, manifest, references, runtime, scorer, search, export=code_export):
        self.cfg, self.manifest, self.references = config, manifest, references
        self.runtime, self.scorer, self.search, self.export = runtime, scorer, search, export
        self.arms = primary_arms(config)
        self.out = Path(config["run_dir"]).resolve()
        self.out.mkdir(parents=True, exist_ok=True)
    def run(self, stop_after=None):
        with run_lock(self.out / "coordinator.lock"):
            return self._run(stop_after)
    def _run(self, stop_after):
        cfg = self.cfg; initial = cfg["initial_commit"]
        identity = {"config": cfg, "manifest_hash": self.manifest["cases_hash"],
                    "reference_hash": self.references.sha256, "feedback": "full_label",
                    "order": "input_questionwise", "initial_commit": initial}
        write_once(self.out / "run_identity.json", identity)
        if digest(self.manifest["cases"]) != self.manifest["cases_hash"]:
            raise ProtocolError("manifest tampering")
        h0 = self.export(cfg["upstream_repo"], initial, self.out / "code" / initial)
        arms = self.arms
        state, commits = {}, {a: initial for a in arms}
        for arm in arms:
            rec = transition(self.runtime, h0, None, self.out / "initial" / arm, "initialize", seed=cfg["seed"])
            state[arm] = rec["state"]
        if len(arms) == 2 and tree_hash(state[arms[0]]) != tree_hash(state[arms[1]]):
            raise ProtocolError("initial M5 memory differs across arms")
        completed = []
        for i, row in enumerate(self.manifest["cases"]):
            if stop_after is not None and i >= stop_after: break
            if (self.out / "STOP").exists(): break
            case = public_case(row)
            qdir = self.out / "primary" / f"q{i+1:06d}"
            qdir.mkdir(parents=True, exist_ok=True)
            current_h = {a: self.export(cfg["upstream_repo"], commits[a], self.out / "code" / commits[a]) for a in arms}
            before = dict(state)
            pred = {}
            # Lock the current question for every active arm before releasing feedback.
            for arm in arms:
                pred[arm] = transition(self.runtime, current_h[arm], state[arm], qdir / arm / "predict", "predict",
                                       case=case, seed=cfg["seed"] + i)
            locks = [qdir / a / "predict" / "locked.json" for a in arms]
            reference = self.references.after_lock(case["id"], locks, expected_locks=len(arms))
            feedback = {}
            for arm in arms:
                p = qdir / arm / "feedback.json"
                if p.exists(): feedback[arm] = read_json(p)
                else:
                    feedback[arm] = {"correct": self.scorer.score(case, pred[arm]["result"], reference),
                                     "reference": reference}
                    write_json(p, feedback[arm])
                after = transition(self.runtime, current_h[arm], pred[arm]["state"], qdir / arm / "observe", "observe",
                    case=case, prediction=pred[arm]["result"], feedback=feedback[arm], seed=cfg["seed"] + i)
                state[arm] = after["state"]
            record = {"index": i, "task_id": f"q{i+1:06d}", "case": case, "reference": reference,
                      "before_evolving": before["rrsi_acc"], "commits": dict(commits),
                      "states_after_observe": dict(state), "correct": {a: feedback[a]["correct"] for a in arms},
                      "group_keys": row.get("group_keys", [])}
            write_once(qdir / "completed.json", record)
            completed.append(record)
            if i + 1 < len(self.manifest["cases"]):
                # Event-driven TTL adapter: ONE official round after each feedback checkpoint.
                # This policy is an adapter decision, NOT the upstream offline trigger.
                changed = self.search.advance(completed, state["rrsi_acc"], commits["rrsi_acc"])
                commits["rrsi_acc"], state["rrsi_acc"] = changed["commit"], changed["state"]
            write_json(self.out / "progress.json", {"completed": i+1, "planned": self.manifest["n"],
                       "next_commits": commits, "next_states": state})
        return {"completed": len(completed), "planned": self.manifest["n"],
                "correct": {a: sum(x["correct"][a] for x in completed) for a in arms}}
