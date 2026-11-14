"""Re-run the four ordered memory arms after the corrected Qwen baselines."""

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
from shutil import copy2, copytree, disk_usage, ignore_patterns
import subprocess
import sys
import time


ARMS = {"M2": "expel", "M3": "memp", "M7": "mobilee", "M9": "generative"}
COUNTS = {"chexbench": 618, "slake": 114, "vqarad": 116}
METHODS = ("react", "critic", "reflexion")
MODEL = "StanfordAIMI/CheXagent-8b"
REVISION = "4934e91451945c8218c267aae9c34929a7677829"
ENV = dict(CUDA_VISIBLE_DEVICES="0", R55_MEMEVOLVE_GPU="0", PYTHONDONTWRITEBYTECODE="1",
           HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false",
           LANGCHAIN_TRACING_V2="false", LANGSMITH_TRACING="false", OMP_NUM_THREADS="3",
           MKL_NUM_THREADS="3")


CHECKPOINT_WORKER = '''    elif name=='chest_xray_expert':
        from run_chexagent8_direct import CheXagent, MODEL, REVISION
        model = CheXagent(Path(cfg['chexagent8_snapshot']))
        answer, tokens = model.answer(image, args.get('question','Describe the visible findings.'), max_new_tokens=512)
        observation = raw = [{'response':answer,'model':MODEL,'revision':REVISION,'backend_output_tokens':tokens},
                             {'image_paths':[str(image)],'analysis_status':'completed'}]
        (folder/'provenance.json').write_text(json.dumps({'model':MODEL,'revision':REVISION,
            'checkpoint_path':cfg['chexagent8_snapshot']},indent=2),encoding='utf-8')
'''


def load(path):
    return json.loads(path.read_bytes())


def optional(path):
    return load(path) if path.is_file() else None


