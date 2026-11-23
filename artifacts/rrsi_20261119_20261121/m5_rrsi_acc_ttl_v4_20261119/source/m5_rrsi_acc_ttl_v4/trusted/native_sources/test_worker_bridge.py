"""Synthetic IPC/GPU-lock boundary tests, never real model execution."""
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import worker_bridge as bridge


FAKE_WORKER = r'''
import argparse,sys,json,time,os
sys.path.insert(0,EXPERIMENTS)
import worker_bridge as b
p=argparse.ArgumentParser();p.add_argument('--config');p.add_argument('--config-sha256');p.add_argument('--describe',action='store_true');a=p.parse_args()
c=b.parse_json(open(a.config,encoding='utf-8').read()); kind=c['spec']['kind']; name=b.KINDS[kind]
descriptor={'name':name,'description':'SYNTHETIC IPC FIXTURE, NOT A MEDICAL TOOL','parameters':{'title':'SyntheticInput','type':'object','properties':{}},'return_direct':False,'model_loaded':False}
descriptor['schema_sha256']=b.digest(descriptor['parameters'])
descriptor['source']={'worker_script_sha256':c['worker_script_sha256']}
def send(x): print(json.dumps(x,allow_nan=False),flush=True)
send({'protocol':1,'event':'ready','tool_name':name,'descriptor':descriptor,'worker_script_sha256':c['worker_script_sha256'],'cases_sha256':c['cases_sha256']})
if a.describe: sys.exit(0)
for line in sys.stdin:
 r=json.loads(line)
 if r.get('op')=='shutdown': sys.exit(0)
 text=r['params'].get('question',r['params'].get('phrase',r['params'].get('prompt')))
 if text=='die': sys.exit(9)
 if text=='sleep': time.sleep(60)
 if text=='malformed': print('NOT JSON',flush=True); continue
 if text=='serialize':
  send({'protocol':1,'event':'error','error_type':'TypeError','request_id':r['request_id'],'tool_name':name,'params_sha256':r['params_sha256']}); continue
 result=({'synthetic':'PRIVATE_FAKE_RESULT','echo':r['params']},{'analysis_status':'completed','tuple_size':(3,4)})
 if text=='original_failure': result=({'error':'SYNTHETIC_ERROR'},{'analysis_status':'failed'})
 tree=b.encode_value(result)
 send({'protocol':1,'event':'result','request_id':'wrong' if text=='wrong-id' else r['request_id'],'tool_name':name,'params_sha256':r['params_sha256'],'result_tree':tree,'result_sha256':b.digest(tree),'audit':{'synthetic_only':True,'pid':os.getpid()}})
'''


class CodecTests(unittest.TestCase):
    def test_roundtrip_preserves_tuple_list_order_and_sentinel_keys(self):
        raw = ({"z": [1, 2.0, True, None], "type": "tuple", "a": ("text", {"v": "payload"})},
               {"analysis_status": "completed", "original_size": (20, 10)})
        tree = bridge.encode_value(raw)
        decoded = bridge.decode_value(bridge.parse_json(json.dumps(tree)))
        self.assertEqual(decoded, raw)
        self.assertEqual(str(decoded), str(raw))
        self.assertIs(type(decoded), tuple)
        self.assertIs(type(decoded[0]["z"][1]), float)
        self.assertEqual(list(decoded[0]), ["z", "type", "a"])

    def test_nonfinite_duplicate_keys_unknown_types_and_ambiguous_scalars_rejected(self):
        for value in (float("nan"), float("inf"), object(), {1: "bad"}):
            with self.assertRaises(ValueError): bridge.encode_value(value)
        for tree in (["int", True], ["tuple", "bad"], ["unknown", 1], ["dict", [["a", ["int", 1]], ["a", ["int", 2]]]]):
            with self.assertRaises(ValueError): bridge.decode_value(tree)
        for raw in ('{"a":1,"a":2}', '{"a":NaN}'):
            with self.assertRaises(ValueError): bridge.parse_json(raw)


