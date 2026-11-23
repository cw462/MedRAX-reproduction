"""Synthetic offline MAIRA boundaries; no actual model/GPU/medical result."""
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import maira_smoke as smoke


class Tensor:
    def __init__(self, values):
        self.values = values
        self.shape = (len(values), len(values[0]))

    def detach(self): return self
    def cpu(self): return self
    def tolist(self): return self.values
    def __eq__(self, value):
        count = sum(token == value for row in self.values for token in row)
        return SimpleNamespace(sum=lambda: SimpleNamespace(item=lambda: count))


class LoaderTests(unittest.TestCase):
    def test_local_loader_preserves_original_quantization_and_denies_other_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            calls, records = [], []
            loader = smoke.local_loader(lambda *a, **k: calls.append((a, k)), kind="model",
                                        snapshot=Path(directory), loads=records)
            quant = object()
            loader(smoke.REPO_ID, device_map="cuda:0", trust_remote_code=True, quantization_config=quant)
            self.assertIs(calls[0][1]["quantization_config"], quant)
            self.assertTrue(calls[0][1]["local_files_only"])
            self.assertTrue(calls[0][1]["trust_remote_code"])
            self.assertTrue(calls[0][1]["use_safetensors"])
            self.assertNotIn("torch_dtype", calls[0][1])
            for source, kwargs in [("other/model", {"trust_remote_code": True}),
                                   (smoke.REPO_ID, {"trust_remote_code": True, "code_revision": "main"}),
                                   (smoke.REPO_ID, {"trust_remote_code": False})]:
                with self.assertRaises(ValueError): loader(source, **kwargs)
            self.assertEqual(len(calls), 1)
            self.assertNotIn(directory, json.dumps(records))

    def test_custom_code_digest_can_change_but_private_module_cache_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            modules, objects, files = {}, {}, {}
            for role, (name, filename) in smoke.CUSTOM_CLASSES.items():
                raw = ("# SYNTHETIC " + name).encode()
                (cache / filename).write_bytes(raw)
                module_name = "synthetic_maira_" + role
                modules[module_name] = SimpleNamespace(__file__=str(cache / filename))
                objects[role] = type(name, (), {"__module__": module_name})()
                files[filename] = (len(raw), hashlib.sha256(raw).hexdigest())
            objects["model"].config = objects["config"]
            tool = SimpleNamespace(model=objects["model"], processor=objects["processor"])
            with patch.dict(sys.modules, modules), patch.object(smoke, "MODEL_SPEC", {"files": files}):
                self.assertEqual(len(smoke.loaded_custom_code(tool, cache)), 3)
                with self.assertRaises(ValueError): smoke.loaded_custom_code(tool, cache / "elsewhere")
                (cache / "modeling_maira2.py").write_text("# TAMPERED")
                observed = smoke.loaded_custom_code(tool, cache)
                model = next(x for x in observed if x["role"] == "model")
                self.assertEqual(model["sha256"], hashlib.sha256(b"# TAMPERED").hexdigest())

    def test_factory_preserves_original_8bit_and_uses_reviewed_local_loaders(self):
        with tempfile.TemporaryDirectory() as directory:
            root, constructor_calls = Path(directory), []
            config = SimpleNamespace(image_seq_length=576)
            model = SimpleNamespace(is_loaded_in_8bit=True, is_loaded_in_4bit=False, device="cuda:0", dtype="fp16",
                config=config, generation_config=SimpleNamespace(eos_token_id=2, pad_token_id=0, max_new_tokens=450),
                vision_tower=SimpleNamespace(parameters=lambda: iter([SimpleNamespace(dtype="fp16")])))
            class ModelLoader:
                @classmethod
                def from_pretrained(cls, source, **kwargs): return model
            class ProcessorLoader:
                @classmethod
                def from_pretrained(cls, source, **kwargs): return SimpleNamespace()
            class Tool:
                name, description = "xray_phrase_grounding", "synthetic"
                args_schema = SimpleNamespace(model_json_schema=lambda: {"synthetic": True})
                def __init__(self, **kwargs):
                    constructor_calls.append(kwargs)
                    self.model = ModelLoader.from_pretrained(kwargs["model_path"], trust_remote_code=True,
                        device_map=kwargs["device"], quantization_config={"load_in_8bit": kwargs["load_in_8bit"]})
                    self.processor = ProcessorLoader.from_pretrained(kwargs["model_path"], trust_remote_code=True)
            module = SimpleNamespace(AutoModelForCausalLM=ModelLoader, AutoProcessor=ProcessorLoader, XRayPhraseGroundingTool=Tool)
            dynamic = SimpleNamespace(HF_MODULES_CACHE="synthetic_default")
            tf = SimpleNamespace(__version__=smoke.TRANSFORMERS_VERSION, dynamic_module_utils=dynamic)
            torch = SimpleNamespace(load=lambda *a, **k: None,
                cuda=SimpleNamespace(is_available=lambda: True, device_count=lambda: 1, set_device=lambda n: None))
            with ExitStack() as stack:
                stack.enter_context(patch.dict(sys.modules, {"torch": torch, "transformers": tf,
                    "transformers.dynamic_module_utils": dynamic, "matplotlib": SimpleNamespace(use=lambda *a: None)}))
                stack.enter_context(patch.object(smoke, "source_provenance", return_value={"synthetic": True}))
                stack.enter_context(patch.object(smoke.audit, "inspect_snapshot", return_value=(root, {"synthetic": True}, {})))
                stack.enter_context(patch.object(smoke, "_module", return_value=module))
                stack.enter_context(patch.object(smoke, "loaded_custom_code", return_value=[{"synthetic": True}]))
                stack.enter_context(patch.object(smoke.audit, "environment", return_value={"synthetic": True}))
                tool, provenance = smoke.create_maira_tool(root, cache_dir=root, temp_dir=root / "worker")
                with self.assertRaises(FileExistsError):
                    smoke.create_maira_tool(root, cache_dir=root, temp_dir=root / "worker")
            self.assertIs(type(tool), Tool)
            params = constructor_calls[0]
            self.assertEqual((params["load_in_8bit"], params["load_in_4bit"]), (True, False))
            self.assertEqual(params["model_path"], smoke.REPO_ID)
            self.assertNotIn("torch_dtype", params)
            self.assertEqual(provenance["changed_fields"], [])
            self.assertFalse(provenance["factory_did_inference"])
            self.assertEqual(len(provenance["asset_loads"]), 2)
            self.assertNotIn(directory, json.dumps(provenance))
            self.assertEqual(dynamic.HF_MODULES_CACHE, "synthetic_default")

    def test_module_import_remains_lightweight(self):
        code = "import sys; import maira_smoke; assert not any(x in sys.modules for x in ('torch','transformers','PIL','numpy'))"
        run = subprocess.run([sys.executable, "-B", "-c", code], cwd=Path(smoke.__file__).parent,
                             capture_output=True, text=True, check=False)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_source_and_all_runtime_metadata_are_pinned(self):
        self.assertEqual(len(smoke.MODEL_SPEC["files"]), 22)
        self.assertEqual(sum(n for n, _ in smoke.MODEL_SPEC["files"].values()), 27525118360)
        for name in ("tokenizer.json", "chat_template.json", "processing_maira2.py", "preprocessor_config.json"):
            self.assertEqual(len(smoke.MODEL_SPEC["files"][name][1]), 64)


