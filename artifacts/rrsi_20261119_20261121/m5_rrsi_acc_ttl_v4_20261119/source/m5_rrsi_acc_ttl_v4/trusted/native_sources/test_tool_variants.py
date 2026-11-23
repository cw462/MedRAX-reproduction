"""Synthetic local tool/asset fixtures only; no GPU, model inference or network."""
import asyncio
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import tool_variants as variants


class Schema:
    @classmethod
    def model_json_schema(cls):
        return {"type": "object", "properties": {"image_path": {"type": "string"}}}


class SyntheticClassifier:
    name = "chest_xray_classifier"
    description = "synthetic original description"
    args_schema = Schema

    def __init__(self):
        self.values = {name: (i + 1) / 20 for i, name in enumerate(variants.CLASSIFIER_LABELS)}
        self.metadata = {"analysis_status": "completed", "note": "synthetic original note",
                         "image_path": "DO_NOT_LOG_PRIVATE_IMAGE"}

    def _run(self, *args, **kwargs):
        self.last_arguments = (args, kwargs)
        return self.values, self.metadata

    async def _arun(self, *args, **kwargs):
        return self._run(*args, **kwargs)


class Config:
    def __init__(self, **kwargs):
        self.num_beams, self.do_sample = 1, False
        vars(self).update(kwargs)


def synthetic_model():
    return SimpleNamespace(config=SimpleNamespace(bos_token_id=0, eos_token_id=None, pad_token_id=1,
                                                  decoder=SimpleNamespace(eos_token_id=3)),
                           dtype="torch.float32", generate=Mock(return_value="SYNTHETIC_TOKEN_OBJECT"))