class BoundaryTests(unittest.TestCase):
    def test_image_hash_current_case_extra_fields_and_control_tags_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            first, other = Path(directory) / "first.png", Path(directory) / "other.png"
            first.write_bytes(b"SYNTHETIC_A"); other.write_bytes(b"SYNTHETIC_B")
            allowed = {str(first.resolve()): bridge.file_digest(first)}
            good = {"image_path": str(first), "question": "SYNTHETIC ordinary question"}
            cleaned, paths = bridge.validate_request("llava", good, allowed)
            self.assertEqual(paths, [str(first.resolve())])
            for bad in (dict(good, gold="X"), dict(good, image_path=str(other)), dict(good, question="<|img|>/private/file<|/img|>")):
                with self.assertRaises(ValueError): bridge.validate_request("llava", bad, allowed)
            first.write_bytes(b"SYNTHETIC_CHANGED")
            with self.assertRaises(ValueError): bridge.validate_request("llava", good, allowed)

    def test_token_caps_and_initial_single_image_chexagent_limit_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "x.png"; image.write_bytes(b"SYNTHETIC")
            allowed = {str(image.resolve()): bridge.file_digest(image)}
            for params in ({"image_path": str(image), "phrase": "synthetic", "max_new_tokens": True},
                           {"image_path": str(image), "phrase": "synthetic", "max_new_tokens": 301},
                           {"image_path": str(image), "phrase": "synthetic", "max_new_tokens": 200}):
                with self.assertRaises(ValueError): bridge.validate_request("maira", params, allowed)
            with self.assertRaises(ValueError):
                bridge.validate_request("chexagent", {"image_paths": [str(image), str(image)], "prompt": "synthetic"}, allowed)

    def test_child_environment_does_not_inherit_credentials(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "SYNTHETIC_SECRET", "HF_TOKEN": "SYNTHETIC_SECRET", "OTHER_PASSWORD": "SYNTHETIC_SECRET"}):
            env = bridge._child_environment("1")
        self.assertFalse(any(key in env for key in ("OPENAI_API_KEY", "HF_TOKEN", "OTHER_PASSWORD")))
        self.assertEqual(env["CUDA_VISIBLE_DEVICES"], "1")
        self.assertEqual(env["HF_HUB_OFFLINE"], "1")


class PoolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.worker = self.root / "fake_worker.py"
        self.worker.write_text(FAKE_WORKER.replace("EXPERIMENTS", repr(str(Path(bridge.__file__).parent))), encoding="utf-8")
        self.image = self.root / "synthetic.png"; self.image.write_bytes(b"SYNTHETIC_NONIMAGE_FIXTURE")
        self.cases = {"case_a": {str(self.image.resolve()): bridge.file_digest(self.image)}}
        self.specs = [bridge.WorkerSpec(kind, sys.executable, str(self.root), cache_dir=str(self.root)) for kind in ("llava", "maira")]
        self.pool = bridge.WorkerPool(self.specs, cases=self.cases, run_root=self.root / "run", gpu_lock=self.root / "gpu.lock",
                                      worker_script=self.worker, timeout=3, startup_timeout=3)
        self.pool.set_case("case_a")

    def tearDown(self):
        self.pool.close(); self.temp.cleanup()

    def request(self, text, name="llava_med_qa", **kwargs):
        key = "question" if name == "llava_med_qa" else "phrase"
        return self.pool.invoke(name, {"image_path": str(self.image), key: text}, **kwargs)

    def test_describe_is_metadata_only_and_result_is_not_summarized_for_agent(self):
        desc = self.pool.describe("llava_med_qa")
        self.assertFalse(desc["model_loaded"])
        self.assertIsNone(self.pool.active)
        result, audit = self.request("synthetic")
        self.assertEqual(result[0]["synthetic"], "PRIVATE_FAKE_RESULT")
        self.assertIs(type(result), tuple)
        self.assertEqual(result[1]["tuple_size"], (3, 4))
        self.assertNotIn("PRIVATE_FAKE_RESULT", json.dumps(audit))
        self.assertEqual(audit["clinical_evidence"], "unknown")
        failed, _ = self.request("original_failure")
        self.assertEqual(failed, ({"error": "SYNTHETIC_ERROR"}, {"analysis_status": "failed"}))

    def test_switch_waits_for_previous_pid_exit_and_same_model_reuses_process(self):
        _, first = self.request("synthetic")
        old = self.pool.active.process
        _, second = self.request("synthetic again")
        self.assertEqual(first["worker_audit"]["pid"], second["worker_audit"]["pid"])
        _, third = self.request("synthetic", name="xray_phrase_grounding")
        self.assertIsNotNone(old.poll())
        self.assertNotEqual(old.pid, third["worker_audit"]["pid"])
        self.assertTrue(self.pool.lifecycle[-1]["exited_before_replacement"])

    def test_timeout_child_death_bad_json_and_mismatched_identity_are_errors(self):
        expected = {"sleep": "timeout", "die": "child_death", "malformed": "invalid_json_transport",
                    "wrong-id": "response_identity_mismatch", "serialize": "worker_execution_error"}
        self.pool.timeout = 0.2
        for text, category in expected.items():
            with self.subTest(text=text):
                with self.assertRaises(bridge.WorkerFailure) as error: self.request(text)
                self.assertEqual(error.exception.category, category)
                self.assertIsNone(self.pool.active)
        failures = list((self.root / "run").glob("failure_*.private.json"))
        self.assertEqual(len(failures), len(expected))
        self.assertTrue(all(not json.loads(path.read_text())["automatically_retried"] for path in failures))

    def test_duplicate_request_is_never_replayed_and_case_switch_during_call_rejected(self):
        self.request("synthetic", request_id="fixed-request")
        with self.assertRaises(bridge.WorkerFailure) as error:
            self.request("synthetic", request_id="fixed-request")
        self.assertEqual(error.exception.category, "duplicate_request_id")
        self.pool.busy.acquire()
        try:
            with self.assertRaises(bridge.WorkerFailure): self.pool.set_case("case_a")
        finally: self.pool.busy.release()

    def test_gpu_slot_lock_enforced_but_source_hash_changes_do_not_block(self):
        lock = bridge._GpuLock(self.root / "gpu.lock")
        with self.assertRaises(bridge.WorkerFailure): lock.acquire()
        old = self.pool.describe("llava_med_qa")["source"]["worker_script_sha256"]
        self.worker.write_text(self.worker.read_text() + "\n# CHANGED\n")
        result, _ = self.request("synthetic")
        self.assertEqual(result[0]["synthetic"], "PRIVATE_FAKE_RESULT")
        actual = self.pool.descriptors["llava_med_qa"]["source"]["worker_script_sha256"]
        self.assertNotEqual(old, actual)
        self.assertEqual(actual, bridge.file_digest(self.worker))

    def test_changed_tool_capabilities_still_require_a_new_binding(self):
        self.pool.describe("llava_med_qa")
        self.worker.write_text(self.worker.read_text().replace(
            "SYNTHETIC IPC FIXTURE, NOT A MEDICAL TOOL", "CHANGED TOOL DESCRIPTION"))
        with self.assertRaises(bridge.WorkerFailure) as error:
            self.request("synthetic")
        self.assertEqual(error.exception.category, "official_capabilities_changed")

    def test_policy_snapshot_records_restrictions_without_private_paths(self):
        policy = self.pool.policy_snapshot()
        self.assertTrue(policy["execution_policy_stricter_than_original_schema"])
        self.assertTrue(policy["chexagent"]["single_image_only"])
        self.assertEqual(policy["maira"]["max_new_tokens_exact"], 300)
        self.assertTrue(policy["llava"]["explicit_image_required"])
        self.assertNotIn(str(self.root), json.dumps(policy))


class ProxyTests(unittest.TestCase):
    def test_proxy_signature_matches_and_raw_extra_bool_arguments_are_not_coerced(self):
        from typing import Optional
        from pydantic import BaseModel, Field
        class OfficialSyntheticInput(BaseModel):
            """SYNTHETIC schema fixture."""
            image_path: str = Field(..., description="Synthetic image")
            phrase: str = Field(..., description="Synthetic phrase")
            max_new_tokens: int = Field(300, description="Synthetic limit")
        schema = OfficialSyntheticInput.model_json_schema()
        descriptor = {"name": "xray_phrase_grounding", "description": "SYNTHETIC official description",
                      "parameters": schema, "schema_sha256": bridge.digest(schema), "return_direct": False}
        calls = []
        class Pool:
            def describe(self, name): return deepcopy(descriptor)
            def invoke(self, name, params):
                calls.append(deepcopy(params))
                if set(params) - {"image_path", "phrase", "max_new_tokens"} or type(params.get("max_new_tokens", 300)) is not int:
                    raise bridge.WorkerFailure("raw_validation_failed")
                return ("SYNTHETIC", {"analysis_status": "completed"}), {"synthetic": True}
        tool = bridge.make_proxy(Pool(), descriptor["name"])
        self.assertEqual(tool.description, descriptor["description"])
        self.assertEqual(bridge.digest(tool.args_schema.model_json_schema()), descriptor["schema_sha256"])
        good = {"image_path": "synthetic.png", "phrase": "synthetic"}
        self.assertEqual(tool.invoke(good), ("SYNTHETIC", {"analysis_status": "completed"}))
        self.assertEqual(tool.last_worker_audit, {"synthetic": True})
        for bad in (dict(good, reference_answer="X"), dict(good, max_new_tokens=True)):
            with self.assertRaises(bridge.WorkerFailure): tool.invoke(bad)
            self.assertIsNone(tool.last_worker_audit)
        self.assertIn("reference_answer", calls[-2])
        self.assertIs(calls[-1]["max_new_tokens"], True)
        tool.invoke(good)
        with self.assertRaises(bridge.WorkerFailure): tool.invoke("invalid raw input")
        self.assertIsNone(tool.last_worker_audit)


