"""Connect the actual GEPA and RSI Meta-Harness loops to causal M5 evaluations."""

from dataclasses import dataclass
from functools import cache
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from .data import digest, read, write
from .policy import H0, P0, HarnessPolicy, prompt_set


RSI_COMMIT = "73564ae9b7f9ac3641fe276d5ceb9c549e8c17e8"
GEPA_RELEASE = "0.1.4"
GEPA_WHEEL_HASH = "12b971039599625c156d2231f6d72a29c31a22e9c237689459b5f1a3c353f532"
ARMS = {"DATA": (), "GEPA": (("gepa", 12),), "META": (("meta", 12),),
        "GEPA_META": (("gepa", 6), ("meta", 6))}
SELECTION_BRIEF = """Optimize the M5 CerebraFusionMemory retrieval policy for new medical VQA tasks.
The overall score is isolated online validation accuracy. The per-task traces and scores are from training.
Make a generalizable retrieval change grounded in the recorded training traces and aggregate validation scores.
Edit exactly policy.py. A candidate is never imported. Preserve its two function signatures and three setting names.
top_k is 1 to 10, semantic_weight is 0 to 1, and max_neighbors is 0 to 6.
rank and keep may use only score, position, is_neighbor, bounded numeric or boolean literals, comparisons,
and short arithmetic or conditional expressions. rank returns a finite number and keep a boolean.
No other files, imports, string literals, additional instructions, or task-specific lookups are allowed.
"""