def replace(path, content):
    temp = path.with_name(f".{path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)


def record(path, info):
    replace(path, json.dumps(info, indent=2, ensure_ascii=False) + "\n")


@contextmanager
def lock(path):
    with path.open("a") as fd:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def stage(old, new, scratch):
    snapshot = old / "models/chexagent8_4934e91"
    weights = load(snapshot / "snapshot.json")
    if (weights["repo"], weights["revision"], len(weights["shards"])) != (MODEL, REVISION, 7):
        raise ValueError("Wrong CheXagent checkpoint")
    for filename, size in weights["shards"].items():
        if (snapshot / filename).stat().st_size != size:
            raise ValueError(f"Incomplete checkpoint file {filename}")

    if (new / "plan.json").is_file():
        return load(new / "plan.json")
    new.mkdir(mode=0o700, exist_ok=True)
    with lock(new / "stage.lock"):
        if (new / "plan.json").is_file():
            return load(new / "plan.json")
        code = new / "code"
        ignore = ignore_patterns("__pycache__", "*.pyc")
        copytree(old / "code", code, ignore=ignore, dirs_exist_ok=True)
        copytree(old / "bin", new / "bin", ignore=ignore, dirs_exist_ok=True)
        for name in ("data", "refs", "runtime", "env"):
            link = new / name
            if not link.is_symlink():
                link.symlink_to(old / name, target_is_directory=True)
        runner = code / "experiments/tool_worker_r54.py"
        source = runner.read_text(encoding="utf-8")
        start = source.index("    elif name=='chest_xray_expert':")
        stop = source.index("    elif ", start + 9)
        if "chexagent_smoke" not in source[start:stop]:
            raise ValueError("Previous CheXagent worker did not match the expected entry point")
        patched = source[:start] + CHECKPOINT_WORKER + source[stop:]
        ast.parse(patched)
        replace(runner, patched)
        model_wrapper = (old / "r55_direct_answer_rerun_20261114/code/run_chexagent8_direct.py").read_text()
        if "def answer(self, image, prompt):" in model_wrapper:
            model_wrapper = model_wrapper.replace("def answer(self, image, prompt):",
                                                  "def answer(self, image, prompt, max_new_tokens=64):")
            model_wrapper = model_wrapper.replace("generation_config=self.config, max_new_tokens=64",
                                                  "generation_config=self.config, max_new_tokens=max_new_tokens")
        ast.parse(model_wrapper)
        replace(runner.with_name("run_chexagent8_direct.py"), model_wrapper)

        jobs = new / "jobs"
        ready = jobs / "priority-tool-ready"
        ready.mkdir(mode=0o700, parents=True, exist_ok=True)
        inherited_ready = old / "jobs/priority-tool-ready"
        gpu_paths = {}
        for arm, provider in ARMS.items():
            dst = new / "manifests" / arm
            dst.mkdir(parents=True, exist_ok=True)
            for ds, count in COUNTS.items():
                manifest = load(old / "manifests" / arm / f"{ds}.json")
                if (len(manifest["inputs"]), manifest["memory_provider"], manifest["initial_repo"],
                        manifest["skill_enabled"]) != (count, provider, "empty", False):
                    raise ValueError(f"Wrong old cohort or memory configuration for {arm}/{ds}")
                runtime = manifest["runtime"]
                tools = runtime["arms"]["M"]["tools"]
                if len(tools) != 11 or set(tools) != set(runtime["tools"]):
                    raise ValueError(f"Wrong tool set for {arm}/{ds}")
                for name in tools:
                    receipt = inherited_ready / f"{name}.json"
                    if receipt.is_file() and name != "chest_xray_expert":
                        copy2(receipt, ready / receipt.name)
                spec = runtime["tools"]["chest_xray_expert"]
                spec.update(revision=REVISION, deployment_status=MODEL)
                runtime["backend_config"].pop("chexagent_snapshot", None)
                runtime["backend_config"]["chexagent8_snapshot"] = str(snapshot)
                protocol = manifest["protocol"]
                protocol["experiment_id"] = f"{new.name}-{arm}-{ds}"
                # Preserve the exact request payload through the existing lossless image archive.
                protocol["request_archive"] = "image_base64_content_addressed_v1"
                manifest["implementation_revision"] = "R55-top4-full848-CheXagent8B"
                manifest["chexagent"] = {"model": MODEL, "revision": REVISION, "max_new_tokens": 512}
                file = dst / f"{ds}.json"
                manifest["config"].update(protocol=str(file), runtime=str(file))
                record(file, manifest)

            gen = new / "generation"
            gen.mkdir(mode=0o700, exist_ok=True)
            output = gen / arm
            if arm in ("M7", "M9"):
                volume = scratch / "rerun_chexagent8_generation" / arm
                volume.mkdir(mode=0o700, parents=True, exist_ok=True)
                if not output.is_symlink():
                    output.symlink_to(volume, target_is_directory=True)
            else:
                output.mkdir(mode=0o700, exist_ok=True)
            gpu_paths[arm] = str(output.resolve())

        plan = dict(previous_run=str(old), root=str(new), arms=ARMS, counts=COUNTS, tool_count=11,
                    checkpoint=str(snapshot), chexagent=MODEL, revision=REVISION,
                    baseline=str(old / "chexagent8"), baseline_methods=METHODS,
                    output_paths=gpu_paths, initial_memory="empty", skill_enabled=False,
                    storage_bytes={str(path):disk_usage(path).free for path in (new, scratch)})
        record(new / "plan.json", plan)
        return plan


def run_smoke(root):
    receipt = root / "jobs/priority-tool-ready/chest_xray_expert.json"
    if receipt.is_file():
        return load(receipt)
    manifest = load(root / "manifests/M2/chexbench.json")
    runtime = manifest["runtime"]
    backend = runtime["backend_config"]
    image = root / "data/chexbench" / manifest["inputs"][0]["images"][0]
    directory = root / "smoke" / f"attempt-{time.time_ns()}"
    directory.mkdir(mode=0o700, parents=True)
    spec = runtime["tools"]["chest_xray_expert"]
    request = {"tool":"chest_xray_expert", "backend":spec["backend"],
               "args":{"question":"What imaging modality is shown? Answer briefly."},
               "image":str(image.resolve(strict=True)), "artifact_dir":str(directory / "artifacts"),
               "runtime":backend}
    command = [spec["python"], "-B", str(root / "code/experiments/tool_worker_r54.py")]
    result = subprocess.run(command, input=json.dumps(request), capture_output=True, text=True,
                            env={**os.environ, **spec.get("worker_env", {}), **ENV}, timeout=300)
    (directory / "stdout.log").write_text(result.stdout, encoding="utf-8")
    (directory / "stderr.log").write_text(result.stderr, encoding="utf-8")
    result.check_returncode()
    value = json.loads(result.stdout.split("CXR_VQA_RESULT=")[-1])
    obs = value.get("observation") or []
    if (value["status"] != "completed" or not obs or
            (obs[0].get("model"), obs[0].get("revision")) != (MODEL, REVISION) or
            not obs[0].get("response") or
            not any(e["status"] == "completed" for e in value["actual_model_events"])):
        raise RuntimeError(f"CheXagent-8B tool smoke failed, see {directory}")
    details = dict(model=MODEL, revision=REVISION, answer=obs[0]["response"],
                   output_tokens=obs[0]["backend_output_tokens"], worker_exit=0, completed=True,
                   peak_bytes=value["cuda_peak_allocated_bytes_by_visible_device"], attempt=str(directory))
    record(receipt, details)
    return details


def baseline_scores(out, method):
    scores = {}
    for ds, size in COUNTS.items():
        folder = out / method / ds
        score = optional(folder / "summary.json")
        predictions = set((folder / "predictions").glob("*.json"))
        if score and (score["arm"], score["dataset"], score["questions"], len(predictions)) == (
                method, ds, size, size):
            scores[ds] = {"correct": score["correct"], "questions": size}
    return scores


def run_baselines(root, plan, main_key):
    previous = Path(plan["previous_run"])
    out = previous / "chexagent8"
    migrated = load(out / "migration.json")
    if (migrated["model"], migrated["revision"], migrated["output_name"]) != (MODEL, REVISION, out.name):
        raise ValueError("Incorrect migrated baseline model or archive identity")
    snapshot = Path(plan["checkpoint"])
    sys.path.insert(0, str(out / "code"))
    from queue_chexagent8_lab import environment, release_worker, run_process

    env = {**environment("0", snapshot), "R55_BASELINE_SOURCE_DIR": migrated["source"]}
    methods = {}
    for method in METHODS:
        record(root / "jobs/queue_state.json",
               dict(phase="qwen_baselines", method=method, completed=methods, epoch=time.time()))
        job = out / "jobs" / method
        job.mkdir(parents=True, exist_ok=True)
        done = optional(job / "complete.json")
        if done and done["revision"] == REVISION and baseline_scores(out, method) == done["datasets"]:
            methods[method] = done
            continue
        attempt = job / f"attempt-{time.time_ns()}"
        command = [str(root / "env/modern/bin/python"), "-B", "-u", str(out / "code/run_qwen_baselines.py"),
                   str(previous), str(out), method, "--workers", "4"]
        try:
            rc = run_process(command, env, attempt, main_key + b"\n")
        finally:
            release_worker(out, "0")
        scores = baseline_scores(out, method)
        if rc != 0 or set(scores) != set(COUNTS):
            raise RuntimeError(f"Qwen {method} exited {rc} with {len(scores)}/3 finished datasets, see {attempt}")
        result = dict(revision=REVISION, method=method, exit=rc, datasets=scores)
        record(job / "complete.json", result)
        methods[method] = result
    record(root / "jobs/baseline_gate.accepted.json", dict(revision=REVISION, methods=methods))


def run_dataset(root, arm, dataset, keys):
    stage = root / "jobs" / arm / dataset
    stage.mkdir(mode=0o700, parents=True, exist_ok=True)
    out = root / "generation" / arm / dataset
    if (stage / "score.exitcode").is_file() and (stage / "score.exitcode").read_text().strip() == "0":
        return load(out / "analysis/summary.json")
    attempt = stage / f"attempt-{time.time_ns()}"
    attempt.mkdir()
    common = [str(root / "env/modern/bin/python"), "-B", "-u", str(root / "bin/run_top4_priority.py")]
    env = {**os.environ, **ENV}
    if not (out / "generation.exitcode").is_file() or (out / "generation.exitcode").read_text().strip() != "0":
        with (attempt / "runner.stdout.log").open("xb") as stdout, (attempt / "runner.stderr.log").open("xb") as stderr:
            proc = subprocess.Popen([*common, "dataset", str(root), arm, "--dataset", dataset],
                                    stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, cwd=root, env=env)
            replace(stage / "runner.pid", f"{proc.pid}\n")
            record(attempt / "runner.started.json", dict(pid=proc.pid, epoch=time.time()))
            proc.communicate(keys)
        replace(stage / "runner.exitcode", f"{proc.returncode}\n")
        if out.is_dir():
            replace(out / "generation.exitcode", f"{proc.returncode}\n")
        if proc.returncode:
            raise RuntimeError(f"{arm}/{dataset} generation exited {proc.returncode}, see {attempt}")
    with (attempt / "score.stdout.log").open("xb") as stdout, (attempt / "score.stderr.log").open("xb") as stderr:
        result = subprocess.run([*common, "score", str(root), arm, "--dataset", dataset],
                                stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, cwd=root, env=env)
    replace(stage / "score.exitcode", f"{result.returncode}\n")
    result.check_returncode()
    s = load(out / "analysis/summary.json")
    if (s["arm"], s["dataset"], s["questions"]) != (f"R55-{arm}", dataset, COUNTS[dataset]):
        raise ValueError(f"Invalid completed score for {arm}/{dataset}")
    return s


def run_arm(root, arm, keys):
    job = root / "jobs" / arm
    job.mkdir(mode=0o700, exist_ok=True)
    with lock(job / "controller.lock"):
        try:
            scores = {dataset: run_dataset(root, arm, dataset, keys) for dataset in COUNTS}
            details = dict(arm=arm, datasets=scores,
                           questions=sum(v["questions"] for v in scores.values()),
                           correct=sum(v["correct"] for v in scores.values()))
            record(job / "controller.completed.json", details)
            replace(job / "controller.exitcode", "0\n")
            return dict(correct=details["correct"], questions=details["questions"])
        except Exception:
            replace(job / "controller.exitcode", "1\n")
            raise


def run_queue(root, keys):
    if len(keys.splitlines()) != 2 or not all(keys.splitlines()):
        raise ValueError("Missing existing main or memory model credentials")
    jobs = root / "jobs"
    plan = load(root / "plan.json")
    with lock(jobs / "queue.lock"):
        state = jobs / "queue_state.json"
        try:
            record(state, dict(phase="tool_smoke", epoch=time.time()))
            run_smoke(root)
            run_baselines(root, plan, keys.splitlines()[0])
        except Exception as exc:
            record(state, dict(phase="failed_before_memory_rerun", error=str(exc), epoch=time.time()))
            raise
        record(state, dict(phase="running", arms=list(ARMS), epoch=time.time()))
        finished, failed = {}, {}
        with ThreadPoolExecutor(max_workers=len(ARMS)) as workers:
            futures = {workers.submit(run_arm, root, arm, keys): arm for arm in ARMS}
            for future in as_completed(futures):
                arm = futures[future]
                try:
                    finished[arm] = future.result()
                except Exception as exc:
                    failed[arm] = str(exc)
                record(state, dict(phase="running", completed=finished, failed=failed, epoch=time.time()))
        phase = "finished_with_errors" if failed else "complete"
        record(state, dict(phase=phase, completed=finished, failed=failed, epoch=time.time()))
        return int(bool(failed))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    for name, fields in {"stage": ("old", "root", "scratch"), "run": ("root",),
                         "smoke": ("root",)}.items():
        command = sub.add_parser(name)
        for field in fields:
            command.add_argument(field, type=Path)
    args = parser.parse_args()
    if args.mode == "stage":
        print(json.dumps(stage(args.old, args.root, args.scratch)))
    elif args.mode == "smoke":
        print(json.dumps(run_smoke(args.root)))
    else:
        raise SystemExit(run_queue(args.root, sys.stdin.buffer.read()))


if __name__ == "__main__":
    main()
