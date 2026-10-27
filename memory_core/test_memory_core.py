"""Synthetic boundary tests only. No models, medical inference, labels or network."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import builtins
import hashlib
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from memory_core import (
    AuditRegistry, BM25Config, Experience, FrozenMemory, MemoryBuilder, RetrievalQuery,
    StepEvaluation, evaluate_execution, retrieval_text,
)
from memory_core.schema import canonical_bytes, digest


def h(text):
    return hashlib.sha256(text.encode()).hexdigest()


def audit_rows():
    return [
        {"question_id": "train-a1", "split": "memory_train", "case_hash": h("case-a")},
        {"question_id": "train-a2", "split": "memory_train", "case_hash": h("case-a")},
        {"question_id": "train-b", "split": "memory_train", "case_hash": h("case-b")},
        {"question_id": "validation-q", "split": "validation", "case_hash": h("case-validation")},
        {"question_id": "test-q", "split": "heldout_test", "case_hash": h("case-test")},
    ]


def record_dict():
    return {
        "source_split": "memory_train", "source_question_id": "train-a1", "source_audit_ref": h("case-a"),
        "source_trace_sha256": h("fabricated-trace"), "task": "laterality", "modality": "CXR", "view": "unknown",
        "conditions": ["orientation_uncertain"], "action": "check_orientation", "risks": ["unknown_evidence"],
        "tool_versions": {"grounding": "fixture-v1"}, "outcome_kind": "success",
        "evaluation": {"execution": "succeeded", "task_outcome": "correct", "clinical_evidence": "unknown", "step_credit": None},
        "memory_version": 1,
    }


def query_dict():
    return {"question_id": "test-q", "text": "image orientation laterality", "task": "laterality",
            "modality": "CXR", "view": "PA", "available_tools": {"grounding": "fixture-v1"}}


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.registry = AuditRegistry.synthetic(audit_rows())
        self.record = Experience.from_dict(record_dict())

    def builder(self, config=None):
        return MemoryBuilder(self.registry, config, allow_synthetic=True)

    def pool(self, config=None, records=None):
        builder = self.builder(config)
        for record in [self.record] if records is None else records:
            builder.add(record)
        return builder.freeze()

    def test_strict_top_level_and_nested_label_fields_are_rejected(self):
        for key in ("answer", "correct_answer", "prediction", "explanation", "patient_id", "raw_report"):
            row = record_dict(); row[key] = "SECRET_REFERENCE"
            with self.subTest(field=key), self.assertRaises(ValueError):
                Experience.from_dict(row)
        row = record_dict(); row["evaluation"]["answer"] = "SECRET_REFERENCE"
        with self.assertRaises(ValueError): Experience.from_dict(row)
        query = query_dict(); query["answer"] = "SECRET_REFERENCE"
        with self.assertRaises(ValueError): RetrievalQuery.from_dict(query)

    def test_free_text_cannot_enter_rule_fields(self):
        for field, value in (("conditions", ["The correct answer is B"]), ("risks", ["patient name example"]),
                             ("action", "Copy prior diagnosis"), ("task", "answer_b")):
            row = record_dict(); row[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): Experience.from_dict(row)

    def test_registry_source_is_verified_not_self_reported(self):
        for qid in ("validation-q", "test-q", "unregistered-question"):
            forged = replace(self.record, source_question_id=qid)
            with self.subTest(qid=qid), self.assertRaises(ValueError): self.builder().add(forged)
        with self.assertRaises(ValueError):
            self.builder().add(replace(self.record, source_audit_ref=h("wrong-case")))
        with self.assertRaises(ValueError):
            Experience.from_dict(dict(record_dict(), source_split="heldout_test"))

    def test_registry_rejects_case_split_conflicts_and_duplicate_questions(self):
        rows = audit_rows(); rows[-1]["case_hash"] = rows[0]["case_hash"]
        with self.assertRaises(ValueError): AuditRegistry.synthetic(rows)
        rows = audit_rows(); rows.append(deepcopy(rows[0]))
        with self.assertRaises(ValueError): AuditRegistry.synthetic(rows)
        with self.assertRaises(ValueError): MemoryBuilder(self.registry)

    def test_same_case_other_question_excluded_and_unknown_case_fails_closed(self):
        pool = self.pool()
        row = query_dict(); row["question_id"] = "train-a2"
        self.assertEqual(pool.search(RetrievalQuery.from_dict(row)), ())
        row["question_id"] = "train-b"
        self.assertEqual(len(pool.search(RetrievalQuery.from_dict(row))), 1)
        row["question_id"] = "unregistered-question"
        with self.assertRaises(ValueError): pool.search(RetrievalQuery.from_dict(row))

    def test_audit_ids_versions_and_feedback_are_not_in_text_or_context(self):
        # Even an adversarial version string is gate-only metadata, not prompt text.
        version = "SECRET_REFERENCE_ANSWER_B"
        record = replace(self.record, tool_versions=(("grounding", version),))
        row = query_dict(); row["available_tools"] = {"grounding": version}
        hit = self.pool(records=[record]).search(RetrievalQuery.from_dict(row))[0]
        context = hit.context()
        public_text = retrieval_text(record) + json.dumps(context)
        for forbidden in (record.source_question_id, record.source_audit_ref, record.source_trace_sha256,
                          version, "task_outcome", "source_split", "outcome_kind"):
            self.assertNotIn(forbidden, public_text)
        context["action"] = "malicious local change"
        self.assertNotEqual(context, hit.context())

    def test_execution_success_and_final_correctness_do_not_create_credit(self):
        checks = {"tool_available": True, "modality_compatible": True, "arguments_valid": True,
                  "call_returned": True, "return_valid": True, "timed_out": False, "cache_hit": False}
        evaluation = evaluate_execution(checks, task_outcome="correct")
        self.assertEqual(evaluation.execution, "succeeded")
        self.assertEqual(evaluation.clinical_evidence, "unknown")
        self.assertIsNone(evaluation.step_credit)
        checks["return_valid"] = None
        self.assertEqual(evaluate_execution(checks, "correct").execution, "unknown")
        checks["timed_out"] = True
        self.assertEqual(evaluate_execution(checks).execution, "timed_out")
        checks["timed_out"] = 1
        with self.assertRaises(ValueError): evaluate_execution(checks)
        for credit in (0, 0.5, True, float("nan")):
            with self.subTest(credit=credit), self.assertRaises(ValueError): StepEvaluation(step_credit=credit)
        for clinical in ("verified", "refuted"):
            with self.assertRaises(ValueError): StepEvaluation(clinical_evidence=clinical)

    def test_task_modality_tool_and_version_are_hard_filters(self):
        pool = self.pool()
        for field, value in (("task", "classification"), ("modality", "CT"),
                             ("available_tools", {}), ("available_tools", {"grounding": "fixture-v2"})):
            row = query_dict(); row[field] = value
            with self.subTest(field=field, value=value):
                self.assertEqual(pool.search(RetrievalQuery.from_dict(row)), ())
        for version in ("unknown", "latest", "*"):
            row = query_dict(); row["available_tools"]["grounding"] = version
            with self.assertRaises(ValueError): RetrievalQuery.from_dict(row)

    def test_view_unknown_only_uses_generic_rules(self):
        specific = replace(self.record, view="PA")
        row = query_dict(); row["view"] = "unknown"
        self.assertEqual(self.pool(records=[specific]).search(RetrievalQuery.from_dict(row)), ())
        self.assertEqual(len(self.pool().search(RetrievalQuery.from_dict(row))), 1)
        row["view"] = "AP"
        self.assertEqual(self.pool(records=[specific]).search(RetrievalQuery.from_dict(row)), ())

    def test_no_positive_overlap_and_high_threshold_return_no_memory(self):
        row = query_dict(); row["text"] = "unmatchedtokenxyz"
        self.assertEqual(self.pool().search(RetrievalQuery.from_dict(row)), ())
        self.assertEqual(self.pool(BM25Config(min_score=1e9)).search(RetrievalQuery.from_dict(query_dict())), ())

    def test_failure_pool_is_opt_in_and_success_requires_correct_feedback(self):
        with self.assertRaises(ValueError):
            replace(self.record, evaluation=StepEvaluation(task_outcome="unknown"))
        failure = replace(self.record, outcome_kind="failure_reflection", evaluation=StepEvaluation("timed_out"))
        query = RetrievalQuery.from_dict(query_dict())
        self.assertEqual(self.pool(records=[failure]).search(query), ())
        self.assertEqual(len(self.pool(BM25Config(include_failure_reflections=True), [failure]).search(query)), 1)

    def test_freeze_deep_immutability_and_builder_closure(self):
        builder = self.builder(); builder.add(self.record); pool = builder.freeze(); before = pool.sha256
        with self.assertRaises(ValueError): builder.add(self.record)
        with self.assertRaises(ValueError): builder.freeze()
        with self.assertRaises(FrozenInstanceError): pool.config.top_k = 1
        with self.assertRaises(TypeError): pool.records[0].tool_versions[0] = ("grounding", "changed")
        exported = pool.records[0].to_dict(); exported["conditions"].append("arbitrary text")
        pool.assert_frozen(before)
        self.assertNotEqual(before, replace(pool, config=BM25Config(top_k=1)).sha256)

    def test_snapshot_roundtrip_and_tamper_rejected_even_with_self_updated_hash(self):
        pool = self.pool()
        with TemporaryDirectory() as temp:
            path = Path(temp) / "snapshot.json"
            pinned = pool.save(path)
            restored = FrozenMemory.load(path, expected_sha256=pinned)
            self.assertEqual(restored.sha256, pinned)
            self.assertEqual(restored.search(RetrievalQuery.from_dict(query_dict())), pool.search(RetrievalQuery.from_dict(query_dict())))
            with self.assertRaises(FileExistsError): pool.save(path)
            envelope = json.loads(path.read_text())
            envelope["payload"]["config"]["top_k"] = 1
            envelope["sha256"] = digest(envelope["payload"])
            path.write_bytes(canonical_bytes(envelope))
            with self.assertRaises(ValueError): FrozenMemory.load(path, expected_sha256=pinned)

    def test_bm25_order_and_pool_hash_do_not_change_with_query_history(self):
        other = replace(self.record, source_question_id="train-b", source_audit_ref=h("case-b"),
                        conditions=("tool_timeout",), action="retry_once")
        pool = self.pool(records=[other, self.record]); before = pool.sha256
        query = RetrievalQuery.from_dict(query_dict())
        first = pool.search(query)
        self.assertEqual(first[0].memory_id, self.record.memory_id)
        for text in ("tool timeout retry", "unmatchedtokenxyz", "orientation"):
            pool.search(replace(query, text=text))
        self.assertEqual(first, pool.search(query))
        pool.assert_frozen(before)
        reverse = self.pool(records=[self.record, other])
        self.assertEqual(pool.sha256, reverse.sha256)

    def test_verified_split_loader_never_reads_label_files_and_detects_changes(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); rows = audit_rows()
            audit_path = root / "audit_index.jsonl"
            audit_path.write_bytes(b"".join(canonical_bytes(x) for x in rows))
            hashes = {audit_path.name: hashlib.sha256(audit_path.read_bytes()).hexdigest()}
            for split in ("memory_train", "validation", "heldout_test"):
                path = root / f"{split}.inputs.jsonl"
                path.write_bytes(b"".join(canonical_bytes({"question_id": r["question_id"], "question": "synthetic query", "images": []})
                                          for r in rows if r["split"] == split))
                hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
                (root / f"{split}.labels.jsonl").write_text("DO NOT READ LABELS", encoding="utf-8")
            (root / "manifest.json").write_bytes(canonical_bytes({"artifact_sha256": hashes}))
            def guard_label_open(original):
                def guarded(file, *args, **kwargs):
                    if not isinstance(file, int) and ".labels." in Path(os.fsdecode(file)).name:
                        raise AssertionError("Label file read")
                    return original(file, *args, **kwargs)
                return guarded
            with patch("builtins.open", guard_label_open(builtins.open)), \
                    patch("io.open", guard_label_open(io.open)), \
                    patch("os.open", guard_label_open(os.open)):
                # Verify the guard itself covers text, bytes, Path.open and raw opens.
                label = root / "heldout_test.labels.jsonl"
                for read_label in (lambda: builtins.open(label), lambda: io.open(label),
                                   lambda: label.open(), lambda: label.read_text(),
                                   lambda: label.read_bytes(), lambda: os.open(label, os.O_RDONLY)):
                    with self.assertRaisesRegex(AssertionError, "Label file read"):
                        read_label()
                registry = AuditRegistry.from_split_directory(root)
            self.assertEqual(registry.source_kind, "split_artifacts")
            builder = MemoryBuilder(registry); builder.add(self.record)
            self.assertEqual(len(builder.freeze().records), 1)
            (root / "memory_train.inputs.jsonl").write_text("{}\n", encoding="utf-8")
            with self.assertRaises(ValueError): AuditRegistry.from_split_directory(root)


if __name__ == "__main__":
    unittest.main()
