"""Run the Qwen3.6-Flash Direct baseline on the frozen R55 question set."""

import argparse
import ast
import base64
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from http.client import HTTPException
import json
from pathlib import Path
import re
import sys
import tarfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DATASETS = ("chexbench", "slake", "vqarad")
COUNTS = {"chexbench": 618, "slake": 114, "vqarad": 116}
ENDPOINT = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions"
MODEL = "qwen3.6-flash"
ANSWER_FORMAT = "Answer with the single best word/phrase or option letter only."


def read_jsonl(path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare(input_dir, archive_dir, cache):
    metadata = {
        row["question_id"]: row
        for row in json.loads((input_dir / "questions_848.json").read_text(encoding="utf-8"))
    }
    cases = []
    for dataset in DATASETS:
        rows = read_jsonl(input_dir / f"{dataset}_inputs.jsonl")
        assert len(rows) == COUNTS[dataset]
        subset_dir = cache / dataset
        subset_dir.mkdir(parents=True, exist_ok=True)
        wanted = {row["question_id"] for row in rows}
        raw_images = {}
        calls = re.compile(r"/calls/react/([^/]+)/1/request\.json$")
        with tarfile.open(archive_dir / dataset / "evidence.tar.gz", mode="r|gz", bufsize=1024 * 1024) as archive:
            for member in archive:
                path = member.name
                if not member.isfile():
                    continue
                if "/request_image_base64/" in path:
                    name = path.rsplit("/", 1)[-1]
                    if re.fullmatch(r"[0-9a-f]{64}", name):
                        (subset_dir / name).write_bytes(archive.extractfile(member).read())
                    continue
                match = calls.search(path)
                if not match or match[1] not in wanted:
                    continue
                request = json.load(archive.extractfile(member))
                images = [
                    part["image_url"]["url"]
                    for message in request["messages"]
                    if isinstance(message.get("content"), list)
                    for part in message["content"]
                    if part.get("type") == "image_url"
                ]
                assert len(images) == 1 and isinstance(images[0], dict), match[1]
                raw_images[match[1]] = images[0]
        assert set(raw_images) == wanted, (dataset, sorted(wanted - set(raw_images)))
        required = set()
        for row in rows:
            qid = row["question_id"]
            image = raw_images[qid]
            name = image["cxr_request_image_base64_sha256"]
            target = subset_dir / name
            if not target.is_file():
                raise FileNotFoundError(f"Archived image for {qid}")
            required.add(name)
            meta = metadata[qid]
            assert row["question"].strip() == meta["question"].strip(), qid
            cases.append({
                "question_id": qid,
                "dataset": dataset,
                "subset": qid.rsplit("_", 1)[0] if dataset == "chexbench" else dataset,
                "question": row["question"],
                "options": meta.get("options") or {},
                "reference": meta["reference"],
                "image": f"{dataset}/{name}",
                "media_type": image["media_type"],
            })
        for existing in subset_dir.iterdir():
            if existing.name not in required and re.fullmatch(r"[0-9a-f]{64}", existing.name):
                existing.unlink()
        print(f"Prepared {dataset}: {len(rows)} questions, {len(required)} source images.", flush=True)
    assert len(cases) == len({case["question_id"] for case in cases}) == 848
    write_json(cache / "cases.json", cases)


def scorer_from(source):
    tree = ast.parse(source.read_text(encoding="utf-8"))
    functions = {"norm_ans", "score"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in functions]
    assert {node.name for node in nodes} == functions
    namespace = {"re": re}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
    return namespace["score"]


def prompt(case):
    question = case["question"]
    if case["options"]:
        options = "; ".join(f"{letter}. {text}" for letter, text in case["options"].items())
        question += "\nOptions: " + options
    return "Question about the image: " + question + "\n" + ANSWER_FORMAT


def request_prediction(case, api_key, cache):
    encoded = (cache / case["image"]).read_text(encoding="ascii").strip()
    media = case["media_type"]
    prefix = base64.b64decode(encoded[:16])
    if prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        media = "image/png"
    elif prefix.startswith(b"\xff\xd8\xff"):
        media = "image/jpeg"
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:{media};base64,{encoded}"}},
            {"type": "text", "text": prompt(case)},
        ]}],
        "temperature": 0,
        "max_tokens": 60,
        "enable_thinking": False,
    }
    request = Request(ENDPOINT, data=json.dumps(payload).encode("utf-8"), headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
    })
    started = time.monotonic()
    last_failure = ""
    for attempt in range(1, 4):
        try:
            with urlopen(request, timeout=65) as response:
                reply = json.load(response)
            choice = reply["choices"][0]
            if not isinstance(choice["message"].get("content"), str):
                raise ValueError("Missing answer content")
            if reply.get("model") != MODEL and not str(reply.get("model", "")).startswith(MODEL + "-"):
                raise ValueError("Response returned a different model")
            if choice["message"].get("reasoning_content"):
                raise ValueError("Response returned native reasoning despite disabled thinking")
            return {**case, "answer": choice["message"]["content"].strip(),
                    "response_model": reply["model"], "finish_reason": choice.get("finish_reason"),
                    "usage": reply.get("usage", {}), "attempts": attempt,
                    "elapsed_seconds": round(time.monotonic() - started, 3)}
        except HTTPError as error:
            message = error.read(700).decode("utf-8", errors="replace").replace(api_key, "[redacted]")
            message = re.sub(r"sk-[A-Za-z0-9_.-]+", "[redacted]", message)
            last_failure = f"HTTP {error.code}: {message}"
            if error.code not in (408, 429, 500, 502, 503, 504):
                break
            try:
                retry_after = float(error.headers.get("Retry-After", 0))
            except ValueError:
                retry_after = 0
            if attempt < 3:
                time.sleep(max(2 ** attempt, min(retry_after, 30)))
        except (URLError, TimeoutError, ConnectionError, HTTPException) as error:
            last_failure = f"Transport {type(error).__name__}: {error}"
            if attempt < 3:
                time.sleep(2 ** attempt)
        except (KeyError, IndexError, ValueError) as error:
            last_failure = f"Invalid model response: {error}"
            break
    return {**case, "error": last_failure, "attempts": attempt,
            "elapsed_seconds": round(time.monotonic() - started, 3)}