def key_for(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@cache
def unpack_gepa(wheel):
    # The wheel omits the ZIP directory entry for a namespace adapter.
    # Normal extraction lets Python resolve the adapter on disk.
    package = TemporaryDirectory(prefix="medrax-gepa-")
    with ZipFile(wheel) as archive:
        archive.extractall(package.name)
    return package


def bind_dependencies(home):
    import subprocess

    rsi = home / "upstream" / "RSI"
    wheel = home / "upstream" / f"gepa-{GEPA_RELEASE}-py3-none-any.whl"
    if (rsi / ".git").exists():
        revision = subprocess.check_output(["git", "-C", str(rsi), "rev-parse", "HEAD"], text=True).strip()
    else:
        snapshot = read(home / "upstream" / "rsi_source.json")
        revision = snapshot["commit"]
        if any(digest(rsi / name) != sha for name, sha in snapshot["sha256"].items()):
            raise ValueError("Staged RSI source files changed")
    if revision != RSI_COMMIT or digest(wheel) != GEPA_WHEEL_HASH:
        raise ValueError("Optimizer dependencies do not match the staged versions")
    sys.path[:0] = [str(rsi), unpack_gepa(wheel).name]


@dataclass(frozen=True)
class Candidate:
    prompts: dict
    harness: str = H0

    def __post_init__(self):
        object.__setattr__(self, "prompts", prompt_set(self.prompts))
        HarnessPolicy(self.harness)

    def wire(self):
        return {"prompts": self.prompts, "harness": self.harness}


class Replay:
    """One chronological train replay per candidate; validation forks its graph.

    The optimizer-facing API can only request the development split handles.
    The trusted runner returns validation scores without outputs or trajectories.
    """

    def __init__(self, root, binding, train_count, val_count, run_stream, *, maximum=13):
        self.root = Path(root)
        self.binding = binding
        self.counts = {"train": train_count, "val": val_count}
        self.run_stream = run_stream
        self.maximum = maximum
        self.root.mkdir(parents=True, exist_ok=True)

    def get(self, candidate, split):
        if split not in self.counts:
            raise ValueError("Search cannot read that split")
        identity = {"candidate": candidate.wire(), "protocol": self.binding}
        path = self.root / key_for(identity)
        record = path / "candidate.json"
        if not record.exists():
            registrations = list(self.root.glob("*/candidate.json"))
            if len(registrations) >= self.maximum:
                raise RuntimeError("Candidate rollout limit reached")
            write(record, {**identity, "order": len(registrations)})
        if split == "val":
            self.get(candidate, "train")
        stream = path / split
        receipt = stream / "replay.completed.json"
        if not receipt.exists():
            snapshot = path / "train" / "warm_snapshot" if split == "val" else None
            result = self.run_stream(candidate, split, stream, snapshot)
            self._check(result, split)
            write(receipt, result)
        result = read(receipt)
        self._check(result, split)
        return result

    def _check(self, result, split):
        if set(result) - {"scores", "train_traces", "usage"}:
            raise ValueError("Unexpected data in the optimizer replay packet")
        scores = result["scores"]
        if len(scores) != self.counts[split] or any(type(x) not in (float, int) or x not in (0, 1) for x in scores):
            raise ValueError(f"Incomplete or non-binary {split} scores")
        traces = result.get("train_traces")
        if split == "val" and traces is not None:
            raise ValueError("Validation trajectories must stay inside the evaluator")
        if split == "train" and (not isinstance(traces, list) or len(traces) != len(scores)):
            raise ValueError("Training trajectories must match the canonical positions")

    def best(self, eligible):
        qualified = []
        for record in self.root.glob("*/candidate.json"):
            receipt = record.parent / "val" / "replay.completed.json"
            if not receipt.is_file():
                continue
            row = read(record)
            candidate = Candidate(**row["candidate"])
            if not eligible(candidate):
                continue
            scores = read(receipt)["scores"]
            qualified.append((-sum(scores), row["order"], candidate))
        if not qualified:
            raise ValueError("Selection has no completed validation replay")
        return min(qualified, key=lambda item: item[:2])[2]


class Slots:
    def __init__(self, root, limit):
        self.root = Path(root)
        self.limit = limit

    @property
    def used(self):
        return len(list(self.root.glob("*.slot.json")))

    def reserve(self, fields):
        ordinal = self.used + 1
        if ordinal > self.limit:
            raise RuntimeError("Proposal slots exhausted")
        file = self.root / f"{ordinal:03d}.slot.json"
        write(file, {"ordinal": ordinal, **fields})
        return file


class GepaReplayAdapter:
    propose_new_texts = None  # The official engine dispatches to our RSI reflector.

    def __init__(self, replay):
        self.replay = replay

    def evaluate(self, batch, candidate, capture_traces=False):
        from gepa.core.adapter import EvaluationBatch

        if not batch:
            return EvaluationBatch([], [], [] if capture_traces else None)
        split = batch[0][0]
        if any(member[0] != split for member in batch):
            raise ValueError("GEPA requested a mixed split")
        evaluation = self.replay.get(Candidate(candidate), split)
        indices = [ix for _, ix in batch]
        trajectories = None
        if capture_traces:
            trajectories = ([evaluation["train_traces"][i] for i in indices]
                            if split == "train" else [None] * len(indices))
        return EvaluationBatch(outputs=[None] * len(indices),
                               scores=[evaluation["scores"][i] for i in indices],
                               trajectories=trajectories)

    def make_reflective_dataset(self, candidate, eval_batch, components_to_update):
        if eval_batch.trajectories is None or any(trace is None for trace in eval_batch.trajectories):
            raise ValueError("Reflection can only use archived training diagnostics")
        records = [{"Training execution": trace, "Correct": score}
                   for trace, score in zip(eval_batch.trajectories, eval_batch.scores, strict=True)]
        return {component: records for component in components_to_update}


def run_gepa(replay, proposer, start, root, *, limit, seed):
    import gepa
    from rsi.core.artifact import Artifact
    from rsi.gepa.reflection import ReflectionProposer, reflection_seed

    root = Path(root)
    slots = Slots(root / "proposals", limit)
    reflector = ReflectionProposer(proposer, max_tokens=2048)
    trainset = [("train", i) for i in range(replay.counts["train"])]
    valset = [("val", i) for i in range(replay.counts["val"])]
    # Run the baseline even when a resumed optimizer has no free proposals.
    replay.get(start, "val")

    def propose(candidate, dataset, components, *, metadata=None):
        marker = slots.reserve({"parent": key_for(candidate), "components": components,
                                "metadata": metadata, "status": "started"})
        proposal = reflector.propose(Artifact(candidate), dataset, components,
                                     seed_fn=lambda name: reflection_seed(seed, slots.used, name))
        updated = {**candidate, **proposal.new_texts}
        try:
            prompt_set(updated)
        except ValueError:
            updated = candidate
        write(marker, {**read(marker), "status": "completed", "new_texts": proposal.new_texts,
                       "rejected": proposal.rejected, "duplicate": updated == candidate})
        return {key: updated[key] for key in components}

    # The engine retains the official sampling, mutation acceptance and frontier.
    if slots.used < limit:
        gepa.optimize(
            seed_candidate=start.prompts, trainset=trainset, valset=valset,
            adapter=GepaReplayAdapter(replay), custom_candidate_proposer=propose,
            use_merge=False, track_best_outputs=False, cache_evaluation=False,
            val_evaluation_policy="full_eval", reflection_minibatch_size=min(4, len(trainset)),
            skip_perfect_score=False, stop_callbacks=lambda _: slots.used >= limit,
            max_metric_calls=(limit + 1) * (len(valset) + 2 * min(4, len(trainset))) + len(trainset),
            run_dir=str(root / "engine"), seed=seed,
        )
    return replay.best(lambda candidate: candidate.harness == H0)


def run_meta(replay, proposer, start, root, *, limit, seed):
    from rsi.core.artifact import Artifact
    from rsi.core.domain import Domain, Trial
    from rsi.core.evaluate import EvalResult
    from rsi.core.tasks import TaskSuite
    from rsi.metaharness.config import Config
    from rsi.metaharness.loop import MetaHarnessLoop
    from rsi.metaharness.proposer import RewriteProposer

    root = Path(root)
    slots = Slots(root / "proposals", limit)
    class BoundedProposer(RewriteProposer):
        def propose(self, *, iteration, view, k, brief, artifacts, seed=0):
            if k != 1:
                raise ValueError("Meta-Harness must reserve one proposal per iteration")
            marker = slots.reserve({"iteration": iteration, "status": "started"})
            batch = super().propose(iteration=iteration, view=view, k=k, brief=brief,
                                    artifacts=artifacts, seed=seed)
            admitted = []
            rejected = []
            for proposed in batch.candidates:
                try:
                    files = proposed.artifact.files
                    if set(files) != {"policy.py"}:
                        raise ValueError("Only policy.py is editable")
                    HarnessPolicy(files["policy.py"])
                    if files["policy.py"] in {item.get("policy.py") for item in artifacts.values()}:
                        raise ValueError("Duplicate policy source")
                    admitted.append(proposed)
                except (ValueError, SyntaxError, TypeError) as exc:
                    rejected.append(str(exc))
            batch.candidates = admitted
            # Do not write arbitrary proposer-defined path names to the history.
            batch.reports = {}
            write(marker, {**read(marker), "status": "completed", "rejected": rejected,
                           "proposal_error": batch.error, "admitted": bool(admitted),
                           "reply": batch.transcript})
            return batch

    class MetaEvaluation(EvalResult):
        @property
        def score(self):
            return self.meta["validation_micro"]

    class OnlineMetaLoop(MetaHarnessLoop):
        def _evaluate(self, name, artifact, t=None):
            candidate = Candidate(start.prompts, artifact.get("policy.py"))
            train = replay.get(candidate, "train")
            val = replay.get(candidate, "val")
            records = {}
            for index, (score, trace) in enumerate(zip(train["scores"], train["train_traces"], strict=True)):
                task_id = f"train_{index:04d}"
                records[task_id] = [Trial(task_id, seed, score, trace=json.dumps(trace, ensure_ascii=False))]
            result = MetaEvaluation(artifact.id, "evolve", records, 1,
                                    meta={"validation_micro": sum(val["scores"]) / len(val["scores"])})
            metrics = self.store.write_eval(name, result, cost={})
            if t is None:
                self.tr.baseline(name, result, metrics)
            else:
                self.tr.evaluation(t, name, result, metrics)
            return metrics

    # Candidate execution is evaluated by the original M5 runner. Proposer code
    # is constrained before it can reach RSI's on-disk history or the evaluator.
    class MemoryDomain(Domain):
        name = "M5 online retrieval policy"

        def describe(self):
            return SELECTION_BRIEF

    domain = MemoryDomain(TaskSuite([], {"evolve": []}))
    config = Config(iterations=limit, k=1, validate=False, finalize=False,
                    objectives=("score",), shadow_monitor=False, seed=seed, summaries="never")
    loop = OnlineMetaLoop(domain, llm_task=None, proposer=BoundedProposer(proposer), config=config,
                          out_dir=root / "engine", baselines={"seed": Artifact({"policy.py": start.harness})})
    loop.run(iterations=limit - slots.used)
    return replay.best(lambda candidate: candidate.prompts == start.prompts)


def search_arm(replay, proposer, arm, output, *, seed=42):
    current = Candidate(P0)
    if arm == "DATA":
        replay.get(current, "val")
    for method, limit in ARMS[arm]:
        stage = Path(output) / method
        receipt = stage / "selection.json"
        if receipt.exists():
            current = Candidate(**read(receipt))
            continue
        run = run_gepa if method == "gepa" else run_meta
        current = run(replay, proposer, current, stage, limit=limit, seed=seed)
        write(receipt, current.wire())
    write(Path(output) / "selected_candidate.json", current.wire())
    return current
