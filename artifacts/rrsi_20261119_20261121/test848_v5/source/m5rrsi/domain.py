"""Domain implementation for official rrsi.loop.Run.
Replay is sequential: start from a historical pre-window state, predict, score,
then update memory on each already completed question. This exposes effects of
writer and graph-maintenance edits, not just inference-time prompt changes.
"""
from __future__ import annotations
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from .io import ProtocolError, digest, git, read_json, write_json, write_once, tree_hash
from .steps import transition


class MedM5Domain:
    name = "med_m5"
    harness_path = "harness"
    source_exts = {".py", ".txt", ".md", ".json", ".yaml", ".yml"}
    critic_patterns = [
        (r"(?:references\.jsonl|public_cases\.jsonl|/(?:data|prepared)/stream\.json)", "benchmark file access"),
        (r"(?:/proc/|docker\.sock|\.ssh/|AWS_SECRET_ACCESS_KEY)", "host/secret access"),
    ]
    component_signals = [
        ("memory", [r"writer\.py", r"memory.*\.py", r"retriev.*\.py", r"graph.*\.py", r"def observe\("]),
        ("control_flow", [r"planner\.py", r"workflow\.py", r"def predict\("]),
        ("context_mgmt", [r"context.*\.py", r"compress.*\.py"]),
        ("client_tool", [r"tool.*\.py", r"services\.tool"]),
        ("subagent", [r"subagent", r"reviewer.*\.py"]),
        ("skill", [r"skills/", r"skill.*\.py"]),
        ("config", [r"config.*\.json", r"settings.*\.py"]),
        ("output_plumbing", [r"output.*\.py", r"parse.*\.py"]),
        ("prompt", [r"prompts?/", r"prompt.*\.py"]),
    ]
    briefs = {
        "analyst": "Analyze medical VQA history. Scores are binary accuracy. Separate visual/tool failures, memory misuse, and successes. Only completed questions are present.",
        "digester": "Use only the provided historical trace. Tool outputs are observations, not ground truth. Feedback was released after the primary answer. Do not invent evidence.",
        "proposer": "Improve the real M5 harness for subsequent questions. Qwen backbone and tool services are fixed. You may edit prompts AND executable memory/control-flow/context/skill modules. Do not edit the scoring or TTL timing. Runtime memory from previously released questions is authorized. Never hard-code historical answers into source. Accuracy only; no cost compensation.",
        "critic": "Question-wise online TTL deliberately reuses past released experience, including related questions. Allow legitimate observe() writes after a locked prediction, but reject source-embedded answer tables, future-feedback access, scorer changes, resource bypass or inert code. Full-label feedback and sequential historical replay are intentional, not independent test evidence.",
    }
    def __init__(self, repo, runtime, scorer, seed=42, repeat_parallel=1, replay_initial_memory=None):
        self.root = Path(repo) / "domains" / self.name
        self.runtime, self.scorer, self.seed = runtime, scorer, seed
        self.rows = []
        self.live_state = None
        self.panel_id = None
        self.repeat_parallel = repeat_parallel
        self.replay_initial_memory = replay_initial_memory
    def bind(self, completed, live_state, window):
        if not completed: raise ProtocolError("cannot evolve without completed history")
        self.rows = completed[-window:]
        self.live_state = str(Path(live_state).resolve())
        # v4 starts at the historical state. v5 starts each replay trial empty.
        self.start = None if self.replay_initial_memory == "empty" else self.rows[0]["before_evolving"]
        self.start_hash = "EMPTY" if self.start is None else tree_hash(self.start)
        self.live_hash = tree_hash(live_state)
        self.panel_id = digest({"items": self.rows, "start": self.start_hash,
                                "live": self.live_hash, "seed": self.seed})
    def harness_dir(self, root): return Path(root) / "domains" / self.name / self.harness_path
    def constitution(self, root):
        d = Path(root) / "domains" / self.name
        return (d / "SKILL.md").read_text(), (d / "PATTERNS.md").read_text()
    def evolve_ids(self): return [r["task_id"] for r in self.rows]
    def heldout_ids(self): return []
    def smoke_ids(self, incumbent_per_task=None): return self.evolve_ids()[:1]
    def regression_threshold(self, k): return 1.0 / max(k, 1)
    def run(self, root, runs_dir, job, ids, k, log_prefix=""):
        if ids != self.evolve_ids(): raise ProtocolError("replay ID order mismatch")
        rows = tuple(self.rows)
        start, live_state = self.start, self.live_state
        meta = {"panel_id": self.panel_id, "replay_start_hash": self.start_hash,
                "live_state_hash": self.live_hash}
        harness = self.harness_dir(root)
        out = Path(runs_dir) / "jobs" / job; out.mkdir(parents=True, exist_ok=True)
        meta = {**meta, "harness_hash": tree_hash(harness), "k": k, "ids": ids,
                "feedback_mode": "full_label", "metric_id": self.scorer.metric_id}
        if start is None:
            program = git(root, "rev-parse", "HEAD")
            if job.startswith("online_parent_"):
                round_number, variant = int(job.removeprefix("online_parent_")) + 1, "incumbent"
            else:
                round_number, variant = int(job[1:-1]) + 1, job[-1]
            meta.update(program_version=program, trial_initial_memory="empty",
                        trial_seeds=[self.seed + j for j in range(k)])
        write_once(out / "binding.json", meta)
        def trial(j):
            trial = out / f"trial_{j}"
            migrated = transition(self.runtime, harness, start, trial / "start",
                                  "initialize" if start is None else "migrate", seed=self.seed + j)
            state = migrated["state"]
            previous_ids = []
            for step, row in enumerate(rows, 1):
                where = trial / row["task_id"]
                case = row["case"]
                current = ({**case, "replay_previous_ids": list(previous_ids)} if start is None else case)
                pred = transition(self.runtime, harness, state, where / "predict", "predict",
                                  case=current, seed=self.seed + j)
                score_file = where / "score.json"
                if score_file.exists():
                    feedback = read_json(score_file)
                else:
                    correct = self.scorer.score(row["case"], pred["result"], row["reference"])
                    feedback = {"correct": correct, "reference": row["reference"]}
                    write_json(score_file, feedback)
                after = transition(self.runtime, harness, pred["state"], where / "observe", "observe",
                    case=current, prediction=pred["result"], feedback=feedback, seed=self.seed + j)
                trace = {"case": case, "prediction": pred["result"],
                         "feedback": feedback, "task_id": row["task_id"]}
                if start is None:
                    trace["replay"] = {"kind": "replay", "phase": "dev", "round": round_number,
                        "variant": variant, "trial": j, "step": step, "dataset": case["dataset"],
                        "qid": case["id"], "correct": feedback["correct"], "program_version": program}
                    previous_ids.append(case["id"])
                write_once(where / "trace.json", trace)
                state = after["state"]
        with ThreadPoolExecutor(max_workers=min(k, self.repeat_parallel)) as pool:
            list(pool.map(trial, range(k)))
        # Separate live-state compatibility check; never use this state for replay scoring.
        live = transition(self.runtime, harness, live_state, out / "live_migration", "migrate", seed=self.seed)
        write_json(out / "complete.json", {**meta, "live_migration": live})
    def score(self, runs_dir, job, ids, k):
        from rrsi.evaluate import TaskResult
        out = Path(runs_dir) / "jobs" / job
        done = read_json(out / "complete.json")
        if done["panel_id"] != self.panel_id or done["ids"] != ids or done["k"] != k:
            raise ProtocolError("stale replay evaluation")
        tasks = {}
        for tid in ids:
            rewards, tokens = [], []
            for j in range(k):
                p = out / f"trial_{j}" / tid
                rewards.append(float(read_json(p / "score.json")["correct"]))
                tokens.append(read_json(p / "predict" / "locked.json")["result"]["usage"]["total_tokens"])
            tasks[tid] = TaskResult(rewards=rewards, tokens=tokens)
        extra = {k: done[k] for k in ("panel_id", "replay_start_hash", "feedback_mode", "metric_id", "harness_hash")}
        extra["live_migration"] = done["live_migration"]
        return tasks, extra
    def load_trial(self, runs_dir, job, task_id, trial):
        p = Path(runs_dir) / "jobs" / job / f"trial_{trial}" / task_id / "trace.json"
        return read_json(p) if p.exists() else None
    def render_trace(self, rec, detail=False):
        return ("=== HISTORICAL CASE ===\n" + json.dumps(rec["case"], ensure_ascii=False)
                + "\n=== AGENT TRACE ===\n" + json.dumps(rec["prediction"], ensure_ascii=False, indent=1)
                + "\n=== GRADING (already released feedback) ===\n" + json.dumps(rec["feedback"], ensure_ascii=False))
    def task_row(self, task_id, rec, tr):
        return f"{task_id} | score={tr.mean:.4f} | source={rec['case']['dataset']} | trace_available=true"
    def guards(self, incumbent, candidate):
        errs = []
        if candidate.extra.get("panel_id") != self.panel_id: errs.append("stale panel")
        live = candidate.extra.get("live_migration", {})
        if not live or not Path(live.get("state", "missing")).is_dir(): errs.append("live state migration missing")
        elif tree_hash(live["state"]) != live["state_hash"]: errs.append("live state migration changed")
        return errs
    def smoke(self, root, runs_dir, job, ids):
        try:
            h = self.harness_dir(root)
            out = Path(runs_dir) / "jobs" / job
            transition(self.runtime, h, self.live_state, out / "check", "check", seed=self.seed)
            transition(self.runtime, h, self.live_state, out / "migrate", "migrate", seed=self.seed)
            return True, {"native_entrypoint_check": True, "migration": True}
        except Exception as e:
            return False, {"error": repr(e)}
