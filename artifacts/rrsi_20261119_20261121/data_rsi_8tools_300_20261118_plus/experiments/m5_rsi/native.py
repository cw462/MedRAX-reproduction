"""Trusted subprocess adapter for the original R55 online engine and M5 provider."""

import argparse
from collections import defaultdict
from contextlib import contextmanager
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

from .data import digest, read, write, write_bytes
from .policy import HarnessPolicy, edit_instruction
from .search import Candidate, key_for


NATIVE_ARM = "R55-M5-DATA-RSI"
GRAPH = Path("storage/cerebra_fusion_memory/cf_database.json")
NATIVE_TOOLS = (
    "chest_xray_expert", "llava_med_qa", "medgemma", "llava_rad", "medvlm_r1",
    "maira2_grounded_report", "xray_phrase_grounding", "roi_crop",
)
QWEN_KEY = "M5_RSI_QWEN_TOKEN_PLAN_KEY"
DEEPSEEK_KEY = "M5_RSI_DEEPSEEK_KEY"
EVAL_DATASETS = {"chexbench", "slake", "vqarad"}


@contextmanager
def run_lock(path):
    import fcntl

    with path.open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def native_paths(binding):
    names = ("experiment_sources", "memory_driver_sources", "memory_runtime", "template")
    paths = {name: Path(binding[name]).resolve(strict=True) for name in names}
    for name in ("experiment_sources", "memory_driver_sources", "memory_runtime"):
        if not paths[name].is_dir():
            raise ValueError(f"Invalid native path {name}")
    if digest(paths["template"]) != binding["template_sha256"]:
        raise ValueError("Bound R55 manifest template changed")
    return paths


def install_native_paths(binding):
    paths = native_paths(binding)
    sys.path[:0] = [str(paths["experiment_sources"]), str(paths["memory_driver_sources"])]
    return paths


def image_order(inputs):
    seen = defaultdict(list)
    order = []
    for row in inputs:
        qid = row["question_id"]
        key = json.dumps(["image_id", row["image_id"]], ensure_ascii=False)
        order.append({"question_id": qid, "image_key": key, "previous_ids": list(seen[key])})
        seen[key].append(qid)
    return order


def public_row(row):
    keys = ("question_id", "question", "options", "images", "image_id")
    return {key: copy.deepcopy(row[key]) for key in keys if key in row}


def load_inputs(root, member, limit=None):
    manifest = read(root / member / "inputs.json")
    rows = manifest["inputs"]
    if limit is not None:
        rows = rows[:limit]
    if not rows:
        raise ValueError("Cannot run an empty online stream")
    inputs = [public_row(row) for row in rows]
    recorded = manifest["order"]
    if recorded and isinstance(recorded[0], dict):
        order = recorded[:len(rows)]
    else:
        if recorded[:len(rows)] != [row["question_id"] for row in rows]:
            raise ValueError("Canonical development order changed")
        order = image_order(inputs)
    return rows, inputs, order


def stage_references(manifests, member, inputs, out):
    refs = out / "sealed_references"
    labels = {row["question_id"]: row for row in read(manifests / member / "labels.json")}
    binding = {}
    for row in inputs:
        qid = row["question_id"]
        if not qid.replace("_", "").isalnum():
            raise ValueError("Unsafe dataset question identifier")
        name = qid + ".json"
        reference = labels[qid]
        if set(reference) - {"question_id", "answer", "answer_text"}:
            raise ValueError("Reference record contains fields not admitted by the broker")
        if (refs / name).is_file() and read(refs / name) != reference:
            raise ValueError("Frozen reference changed")
        if not (refs / name).is_file():
            write(refs / name, reference)
        binding[qid] = {"file": name}
    return refs, binding


def prepare_graph(out, snapshot):
    marker = out / "starting_memory.json"
    if snapshot is None:
        beginning = {"source": "original_generic_M5_patterns", "ingests": 0, "sha256": None}
    else:
        beginning = read(snapshot / "snapshot.json")
        if digest(snapshot / "graph.json") != beginning["sha256"]:
            raise ValueError("Training snapshot differs from the frozen graph")
    if marker.is_file():
        if read(marker) != beginning:
            raise ValueError("Cannot change the initial memory on resume")
        return beginning
    if (out / GRAPH).is_file():
        raise ValueError("Unexpected pre-existing dynamic memory")
    if snapshot is not None:
        write_bytes(out / GRAPH, (snapshot / "graph.json").read_bytes())
    write(marker, beginning)
    return beginning


