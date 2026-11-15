"""Freeze label-free, case-level E3 evidence from the two original CXR tools.

Default mode only prepares the plan. ``--mode generate`` is the explicit local
inference entry point; it is not authorization to launch an experiment. The
caller must separately obtain the user's run approval. No provider API is used.

Inputs are the frozen question JSONL (question_id, case_id, question, images,
optional figure_labels). Modality is supplied BEFORE inference in a separate
JSON manifest: {"schema_version": 1, "images": [{"source_filename": "...",
"modality": "CXR", "provenance": {"kind": "metadata|caption|human_review",
"source": "...", "quote": "..."}}]}. Do not copy diagnosis, answer, category,
reasoning or model-response fields into that manifest. Unknown images are skipped.

One immutable cases/<case_id>.json is assembled for every case. Each tool sees
each eligible unique original filename once within that case; it never sees the
questions, options or reference labels. Invocation checkpoints prohibit automatic
reissue after an interrupted call. Inference consumers use evidence_for_model,
including NO_EVIDENCE when no usable tool observation exists, and still answer
every question from its own original images and complete question/options.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import time

HERE = Path(__file__).resolve().parent
TOOLS = ("chest_xray_classifier", "chest_xray_report_generator")
KINDS = dict(zip(TOOLS, ("classification", "report")))
ROW_FIELDS = {"question_id", "case_id", "question", "images", "figure_labels"}
SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,150}\Z")
CLASSIFIER_FILENAME = ("nih-pc-chex-mimic_ch-google-openi-kaggle-densenet121-"
                       "d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt")
LIMITATIONS = [
    "Unverified model outputs; medical correctness has not been established.",
    "Classifier scores are XRV operating-point normalized scores, not calibrated "
    "disease probabilities; they do not establish localization, laterality or change.",
    "Reports may omit findings or hallucinate. Check claims against the original pixels.",
    "Missing, failed or interrupted evidence does not mean normal or absent disease.",
    "Evidence includes all case originals; match each claim to its source filename "
    "and use only images relevant to the current question. Image order is not chronology.",
]


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read(path):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate_json_key:" + key)
            value[key] = item
        return value
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=pairs)


def transport_scalars(value, conversions, path='$'):
    """Preserve NumPy scalar numeric values as JSON-native Python scalars."""
    if type(value).__module__.startswith('numpy') and hasattr(value, 'item') and getattr(value, 'ndim', 1) == 0:
        converted=value.item()
        conversions.append({'path':path,'source_type':type(value).__name__,
                            'stored_type':type(converted).__name__,'numeric_value_unchanged':True})
        return converted
    if isinstance(value,dict):return {k:transport_scalars(v,conversions,path+'.'+k) for k,v in value.items()}
    if isinstance(value,tuple):return tuple(transport_scalars(v,conversions,path+f'[{i}]') for i,v in enumerate(value))
    if isinstance(value,list):return [transport_scalars(v,conversions,path+f'[{i}]') for i,v in enumerate(value)]
    return value


def write(path, value, *, frozen=False):
    path = Path(path)
    if frozen and path.exists():
        if read(path) != value:
            raise ValueError("frozen_artifact_conflict:" + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


@contextmanager
def output_lock(out):
    """OS lock releases after a crash; concurrent builders cannot duplicate calls."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / ".builder.lock").open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def relative_image(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("image_path_must_be_relative_posix")
    path = PurePosixPath(value)
    if path.is_absolute() or any(x in {".", "..", ""} for x in value.split("/")):
        raise ValueError("unsafe_original_image_path")
    return str(path)


def read_modality_manifest(path):
    value = read(path)
    if (not isinstance(value, dict) or set(value) != {"schema_version", "images"}
            or value["schema_version"] != 1 or not isinstance(value["images"], list)):
        raise ValueError("invalid_modality_manifest_schema")
    result = {}
    for item in value["images"]:
        if not isinstance(item, dict) or set(item) != {"source_filename", "modality", "provenance"}:
            raise ValueError("modality_entry_has_unapproved_fields")
        filename = relative_image(item["source_filename"])
        if filename in result:
            raise ValueError("duplicate_or_conflicting_modality:" + filename)
        if item["modality"] not in {"CXR", "CT", "MRI", "US", "Xray", "other", "unknown"}:
            raise ValueError("unsupported_modality")
        prov = item["provenance"]
        if (not isinstance(prov, dict) or set(prov) != {"kind", "source", "quote"}
                or prov["kind"] not in {"metadata", "caption", "human_review"}
                or any(not isinstance(prov[k], str) for k in prov)
                or not prov["source"].strip()
                or (item["modality"] != "unknown" and not prov["quote"].strip())):
            raise ValueError("modality_requires_frozen_label_free_provenance")
        result[filename] = item
    return result


