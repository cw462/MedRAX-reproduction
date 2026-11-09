"""Offline contract and provenance tests; all report/weight fixtures are fictional."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from report_smoke import (generation_recorder, imported_versions, inspect_snapshot,
                          local_loader, main, REQUIRED_FILES, validate_report)

FICTIONAL_REPORT = "CHEST X-RAY REPORT\n\nFINDINGS:\nOFFLINE TEST A\n\nIMPRESSION:\nOFFLINE TEST B"
COMPLETED = {"analysis_status": "completed", "sections_generated": ["findings", "impression"]}


class FictionalTensor:
    """Minimal tensor-shaped fixture; no Torch import or model inference."""
    def __init__(self, sequence):
        self.sequence = sequence
        self.shape = (1, len(sequence))

    def detach(self):
        return self

    def cpu(self):
        return self

    def tolist(self):
        return [list(self.sequence)]


class ReportGuards(unittest.TestCase):
    def test_requires_complete_string_and_success_metadata(self):
        cases = [({"report": FICTIONAL_REPORT}, COMPLETED),
                 (FICTIONAL_REPORT, {**COMPLETED, "analysis_status": "failed"}),
                 (FICTIONAL_REPORT, {**COMPLETED, "sections_generated": ["findings"]}),
                 (FICTIONAL_REPORT.replace("OFFLINE TEST A", " "), COMPLETED),
                 (FICTIONAL_REPORT.replace("OFFLINE TEST B", ""), COMPLETED),
                 ("Error generating report: sensitive path", COMPLETED)]
        for result in cases:
            with self.subTest(result=result):
                with self.assertRaises(ValueError):
                    validate_report(result)

    def test_summary_contains_hash_and_lengths_but_no_report_or_metadata(self):
        result = validate_report((FICTIONAL_REPORT, {**COMPLETED, "image_path": "SENSITIVE_PATH"}))
        self.assertEqual(result["report_sha256"], hashlib.sha256(FICTIONAL_REPORT.encode()).hexdigest())
        self.assertEqual(result["report_chars"], len(FICTIONAL_REPORT))
        self.assertNotIn("SENSITIVE_PATH", json.dumps(result))
        self.assertNotIn("OFFLINE TEST", json.dumps(result))
        self.assertFalse(result["semantic_completeness_evaluated"])

    def test_generation_eos_and_length_flags_are_independent_and_do_not_change_call(self):
        cases = [([101, 987654321, 2], 2, 5, True, False),
                 ([101, 987654321, 3], 2, 3, False, True),
                 ([101, 987654321, 2], [2, 4], 3, True, True),
                 ([101, 987654321, 0], None, 3, None, True)]
        for sequence, eos, limit, expected_eos, expected_limit in cases:
            with self.subTest(eos=eos, limit=limit):
                config = SimpleNamespace(max_length=limit, num_beams=1, beam_width=2,
                                         do_sample=False, use_cache=True, eos_token_id=eos, pad_token_id=0)
                tensor = FictionalTensor(sequence)
                original = Mock(return_value=tensor)
                calls = []
                image_argument = object()
                result = generation_recorder(original, "findings", calls)(
                    image_argument, generation_config=config)
                self.assertIs(result, tensor)
                original.assert_called_once_with(image_argument, generation_config=config)
                self.assertEqual(config.num_beams, 1)
                self.assertEqual(config.beam_width, 2)
                self.assertEqual(calls[0]["sequence_contains_eos"], expected_eos)
                self.assertEqual(calls[0]["reached_max_length"], expected_limit)
                self.assertEqual(calls[0]["generation_config"]["eos_token_id"], eos)
                self.assertEqual(calls[0]["generation_config"]["pad_token_id"], 0)
                self.assertFalse(calls[0]["termination_reason_inferred"])
                self.assertFalse(calls[0]["semantic_completeness_evaluated"])
                self.assertNotIn("987654321", json.dumps(calls))

    def test_imported_runtime_versions_distinguish_metadata_mismatch_and_unimported(self):
        modules = {"numpy": SimpleNamespace(__version__="1.26.4", __file__="SENSITIVE_PATH"),
                   "torch": SimpleNamespace(__version__="2.2.2+cu121")}
        result = imported_versions({"numpy": "1.26.0", "torch": "2.2.2+cu121",
                                    "transformers": "4.45.2"}, modules)
        self.assertEqual(result["numpy"]["version"], "1.26.4")
        self.assertFalse(result["numpy"]["matches_distribution_metadata"])
        self.assertTrue(result["torch"]["matches_distribution_metadata"])
        self.assertFalse(result["transformers"]["imported"])
        self.assertIsNone(result["transformers"]["version"])
        self.assertIsNone(result["transformers"]["matches_distribution_metadata"])
        self.assertNotIn("SENSITIVE_PATH", json.dumps(result))

    def test_snapshot_requires_complete_assets_and_matching_weight_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = b"FICTIONAL WEIGHT - NOT A MODEL"
            spec = {"repo_id": "fictional/model", "revision": "1" * 40,
                    "weight_bytes": len(fixture), "weight_sha256": hashlib.sha256(fixture).hexdigest()}
            snapshot = root / "models--fictional--model" / "snapshots" / spec["revision"]
            snapshot.mkdir(parents=True)
            with self.assertRaises(FileNotFoundError):
                inspect_snapshot(root, spec)
            for filename in REQUIRED_FILES:
                (snapshot / filename).write_bytes(fixture if filename == "model.safetensors" else b"{}")
            actual, manifest = inspect_snapshot(root, spec)
            self.assertEqual(actual, snapshot)
            self.assertTrue(manifest["weight_matches_official_sha256"])
            self.assertNotIn(str(root), json.dumps(manifest))
            (snapshot / "model.safetensors").write_bytes(b"wrong weight")
            with self.assertRaises(ValueError):
                inspect_snapshot(root, spec)

    def test_loader_forces_offline_verified_source_and_records_only_success(self):
        observed = []
        original = Mock(return_value=object())
        wrapped = local_loader(original, "model", {"fictional/model": ("findings", Path("local"))}, observed)
        value = wrapped("fictional/model", cache_dir="SENSITIVE_CACHE", local_files_only=False)
        self.assertIs(value, original.return_value)
        original.assert_called_once_with("local", local_files_only=True, trust_remote_code=False,
                                         use_safetensors=True)
        self.assertEqual(len(observed), 1)
        self.assertNotIn("SENSITIVE_CACHE", json.dumps(observed))
        with self.assertRaises(ValueError):
            wrapped("unapproved/source")
        original.side_effect = RuntimeError("SENSITIVE_ERROR")
        with self.assertRaises(RuntimeError):
            wrapped("fictional/model")
        self.assertEqual(len(observed), 1)

    def test_existing_output_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sentinel").write_text("keep")
            with redirect_stderr(io.StringIO()):
                code = main(["--repo", str(root), "--image", str(root / "missing.png"),
                             "--output", str(root), "--device", "cpu", "--cache-dir", str(root)])
            self.assertEqual(code, 2)
            self.assertEqual((root / "sentinel").read_text(), "keep")
            self.assertFalse((root / "summary.json").exists())

    def test_failure_has_no_paths_raw_error_or_fabricated_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "new-output"
            with redirect_stdout(io.StringIO()):
                code = main(["--repo", str(root / "missing"), "--image", str(root / "PRIVATE_PERSON.png"),
                             "--output", str(output), "--device", "cpu", "--cache-dir", str(root)])
            self.assertEqual(code, 1)
            raw = (output / "summary.json").read_text(encoding="utf-8")
            result = json.loads(raw)
            self.assertEqual(result["status"], "failed")
            self.assertFalse(result["clinical_correctness_evaluated"])
            self.assertIsNone(result["report_artifact"])
            self.assertEqual(result["generation_calls"], [])
            self.assertNotIn(str(root), raw)
            self.assertNotIn("PRIVATE_PERSON", raw)
            self.assertFalse((output / "report.txt").exists())
            self.assertEqual((output / ".gitignore").read_text(), "*\n")


if __name__ == "__main__":
    unittest.main()
