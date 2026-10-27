"""Strict, label-free rule records and audit provenance; standard library only."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re


SCHEMA_VERSION = 1
SPLITS = ("memory_train", "validation", "heldout_test")
TASKS = ("classification", "laterality", "localization", "vqa", "report_generation", "execution_recovery")
MODALITIES = ("CXR", "CT", "MRI", "OTHER")
VIEWS = ("AP", "PA", "lateral", "unknown")
TOOLS = ("chest_xray_classifier", "chest_xray_vqa", "chest_xray_report", "grounding", "segmentation")

# These reviewed, generic templates are the only strings stored in retrieval text.
# They are operational instructions, not patient-specific medical conclusions.
CONDITIONS = (
    ("orientation_uncertain", "Image orientation and laterality require checking current view metadata."),
    ("comparable_laterality_disagreement", "Comparable tools disagree on orientation or laterality in the same image."),
    ("classifier_scores_needed", "Chest radiograph classification scores are needed as additional tool evidence."),
    ("tool_timeout", "A tool timed out before returning a usable observation."),
    ("invalid_tool_output", "A tool output fails schema or numeric range validation."),
    ("insufficient_evidence", "Available tool evidence is insufficient for the current task."),
)
ACTIONS = (
    ("check_orientation", "Check current image orientation and view metadata before interpreting laterality."),
    ("classify_image", "Run the compatible chest radiograph classifier and check execution status and score schema."),
    ("retry_once", "Retry the compatible tool once only within the remaining call budget."),
    ("stop_uncertain", "Stop and report uncertainty when required evidence remains unavailable."),
)
RISKS = (
    ("scores_not_diagnosis", "Classifier scores are not an independent clinical reference."),
    ("unknown_evidence", "Tool agreement and execution success do not verify clinical correctness."),
    ("avoid_duplicate_calls", "Reuse valid cached results and avoid repeating identical tool calls."),
    ("view_mismatch", "A rule tied to one view may not apply when the current view is unknown or different."),
)


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def strict_fields(value, fields, context):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError(f"{context}: exact fields required")


def sha256_string(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Expected a lowercase SHA-256 audit digest")
    return value


def identifier(value):
    if type(value) is not str or not value.strip() or len(value) > 256 or any(ord(c) < 32 for c in value):
        raise ValueError("Invalid audit identifier")
    return value


def exact_enum(value, choices, context):
    if type(value) is not str or value not in choices:
        raise ValueError(f"Invalid {context}")
    return value


def strict_list(value, context):
    if type(value) is not list:
        raise ValueError(f"{context} must be a JSON list")
    return tuple(value)


def selected_tokens(value, vocabulary, context, nonempty=True):
    if type(value) is not tuple or (nonempty and not value):
        raise ValueError(f"{context} requires immutable selected tokens")
    if any(type(x) is not str or x not in dict(vocabulary) for x in value) or len(set(value)) != len(value):
        raise ValueError(f"{context} includes an unapproved or repeated token")


def tool_versions(value):
    if type(value) is not tuple or not value:
        raise ValueError("At least one immutable tool/version pair is required")
    names = []
    for pair in value:
        if type(pair) is not tuple or len(pair) != 2:
            raise ValueError("Invalid tool/version pair")
        name, version = pair
        exact_enum(name, TOOLS, "tool name")
        # Versions are audit compatibility data and NEVER rendered into context.
        if type(version) is not str or not version.strip() or len(version) > 256 or any(ord(c) < 32 for c in version):
            raise ValueError("Invalid tool version")
        if version.lower() in ("unknown", "latest", "none", "null", "*"):
            raise ValueError("Unpinned/unknown tool versions cannot establish compatibility")
        names.append(name)
    if len(set(names)) != len(names) or tuple(sorted(value)) != value:
        raise ValueError("Tool versions must be unique and sorted")


def parse_versions(value, allow_empty=False):
    if type(value) is not dict or (not value and not allow_empty):
        raise ValueError("tool_versions must be an object")
    if not value and allow_empty:
        return ()
    pairs = tuple(sorted(value.items()))
    tool_versions(pairs)
    return pairs


def read_json(path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON value")))


def read_jsonl(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            # Delegate duplicate-key handling through a local decoder as above.
            def pairs_hook(pairs):
                obj = {}
                for key, value in pairs:
                    if key in obj:
                        raise ValueError("Duplicate JSON key")
                    obj[key] = value
                return obj
            rows.append(json.loads(line, object_pairs_hook=pairs_hook,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON value"))))
    return rows


@dataclass(frozen=True)
class AuditRow:
    question_id: str
    split: str
    case_hash: str

    def __post_init__(self):
        identifier(self.question_id)
        exact_enum(self.split, SPLITS, "split")
        sha256_string(self.case_hash)

    @classmethod
    def from_dict(cls, value):
        strict_fields(value, ("question_id", "split", "case_hash"), "audit row")
        return cls(**value)

    def to_dict(self):
        return {"question_id": self.question_id, "split": self.split, "case_hash": self.case_hash}


@dataclass(frozen=True)
class AuditRegistry:
    rows: tuple[AuditRow, ...]
    source_kind: str
    split_manifest_sha256: str
    audit_file_sha256: str
    input_file_sha256: tuple[tuple[str, str], ...]

    def __post_init__(self):
        exact_enum(self.source_kind, ("split_artifacts", "synthetic_fixture"), "registry source")
        sha256_string(self.split_manifest_sha256)
        sha256_string(self.audit_file_sha256)
        if type(self.rows) is not tuple or not self.rows or any(type(x) is not AuditRow for x in self.rows):
            raise ValueError("Audit registry must have immutable typed rows")
        if tuple(sorted(self.rows, key=lambda x: x.question_id)) != self.rows:
            raise ValueError("Audit rows must be sorted")
        if len({x.question_id for x in self.rows}) != len(self.rows):
            raise ValueError("Duplicate audit question")
        split_by_case = {}
        for row in self.rows:
            if split_by_case.setdefault(row.case_hash, row.split) != row.split:
                raise ValueError("Same case occurs across data splits")
        if type(self.input_file_sha256) is not tuple or len(self.input_file_sha256) != len(SPLITS):
            raise ValueError("Input digests must cover every split")
        if tuple(s for s, _ in self.input_file_sha256) != tuple(sorted(SPLITS)):
            raise ValueError("Input split digests must be unique and sorted")
        for pair in self.input_file_sha256:
            if type(pair) is not tuple:
                raise ValueError("Input digests must be immutable")
            sha256_string(pair[1])

    @classmethod
    def synthetic(cls, rows):
        parsed = tuple(sorted((AuditRow.from_dict(x) for x in rows), key=lambda x: x.question_id))
        fingerprint = digest([x.to_dict() for x in parsed])
        return cls(parsed, "synthetic_fixture", fingerprint, fingerprint,
                   tuple((s, fingerprint) for s in sorted(SPLITS)))

    @classmethod
    def from_split_directory(cls, directory):
        """Verify existing data_tools outputs. Never open any labels file."""
        directory = Path(directory)
        manifest_path = directory / "manifest.json"
        manifest = read_json(manifest_path)
        hashes = manifest.get("artifact_sha256", {})
        audit_path = directory / "audit_index.jsonl"
        audit_hash = hashlib.sha256(audit_path.read_bytes()).hexdigest()
        if hashes.get(audit_path.name) != audit_hash:
            raise ValueError("Audit file digest differs from split manifest")
        rows = tuple(sorted((AuditRow.from_dict(x) for x in read_jsonl(audit_path)), key=lambda x: x.question_id))
        input_hashes, observed = [], set()
        by_question = {r.question_id: r for r in rows}
        for split in sorted(SPLITS):
            path = directory / f"{split}.inputs.jsonl"
            file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if hashes.get(path.name) != file_hash:
                raise ValueError("Inference input digest differs from split manifest")
            input_hashes.append((split, file_hash))
            for row in read_jsonl(path):
                strict_fields(row, ("question_id", "question", "images"), "inference input")
                qid = identifier(row["question_id"])
                if qid in observed or qid not in by_question or by_question[qid].split != split:
                    raise ValueError("Inference input and case audit index disagree")
                if type(row["question"]) is not str or type(row["images"]) is not list or any(type(x) is not str for x in row["images"]):
                    raise ValueError("Invalid inference input types")
                observed.add(qid)
        if observed != set(by_question):
            raise ValueError("Case audit index is not fully covered by inference inputs")
        return cls(rows, "split_artifacts", hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                   audit_hash, tuple(input_hashes))

    def lookup(self, question_id):
        identifier(question_id)
        for row in self.rows:
            if row.question_id == question_id:
                return row
        raise ValueError("Unknown question: cannot establish case exclusion")

    def to_dict(self):
        return {"rows": [x.to_dict() for x in self.rows], "source_kind": self.source_kind,
                "split_manifest_sha256": self.split_manifest_sha256, "audit_file_sha256": self.audit_file_sha256,
                "input_file_sha256": dict(self.input_file_sha256)}

    @classmethod
    def from_dict(cls, value):
        strict_fields(value, ("rows", "source_kind", "split_manifest_sha256", "audit_file_sha256", "input_file_sha256"), "registry")
        if type(value["input_file_sha256"]) is not dict:
            raise ValueError("Input digests must be an object")
        return cls(tuple(AuditRow.from_dict(x) for x in strict_list(value["rows"], "audit rows")),
                   value["source_kind"], value["split_manifest_sha256"], value["audit_file_sha256"],
                   tuple(sorted(value["input_file_sha256"].items())))


@dataclass(frozen=True)
class StepEvaluation:
    execution: str = "unknown"
    task_outcome: str = "unknown"
    clinical_evidence: str = "unknown"
    step_credit: None = None

    def __post_init__(self):
        exact_enum(self.execution, ("unknown", "succeeded", "failed", "timed_out", "cache_hit", "unavailable",
                                   "modality_mismatch", "invalid_arguments", "invalid_return"), "execution status")
        exact_enum(self.task_outcome, ("correct", "incorrect", "unknown"), "task outcome")
        if self.clinical_evidence != "unknown" or type(self.clinical_evidence) is not str or self.step_credit is not None:
            raise ValueError("Independent evidence and paired replay adapters are absent: require unknown/null")

    def to_dict(self):
        return {"execution": self.execution, "task_outcome": self.task_outcome,
                "clinical_evidence": self.clinical_evidence, "step_credit": self.step_credit}

    @classmethod
    def from_dict(cls, value):
        strict_fields(value, ("execution", "task_outcome", "clinical_evidence", "step_credit"), "step evaluation")
        return cls(**value)


def evaluate_execution(checks, task_outcome="unknown"):
    """Rule evaluation of trusted log flags, never a clinical validator."""
    names = ("tool_available", "modality_compatible", "arguments_valid", "call_returned", "return_valid", "timed_out", "cache_hit")
    strict_fields(checks, names, "execution checks")
    if any(v is not None and type(v) is not bool for v in checks.values()):
        raise ValueError("Execution checks must be bool or null")
    status = "unknown"
    for flag, bad_value, failure in (("timed_out", True, "timed_out"), ("tool_available", False, "unavailable"),
            ("modality_compatible", False, "modality_mismatch"), ("arguments_valid", False, "invalid_arguments"),
            ("return_valid", False, "invalid_return"), ("call_returned", False, "failed")):
        if checks[flag] is bad_value:
            status = failure
            break
    else:
        if all(checks[k] is True for k in names[:5]) and checks["timed_out"] is False:
            status = "cache_hit" if checks["cache_hit"] is True else "succeeded"
    return StepEvaluation(status, task_outcome)


@dataclass(frozen=True)
class Experience:
    source_split: str
    source_question_id: str
    source_audit_ref: str
    source_trace_sha256: str
    task: str
    modality: str
    view: str
    conditions: tuple[str, ...]
    action: str
    risks: tuple[str, ...]
    tool_versions: tuple[tuple[str, str], ...]
    outcome_kind: str
    evaluation: StepEvaluation
    memory_version: int = 1

    def __post_init__(self):
        exact_enum(self.source_split, ("memory_train",), "memory source split")
        identifier(self.source_question_id)
        sha256_string(self.source_audit_ref)
        sha256_string(self.source_trace_sha256)
        exact_enum(self.task, TASKS, "task")
        exact_enum(self.modality, MODALITIES, "modality")
        exact_enum(self.view, VIEWS, "view")
        selected_tokens(self.conditions, CONDITIONS, "conditions")
        exact_enum(self.action, dict(ACTIONS), "action")
        selected_tokens(self.risks, RISKS, "risks")
        tool_versions(self.tool_versions)
        exact_enum(self.outcome_kind, ("success", "failure_reflection"), "outcome kind")
        if type(self.evaluation) is not StepEvaluation:
            raise ValueError("Experience requires a typed step evaluation")
        if self.outcome_kind == "success" and self.evaluation.task_outcome != "correct":
            raise ValueError("Success pool admission requires authorized correct/incorrect development feedback")
        if self.outcome_kind == "failure_reflection" and (self.evaluation.task_outcome != "incorrect"
                and self.evaluation.execution not in ("failed", "timed_out", "unavailable", "modality_mismatch", "invalid_arguments", "invalid_return")):
            raise ValueError("Failure reflection requires a recorded failure")
        if type(self.memory_version) is not int or self.memory_version < 1:
            raise ValueError("Memory version must be a positive integer")

    def to_dict(self):
        return {"source_split": self.source_split, "source_question_id": self.source_question_id,
                "source_audit_ref": self.source_audit_ref, "source_trace_sha256": self.source_trace_sha256,
                "task": self.task, "modality": self.modality, "view": self.view, "conditions": list(self.conditions),
                "action": self.action, "risks": list(self.risks), "tool_versions": dict(self.tool_versions),
                "outcome_kind": self.outcome_kind, "evaluation": self.evaluation.to_dict(), "memory_version": self.memory_version}

    @classmethod
    def from_dict(cls, value):
        names = ("source_split", "source_question_id", "source_audit_ref", "source_trace_sha256", "task", "modality", "view",
                 "conditions", "action", "risks", "tool_versions", "outcome_kind", "evaluation", "memory_version")
        strict_fields(value, names, "experience")
        parsed = dict(value)
        parsed["conditions"] = strict_list(value["conditions"], "conditions")
        parsed["risks"] = strict_list(value["risks"], "risks")
        parsed["tool_versions"] = parse_versions(value["tool_versions"])
        parsed["evaluation"] = StepEvaluation.from_dict(value["evaluation"])
        return cls(**parsed)

    @property
    def memory_id(self):
        return "m_" + digest(self.to_dict())


def catalog_payload():
    return {"version": 1, "tasks": TASKS, "modalities": MODALITIES, "views": VIEWS, "tools": TOOLS,
            "conditions": CONDITIONS, "actions": ACTIONS, "risks": RISKS}


def retrieval_text(record):
    """No source identifiers, audit hashes, version strings or task feedback."""
    return " ".join((record.task, record.modality, record.view,
        *(dict(CONDITIONS)[x] for x in record.conditions), dict(ACTIONS)[record.action],
        *(dict(RISKS)[x] for x in record.risks)))


def model_context(record):
    """Only this allow-listed payload is intended for future prompt adapters."""
    return {"memory_id": record.memory_id, "task": record.task, "modality": record.modality, "view": record.view,
            "conditions": [dict(CONDITIONS)[x] for x in record.conditions], "action": dict(ACTIONS)[record.action],
            "risks": [dict(RISKS)[x] for x in record.risks], "required_tools": [x[0] for x in record.tool_versions],
            "execution": record.evaluation.execution, "clinical_evidence": "unknown", "step_credit": None}
