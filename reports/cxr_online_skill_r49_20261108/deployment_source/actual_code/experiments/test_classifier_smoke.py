"""Offline guard checks only; no real model or downloaded assets."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from classifier_smoke import main, validate_scores


class SmokeGuards(unittest.TestCase):
    def setUp(self):
        self.labels = [f"fictional_label_{i}" for i in range(18)]
        self.scores = dict.fromkeys(self.labels, 0.5)

    def test_requires_success_payload_and_all_labels(self):
        with self.assertRaises(ValueError):
            validate_scores((self.scores, {"analysis_status": "failed"}), self.labels)
        with self.assertRaises(ValueError):
            validate_scores((dict(list(self.scores.items())[:-1]), {"analysis_status": "completed"}), self.labels)
        with self.assertRaises(ValueError):
            validate_scores((self.scores, {"analysis_status": "completed"}), list(reversed(self.labels)))

    def test_rejects_nonfinite_out_of_range_and_nonnumeric_scores(self):
        for invalid in [float("nan"), float("inf"), -0.1, 1.1, True, "0.5"]:
            with self.subTest(invalid=invalid):
                scores = dict(self.scores, fictional_label_0=invalid)
                with self.assertRaises(ValueError):
                    validate_scores((scores, {"analysis_status": "completed"}), self.labels)

    def test_metadata_is_not_copied_to_scores(self):
        result = validate_scores((self.scores, {"analysis_status": "completed", "image_path": "SENSITIVE_PATH"}), self.labels)
        self.assertEqual(result, self.scores)
        self.assertNotIn("SENSITIVE_PATH", json.dumps(result))

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "existing"
            output.mkdir()
            sentinel = output / "sentinel"
            sentinel.write_text("keep")
            with redirect_stderr(io.StringIO()):
                result = main(["--repo", str(root / "missing-repo"), "--image", str(root / "missing.png"),
                               "--output", str(output), "--device", "cpu"])
            self.assertEqual(result, 2)
            self.assertEqual(sentinel.read_text(), "keep")
            self.assertFalse((output / "summary.json").exists())

    def test_failure_summary_has_no_input_paths_or_fabricated_scores(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "new-output"
            secret_name = "SENSITIVE_PERSON_IMAGE.png"
            with redirect_stdout(io.StringIO()):
                result = main(["--repo", str(root / "missing-repo"), "--image", str(root / secret_name),
                               "--output", str(output), "--device", "cpu"])
            self.assertEqual(result, 1)
            raw = (output / "summary.json").read_text(encoding="utf-8")
            report = json.loads(raw)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["failed_stage"], "input_validation")
            self.assertIsNone(report["scores"])
            self.assertEqual(report["checkpoints_loaded"], [])
            self.assertNotIn(secret_name, raw)
            self.assertNotIn(str(root), raw)
            self.assertEqual((output / ".gitignore").read_text(), "*\n")


if __name__ == "__main__":
    unittest.main()