def replay_memory(driver, out, prompts, harness, beginning, runtime, key, fixture=None):
    """Keep R55's provider and save a rollback point for the only in-flight ingest."""
    rollback = out / "memory_ingest_pending"
    book = out / "external_memory"
    pending_file = rollback / "pending.json"
    if pending_file.is_file():
        pending = read(pending_file)
        committed = book / "episodes" / pending["qid"] / "ingest.json"
        if not committed.is_file():
            before = rollback / "before.json"
            if digest(before) != pending["graph_sha256"]:
                raise ValueError("Interrupted memory update lost its rollback graph")
            write_bytes(out / GRAPH, before.read_bytes())
    else:
        pending = None

    class RecordedModel(driver.AuditedModel):
        def __init__(self):
            super().__init__(book / "model_calls", key, fixture, use_official=True)
            self.replay = []

        def __call__(self, messages):
            if isinstance(messages, str):
                messages = [{"role": "user", "content": messages}]
            for name in ("memory_write", "advice_synthesis"):
                messages = edit_instruction(messages, name, prompts[name], role="user")
            if self.replay:
                prior = self.replay.pop(0)
                request = read(prior / "request.json")
                res = read(prior / "result.json")
                if request["messages"] != messages or res.get("error"):
                    raise RuntimeError("Saved writer response cannot be replayed without manual evidence resolution")
                return read(prior / "response.raw")["choices"][0]["message"]["content"]
            return super().__call__(messages)

    class TransactionalMemory(driver.Memory):
        def ingest(self, row, trace, feedback):
            qid = row["question_id"]
            completed = self.out / "episodes" / qid / "ingest.json"
            if completed.is_file():
                return super().ingest(row, trace, feedback)
            graph = out / GRAPH
            if not graph.is_file():
                self.provider._persist_db()
            if pending and pending["qid"] == qid:
                ledger = self.model.root / qid / "ingest"
                records = sorted(ledger.glob("*/result.json"), key=lambda item: int(item.parent.name))
                self.model.replay = [item.parent for item in records]
            write_bytes(rollback / "before.json", graph.read_bytes())
            write(pending_file, {"qid": qid, "graph_sha256": digest(graph)})
            result = super().ingest(row, trace, feedback)
            if self.model.replay:
                raise RuntimeError("Ingest failed to consume its saved responses")
            write(out / "memory_versions" / f"{qid}.json", {
                "graph_after": digest(graph), "task_counter": self.provider.task_counter,
            })
            pending_file.unlink()
            return result

    memory = TransactionalMemory("M5", runtime, book, key, fixture, use_official=True)
    model = RecordedModel()
    model.calls = memory.model.calls
    memory.model = memory.provider.model = model
    ingests = list(book.glob("episodes/*/ingest.json"))
    successes = sum(read(path)["native_description"].startswith("Ingested ") for path in ingests)
    memory.provider.task_counter = (beginning["ingests"] + successes) % memory.provider.consolidation_interval
    if memory.provider.enable_tool_memory:
        raise ValueError("Native M5 unexpectedly allows generated tools")
    if not ingests and beginning["sha256"] is None and len(memory.provider.nodes) != 7:
        raise ValueError("Native generic seed pattern count changed")
    HarnessPolicy(harness).apply(memory.provider)
    return memory