class ToolVariantTests(unittest.TestCase):
    def test_module_import_does_not_import_ml_frameworks(self):
        code = ("import sys; import tool_variants; "
                "assert not any(x in sys.modules for x in "
                "('torch','torchvision','torchxrayvision','transformers','langchain_core','pydantic'))")
        child = subprocess.run([sys.executable, "-B", "-c", code], cwd=Path(__file__).parent,
                               capture_output=True, text=True, timeout=15)
        self.assertEqual(child.returncode, 0, child.stderr)

    def test_classifier_changes_only_description_and_success_note(self):
        self.assertIs(variants.classifier_variant_class(SyntheticClassifier, "original"), SyntheticClassifier)
        cls = variants.classifier_variant_class(SyntheticClassifier, "operating_point")
        tool = cls(); before = deepcopy(tool.metadata)
        output, metadata = tool._run("synthetic.png", run_manager="synthetic-manager")
        self.assertIs(output, tool.values)
        self.assertIs(tool.args_schema, SyntheticClassifier.args_schema)
        self.assertEqual(tool.name, SyntheticClassifier.name)
        self.assertEqual(tool.last_arguments, (("synthetic.png",), {"run_manager": "synthetic-manager"}))
        self.assertEqual(tool.metadata, before)
        self.assertEqual({k: v for k, v in metadata.items() if k != "note"},
                         {k: v for k, v in before.items() if k != "note"})
        self.assertEqual(metadata["note"], variants.CLASSIFIER_NOTE)
        self.assertIn("not direct disease probabilities", tool.description)
        async_output = asyncio.run(tool._arun("synthetic.png"))
        self.assertIs(async_output[0], tool.values)
        self.assertEqual(async_output[1]["note"], variants.CLASSIFIER_NOTE)

    def test_classifier_failure_is_not_rewritten_as_success(self):
        tool = variants.classifier_variant_class(SyntheticClassifier, "operating_point")()
        tool.values = {"error": "DO_NOT_LOG_FAILURE"}
        tool.metadata = {"analysis_status": "failed", "image_path": "DO_NOT_LOG_PATH"}
        output, metadata = tool._run("synthetic.png")
        self.assertIs(output, tool.values); self.assertIs(metadata, tool.metadata)
        details = variants.validate_observation("classifier", (output, metadata))
        self.assertFalse(details["valid"])
        self.assertEqual(details["clinical_evidence"], "unknown")
        self.assertNotIn("DO_NOT_LOG", json.dumps(details))

    def test_observation_validation_does_not_modify_scores_or_accept_bad_numbers(self):
        tool = SyntheticClassifier(); original = deepcopy(tool.values)
        result = variants.validate_observation("classification", tool._run())
        self.assertTrue(result["valid"])
        self.assertEqual(result["scores"], original)
        self.assertEqual(tool.values, original)
        self.assertNotIn("DO_NOT_LOG", json.dumps(result))
        self.assertIsNone(result["step_credit"])
        for bad in (float("nan"), float("inf"), True, "0.2", -1, 1.1):
            scores = deepcopy(original); scores[variants.CLASSIFIER_LABELS[0]] = bad
            with self.subTest(value=repr(bad)):
                self.assertFalse(variants.validate_observation("classifier", (scores, tool.metadata))["valid"])
        self.assertFalse(variants.validate_observation("classifier", (dict(reversed(list(original.items()))), tool.metadata))["valid"])

    def test_report_summary_never_contains_report_or_identifying_metadata(self):
        text = "CHEST X-RAY REPORT\n\nFINDINGS:\nSYNTHETIC_FINDINGS_SECRET\n\nIMPRESSION:\nSYNTHETIC_IMPRESSION_SECRET"
        meta = {"analysis_status": "completed", "sections_generated": ["findings", "impression"],
                "image_path": "DO_NOT_LOG_PATH", "clinical_evidence": "verified"}
        result = variants.validate_observation("report", (text, meta))
        self.assertTrue(result["valid"])
        self.assertEqual(result["report_chars"], len(text))
        self.assertEqual(result["report_sha256"], hashlib.sha256(text.encode()).hexdigest())
        self.assertEqual(result["clinical_evidence"], "unknown")
        self.assertFalse(result["semantic_completeness_evaluated"])
        self.assertNotIn("SECRET", json.dumps(result)); self.assertNotIn("DO_NOT_LOG", json.dumps(result))
        for malformed in ("Error generating report: PRIVATE", "", text.replace("IMPRESSION:", "MISSING:")):
            self.assertFalse(variants.validate_observation("report", (malformed, meta))["valid"])
        failed = variants.validate_observation("report", ("PRIVATE_BODY", {"analysis_status": "failed", "error": "PRIVATE_ERROR"}))
        self.assertFalse(failed["valid"]); self.assertNotIn("PRIVATE", json.dumps(failed))

    def test_eos_only_changes_one_parameter_and_retains_generated_text(self):
        class OriginalReport:
            generation_args = variants.ORIGINAL_GENERATION_ARGS.copy()
            name, args_schema = "chest_xray_report_generator", Schema

        self.assertIs(variants.report_variant_class(OriginalReport, Config, "original"), OriginalReport)
        model = synthetic_model()
        tokenizer = SimpleNamespace(cls_token_id=2, sep_token_id=3,
                                    batch_decode=Mock(return_value=["UNMODIFIED_SYNTHETIC_MODEL_TEXT"]))
        original = variants.report_generation_parameters(OriginalReport.generation_args, model, tokenizer, "original")
        eos = variants.report_generation_parameters(OriginalReport.generation_args, model, tokenizer, "eos_only")
        self.assertEqual({k for k in original if original[k] != eos[k]}, {"eos_token_id"})
        self.assertEqual(eos["beam_width"], 2); self.assertNotIn("num_beams", eos)
        tool = variants.report_variant_class(OriginalReport, Config, "eos_only")()
        result = tool._generate_report_section("SYNTHETIC_PIXELS", model, tokenizer)
        self.assertEqual(result, "UNMODIFIED_SYNTHETIC_MODEL_TEXT")
        self.assertEqual(model.generate.call_args.kwargs["generation_config"].eos_token_id, 3)
        self.assertEqual(model.generate.call_args.kwargs["generation_config"].num_beams, 1)
        self.assertIsNone(model.config.eos_token_id)
        tokenizer.batch_decode.assert_called_once_with("SYNTHETIC_TOKEN_OBJECT", skip_special_tokens=True)
        tokenizer.sep_token_id = 99
        with self.assertRaises(ValueError): variants.report_generation_parameters(OriginalReport.generation_args, model, tokenizer, "eos_only")
        with self.assertRaises(ValueError): variants.report_generation_parameters({**OriginalReport.generation_args, "num_beams": 2}, model, tokenizer, "original")

    def test_fixed_assets_include_configs_not_only_weights(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); specs, expected = {}, {}
            for role in ("findings", "impression"):
                spec = {"repo_id": "synthetic/" + role, "revision": "fixture-revision",
                        "weight_bytes": 4, "weight_sha256": hashlib.sha256(b"FAKE").hexdigest()}
                folder = root / ("models--synthetic--" + role) / "snapshots" / spec["revision"]
                folder.mkdir(parents=True)
                for filename in variants.report_audit.REQUIRED_FILES:
                    (folder / filename).write_bytes(b"FAKE" if filename == "model.safetensors" else b"SYNTHETIC")
                _, manifest = variants.report_audit.inspect_snapshot(root, spec)
                specs[role] = spec; expected[role] = manifest["manifest_sha256"]
            with patch.object(variants.report_audit, "MODEL_SPECS", specs), patch.object(variants, "REPORT_ASSET_MANIFESTS", expected):
                snapshots, manifests = variants._report_assets(root)
                self.assertEqual(len(manifests), 2)
                self.assertNotIn(str(root), json.dumps(manifests))
                (snapshots["synthetic/findings"][1] / "config.json").write_text("CHANGED_SYNTHETIC_CONFIG")
                _, changed = variants._report_assets(root)
                self.assertNotEqual(manifests[0]["manifest_sha256"], changed[0]["manifest_sha256"])
                self.assertEqual(changed[0]["checksum_verification"], "skipped_by_user")

    def test_source_edits_and_dirty_checkout_are_recorded_without_a_hash_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve(); source = root / variants.SOURCE_RELATIVE["classification"]
            source.parent.mkdir(parents=True); source.write_text("# locally updated source\n")
            def git(command, **kwargs):
                return str(root) if "--show-toplevel" in command else " M local.py" if "status" in command else "different-commit"
            with patch.object(variants.subprocess, "check_output", side_effect=git):
                details = variants._source(root, "classification")
            self.assertTrue(details["working_tree_dirty"])
            self.assertEqual(details["commit"], "different-commit")
            self.assertEqual(details["tool_sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(details["hash_policy"], "record_only")

    def test_checkpoint_digest_does_not_need_to_match_or_be_read(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / variants.CLASSIFIER_FILENAME; path.write_bytes(b"UPDATED")
            with patch.object(variants, "CLASSIFIER_WEIGHT_BYTES", len(b"UPDATED")), \
                    patch.object(variants.classifier_audit, "sha256_file", side_effect=AssertionError("no weight hashing")):
                details = variants._classifier_asset(path)
            self.assertIsNone(details["sha256"])
            self.assertEqual(details["checksum_verification"], "skipped_by_user")

    def test_report_factory_is_offline_load_only_and_provenance_has_no_paths(self):
        loads = []
        class Loader:
            @classmethod
            def from_pretrained(cls, path, **kwargs):
                loads.append((cls.__name__, path, kwargs))
                if cls.__name__ == "ModelLoader":
                    model = synthetic_model(); model.generate.side_effect = AssertionError("No inference in factory")
                    return model
                return SimpleNamespace(cls_token_id=2, sep_token_id=3)
        class ModelLoader(Loader): pass
        class TokenizerLoader(Loader): pass
        class ProcessorLoader(Loader): pass
        class SyntheticReport:
            name, description, args_schema = "chest_xray_report_generator", "synthetic report description", Schema
            generation_args = variants.ORIGINAL_GENERATION_ARGS.copy()
            def __init__(self, **kwargs):
                for role, spec in variants.report_audit.MODEL_SPECS.items():
                    for suffix, cls in (("model", ModelLoader), ("tokenizer", TokenizerLoader), ("processor", ProcessorLoader)):
                        setattr(self, role + "_" + suffix, cls.from_pretrained(spec["repo_id"], cache_dir="PRIVATE_CACHE"))
        module = SimpleNamespace(ChestXRayReportGeneratorTool=SyntheticReport, GenerationConfig=Config,
                                 VisionEncoderDecoderModel=ModelLoader, BertTokenizer=TokenizerLoader,
                                 ViTImageProcessor=ProcessorLoader)
        snapshots = {spec["repo_id"]: (role, Path("/SYNTHETIC_PRIVATE_CACHE") / role)
                     for role, spec in variants.report_audit.MODEL_SPECS.items()}
        assets = [{"role": role, "sha256": "synthetic-digest"} for role in ("findings", "impression")]
        with ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, {"torch": SimpleNamespace(), "transformers": SimpleNamespace(__version__="4.45.2")}))
            stack.enter_context(patch.object(variants, "_source", return_value={"commit": "synthetic"}))
            stack.enter_context(patch.object(variants, "_report_assets", return_value=(snapshots, assets)))
            stack.enter_context(patch.object(variants, "_device", return_value="cpu"))
            stack.enter_context(patch.object(variants, "_module", return_value=module))
            tool, provenance = variants.create_report_tool("/SYNTHETIC_PRIVATE_REPO", cache_dir="/SYNTHETIC_PRIVATE_CACHE", device="cpu")
        self.assertIs(type(tool), SyntheticReport)
        self.assertEqual(len(loads), 6)
        for loader, path, kwargs in loads:
            self.assertTrue(kwargs["local_files_only"])
            self.assertFalse(kwargs["trust_remote_code"])
            self.assertNotIn("cache_dir", kwargs)
            if loader == "ModelLoader": self.assertTrue(kwargs["use_safetensors"])
        self.assertEqual(provenance["changed_fields"], [])
        self.assertEqual(provenance["effective_generation_config"]["findings"]["num_beams"], 1)
        self.assertIsNone(provenance["effective_generation_config"]["findings"]["eos_token_id"])
        self.assertNotIn("PRIVATE", json.dumps(provenance))

    def test_invalid_mode_and_missing_asset_fail_before_heavy_import(self):
        for function, kwargs in ((variants.create_classifier_tool, {"checkpoint": "absent"}),
                                 (variants.create_report_tool, {"cache_dir": "absent"})):
            with self.assertRaises(ValueError): function("absent", device="cpu", mode="unplanned", **kwargs)
        with self.assertRaises(FileNotFoundError): variants._classifier_asset(Path("missing-checkpoint"))
        with self.assertRaises(ValueError): variants.validate_observation("unknown-kind", None)

    def segmentation_fixture(self, directory, requested=None):
        path = Path(directory) / "segmentation_1234abcd.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\nSYNTHETIC_SIGNATURE_FIXTURE_NOT_REAL_IMAGE")
        metric = {"area_pixels": 100, "area_cm2": 0.04, "centroid": (4.5, 4.5),
                  "bbox": (0, 0, 10, 10), "width": 10, "height": 10, "aspect_ratio": 1.0,
                  "relative_position": {"top": 0.045, "left": 0.045,
                                        "center_dist": math.hypot(0.045 - 0.5, 0.045 - 0.5)},
                  "mean_intensity": 100.0, "std_intensity": 10.0, "confidence_score": 0.7}
        requested = ["Heart"] if requested is None else requested
        metrics = {name: deepcopy(metric) for name in requested}
        return ({"segmentation_image_path": str(path), "metrics": metrics},
                {"analysis_status": "completed", "image_path": "PRIVATE_IMAGE_PATH",
                 "segmentation_image_path": str(path), "original_size": (100, 100), "model_size": (512, 512),
                 "pixel_spacing_mm": 0.2, "requested_organs": requested, "processed_organs": list(metrics)})

    def test_segmentation_subset_original_contract_and_safe_private_overlay_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.segmentation_fixture(directory, ["Right Lung", "Heart"])
            original = deepcopy(result)
            safe = variants.validate_observation("segmentation", result, artifact_dir=directory)
            self.assertTrue(safe["valid"])
            self.assertEqual(safe["metrics_returned_count"], 2)
            self.assertEqual(safe["configured_model_channel_count"], 14)
            self.assertFalse(safe["forward_prediction_audited"])
            self.assertFalse(safe["physical_area_calibrated"])
            self.assertFalse(safe["segmentation_is_reference_label"])
            self.assertEqual(safe["clinical_evidence"], "unknown")
            self.assertEqual(result, original)
            self.assertNotIn(directory, json.dumps(safe))
            self.assertNotIn("PRIVATE", json.dumps(safe))
            self.assertNotIn("segmentation_1234abcd", json.dumps(safe))

    def test_segmentation_unknown_organ_bad_metrics_and_overlay_escape_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.segmentation_fixture(directory)
            self.assertFalse(variants.validate_observation("segmentation", result)["valid"])
            self.assertFalse(variants.validate_observation("segmentation", result,
                                                         artifact_dir=Path(directory) / "other")["valid"])
            bad = deepcopy(result); bad[0]["metrics"]["Heart"]["area_cm2"] = 999
            self.assertFalse(variants.validate_observation("segmentation", bad, artifact_dir=directory)["valid"])
            bad = deepcopy(result); bad[1]["requested_organs"] = ["UNKNOWN_PRIVATE_NAME"]
            safe = variants.validate_observation("segmentation", bad, artifact_dir=directory)
            self.assertFalse(safe["valid"]); self.assertNotIn("PRIVATE", json.dumps(safe))
            bad = deepcopy(result); bad[1]["pixel_spacing_mm"] = 1.0
            self.assertFalse(variants.validate_observation("segmentation", bad, artifact_dir=directory)["valid"])

    def test_segmentation_omitted_metrics_are_not_invented_as_negative_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.segmentation_fixture(directory, list(variants.segmentation_audit.ORGANS))
            result[0]["metrics"] = {}; result[1]["processed_organs"] = []
            safe = variants.validate_observation("segmentation", result, artifact_dir=directory)
            self.assertTrue(safe["valid"])
            self.assertEqual(safe["requested_structure_count"], 14)
            self.assertEqual(safe["metrics_returned_count"], 0)
            self.assertFalse(safe["omission_reason_verified"])
            failed = ({"error": "PRIVATE"}, {"analysis_status": "failed", "error_traceback": "PRIVATE_TRACE"})
            safe = variants.validate_observation("segmentation", failed, artifact_dir=directory)
            self.assertFalse(safe["valid"]); self.assertNotIn("PRIVATE", json.dumps(safe))

    def test_segmentation_factory_preserves_official_class_and_does_no_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint, output = root / variants.segmentation_audit.CHECKPOINT_NAME, root / "new-overlays"
            fake_torch = SimpleNamespace(load=lambda *args, **kwargs: "SYNTHETIC_WEIGHT_OBJECT")
            xrv = SimpleNamespace(__version__="1.3.5", __file__=str(root / "xrv" / "__init__.py"),
                                  utils=SimpleNamespace(get_cache_dir=lambda: "UNUSED", download=lambda *a: None))
            init_calls = []
            class Segmentation:
                name, description, args_schema = "chest_xray_segmentation", "synthetic", Schema
                pixel_spacing_mm = 0.2
                organ_map = dict(zip(variants.segmentation_audit.ORGANS, range(14)))
                model = SimpleNamespace(targets=list(variants.segmentation_audit.ORGANS))
                def __init__(self, **kwargs):
                    init_calls.append(kwargs)
                    fake_torch.load(checkpoint)
            with ExitStack() as stack:
                stack.enter_context(patch.dict(sys.modules, {"torch": fake_torch, "torchxrayvision": xrv,
                    "matplotlib": SimpleNamespace(use=lambda *a: None)}))
                stack.enter_context(patch.object(variants, "_source", return_value={"synthetic": True}))
                stack.enter_context(patch.object(variants, "_device", return_value="cuda:0"))
                stack.enter_context(patch.object(variants, "_module", return_value=SimpleNamespace(ChestXRaySegmentationTool=Segmentation)))
                stack.enter_context(patch.object(variants, "_checkpoint_asset", return_value={"sha256": None, "checksum_verification": "skipped_by_user"}))
                stack.enter_context(patch.object(variants.segmentation_audit, "sha256_file", return_value=variants.segmentation_audit.XRV_WRAPPER_SHA256))
                tool, provenance = variants.create_segmentation_tool(root, checkpoint=checkpoint, device="cuda:0", temp_dir=output)
                with self.assertRaises(FileExistsError):
                    variants.create_segmentation_tool(root, checkpoint=checkpoint, device="cuda:0", temp_dir=output)
            self.assertIs(type(tool), Segmentation)
            self.assertEqual(init_calls, [{"device": "cuda:0", "temp_dir": output}])
            self.assertEqual(provenance["changed_fields"], [])
            self.assertFalse(provenance["factory_did_inference"])
            self.assertEqual(len(provenance["loads_observed"]), 1)
            self.assertNotIn(directory, json.dumps(provenance))
            self.assertEqual((output / ".gitignore").read_text(), "*\n")


if __name__ == "__main__":
    unittest.main()