def prepare_plan(inputs, image_root, modality_manifest, *, expected_cases=99,
                 expected_questions=402):
    """Only JSON/image bytes are inspected. No tool/ML import or initialization."""
    from PIL import Image
    root = Path(image_root).resolve(strict=True)
    modalities = read_modality_manifest(modality_manifest)
    rows = [json.loads(line) for line in Path(inputs).read_text(encoding="utf-8-sig").splitlines()
            if line.strip()]
    by_case, qids, image_cache = {}, set(), {}
    for row in rows:
        if (not isinstance(row, dict) or set(row) - ROW_FIELDS
                or not {"question_id", "case_id", "question", "images"} <= set(row)):
            raise ValueError("label_free_question_schema_required")
        qid, cid = row["question_id"], row["case_id"]
        if any(not isinstance(x, str) or not SAFE_ID.fullmatch(x) for x in (qid, cid)):
            raise ValueError("unsafe_question_or_case_id")
        if qid in qids:
            raise ValueError("duplicate_question_id:" + qid)
        qids.add(qid)
        if not isinstance(row["question"], str) or not row["question"].strip():
            raise ValueError("question_text_required")
        if not isinstance(row["images"], list) or not row["images"]:
            raise ValueError("original_images_required")
        labels = row.get("figure_labels", [""] * len(row["images"]))
        if (not isinstance(labels, list) or len(labels) != len(row["images"])
                or any(not isinstance(x, str) for x in labels)):
            raise ValueError("figure_label_count_mismatch")
        case = by_case.setdefault(cid, {"case_id": cid, "question_ids": [], "images": {}})
        case["question_ids"].append(qid)
        for filename, label in zip(row["images"], labels):
            filename = relative_image(filename)
            if filename not in image_cache:
                path = (root / filename).resolve(strict=True)
                if not path.is_relative_to(root) or not path.is_file():
                    raise ValueError("image_outside_root")
                with Image.open(path) as im:
                    size, fmt = list(im.size), im.format
                if min(size) <= 10 or fmt not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("unsupported_original_image")
                # One digest per unique original, never weights or unrelated files.
                content = path.read_bytes()
                item = modalities.get(filename, {"modality": "unknown", "provenance": None})
                image_cache[filename] = {"source_filename": filename, "path": str(path),
                    "size": size, "format": fmt, "bytes": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(), "role": "original",
                    "modality": item["modality"], "modality_provenance": item["provenance"],
                    "eligible": item["modality"] == "CXR",
                    "skip_reason": None if item["modality"] == "CXR" else "not_confirmed_chest_radiograph"}
            image = case["images"].setdefault(filename, dict(image_cache[filename],
                                                            question_ids=[], figure_labels=[]))
            if qid not in image["question_ids"]:
                image["question_ids"].append(qid)
            if label and label not in image["figure_labels"]:
                image["figure_labels"].append(label)
    if expected_questions is not None and len(rows) != expected_questions:
        raise ValueError("frozen_question_count_mismatch")
    if expected_cases is not None and len(by_case) != expected_cases:
        raise ValueError("frozen_case_count_mismatch")
    if not rows:
        raise ValueError("empty_selection")
    cases = []
    for cid, case in sorted(by_case.items()):
        case["question_ids"].sort()
        case["images"] = [dict(image, image_id="original:" + str(index))
                          for index, (_, image) in enumerate(sorted(case["images"].items()), 1)]
        for image in case["images"]:
            image["question_ids"].sort()
            image["figure_labels"].sort()
        cases.append(case)
    eligible = sum(im["eligible"] for case in cases for im in case["images"])
    plan = {"schema_version": 1, "protocol": "E3_case_original_tools_v1",
        "selection_sha256": digest(sorted(rows, key=lambda x: x["question_id"])),
        "modality_manifest_sha256": digest(modalities), "case_count": len(cases),
        "question_count": len(rows), "unique_original_filename_count": len(image_cache),
        "case_image_count": sum(len(c["images"]) for c in cases),
        "eligible_case_image_count": eligible, "planned_tool_invocations": eligible * len(TOOLS),
        "tools": list(TOOLS), "labels_read_by_generation": False,
        "questions_or_options_sent_to_tools": False,
        "deduplication": "source_filename_within_case; union_across_all_case_questions",
        "retry_policy": "never_reissue_started_invocation; preserve_errors_and_interrupted_unknown",
        "cases": cases}
    plan["plan_sha256"] = digest(plan)
    return plan