def generate(args):
    api_key = sys.stdin.readline().strip()
    if not api_key:
        raise SystemExit("The API credential is required on standard input.")
    args.out.mkdir(parents=True, exist_ok=True)
    cases = json.loads((args.cache / "cases.json").read_text(encoding="utf-8"))
    raw = args.out / "generation.jsonl"
    already = read_jsonl(raw) if raw.is_file() else []
    completed = {row["question_id"] for row in already if "error" not in row}
    pending = [case for case in cases if case["question_id"] not in completed]
    if not pending:
        print("The frozen cohort already has 848 responses.", flush=True)
        return
    protocol_path = args.out / "protocol.json"
    if not protocol_path.is_file():
        write_json(protocol_path, {
            "model": MODEL, "endpoint": ENDPOINT, "generation_start": datetime.now().astimezone().isoformat(),
            "prompt_prefix": "Question about the image: ", "answer_format": ANSWER_FORMAT,
            "temperature": 0, "max_tokens": 60, "enable_thinking": False, "tools": [],
            "cohorts": COUNTS, "workers": args.workers, "source": "Frozen R55 first-call original-image archives",
            "scoring": "RAG handoff Direct scorer",
        })
    with raw.open("a", encoding="utf-8", buffering=1) as stream:
        def save(row):
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")

        # The preflight is an actual cohort case and its successful answer counts.
        first = request_prediction(pending[0], api_key, args.cache)
        save(first)
        if "error" in first:
            raise SystemExit(f"{first['question_id']}: {first['error']}")
        print(f"First Direct response accepted. Completed {len(completed) + 1}/848.", flush=True)
        failures = 0
        done = len(completed) + 1
        start = time.monotonic()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(request_prediction, case, api_key, args.cache): case for case in pending[1:]}
            try:
                for future in as_completed(futures):
                    row = future.result()
                    save(row)
                    done += 1
                    if "error" in row:
                        failures += 1
                        print(f"{row['question_id']}: {row['error']}", flush=True)
                        if failures >= 5:
                            raise RuntimeError("Five provider failures. Completed responses were retained.")
                    if done % 40 == 0 or done == len(cases):
                        print(f"Attempted {done}/848; provider failures {failures}; {time.monotonic()-start:.0f}s.", flush=True)
            except BaseException:
                for future in futures:
                    future.cancel()
                raise
    if failures:
        raise SystemExit(f"{failures} cases need technical recovery. Completed responses were retained.")


def summarize(args):
    cases = json.loads((args.cache / "cases.json").read_text(encoding="utf-8"))
    generated = read_jsonl(args.out / "generation.jsonl")
    responses = {row["question_id"]: row for row in generated if "answer" in row}
    expected = {case["question_id"] for case in cases}
    if len(responses) != 848 or set(responses) != expected:
        raise SystemExit(f"The score requires all 848 responses. Available: {len(responses)}.")
    score = scorer_from(args.scorer)
    results = []
    for case in cases:
        row = responses[case["question_id"]]
        row["correct"] = bool(score(row["answer"], row["reference"], row["options"]))
        results.append(row)

    def aggregate(rows):
        correct = sum(row["correct"] for row in rows)
        return {"correct": correct, "total": len(rows), "accuracy_pct": correct * 100 / len(rows)}

    by_dataset = {ds: aggregate([row for row in results if row["dataset"] == ds]) for ds in DATASETS}
    by_subset = {
        subset: aggregate([row for row in results if row["subset"] == subset])
        for subset in ("chexbench_openi", "chexbench_rad_restruct", "chexbench_slake")
    }
    usage = Counter()
    for row in results:
        usage.update({k: v for k, v in row["usage"].items() if isinstance(v, int)})
    summary = {"datasets": by_dataset, "chexbench_subsets": by_subset,
               "overall": aggregate(results), "usage_tokens": dict(usage),
               "finish_reasons": dict(Counter(row["finish_reason"] for row in results)),
               "response_models": dict(Counter(row["response_model"] for row in results)),
               "provider_failures_recovered": len(generated) - len(results),
               "scored_at": datetime.now().astimezone().isoformat()}
    with (args.out / "predictions.jsonl").open("w", encoding="utf-8") as stream:
        for row in results:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    write_json(args.out / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "generate", "summarize"))
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--archive-dir", type=Path)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--scorer", type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.input_dir, args.archive_dir, args.cache)
    elif args.command == "generate":
        generate(args)
    else:
        summarize(args)


if __name__ == "__main__":
    main()