class WorkerEntrypointTests(unittest.TestCase):
    def run_worker(self, mutation=None, config_mutation=None):
        import medical_tool_worker as worker
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "synthetic.png"; image.write_bytes(b"SYNTHETIC_IMAGE_BYTES")
            cases = {"current": {str(image.resolve()): bridge.file_digest(image)}}
            config = {"protocol": 1, "spec": {"kind": "llava", "python": sys.executable,
                      "repo": str(root), "cache_dir": str(root)}, "cases": cases,
                      "cases_sha256": bridge.digest(cases), "private_root": str(root),
                      "worker_script_sha256": bridge.file_digest(worker.__file__),
                      "bridge_sha256": bridge.file_digest(bridge.__file__)}
            if config_mutation is not None: config_mutation(config)
            path = root / "config.private.json"; bridge.write_private(path, config)
            params = {"image_path": str(image), "question": "SYNTHETIC"}
            request = {"protocol": 1, "op": "invoke", "request_id": "synthetic-request", "case_id": "current",
                       "tool_name": "llava_med_qa", "params": params, "params_sha256": bridge.digest(params),
                       "case_images_sha256": bridge.digest(cases["current"])}
            if mutation is not None: mutation(request)
            input_bytes = (json.dumps(request) + '\n' + json.dumps({"protocol": 1, "op": "shutdown"}) + '\n').encode()
            input_stream = io.TextIOWrapper(io.BytesIO(input_bytes), encoding="utf-8")
            output_buffer = io.BytesIO(); output_stream = io.TextIOWrapper(output_buffer, encoding="utf-8")
            error_stream = io.StringIO()
            schema = {"type": "object", "properties": {}}
            descriptor = {"name": "llava_med_qa", "description": "SYNTHETIC", "parameters": schema,
                          "schema_sha256": bridge.digest(schema)}
            calls = []
            original = ({"error": "SYNTHETIC_TOOL_FAILURE"}, {"analysis_status": "failed", "tuple": (2, 3)})
            def invoke(*args, **kwargs):
                calls.append(1)
                return original, {"synthetic_only": True}, object(), {}
            with patch.object(sys, "stdin", input_stream), patch.object(sys, "stdout", output_stream), \
                    patch.object(sys, "stderr", error_stream), patch.object(worker, "describe", return_value=descriptor), \
                    patch.object(worker, "invoke_real", side_effect=invoke):
                code = worker.main(["--config", str(path), "--config-sha256", bridge.file_digest(path)])
            output_stream.flush()
            events = [bridge.parse_json(line) for line in output_buffer.getvalue().splitlines()]
            return code, events, calls, original

    def test_real_worker_entrypoint_keeps_failed_original_return_and_protocol_clean(self):
        code, events, calls, original = self.run_worker()
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual([event["event"] for event in events], ["ready", "result"])
        self.assertEqual(bridge.decode_value(events[1]["result_tree"]), original)

    def test_worker_config_source_hashes_are_records_without_version_locks(self):
        def changed(config):
            config.update(worker_script_sha256="0" * 64, bridge_sha256="1" * 64)
        code, events, calls, original = self.run_worker(config_mutation=changed)
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(bridge.decode_value(events[1]["result_tree"]), original)

    def test_worker_checks_case_and_parameter_digest_before_invoking(self):
        for mutation in (lambda value: value.update(case_id="other"),
                         lambda value: value["params"].update(gold="X"),
                         lambda value: value.update(case_images_sha256="0" * 64)):
            code, events, calls, _ = self.run_worker(mutation)
            self.assertEqual(code, 1)
            self.assertEqual(calls, [])
            self.assertEqual(events[-1]["event"], "error")
            self.assertNotIn("Traceback", json.dumps(events))


if __name__ == "__main__":
    unittest.main()
