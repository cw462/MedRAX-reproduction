"""Build auditable, case-grouped ChestAgentBench splits, with isolated labels.

Only fields on an explicit allow-list are copied into agent inputs. This is
research data preparation, not a medical anonymization guarantee.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

SPLITS = ("memory_train", "validation", "heldout_test")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def read_metadata(path):
    raw = Path(path).read_bytes()
    rows = []
    for lineno, line in enumerate(raw.decode("utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON at line {lineno}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"line {lineno} must be an object")
        rows.append(row)
    if not rows:
        raise ValueError("dataset is empty")
    return raw, rows


def string_list(value, field):
    # The released metadata uses flat lists. Fail closed on unexpected schema.
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise ValueError(f"{field} must be a flat list of strings")
    return value


def build(rows, seed):
    groups = {}
    question_ids = set()
    for row in rows:
        case = row.get("case_id")
        qid = row.get("question_id")
        question = row.get("question")
        answer = row.get("answer")
        if not isinstance(case, (str, int)) or isinstance(case, bool) or not str(case).strip():
            raise ValueError("missing reliable explicit case_id; refusing to infer one")
        if not isinstance(qid, str) or not qid.strip() or qid in question_ids:
            raise ValueError("missing or duplicate question_id")
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"missing question for {qid}")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError(f"missing answer for {qid}")
        images = string_list(row.get("images"), "images")
        urls = string_list(row.get("image_source_urls"), "image_source_urls")
        question_ids.add(qid)
        case = str(case).strip()
        groups.setdefault(case, []).append((qid, question, images, urls, answer))
    if len(groups) < 3:
        raise ValueError("at least 3 case groups are needed")

    # Case counts, not question counts. The frozen seed must not be tuned on test labels.
    cases = sorted(groups, key=lambda c: digest(f"{seed}\0{c}".encode("utf-8")))
    n_train = max(1, int(len(cases) * 0.6))
    n_validation = max(1, int(len(cases) * 0.2))
    assignment = {case: (SPLITS[0] if i < n_train else SPLITS[1] if i < n_train + n_validation else SPLITS[2])
                  for i, case in enumerate(cases)}
    inputs = {s: [] for s in SPLITS}
    labels = {s: [] for s in SPLITS}
    image_locations = {}
    for case in sorted(groups):
        split = assignment[case]
        for qid, question, images, urls, answer in sorted(groups[case]):
            for kind, values in (("path", images), ("url", urls)):
                for value in values:
                    if not value.strip():
                        continue
                    key = (kind, value)
                    previous = image_locations.setdefault(key, split)
                    if previous != split:
                        raise ValueError(f"same image {kind} appears across splits; resolve before use")
            inputs[split].append({"question_id": qid, "question": question, "images": images})
            labels[split].append({"question_id": qid, "answer": answer})
    manifest = {
        "schema_version": 1, "seed": seed, "grouping": "explicit case_id",
        "split_case_counts": {s: sum(assignment[c] == s for c in cases) for s in SPLITS},
        "split_question_counts": {s: len(inputs[s]) for s in SPLITS},
        "assignment_sha256": digest(b"".join(json_bytes({"case_id": c, "split": assignment[c]}) for c in sorted(cases))),
        "image_checks": "identical path and URL strings checked across splits; no image bytes inspected",
        "limitations": ["case independence is not proven patient independence", "image content or perceptual duplicates not checked", "question content not medically de-identified", "file separation is not OS access control"],
    }
    return inputs, labels, manifest


def write_jsonl(path, rows):
    path.write_bytes(b"".join(json_bytes(row) for row in rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("output", type=Path, help="new directory; must not already exist")
    parser.add_argument("--seed", default="medrax-20261027")
    args = parser.parse_args()
    try:
        raw, rows = read_metadata(args.metadata)
        inputs, labels, manifest = build(rows, args.seed)
        manifest["source_sha256"] = digest(raw)
        args.output.mkdir(parents=True, exist_ok=False)
        qid_to_case = {row["question_id"]: str(row["case_id"]).strip() for row in rows}
        audit_index = []
        artifact_hashes = {}
        for split in SPLITS:
            input_path = args.output / f"{split}.inputs.jsonl"
            label_path = args.output / f"{split}.labels.jsonl"
            write_jsonl(input_path, inputs[split])
            write_jsonl(label_path, labels[split])
            artifact_hashes[input_path.name] = digest(input_path.read_bytes())
            artifact_hashes[label_path.name] = digest(label_path.read_bytes())
            audit_index.extend({"question_id": r["question_id"], "split": split,
                                "case_hash": digest(qid_to_case[r["question_id"]].encode("utf-8"))}
                               for r in inputs[split])
        audit_path = args.output / "audit_index.jsonl"
        write_jsonl(audit_path, sorted(audit_index, key=lambda r: r["question_id"]))
        artifact_hashes[audit_path.name] = digest(audit_path.read_bytes())
        manifest["artifact_sha256"] = artifact_hashes
        (args.output / "manifest.json").write_bytes(json_bytes(manifest))
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, UnicodeError) as exc:
        print(f"preparation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
