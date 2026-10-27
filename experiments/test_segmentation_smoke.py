"""Synthetic offline contracts only: no real checkpoint, image, model or GPU."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from segmentation_smoke import (CHECKPOINT_NAME, ORGANS, imported_versions, main,
                                offline_load_recorder, safe_tool_status,
                                validate_checkpoint, validate_result)


def fictional_metrics():
    cy, cx = 19.5, 39.5
    return {"area_pixels": 400, "area_cm2": 400 * 0.0004, "centroid": (cy, cx),
            "bbox": (10, 20, 30, 60), "width": 40, "height": 20, "aspect_ratio": 0.5,
            "relative_position": {"top": cy / 100, "left": cx / 200,
                                  "center_dist": math.hypot(cy / 100 - 0.5, cx / 200 - 0.5)},
            "mean_intensity": 128.0, "std_intensity": 10.0, "confidence_score": 0.6}


class SegmentationGuards(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir()
        self.visual = self.artifacts / "segmentation_1234abcd.png"
        self.visual.write_bytes(b"SYNTHETIC PATH FIXTURE, NOT A REAL IMAGE")
        self.prediction = {"output_shape": [1, 14, 512, 512], "all_logits_finite": True,
                           "positive_pixels": [100] + [0] * 13,
                           "mean_probabilities": [0.6] + [0.1] * 13}
        self.result = ({"segmentation_image_path": str(self.visual),
                        "metrics": {ORGANS[0]: fictional_metrics()}},
                       {"image_path": "PRIVATE_PERSON_PATH", "analysis_status": "completed",
                        "segmentation_image_path": str(self.visual), "original_size": (100, 200),
                        "model_size": (512, 512), "pixel_spacing_mm": 0.2,
                        "requested_organs": list(ORGANS), "processed_organs": [ORGANS[0]]})

    def tearDown(self):
        self.temporary.cleanup()

    def validate(self, result=None, prediction=None):
        return validate_result(self.result if result is None else result, (100, 200), self.artifacts,
                               self.prediction if prediction is None else prediction)

    def test_fourteen_channels_allow_only_nonempty_metric_subset(self):
        checks, path = self.validate()
        self.assertEqual(checks["model_channel_count"], 14)
        self.assertEqual(checks["requested_structure_count"], 14)
        self.assertEqual(checks["metrics_returned_count"], 1)
        self.assertEqual(len(checks["structures"]), 14)
        self.assertEqual(checks["structures"][0]["status"], "metrics_returned")
        self.assertTrue(all(item["status"] == "empty_model_mask" for item in checks["structures"][1:]))
        self.assertEqual(path, self.visual)
        self.assertNotIn("PRIVATE_PERSON_PATH", json.dumps(checks))
        self.assertNotIn(str(self.root), json.dumps(checks))

    def test_empty_masks_and_alignment_loss_are_audited_without_inventing_metrics(self):
        result = deepcopy(self.result)
        result[0]["metrics"] = {}
        result[1]["processed_organs"] = []
        checks, _ = self.validate(result)
        self.assertEqual(checks["structures"][0]["status"], "no_metrics_after_alignment")
        self.assertFalse(checks["all_structures_empty"])
        prediction = deepcopy(self.prediction)
        prediction["positive_pixels"] = [0] * 14
        prediction["mean_probabilities"] = [0.1] * 14
        checks, _ = self.validate(result, prediction)
        self.assertTrue(checks["all_structures_empty"])
        self.assertEqual(checks["metrics"], {})

    def test_failed_tool_metadata_cannot_be_mistaken_for_success_or_leak_error(self):
        result = ({"error": "PRIVATE_PERSON_PATH"}, {"analysis_status": "failed",
                  "image_path": "PRIVATE_PERSON_PATH", "error_traceback": "PRIVATE_TRACEBACK"})
        safe = safe_tool_status(result)
        self.assertEqual(safe["analysis_status"], "failed")
        self.assertTrue(safe["error_metadata_present"])
        self.assertNotIn("PRIVATE", json.dumps(safe))
        with self.assertRaises(ValueError):
            self.validate(result)

    def test_rejects_wrong_channels_unknown_organs_and_geometry_metadata(self):
        prediction = deepcopy(self.prediction)
        prediction["output_shape"] = [1, 13, 512, 512]
        with self.assertRaises(ValueError):
            self.validate(prediction=prediction)
        for key, value in (("pixel_spacing_mm", 0.3), ("model_size", (224, 224)),
                           ("requested_organs", list(reversed(ORGANS))), ("processed_organs", [])):
            with self.subTest(key=key):
                result = deepcopy(self.result); result[1][key] = value
                with self.assertRaises(ValueError): self.validate(result)
        result = deepcopy(self.result)
        result[0]["metrics"]["not-an-official-organ"] = fictional_metrics()
        with self.assertRaises(ValueError): self.validate(result)

    def test_metric_validation_rejects_nonfinite_out_of_bounds_and_false_calibration(self):
        edits = (("area_pixels", True), ("area_cm2", 400), ("centroid", (999.0, 39.5)),
                 ("bbox", (10, 20, 500, 60)), ("width", 100), ("aspect_ratio", 2.0),
                 ("confidence_score", float("nan")), ("mean_intensity", 256.0))
        for key, value in edits:
            with self.subTest(key=key):
                result = deepcopy(self.result); result[0]["metrics"][ORGANS[0]][key] = value
                with self.assertRaises(ValueError): self.validate(result)
        prediction = deepcopy(self.prediction); prediction["positive_pixels"][0] = 0
        with self.assertRaises(ValueError): self.validate(prediction=prediction)

    def test_visualization_must_exist_inside_output_and_match_metadata(self):
        outside = self.root / "segmentation_aaaabbbb.png"
        outside.write_bytes(b"SYNTHETIC")
        result = deepcopy(self.result)
        result[0]["segmentation_image_path"] = result[1]["segmentation_image_path"] = str(outside)
        with self.assertRaises(ValueError): self.validate(result)
        self.visual.unlink()
        with self.assertRaises(ValueError): self.validate()

    def test_checkpoint_requires_pre_recorded_matching_digest_and_size(self):
        fixture = b"SYNTHETIC CHECKPOINT TEST, NEVER LOADED"
        checkpoint = self.root / CHECKPOINT_NAME
        checkpoint.write_bytes(fixture)
        digest = hashlib.sha256(fixture).hexdigest()
        result = validate_checkpoint(checkpoint, digest, expected_bytes=len(fixture))
        self.assertEqual(result["sha256"], digest)
        self.assertFalse(result["upstream_digest_available"])
        self.assertEqual(result["digest_provenance"], "caller_pinned_local_download_sha256")
        self.assertNotIn(str(self.root), json.dumps(result))
        for wrong in ("", "0" * 64, "z" * 64):
            with self.assertRaises(ValueError):
                validate_checkpoint(checkpoint, wrong, expected_bytes=len(fixture))
        with self.assertRaises(ValueError): validate_checkpoint(checkpoint, digest)

    def test_torch_load_only_observes_verified_file_without_changing_load_arguments(self):
        checkpoint = self.root / CHECKPOINT_NAME
        checkpoint.write_bytes(b"SYNTHETIC")
        original = Mock(return_value=object()); records = []
        load = offline_load_recorder(original, checkpoint, records)
        result = load(str(checkpoint), map_location="cpu")
        self.assertIs(result, original.return_value)
        original.assert_called_once_with(str(checkpoint), map_location="cpu")
        self.assertEqual(len(records), 1)
        with self.assertRaises(ValueError): load(str(self.root / "unapproved.pth"))
        original.side_effect = RuntimeError("SYNTHETIC ERROR")
        with self.assertRaises(RuntimeError): load(str(checkpoint))
        self.assertEqual(len(records), 1)

    def test_runtime_version_distinguishes_imported_numpy_from_distribution_metadata(self):
        result = imported_versions({"numpy": "1.26.0"}, {"numpy": SimpleNamespace(__version__="1.26.4")})
        self.assertEqual(result["numpy"]["version"], "1.26.4")
        self.assertFalse(result["numpy"]["matches_distribution_metadata"])

    def test_existing_output_is_not_overwritten(self):
        sentinel = self.root / "sentinel"; sentinel.write_text("keep")
        with redirect_stderr(io.StringIO()):
            code = main(["--repo", str(self.root), "--image", str(self.root / "absent.png"),
                         "--output", str(self.root), "--device", "cpu", "--checkpoint", str(self.root / CHECKPOINT_NAME),
                         "--checkpoint-sha256", "0" * 64])
        self.assertEqual(code, 2)
        self.assertEqual(sentinel.read_text(), "keep")
        self.assertFalse((self.root / "summary.json").exists())

    def test_failure_does_not_invent_output_and_keeps_generated_artifacts_out_of_git(self):
        output = self.root / "new-output"
        with redirect_stdout(io.StringIO()):
            code = main(["--repo", str(self.root / "absent"), "--image", str(self.root / "PRIVATE_IMAGE.png"),
                         "--output", str(output), "--device", "cpu", "--checkpoint", str(self.root / CHECKPOINT_NAME),
                         "--checkpoint-sha256", "0" * 64])
        self.assertEqual(code, 1)
        raw = (output / "summary.json").read_text(encoding="utf-8")
        result = json.loads(raw)
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["physical_area_calibrated"])
        self.assertFalse(result["segmentation_is_reference_label"])
        self.assertIsNone(result["visualization"])
        self.assertIsNone(result["output_checks"])
        self.assertEqual(result["checkpoint_loads"], [])
        self.assertEqual((output / ".gitignore").read_text(), "*\n")
        self.assertNotIn(str(self.root), raw)
        self.assertNotIn("PRIVATE_IMAGE", raw)


if __name__ == "__main__":
    unittest.main()