class InputOutputTests(unittest.TestCase):
    def result(self, directory, *, size=(200, 100)):
        path = Path(directory) / "grounding_1234abcd.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\nSYNTHETIC_SIGNATURE_ONLY")
        box = [0.1, 0.2, 0.8, 0.9]
        return ({"predictions": [{"phrase": "PRIVATE_SYNTHETIC_PHRASE", "bounding_boxes": {
            "model_coordinates": [box], "image_coordinates": [smoke.adjusted_box(box, size)]}}],
            "visualization_path": str(path)}, {"analysis_status": "completed", "original_size": size,
                                               "model_input_size": (518, 518), "image_path": "PRIVATE_PATH"})

    def test_constant_input_rejected_and_nonconstant_png_decoded_without_model(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.png"
            image = Image.new("RGB", (4, 4), (50, 50, 50)); image.save(path)
            with self.assertRaises(ValueError): smoke.validate_image(path)
            image.putpixel((0, 0), (70, 70, 70)); image.save(path)
            details = smoke.validate_image(path)
            self.assertTrue(details["grayscale_nonconstant"])
            self.assertNotIn(directory, json.dumps(details))

    def test_original_grounding_coordinates_validated_without_exposing_phrase_or_path(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.result(directory)
            unchanged = deepcopy(result)
            safe = smoke.validate_observation(result, artifact_dir=directory, image_size=[200, 100])
            self.assertTrue(safe["valid"])
            self.assertEqual(safe["box_count"], 1)
            self.assertEqual(safe["clinical_evidence"], "unknown")
            self.assertFalse(safe["bounding_boxes_are_reference_labels"])
            self.assertNotIn("PRIVATE", json.dumps(safe))
            self.assertNotIn(directory, json.dumps(safe))
            self.assertEqual(result, unchanged)

    def test_bad_geometry_alignment_metadata_and_overlay_escape_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            good = self.result(directory)
            cases = []
            for coordinate in ([0.8, 0.2, 0.1, 0.9], [0.1, 0.2, float("nan"), 0.9], [0.1, 0.2, 1.1, 0.9]):
                bad = deepcopy(good); bad[0]["predictions"][0]["bounding_boxes"]["model_coordinates"] = [coordinate]; cases.append(bad)
            bad = deepcopy(good); bad[0]["predictions"][0]["bounding_boxes"]["image_coordinates"] = [[0.1, 0.2, 0.8, 0.9]]; cases.append(bad)
            bad = deepcopy(good); bad[1]["original_size"] = [100, 200]; cases.append(bad)
            for bad in cases:
                self.assertFalse(smoke.validate_observation(bad, artifact_dir=directory, image_size=[200, 100])["valid"])
            self.assertFalse(smoke.validate_observation(good, artifact_dir=Path(directory) / "other", image_size=[200, 100])["valid"])

    def test_no_finding_and_failed_metadata_are_distinct_and_never_clinical_labels(self):
        result = ({"predictions": [], "visualization_path": None}, {"analysis_status": "completed_no_finding",
                  "original_size": (200, 100), "model_input_size": (518, 518)})
        safe = smoke.validate_observation(result, artifact_dir="unused", image_size=[200, 100])
        self.assertTrue(safe["valid"])
        self.assertFalse(safe["no_finding_is_verified_negative"])
        failed = ({"error": "PRIVATE_ERROR"}, {"analysis_status": "failed", "error_details": "PRIVATE_PATH"})
        safe = smoke.validate_observation(failed, artifact_dir="unused", image_size=[200, 100])
        self.assertFalse(safe["valid"])
        self.assertEqual(safe["validation_status"], "tool_reported_failure")
        self.assertNotIn("PRIVATE", json.dumps(safe))
        result[1]["analysis_status"] = "completed"
        self.assertFalse(smoke.validate_observation(result, artifact_dir="unused", image_size=[200, 100])["valid"])

    def test_cli_failure_nonzero_and_existing_output_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            args = ["--repo", directory, "--cache-dir", directory, "--image", "missing.png", "--phrase", "PRIVATE_PHRASE",
                    "--output", str(output)]
            self.assertEqual(smoke.main(args), 1)
            raw = (output / "summary.json").read_bytes()
            self.assertEqual(smoke.main(args), 2)
            self.assertEqual((output / "summary.json").read_bytes(), raw)
            self.assertNotIn("PRIVATE_PHRASE", raw.decode())
            self.assertNotIn(directory, raw.decode())


class GenerationTests(unittest.TestCase):
    def fixture(self, extra):
        ids = Tensor([[1, 32204, 5]])
        model = SimpleNamespace(generation_config=SimpleNamespace(eos_token_id=2, pad_token_id=0, do_sample=False, num_beams=1),
                                config=SimpleNamespace(image_token_index=32204))
        params = {"input_ids": ids, "attention_mask": Tensor([[1, 1, 1]]),
                  "pixel_values": SimpleNamespace(shape=(1, 3, 518, 518)), "max_new_tokens": 300, "use_cache": True}
        return model, params, Tensor([[1, 32204, 5] + extra])

    def test_real_call_wrapper_preserves_parameters_and_checks_prefix_eos(self):
        model, params, output = self.fixture([7, 2])
        calls, logs = [], []
        def original(**kwargs): calls.append(kwargs); return output
        wrapped = smoke.generation_recorder(original, model, logs)
        self.assertIs(wrapped(**params), output)
        self.assertEqual(calls, [params])
        self.assertTrue(logs[0]["prefix_preserved"])
        self.assertTrue(logs[0]["eos_in_new_tokens"])
        self.assertEqual(logs[0]["new_token_count"], 2)
        self.assertNotIn("[1, 32204, 5]", json.dumps(logs))

    def test_changed_cap_prefix_or_oversized_output_fail_closed(self):
        model, params, output = self.fixture([7] * 301)
        calls, logs = [], []
        def original(**kwargs): calls.append(1); return output
        wrapped = smoke.generation_recorder(original, model, logs)
        with self.assertRaises(ValueError): wrapped(**{**params, "max_new_tokens": 301})
        self.assertEqual(calls, [])
        with self.assertRaises(ValueError): wrapped(**params)
        self.assertEqual(logs[-1]["status"], "failed")
        wrong = smoke.generation_recorder(lambda **kw: Tensor([[99, 32204, 5, 2]]), model, logs)
        with self.assertRaises(ValueError): wrong(**params)

    def test_cap_flags_features_and_plaintext_converter_preserve_unknown(self):
        model, params, output = self.fixture([7] * 300)
        logs = []
        smoke.generation_recorder(lambda **kw: output, model, logs)(**params)
        self.assertTrue(logs[0]["reached_new_token_cap"])
        self.assertFalse(logs[0]["eos_in_new_tokens"])
        features = []
        raw = SimpleNamespace(shape=(1, 1369, 4096))
        self.assertIs(smoke.feature_recorder(lambda **kw: raw, features)(pixel_values="synthetic"), raw)
        with self.assertRaises(ValueError):
            smoke.feature_recorder(lambda: SimpleNamespace(shape=(1, 576, 4096)), [])()
        converted = []
        text = "PRIVATE_SYNTHETIC_PLAINTEXT"
        self.assertEqual(smoke.conversion_recorder(lambda value: value, converted)(text), text)
        self.assertEqual(converted[0]["returned_type"], "str")
        self.assertNotIn(text, json.dumps(converted))
        self.assertNotIn("clinical_evidence", converted[0])


if __name__ == "__main__":
    unittest.main()
