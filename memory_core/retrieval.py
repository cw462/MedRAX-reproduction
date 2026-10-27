"""Training-only admission, immutable snapshots, and deterministic BM25."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re

from .schema import (
    SCHEMA_VERSION, TASKS, MODALITIES, VIEWS, AuditRegistry, Experience,
    canonical_bytes, catalog_payload, digest, exact_enum, identifier, model_context,
    parse_versions, read_json, retrieval_text, sha256_string, strict_fields, strict_list,
)


TOKENIZER_VERSION = "lowercase-ascii-words-and-han-codepoints-v1"


def implementation_hashes():
    # Normalize only line endings for checkouts on Windows and Linux.
    root = Path(__file__).resolve().parent
    return {name: hashlib.sha256((root / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for name in ("schema.py", "retrieval.py")}


def tokenize(text):
    return re.findall(r"[a-z0-9]+|[\u3400-\u9fff]", text.lower())


@dataclass(frozen=True)
class BM25Config:
    top_k: int = 3
    min_score: float = 0.1
    k1: float = 1.5
    b: float = 0.75
    include_failure_reflections: bool = False

    def __post_init__(self):
        if type(self.top_k) is not int or self.top_k not in (1, 3, 5):
            raise ValueError("top_k must be one of the declared validation choices: 1, 3, 5")
        if type(self.include_failure_reflections) is not bool:
            raise ValueError("Failure reflection switch must be bool")
        for value in (self.min_score, self.k1, self.b):
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("BM25 parameters must be finite real numbers")
        if self.min_score < 0 or self.k1 <= 0 or not 0 <= self.b <= 1:
            raise ValueError("Invalid BM25 parameter range")

    def to_dict(self):
        return {"top_k": self.top_k, "min_score": self.min_score, "k1": self.k1, "b": self.b,
                "include_failure_reflections": self.include_failure_reflections}

    @classmethod
    def from_dict(cls, value):
        strict_fields(value, ("top_k", "min_score", "k1", "b", "include_failure_reflections"), "BM25 config")
        return cls(**value)


@dataclass(frozen=True)
class RetrievalQuery:
    question_id: str
    text: str
    task: str
    modality: str
    view: str
    available_tools: tuple[tuple[str, str], ...]

    def __post_init__(self):
        identifier(self.question_id)
        if type(self.text) is not str or not self.text.strip() or len(self.text) > 32000:
            raise ValueError("Query text must be nonempty and bounded")
        exact_enum(self.task, TASKS, "query task")
        exact_enum(self.modality, MODALITIES, "query modality")
        exact_enum(self.view, VIEWS, "query view")
        if type(self.available_tools) is not tuple or any(type(x) is not tuple for x in self.available_tools):
            raise ValueError("Available tool versions must be immutable")
        if parse_versions(dict(self.available_tools), allow_empty=True) != self.available_tools:
            raise ValueError("Available tools must be unique and sorted")

    @classmethod
    def from_dict(cls, value):
        strict_fields(value, ("question_id", "text", "task", "modality", "view", "available_tools"), "retrieval query")
        parsed = dict(value)
        parsed["available_tools"] = parse_versions(value["available_tools"], allow_empty=True)
        return cls(**parsed)


@dataclass(frozen=True)
class RetrievalHit:
    """Contains no raw record or audit reference; context() returns a fresh dict."""
    memory_id: str
    score: float
    _context_bytes: bytes

    def context(self):
        import json
        return json.loads(self._context_bytes)


def validate_admission(record, registry):
    if type(record) is not Experience:
        raise ValueError("Only validated structured experiences can enter memory")
    source = registry.lookup(record.source_question_id)
    if source.split != "memory_train" or record.source_split != source.split:
        raise ValueError("Source question is not in the frozen memory_train partition")
    if record.source_audit_ref != source.case_hash:
        raise ValueError("Source audit reference differs from independent case registry")


class MemoryBuilder:
    """Mutable build phase; freeze closes admission permanently for this builder."""
    def __init__(self, registry, config=None, *, allow_synthetic=False):
        if type(registry) is not AuditRegistry:
            raise ValueError("An independently constructed case registry is required")
        if registry.source_kind == "synthetic_fixture" and allow_synthetic is not True:
            raise ValueError("Synthetic fixtures need an explicit testing-only override")
        self.registry = registry
        self.config = BM25Config() if config is None else config
        if type(self.config) is not BM25Config:
            raise ValueError("A typed frozen BM25 configuration is required")
        self._records = []
        self._closed = False

    def add(self, record):
        if self._closed:
            raise ValueError("Builder is frozen; create a separately versioned build")
        validate_admission(record, self.registry)
        if any(x.memory_id == record.memory_id for x in self._records):
            raise ValueError("Duplicate memory record")
        self._records.append(record)

    def freeze(self):
        if self._closed:
            raise ValueError("Builder has already been frozen")
        snapshot = FrozenMemory(self.registry, self.config,
                                tuple(sorted(self._records, key=lambda x: x.memory_id)))
        self._closed = True
        return snapshot


@dataclass(frozen=True)
class FrozenMemory:
    registry: AuditRegistry
    config: BM25Config
    records: tuple[Experience, ...]

    def __post_init__(self):
        if type(self.registry) is not AuditRegistry or type(self.config) is not BM25Config or type(self.records) is not tuple:
            raise ValueError("Snapshot components must be deeply immutable typed values")
        for record in self.records:
            validate_admission(record, self.registry)
        ids = [x.memory_id for x in self.records]
        if ids != sorted(ids) or len(set(ids)) != len(ids):
            raise ValueError("Snapshot entries must be unique and sorted")

    def _payload(self):
        return {"schema_version": SCHEMA_VERSION, "catalog": catalog_payload(), "tokenizer": TOKENIZER_VERSION,
                "implementation_sha256": implementation_hashes(),
                "registry": self.registry.to_dict(), "config": self.config.to_dict(),
                "records": [x.to_dict() for x in self.records],
                "evidence_kind": "synthetic_fixture_only" if self.registry.source_kind == "synthetic_fixture" else "unvalidated_development_rules"}

    @property
    def sha256(self):
        # Recompute from current values instead of trusting a cached fingerprint.
        return digest(self._payload())

    def assert_frozen(self, expected_sha256):
        if self.sha256 != sha256_string(expected_sha256):
            raise ValueError("Snapshot contents or retrieval configuration changed")

    def save(self, path):
        payload = self._payload()
        envelope = {"sha256": digest(payload), "payload": payload}
        with Path(path).open("xb") as stream:
            stream.write(canonical_bytes(envelope))
        return envelope["sha256"]

    @classmethod
    def load(cls, path, *, expected_sha256):
        """Requires an independently pinned digest, not just the file's own claim."""
        expected_sha256 = sha256_string(expected_sha256)
        envelope = read_json(path)
        strict_fields(envelope, ("sha256", "payload"), "snapshot envelope")
        payload = envelope["payload"]
        strict_fields(payload, ("schema_version", "catalog", "tokenizer", "implementation_sha256", "registry", "config", "records", "evidence_kind"), "snapshot")
        if envelope["sha256"] != expected_sha256 or digest(payload) != expected_sha256:
            raise ValueError("Frozen snapshot digest does not match the independently pinned value")
        if type(payload["schema_version"]) is not int or payload["schema_version"] != SCHEMA_VERSION:
            raise ValueError("Unsupported snapshot schema")
        if canonical_bytes(payload["catalog"]) != canonical_bytes(catalog_payload()) or payload["tokenizer"] != TOKENIZER_VERSION:
            raise ValueError("Snapshot vocabulary/tokenizer differs from this implementation")
        if payload["implementation_sha256"] != implementation_hashes():
            raise ValueError("Snapshot implementation differs from this source revision")
        snapshot = cls(AuditRegistry.from_dict(payload["registry"]), BM25Config.from_dict(payload["config"]),
                       tuple(Experience.from_dict(x) for x in strict_list(payload["records"], "memory records")))
        # Also validates evidence_kind against registry provenance.
        snapshot.assert_frozen(expected_sha256)
        return snapshot

    def search(self, query):
        if type(query) is not RetrievalQuery:
            raise ValueError("A strict, label-free retrieval query is required")
        current_case = self.registry.lookup(query.question_id).case_hash
        available = dict(query.available_tools)
        candidates = []
        for record in self.records:
            if record.source_audit_ref == current_case:
                continue
            if record.task != query.task or record.modality != query.modality:
                continue
            if record.view != "unknown" and record.view != query.view:
                continue
            if any(available.get(name) != version for name, version in record.tool_versions):
                continue
            if record.outcome_kind != "success" and not self.config.include_failure_reflections:
                continue
            candidates.append(record)
        terms = set(tokenize(query.text))
        if not candidates or not terms:
            return ()
        # BM25 statistics depend only on this eligible frozen subset, never past searches.
        counts = [Counter(tokenize(retrieval_text(x))) for x in candidates]
        lengths = [sum(x.values()) for x in counts]
        average = sum(lengths) / len(lengths)
        document_frequency = Counter(term for count in counts for term in count)
        hits = []
        for record, count, length in zip(candidates, counts, lengths):
            score = 0.0
            for term in sorted(terms):
                frequency = count[term]
                if not frequency:
                    continue
                df = document_frequency[term]
                idf = math.log(1 + (len(candidates) - df + 0.5) / (df + 0.5))
                score += idf * frequency * (self.config.k1 + 1) / (
                    frequency + self.config.k1 * (1 - self.config.b + self.config.b * length / average))
            if score > 0 and score >= self.config.min_score:
                hits.append(RetrievalHit(record.memory_id, score, canonical_bytes(model_context(record))))
        hits.sort(key=lambda x: (-x.score, x.memory_id))
        return tuple(hits[:self.config.top_k])
