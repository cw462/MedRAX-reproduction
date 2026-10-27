"""Synthetic-only selection and complete-image preservation checks."""
from pathlib import Path
import tempfile
import unittest
from unittest import mock

try:
    from . import audit_figures as audit
    from . import freeze_validation as freeze
    from .test_audit_figures import run_audit
except ImportError:
    import audit_figures as audit
    import freeze_validation as freeze
    from test_audit_figures import run_audit


class ValidationFreezeTest(unittest.TestCase):
    def test_choice_content_does_not_drive_tags(self):
        self.assertEqual(freeze.task_tags("Which statement is true?\nA. Diagnosis and location\nB. Type and severity"), ["unspecified"])
        self.assertEqual(freeze.task_tags("Where is the abnormality?\nA) Answer\nB) Other"), ["detection", "localization"])

    def test_fixed_seed_input_order_independence_distinct_cases_and_quotas(self):
        with tempfile.TemporaryDirectory() as temp:
            split_root, _, _, _, _ = run_audit(Path(temp))
            rows, index, _ = audit.load_splits(split_root)
            selected, info = freeze.select_questions(rows["validation"], index, count=3, seed=7)
            reversed_selected, reversed_info = freeze.select_questions(list(reversed(rows["validation"])), index, count=3, seed=7)
            self.assertEqual(selected, reversed_selected)
            self.assertEqual(info, reversed_info)
            self.assertEqual(len({r["case_hash"] for r in selected}), 3)
            self.assertEqual(info["actual_image_count_quotas"], {"single": 2, "multiple": 1})
            self.assertEqual(info["skipped_zero_image_question_ids"], ["v0"])
            smaller, info = freeze.select_questions(rows["validation"], index, count=30)
            self.assertEqual(len(smaller), 3)
            self.assertEqual(info["requested_question_count"], 30)

    def test_overlap_of_single_and_multi_case_options_does_not_starve_quota(self):
        rows = [{"question_id": qid, "question": "What is the diagnosis?", "images": ["x"]*n}
                for qid, case, n in [("both_single", "both", 1), ("both_multi", "both", 2),
                                     ("only_single", "single", 1), ("only_multi", "multi", 2),
                                     ("other_multi", "multi2", 3)]]
        index = {qid: {"case_hash": case, "split": "validation"}
                 for qid, case in [("both_single", "both"), ("both_multi", "both"), ("only_single", "single"),
                                   ("only_multi", "multi"), ("other_multi", "multi2")]}
        for seed in range(10):
            chosen, info = freeze.select_questions(rows, index, count=4, seed=seed)
            self.assertEqual(info["actual_image_count_quotas"], {"single": 2, "multiple": 2})
            self.assertIn("both_single", {r["row"]["question_id"] for r in chosen})

    def test_complete_original_image_bundles_strict_inference_and_no_label_read(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            split_root, archive, image_bytes, image_audit, _ = run_audit(root)
            output = root/"validation"
            original_open = Path.open
            def guarded(path, mode="r", *args, **kwargs):
                if "r" in mode and ".labels." in path.name:
                    self.fail("Forbidden label read")
                return original_open(path, mode, *args, **kwargs)
            with mock.patch.object(Path, "open", guarded):
                manifest = freeze.freeze(archive, split_root, image_audit, output, count=3)
            actual = audit.read_jsonl(output/"inference.jsonl")
            source = {r["question_id"]: r for r in audit.read_jsonl(split_root/"validation.inputs.jsonl")}
            mappings = {r["question_id"]: r for r in audit.read_json(output/"audit_manifest.json")["records"]}
            self.assertEqual(manifest["question_count"], 3)
            self.assertEqual(manifest["distinct_case_count"], 3)
            self.assertEqual(manifest["image_file_count"], 4)
            for row in actual:
                self.assertEqual(set(row), {"question_id", "question", "images"})
                self.assertEqual(row["question"], source[row["question_id"]]["question"])
                self.assertEqual(len(row["images"]), len(source[row["question_id"]]["images"]))
                for local, original in zip(row["images"], source[row["question_id"]]["images"]):
                    self.assertEqual((output/"images"/local).read_bytes(), image_bytes[original])
                self.assertEqual([r["dataset_image_path"] for r in mappings[row["question_id"]]["images"]], source[row["question_id"]]["images"])
            with self.assertRaises(FileExistsError):
                freeze.freeze(archive, split_root, image_audit, output, count=3)

    def test_missing_image_frame_not_silently_resampled(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            split_root, archive, _, image_audit, _ = run_audit(root, missing=True)
            with self.assertRaisesRegex(ValueError, "unavailable images"):
                freeze.freeze(archive, split_root, image_audit, root/"out", count=3)
            self.assertFalse((root/"out").exists())

    def test_non_validation_rows_rejected(self):
        with self.assertRaisesRegex(ValueError, "Only validation"):
            freeze.select_questions([{"question_id": "t", "question": "Q", "images": ["x"]}],
                                    {"t": {"case_hash": "case", "split": "heldout_test"}})


if __name__ == "__main__":
    unittest.main()