def execute(packet):
    """Execute one trusted chronological replay on the staged native Linux environment."""
    binding = packet["binding"]
    paths = install_native_paths(binding)
    import run_online_skill_r54 as engine
    import r55_memevolve_driver_official as driver
    from online_memory_r49 import ReferenceVault
    from skill_services_r55 import Services

    candidate = Candidate(**packet["candidate"])
    out = Path(packet["out"]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    member = packet["member"]
    phase = packet["phase"]
    if phase in {"search", "smoke", "warmup"} and member not in {"train_new", "val_new"}:
        raise ValueError("A development replay cannot open final evaluation data")
    if phase == "evaluate" and member not in {f"eval_848/{d}" for d in EVAL_DATASETS}:
        raise ValueError("Final scoring requires a frozen evaluation dataset")
    if phase not in {"search", "smoke", "warmup", "evaluate"}:
        raise ValueError("Unknown native replay phase")
    manifests = Path(binding["manifests"]).resolve()
    assets = Path(binding["assets"]).resolve()
    snapshot = Path(packet["snapshot"]).resolve() if packet.get("snapshot") else None
    main_key = os.environ[QWEN_KEY]
    memory_key = os.environ[DEEPSEEK_KEY]
    template = read(paths["template"])
    if template["protocol"]["model"] != binding["model"]:
        raise ValueError("Native model route changed")
    runtime = copy.deepcopy(template["runtime"])
    tools = runtime["arms"]["M"]["tools"]
    if tuple(tools) != NATIVE_TOOLS or set(tools) != set(runtime["tools"]):
        raise ValueError("Native 11-tool configuration required")
    rows, inputs, order = load_inputs(manifests, member, packet.get("limit"))
    views = runtime["backend_config"]["r54_image_views_by_path"]
    for row in rows:
        for image in row["images"]:
            path = (assets / image).resolve(strict=True)
            canonical = next(item["asset"] for item in row["image_hashes"] if "images/" + item["asset"] == image)
            if member.startswith("eval_848/"):
                # Evaluation originals carry the existing audited modality/view binding.
                view = binding["eval_views"][canonical]
            else:
                modality = row["modality"]
                view = {"modality": "CXR" if modality == "X-Ray" and row["view"] == "frontal" else
                        "other" if modality in {"CT", "MRI"} else "unknown",
                        "view": row["view"], "source": row["source_version"]}
            views[str(path)] = view

    class PromptServices(Services):
        def call(self, row, role, ordinal, messages):
            if role == "R49-AGENT":
                messages = edit_instruction(messages, "solver_instruction", candidate.prompts["solver_instruction"],
                                            role="system", required=True)
            return super().call(row, role, ordinal, messages)

    with run_lock(out / "stream.lock"):
        request_hash = key_for(packet)
        identity = out / "stream_binding.json"
        if identity.is_file() and read(identity)["hash"] != request_hash:
            raise ValueError("Cannot change a started stream's inputs, model, memory, or candidate")
        write(identity, {"hash": request_hash})
        receipt = out / "native.completed.json"
        if receipt.is_file():
            return read(receipt)
        engine.ARM = NATIVE_ARM
        references, ref_map = stage_references(manifests, member, inputs, out)
        driver.load_runtime(paths["memory_runtime"], out)
        initial = prepare_graph(out, snapshot)
        memory = replay_memory(driver, out, candidate.prompts, candidate.harness, initial,
                               paths["memory_runtime"], memory_key)
        service = PromptServices(template["config"], template["protocol"], runtime, out / "services", main_key,
                                 template["embedding_model"], template.get("embedding_base_url"))
        engine.run_stream(inputs, order, assets, out, service, ReferenceVault(references, ref_map), tools,
                          evolver=engine.disabled_evolve, external_memory=memory)
        scores, traces = [], []
        for row in inputs:
            qid = row["question_id"]
            event = read(out / "feedback" / f"{qid}.json")
            pred = read(out / "predictions" / NATIVE_ARM / f"{qid}.json")
            reward = engine.released_reward(row, pred, event["reference_annotation"])
            scores.append(reward)
            if member == "train_new" and phase != "warmup":
                traces.append({
                    "question": row["question"], "options": row.get("options"), "answer": pred.get("answer"),
                    "reference": event["reference_annotation"], "reason": pred.get("reason"),
                    "decisions": [{"response": entry.get("response", "")[:1500]}
                                  for entry in read(out / "steps" / f"{qid}.json")[:5]],
                })
        if member == "train_new":
            sealed = out / "warm_snapshot"
            graph = out / GRAPH
            if not graph.is_file():
                memory.provider._persist_db()
            write_bytes(sealed / "graph.json", graph.read_bytes())
            ingests = sum(read(x)["native_description"].startswith("Ingested ")
                          for x in (out / "external_memory").glob("episodes/*/ingest.json"))
            write(sealed / "snapshot.json", {"source": "one_chronological_development_pass",
                                             "ingests": ingests, "sha256": digest(graph)})
        result = {"scores": scores}
        if traces:
            result["train_traces"] = traces
        write(receipt, result)
        return result


class NativeRunner:
    """The optimizer sees only the subprocess response for train/validation."""

    def __init__(self, binding, executable, workspace, *, phase="search", limits=None):
        self.binding, self.executable, self.workspace = binding, executable, workspace
        self.phase, self.limits = phase, limits or {}

    def __call__(self, candidate, split, stream, snapshot):
        member = {"train": "train_new", "val": "val_new"}.get(split, split)
        result = self.invoke(candidate, member, stream, snapshot, self.phase, self.limits.get(split))
        if split != "train" and "train_traces" in result:
            raise ValueError("A trusted non-training replay returned text traces")
        return result

    def invoke(self, candidate, member, stream, snapshot, phase, limit=None):
        stream = Path(stream)
        packet = {"binding": self.binding, "candidate": candidate.wire(), "phase": phase,
                  "member": member, "limit": limit, "out": str(stream), "snapshot": str(snapshot) if snapshot else None}
        fname = stream / "native_request.json"
        write(fname, packet)
        subprocess.run([self.executable, "-B", "-m", "experiments.m5_rsi.native", str(fname)],
                       cwd=self.workspace, check=True)
        return read(stream / "native.completed.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    execute(read(parser.parse_args().packet))
