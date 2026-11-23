"""TTL orchestration around the OFFICIAL RRSI Run.round (not a rewritten loop)."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
from .io import ProtocolError, read_json, write_json, write_once, tree_hash, digest, git
from .domain import MedM5Domain
from . import llm, upstream


def official_round(run, t, draft_parallel=1):
    """Run the official round with independent official drafts in flight."""
    if draft_parallel == 1:
        return run.round(t)
    from rrsi import gitops
    original_draft = run._draft
    original_add, original_remove = gitops.worktree_add, gitops.worktree_remove
    git_lock = threading.RLock()

    def worktree_add(*args, **kwargs):
        with git_lock:
            return original_add(*args, **kwargs)

    def worktree_remove(*args, **kwargs):
        with git_lock:
            return original_remove(*args, **kwargs)

    try:
        with ThreadPoolExecutor(max_workers=draft_parallel) as pool:
            futures = {}

            def draft(t, vid, rdir, report, digests, traces, inc_ev, budget, explore,
                      reserved, prune, hist_rows, skill_md, patterns_md):
                if not futures:
                    for index in range(run.cfg.m):
                        label = "ABCDEFGH"[index]
                        slot = bool(explore["sigma"] and explore["untried"]
                                    and index >= run.cfg.m - run.cfg.m_draft)
                        futures[label] = pool.submit(original_draft, t, label, rdir, report,
                            digests, traces, inc_ev, budget, explore, slot, prune,
                            hist_rows, skill_md, patterns_md)
                return futures[vid].result()

            gitops.worktree_add, gitops.worktree_remove = worktree_add, worktree_remove
            run._draft = draft
            return run.round(t)
    finally:
        run._draft = original_draft
        gitops.worktree_add, gitops.worktree_remove = original_add, original_remove


class OfficialSearch:
    def __init__(self, cfg, runtime, scorer):
        self.cfg = cfg
        self.repo = Path(cfg["upstream_repo"]).resolve()
        self.root = Path(cfg["run_dir"]).resolve() / "search"
        self.root.mkdir(parents=True, exist_ok=True)
        self.loop, self.lock = upstream.load(self.repo, cfg["upstream_lock"])
        from rrsi.config import RRSIConfig
        c = cfg["search"]
        self.domain = MedM5Domain(self.repo, runtime, scorer, cfg["seed"],
                                  repeat_parallel=c.get("repeat_parallel", 1))
        self.rrsi_cfg = RRSIConfig(T=c["max_rounds"], k=c["repeats"], m=c["candidates"],
            b_min=c["edit_budget_min"], b_max=c["edit_budget_max"], w=c["stall_window"],
            m_draft=min(1, c["candidates"]), delta=c["min_gain"],
            repair_rounds=c["repair_rounds"], invalid_missing_frac=0.0,
            n_fail_traces=c["failure_traces"], n_success_traces=c["success_traces"],
            eval_parallel=c.get("eval_parallel", 1), proposer_model=cfg["search_llm"]["model"],
            analyst_model=cfg["search_llm"]["model"], critic_model=cfg["search_llm"]["model"])
        self.run = self.loop.Run(self.domain, self.rrsi_cfg, self.repo, self.root / "official")
        llm.configure(cfg["search_llm"], self.root / "search_usage.jsonl")
        upstream.patch_roles(self.loop, llm, self.run, self.root / "runtime_hooks.json")
    def _completed_rounds(self, before_index):
        files = sorted((self.root / "checkpoints").glob("after_*/done.json"))
        return sum(read_json(p).get("round") is not None and read_json(p)["after_questions"] < before_index for p in files)
    def advance(self, completed, live_state, current_commit):
        n = len(completed); cdir = self.root / "checkpoints" / f"after_{n:06d}"
        cdir.mkdir(parents=True, exist_ok=True)
        fingerprint = digest({"completed": completed, "live": tree_hash(live_state), "commit": current_commit})
        done_path = cdir / "done.json"
        if done_path.exists():
            rec = read_json(done_path)
            if rec["input_hash"] != fingerprint or tree_hash(rec["state"]) != rec["state_hash"]:
                raise ProtocolError("search checkpoint inputs/state changed")
            return rec
        t = self._completed_rounds(n)
        if t >= self.cfg["search"]["max_rounds"]:
            rec = {"after_questions": n, "round": None, "reason": "predeclared_round_budget_exhausted",
                   "input_hash": fingerprint, "commit": current_commit,
                   "state": str(live_state), "state_hash": tree_hash(live_state)}
            write_json(done_path, rec); return rec
        self.domain.bind(completed, live_state, self.cfg["search"]["replay_window_cases"])
        self.run.ensure_branch()
        intent_path = cdir / "intent.json"
        if not intent_path.exists():
            if git(self.repo, "rev-parse", self.run.branch) != git(self.repo, "rev-parse", current_commit):
                raise ProtocolError("official frontier differs from stream incumbent")
            backup = {}
            for name, p in (("history", self.run.history.path), ("attribution", self.run.attribution_path),
                            ("analysis", self.run.global_analysis)):
                backup[name] = p.read_text() if p.exists() else None
            write_json(intent_path, {"input_hash": fingerprint, "round": t,
                "parent_commit": git(self.repo, "rev-parse", current_commit), "backups": backup})
        intent = read_json(intent_path)
        if intent["input_hash"] != fingerprint or intent["round"] != t:
            raise ProtocolError("attempt to resume a different search checkpoint")
        prepared = cdir / "round_frontier.json"
        finished = False
        if prepared.exists() and self.run.frontier_path.exists():
            fr = self.run.frontier()
            finished = (len(fr["trajectory"]) == t + 2 and fr["trajectory"][-1]["t"] == t + 1
                and git(self.repo, "rev-parse", fr["incumbent"]["commit"]) == git(self.repo, "rev-parse", self.run.branch))
            if not finished:
                # Transactional repair only to this checkpoint's recorded parent.
                tip = git(self.repo, "rev-parse", self.run.branch)
                if tip != intent["parent_commit"]:
                    candidate_commits = []
                    for p in (self.run.runs / f"r{t}").glob("*/prep.json"):
                        r = read_json(p)
                        if r.get("commit"): candidate_commits.append(git(self.repo, "rev-parse", r["commit"]))
                    if tip not in candidate_commits: raise ProtocolError("unknown external branch change; manual audit required")
                    git(self.repo, "update-ref", "refs/heads/" + self.run.branch, intent["parent_commit"], tip)
                self.run.save_frontier(read_json(prepared))
                for name, p in (("history", self.run.history.path), ("attribution", self.run.attribution_path),
                                ("analysis", self.run.global_analysis)):
                    old = intent["backups"][name]
                    if old is None: p.unlink(missing_ok=True)
                    else: p.write_text(old)
        if not prepared.exists():
            from rrsi.evaluate import evaluate
            wt = self.run.checkout(f"online_parent_{t}", current_commit)
            job = f"online_parent_{t}"
            ev = evaluate(self.domain, wt, self.run.runs, job, self.domain.evolve_ids(), self.rrsi_cfg.k)
            ev.save(self.run.eval_path(job))
            if ev.missing: raise ProtocolError("parent reevaluation incomplete")
            fr = self.run.frontier() if self.run.frontier_path.exists() else {
                "domain": self.domain.name, "trajectory": [{"t": 0, "S": ev.S, "C": ev.C,
                "commit": current_commit, "job": job}], "config": self.rrsi_cfg.dump()}
            if len(fr["trajectory"]) != t + 1: raise ProtocolError("unexpected official round index")
            fr["incumbent"] = {"t": t, "commit": current_commit,
                "harness_tree": self.run.harness_tree(current_commit), "job": job,
                "S": ev.S, "C": ev.C, "extra": ev.extra}
            fr["S_star"] = ev.S  # reset only panel-relative baseline, never compare old panels
            fr["ttl_panel_id"] = self.domain.panel_id
            self.run.save_frontier(fr)
            write_json(prepared, fr)
        if not finished:
            # The critical direct-reuse call: official proposal/critic/repair/smoke,
            # worktree evaluation, history, pruning/exploration and fast-forward.
            official_round(self.run, t, self.cfg["search"].get("draft_parallel", 1))
        fr = self.run.frontier()
        if len(fr["trajectory"]) != t + 2: raise ProtocolError("official round did not complete")
        parent_ev = read_json(prepared)["incumbent"]
        commit = git(self.repo, "rev-parse", fr["incumbent"]["commit"])
        accepted = commit != intent["parent_commit"]
        state = (fr["incumbent"]["extra"]["live_migration"]["state"] if accepted else str(live_state))
        rec = {"after_questions": n, "round": t, "input_hash": fingerprint, "commit": commit,
               "accepted": accepted, "parent_commit": intent["parent_commit"],
               "panel_id": self.domain.panel_id, "state": state, "state_hash": tree_hash(state),
               "parent_replay_accuracy": parent_ev["S"], "selected_replay_accuracy": fr["incumbent"]["S"],
               "delta_accuracy": fr["incumbent"]["S"] - parent_ev["S"],
               "not_independent_validation": True}
        write_json(done_path, rec)
        return rec