class LocalToolPool:
    """Lazy fixed local factories; no initialization in prepare-only mode."""
    def __init__(self, *, repo, cache_dir, classifier_checkpoint, report_cache, out, device):
        self.options = dict(repo=Path(repo), cache_dir=Path(cache_dir),
            classifier_checkpoint=Path(classifier_checkpoint), report_cache=Path(report_cache),
            segmentation_checkpoint=None, temp_dir=Path(out) / "tool_runtime", device_main=device)
        self.out, self.tools, self.provenance = Path(out), {}, {}

    def get(self, name):
        if name not in self.tools:
            error_path = self.out / "initialization_errors" / (name + ".json")
            if error_path.exists():
                raise RuntimeError("previous_tool_initialization_failed:" + name)
            if str(HERE) not in sys.path:
                sys.path.insert(0, str(HERE))
            from tool_registry_ext import build_tools
            try:
                built, provenance = build_tools(**self.options, tools=[name])
                self.tools.update(built)
                self.provenance.update(provenance)
                write(self.out / "tool_provenance" / (name + ".json"), provenance[name], frozen=True)
            except Exception as exc:
                write(error_path, {"utc": now(), "tool": name, "error_type": type(exc).__name__,
                                   "error_message": str(exc), "inference_invoked": False}, frozen=True)
                raise
        return self.tools[name], self.provenance[name]


def invoke_once(case, image, name, pool, out, plan_sha256):
    from experiments.worker_bridge import encode_value
    from experiments.tool_variants import validate_observation
    folder = Path(out) / "invocations" / case["case_id"] / image["image_id"].replace(":", "_") / name
    result_path, start_path = folder / "result.json", folder / "started.json"
    identity = {"plan_sha256": plan_sha256, "case_id": case["case_id"],
        "image_id": image["image_id"], "source_filename": image["source_filename"],
        "image_sha256": image["sha256"], "tool": name,
        "arguments": {"image_path": image["path"]}}
    if result_path.exists():
        saved = read(result_path)
        if saved.get("identity") != identity:
            raise ValueError("invocation_cache_identity_conflict")
        return saved
    if start_path.exists():
        started = read(start_path)
        if started.get("identity") != identity:
            raise ValueError("started_invocation_identity_conflict")
        result = dict(started, status="interrupted_unknown", usable=False, invoked=None,
                      ended_utc=now(), error_type="InterruptedUnknown",
                      error_message="Call status is unknown; no automatic reissue.")
        write(result_path, result, frozen=True)
        return result
    record = {"identity": identity, "started_utc": now(), "status": "started",
              "invoked": False, "usable": False}
    write(start_path, record, frozen=True)
    began = time.monotonic()
    try:
        tool, provenance = pool.get(name)
        record["provenance"] = provenance
        schema = tool.args_schema
        schema = schema.model_json_schema() if hasattr(schema, "model_json_schema") else schema.schema()
        if set(schema.get("properties", {})) != {"image_path"}:
            raise ValueError("unexpected_tool_input_schema")
        # Only this explicit original image path reaches the medical tool.
        record["invoked"] = True
        returned = tool.invoke(identity["arguments"])
        conversions=[]
        returned=transport_scalars(returned, conversions)
        record['serialization_scalar_conversions']=conversions
        record["typed_result"] = encode_value(returned)
        record["result"] = json.loads(json.dumps(returned, ensure_ascii=False, allow_nan=False))
        checked = validate_observation(KINDS[name], returned)
        checked["raw_content_logged"] = True
        record.update(output_contract=checked, usable=checked["valid"], status="returned")
    except Exception as exc:
        record.update(status="error", usable=False, error_type=type(exc).__name__, error_message=str(exc))
    record.update(ended_utc=now(), elapsed_s=round(time.monotonic() - began, 6))
    write(result_path, record, frozen=True)
    return record


