"""Offline synthetic boundary tests. No real model, GPU, network or medical result."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import llava_smoke as smoke


class Tensor:
    def __init__(self, values):
        self.values = values
        self.shape = (len(values), len(values[0]))

    def detach(self):
        return self

    def cpu(self):
        return self

    def tolist(self):
        return self.values


class SnapshotTests(unittest.TestCase):
    def fixture(self, root):
        files = {"config.json": b'{"synthetic":true}', "a.safetensors": b"not-real-weights"}
        files["model.safetensors.index.json"] = json.dumps({"weight_map": {"weight": "a.safetensors"}}).encode()
        spec = {"repo_id": "test/synthetic", "revision": "fixed", "files": {
            name: (len(raw), hashlib.sha256(raw).hexdigest()) for name, raw in files.items()}}
        snapshot = root / "models--test--synthetic" / "snapshots" / "fixed"
        snapshot.mkdir(parents=True)
        for name, raw in files.items():
            (snapshot / name).write_bytes(raw)
        return spec, snapshot

    def test_complete_snapshot_and_no_paths_in_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec, path = self.fixture(root)
            actual, manifest, states = smoke.inspect_snapshot(root, spec)
            self.assertEqual(actual, path.resolve())
            self.assertEqual(len(states), 3)
            self.assertNotIn(directory, json.dumps(manifest))
            smoke.assert_files_unchanged(actual, states)

    def test_unknown_files_rejected_but_changed_config_digest_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec, path = self.fixture(root)
            (path / "tokenizer.json").write_text("{}")
            with self.assertRaises(ValueError):
                smoke.inspect_snapshot(root, spec)
            (path / "tokenizer.json").unlink()
            (path / "config.json").write_bytes(b"X" * spec["files"]["config.json"][0])
            _, observed, _ = smoke.inspect_snapshot(root, spec)
            config = next(x for x in observed["files"] if x["filename"] == "config.json")
            self.assertEqual(config["sha256"], hashlib.sha256((path / "config.json").read_bytes()).hexdigest())
            self.assertEqual(observed["hash_policy"], "record_only")

    def test_missing_shard_and_index_reference_escape_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec, path = self.fixture(root)
            index = json.dumps({"weight_map": {"weight": "../other.safetensors"}}).encode()
            (path / "model.safetensors.index.json").write_bytes(index)
            spec["files"]["model.safetensors.index.json"] = (len(index), hashlib.sha256(index).hexdigest())
            with self.assertRaises(ValueError):
                smoke.inspect_snapshot(root, spec)
            (path / "a.safetensors").unlink()
            with self.assertRaises(FileNotFoundError):
                smoke.inspect_snapshot(root, spec)

    def test_post_load_stat_change_is_observational(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec, path = self.fixture(root)
            actual, _, states = smoke.inspect_snapshot(root, spec)
            (path / "a.safetensors").write_bytes(b"changed-length")
            self.assertFalse(smoke.assert_files_unchanged(actual, states))


class LoaderTests(unittest.TestCase):
    def test_redirect_preserves_numeric_arguments_and_nested_local_source(self):
        with tempfile.TemporaryDirectory() as directory:
            calls, loads = [], []
            path = Path(directory).resolve()
            def original(*args, **kwargs):
                calls.append((args, kwargs))
                return "synthetic loaded marker"
            loader = smoke.local_loader(original, role="llava", kind="model", snapshot=path, loads=loads)
            params = {"load_in_8bit": True, "torch_dtype": "bf16", "device_map": {"": "cuda:0"},
                      "low_cpu_mem_usage": True, "use_flash_attention_2": False, "cache_dir": "ignored"}
            self.assertEqual(loader(smoke.MODEL_SPECS["llava"]["repo_id"], **params), "synthetic loaded marker")
            loader(path, **params)
            for args, kwargs in calls:
                self.assertEqual(args, (str(path),))
                self.assertTrue(kwargs["local_files_only"])
                self.assertTrue(kwargs["use_safetensors"])
                self.assertFalse(kwargs["trust_remote_code"])
                self.assertNotIn("cache_dir", kwargs)
                for key in set(params) - {"cache_dir"}:
                    self.assertEqual(kwargs[key], params[key])
            self.assertEqual(params["cache_dir"], "ignored")
            self.assertNotIn(directory, json.dumps(loads))

    def test_unknown_repo_revision_and_remote_code_fail_before_load(self):
        calls = []
        loader = smoke.local_loader(lambda *a, **k: calls.append(1), role="clip", kind="model",
                                    snapshot=Path("synthetic-fixed"), loads=[])
        for source, kwargs in [("other/model", {}),
                               (smoke.MODEL_SPECS["clip"]["repo_id"], {"revision": "main"}),
                               (smoke.MODEL_SPECS["clip"]["repo_id"], {"trust_remote_code": True})]:
            with self.assertRaises(ValueError):
                loader(source, **kwargs)
        self.assertEqual(calls, [])

    def test_clip_uses_verified_bin_and_pickle_loader_is_restricted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve()
            calls, loads = [], []
            loader = smoke.local_loader(lambda *a, **k: calls.append(k), role="clip", kind="model",
                                        snapshot=path, loads=loads)
            loader(smoke.MODEL_SPECS["clip"]["repo_id"])
            self.assertFalse(calls[0]["use_safetensors"])
            allowed = path / "pytorch_model.bin"
            checkpoint_loader = smoke._torch_loader(lambda *a, **k: "synthetic", allowed, loads)
            self.assertEqual(checkpoint_loader(allowed, map_location="cpu"), "synthetic")
            with self.assertRaises(ValueError):
                checkpoint_loader(path / "unexpected.bin")

    def test_cpu_and_multiple_visible_gpus_rejected(self):
        selected = []
        fake = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True, device_count=lambda: 2,
                                                    set_device=selected.append))
        for device in ("cuda:0", "cpu", "cuda:1"):
            with self.assertRaises(ValueError):
                smoke._device(fake, device)
        fake.cuda.device_count = lambda: 1
        self.assertEqual(smoke._device(fake, "cuda"), "cuda:0")
        self.assertEqual(selected, [0])

    def test_factory_keeps_repo_branch_original_8bit_and_all_clip_loaders(self):
        # Simulated loader calls verify wiring only; this is not model execution.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshots = {role: root / role for role in smoke.MODEL_SPECS}
            for path in snapshots.values():
                path.mkdir()
            constructor_calls = []
            def loader_class():
                class Loader:
                    @classmethod
                    def from_pretrained(cls, source, **kwargs):
                        return SimpleNamespace()
                return Loader
            builder = SimpleNamespace(AutoTokenizer=loader_class(), LlavaMistralForCausalLM=loader_class())
            clip = SimpleNamespace(CLIPVisionConfig=loader_class(), CLIPImageProcessor=loader_class(),
                                   CLIPVisionModel=loader_class())
            fake_torch = SimpleNamespace(bfloat16="bf16", load=lambda *a, **k: {},
                cuda=SimpleNamespace(is_available=lambda: True, device_count=lambda: 1, set_device=lambda index: None))
            fake_transformers = SimpleNamespace(__version__=smoke.TRANSFORMERS_VERSION)
            class FakeTool:
                def __init__(self, **kwargs):
                    constructor_calls.append(kwargs)
                    source = kwargs["model_path"]
                    builder.AutoTokenizer.from_pretrained(source)
                    builder.LlavaMistralForCausalLM.from_pretrained(source)
                    clip_id = smoke.MODEL_SPECS["clip"]["repo_id"]
                    clip.CLIPVisionConfig.from_pretrained(clip_id)
                    clip.CLIPImageProcessor.from_pretrained(clip_id)
                    clip.CLIPVisionModel.from_pretrained(clip_id)
                    fake_torch.load(snapshots["clip"] / "pytorch_model.bin")
                    self.name, self.description, self.context_len = "llava_med_qa", "synthetic", 2048
                    self.args_schema = SimpleNamespace(model_json_schema=lambda: {"synthetic": True})
                    self.model = SimpleNamespace(device="cuda:0", dtype="bf16", is_loaded_in_8bit=True,
                        is_loaded_in_4bit=False, get_vision_tower=lambda: SimpleNamespace(
                            is_loaded=True, dtype="bf16", device="cuda:0"))
            def inspect(cache, spec):
                role = next(key for key, val in smoke.MODEL_SPECS.items() if val is spec)
                return snapshots[role], {"repo_id": spec["repo_id"]}, {}
            original_import = smoke.importlib.import_module
            def import_module(name, *args):
                if name == "medrax.llava.model.builder": return builder
                if name == "medrax.llava.model.multimodal_encoder.clip_encoder": return clip
                return original_import(name, *args)
            with ExitStack() as stack:
                stack.enter_context(patch.dict(sys.modules, {"torch": fake_torch, "transformers": fake_transformers}))
                stack.enter_context(patch.object(smoke, "source_provenance", return_value={"synthetic": True}))
                stack.enter_context(patch.object(smoke, "inspect_snapshot", side_effect=inspect))
                stack.enter_context(patch.object(smoke, "_module", return_value=SimpleNamespace(LlavaMedTool=FakeTool)))
                stack.enter_context(patch.object(smoke.importlib, "import_module", side_effect=import_module))
                stack.enter_context(patch.object(smoke, "environment", return_value={"synthetic": True}))
                tool, provenance = smoke.create_llava_tool(root, cache_dir=root)
            self.assertEqual(tool.name, "llava_med_qa")
            params = constructor_calls[0]
            self.assertEqual(params["model_path"], smoke.MODEL_SPECS["llava"]["repo_id"])
            self.assertEqual((params["load_in_8bit"], params["load_in_4bit"]), (True, False))
            self.assertEqual(params["torch_dtype"], "bf16")
            self.assertEqual(len(provenance["asset_loads"]), 6)
            self.assertFalse(provenance["factory_did_inference"])
            self.assertEqual(provenance["changed_fields"], [])
            self.assertNotIn(directory, json.dumps(provenance))


class OutputTests(unittest.TestCase):
    def test_result_logs_only_status_hash_length_even_with_private_metadata(self):
        answer = "SYNTHETIC NONMEDICAL ANSWER"
        result = (answer, {"analysis_status": "completed", "image_path": "/private/patient.png",
                           "question": "PRIVATE QUESTION", "untrusted": "anything"})
        safe = smoke.validate_observation(result)
        self.assertTrue(safe["valid"])
        self.assertEqual(safe["clinical_evidence"], "unknown")
        self.assertFalse(safe["clinical_correctness_evaluated"])
        dumped = json.dumps(safe)
        for private in (answer, "PRIVATE QUESTION", "patient.png", "untrusted"):
            self.assertNotIn(private, dumped)
        for bad in [(answer, {"analysis_status": "failed"}), ("", {"analysis_status": "completed"}),
                    (None, {"analysis_status": "completed"}), ("a\x00b", {"analysis_status": "completed"}),
                    (answer, {"analysis_status": "/private/path"}), [answer]]:
            self.assertFalse(smoke.validate_observation(bad)["valid"])

    def test_generation_keeps_original_args_and_reports_only_termination_flags(self):
        config = SimpleNamespace(eos_token_id=2, pad_token_id=0, num_beams=1)
        observations, calls = [], []
        result = Tensor([[7, 8, 2]])
        def original(*args, **kwargs):
            calls.append(kwargs)
            return result
        wrapper = smoke.generation_recorder(original, SimpleNamespace(generation_config=config), observations)
        image = SimpleNamespace(shape=(1, 3, 336, 336))
        self.assertIs(wrapper(Tensor([[11, 12]]), images=image, **smoke.GENERATION_ARGS), result)
        self.assertEqual(calls[0], {"images": image, **smoke.GENERATION_ARGS})
        self.assertTrue(observations[0]["eos_present"])
        self.assertTrue(observations[0]["last_token_is_eos"])
        self.assertFalse(observations[0]["returned_sequence_length_at_least_max_new_tokens"])
        self.assertNotIn("[7, 8, 2]", json.dumps(observations))
        with self.assertRaises(ValueError):
            wrapper(Tensor([[1]]), images=image, **{**smoke.GENERATION_ARGS, "max_new_tokens": 501})
        self.assertEqual(len(calls), 1)

    def test_generation_limit_and_failure_never_imply_medical_completeness(self):
        config = SimpleNamespace(eos_token_id=[2, 3], pad_token_id=None, num_beams=1)
        model, image = SimpleNamespace(generation_config=config), SimpleNamespace(shape=(1, 3, 336, 336))
        observations = []
        wrapper = smoke.generation_recorder(lambda *a, **k: Tensor([[7] * 500]), model, observations)
        wrapper(Tensor([[1]]), images=image, **smoke.GENERATION_ARGS)
        self.assertFalse(observations[0]["eos_present"])
        self.assertTrue(observations[0]["returned_sequence_length_at_least_max_new_tokens"])
        self.assertTrue(observations[0]["length_flag_is_not_semantic_completeness"])
        def broken(*args, **kwargs):
            raise RuntimeError("PRIVATE ERROR DETAILS")
        wrapper = smoke.generation_recorder(broken, model, observations)
        with self.assertRaises(RuntimeError):
            wrapper(Tensor([[1]]), images=image, **smoke.GENERATION_ARGS)
        self.assertEqual(observations[-1]["status"], "failed")
        self.assertNotIn("PRIVATE ERROR DETAILS", json.dumps(observations))

    def test_failing_cli_nonzero_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            args = ["--repo", directory, "--cache-dir", directory, "--image", str(Path(directory) / "absent.png"),
                    "--question", "PRIVATE QUESTION", "--output", str(output)]
            self.assertEqual(smoke.main(args), 1)
            raw = (output / "summary.json").read_bytes()
            self.assertEqual(smoke.main(args), 2)
            self.assertEqual(raw, (output / "summary.json").read_bytes())
            self.assertNotIn(directory, raw.decode())
            self.assertNotIn("PRIVATE QUESTION", raw.decode())

    def test_import_does_not_import_heavy_libraries(self):
        code = "import sys; import llava_smoke; assert not any(x in sys.modules for x in ('torch','transformers','PIL','numpy'))"
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=Path(smoke.__file__).parent,
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
