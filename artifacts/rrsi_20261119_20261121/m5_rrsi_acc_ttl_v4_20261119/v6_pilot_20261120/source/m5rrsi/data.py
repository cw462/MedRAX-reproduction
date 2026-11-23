from __future__ import annotations
import json
from pathlib import Path
from .io import ProtocolError, digest, file_hash, write_json

PUBLIC_FIELDS = {"id", "dataset", "question", "options", "images", "group_keys"}


def read_rows(path):
    return [json.loads(s) for s in Path(path).read_text(encoding="utf-8").splitlines() if s.strip()]


def prepare(inputs, output):
    """Read ONLY public cases. Do not reorder or consult a reference file."""
    rows = read_rows(inputs); seen = set(); result = []
    base = Path(inputs).resolve().parent
    for index, x in enumerate(rows):
        extra = set(x) - PUBLIC_FIELDS
        if extra: raise ProtocolError(f"unapproved public fields at row {index}: {sorted(extra)}")
        tid = str(x["id"])
        if not tid or tid in seen: raise ProtocolError("empty/duplicate case id")
        seen.add(tid)
        if not isinstance(x["question"], str) or not x["question"].strip():
            raise ProtocolError("question must be nonempty text")
        if not isinstance(x["options"], list):
            raise ProtocolError("options must be an ORDERED list of {label,text}, empty for open questions")
        labels = []
        for o in x["options"]:
            if set(o) != {"label", "text"}: raise ProtocolError("option schema")
            labels.append(o["label"])
        if len(labels) != len(set(labels)): raise ProtocolError("duplicate option labels")
        images = []
        for name in x["images"]:
            p = Path(name); p = p if p.is_absolute() else base / p
            p = p.resolve()
            if not p.is_file(): raise ProtocolError(f"missing original image: {p}")
            images.append({"path": str(p), "sha256": file_hash(p)})
        if not images: raise ProtocolError("medical VQA case has no original image")
        result.append({"index": index, "id": tid, "dataset": str(x["dataset"]),
                       "question": x["question"], "options": x["options"], "images": images,
                       "group_keys": x.get("group_keys", [])})
    m = {"schema": 1, "order": "input_questionwise", "n": len(result),
         "cases": result, "cases_hash": digest(result)}
    write_json(output, m)
    return m


def public_case(row):
    return {k: row[k] for k in ("id", "dataset", "question", "options", "images")}


class References:
    """Trusted coordinator only. Never pass this object/path into candidate code."""
    def __init__(self, path, case_ids):
        self.path = Path(path).resolve()
        self.sha256 = file_hash(self.path)
        rows = read_rows(path)
        if any(set(x) != {"id", "reference"} for x in rows):
            raise ProtocolError("references schema is {id,reference}")
        self._data = {str(x["id"]): x["reference"] for x in rows}
        if len(self._data) != len(rows) or set(self._data) != set(case_ids):
            raise ProtocolError("reference IDs do not match manifest")
    def after_lock(self, case_id, lock_paths, expected_locks=2):
        if (expected_locks not in (1, 2) or len(lock_paths) != expected_locks
                or not all(Path(p).is_file() for p in lock_paths)):
            raise ProtocolError("all active current predictions must be locked before feedback")
        return self._data[case_id]