def generate_cases(plan, out, pool):
    """Caller holds output_lock. Accept an injected fake pool for offline tests."""
    out = Path(out)
    write(out / "plan.json", plan, frozen=True)
    index = {"schema_version": 1, "plan_sha256": plan["plan_sha256"], "status": "complete",
             "case_count": plan["case_count"], "question_count": plan["question_count"],
             "planned_tool_invocations": plan["planned_tool_invocations"],
             "question_to_case": {}, "cases": []}
    for case in plan["cases"]:
        path = out / "cases" / (case["case_id"] + ".json")
        if path.exists():
            evidence = read(path)
            if evidence.get("plan_sha256") != plan["plan_sha256"]:
                raise ValueError("case_cache_plan_conflict")
        else:
            results = [invoke_once(case, image, name, pool, out, plan["plan_sha256"])
                       for image in case["images"] if image["eligible"] for name in TOOLS]
            model_images = []
            for image in case["images"]:
                hypotheses = [{"tool": r["identity"]["tool"], "result": r["result"]}
                    for r in results if r["identity"]["image_id"] == image["image_id"] and r["usable"]]
                if hypotheses:
                    model_images.append({"source_filename": image["source_filename"],
                        "figure_labels": image["figure_labels"], "modality": image["modality"],
                        "tool_hypotheses": hypotheses})
            status = "UNVERIFIED_TOOL_EVIDENCE" if model_images else "NO_EVIDENCE"
            evidence = dict(case, schema_version=1, plan_sha256=plan["plan_sha256"],
                assembled_utc=now(), unique_original_count=len(case["images"]),
                eligible_original_count=sum(i["eligible"] for i in case["images"]),
                tool_results=results, evidence_status=status,
                tool_invocation_count=sum(r["invoked"] is True for r in results),
                interrupted_unknown_count=sum(r["invoked"] is None for r in results),
                usable_tool_return_count=sum(r["usable"] for r in results),
                evidence_for_model={"status": status, "limitations": LIMITATIONS, "images": model_images})
            write(path, evidence, frozen=True)
        index["cases"].append({"case_id": case["case_id"], "path": "cases/" + path.name,
            "evidence_status": evidence["evidence_status"],
            "unique_original_count": evidence["unique_original_count"],
            "eligible_original_count": evidence["eligible_original_count"],
            "tool_invocation_count": evidence["tool_invocation_count"],
            "interrupted_unknown_count": evidence["interrupted_unknown_count"],
            "usable_tool_return_count": evidence["usable_tool_return_count"]})
        index["question_to_case"].update({qid: case["case_id"] for qid in case["question_ids"]})
        print(json.dumps({'event': 'case_evidence_saved', 'case_id': case['case_id'],
                          'completed_cases': len(index['cases']),
                          'usable_tool_return_count': evidence['usable_tool_return_count']}), flush=True)
    for key in ("tool_invocation_count", "interrupted_unknown_count", "usable_tool_return_count"):
        index[key] = sum(c[key] for c in index["cases"])
    index["no_evidence_case_count"] = sum(c["evidence_status"] == "NO_EVIDENCE" for c in index["cases"])
    write(out / "index.json", index, frozen=True)
    return index


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("prepare-only", "generate"), default="prepare-only")
    for name in ("inputs", "image-root", "modality-manifest", "repo", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--classifier-checkpoint", type=Path)
    parser.add_argument("--report-cache", type=Path)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--expected-cases", type=int, default=99)
    parser.add_argument("--expected-questions", type=int, default=402)
    args = parser.parse_args(argv)
    with output_lock(args.out):
        plan = prepare_plan(args.inputs, args.image_root, args.modality_manifest,
            expected_cases=args.expected_cases, expected_questions=args.expected_questions)
        write(args.out / "plan.json", plan, frozen=True)
        if args.mode == "prepare-only":
            result = {"status": "prepared_no_inference", "plan_sha256": plan["plan_sha256"],
                      **{k: plan[k] for k in ("case_count", "question_count", "case_image_count",
                          "eligible_case_image_count", "planned_tool_invocations")}}
        else:
            runtime = args.repo.resolve().parent.parent
            pool = LocalToolPool(repo=args.repo, cache_dir=args.cache_dir or runtime / "models/hf_full",
                classifier_checkpoint=args.classifier_checkpoint or runtime / "models/home/.torchxrayvision/models_data" / CLASSIFIER_FILENAME,
                report_cache=args.report_cache or runtime / "models/hf_report", out=args.out, device=args.device)
            # An unavailable tool runtime must not silently turn the entire
            # planned arm into NO_EVIDENCE. Loading performs no image inference.
            for name in TOOLS:
                pool.get(name)
            result = generate_cases(plan, args.out, pool)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    # Both ``python -m experiments.build_case_tool_evidence`` and direct script use.
    if str(HERE.parent) not in sys.path:
        sys.path.insert(0, str(HERE.parent))
    raise SystemExit(main())
