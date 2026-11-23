import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from m5rrsi import llm
from m5rrsi.io import ProtocolError

class Response:
    def __init__(self, payload): self.raw=json.dumps(payload).encode()
    def __enter__(self): return self
    def __exit__(self,*x): pass
    def read(self,*x): return self.raw

class ClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        llm.configure({"api_key_env":"TEST_M5_KEY","base_url_env":"TEST_M5_URL","model":"qwen-test",
                        "max_tokens":100,"retries":1},Path(self.tmp.name)/"log.jsonl")
        self.env=patch.dict(os.environ,{"TEST_M5_KEY":"not-a-real-key","TEST_M5_URL":"https://example.invalid/v1"}); self.env.start()
    def tearDown(self): self.env.stop(); self.tmp.cleanup()
    def response(self,usage=True):
        p={"model":"qwen-test","choices":[{"message":{"content":'{"action":"done"}'},"finish_reason":"stop"}]}
        if usage:p["usage"]={"total_tokens":10}
        return Response(p)
    def test_compatible_json_call_and_usage(self):
        with patch("urllib.request.urlopen",return_value=self.response()) as m:
            self.assertEqual(json.loads(llm.generate("hello",json_only=True)),{"action":"done"})
            req=m.call_args.args[0]; body=json.loads(req.data)
            self.assertEqual(body["model"],"qwen-test"); self.assertEqual(body["max_tokens"],100)
    def test_missing_usage_stops(self):
        with patch("urllib.request.urlopen",return_value=self.response(False)):
            with self.assertRaises(ProtocolError): llm.generate("hello")
    def test_no_silent_model_fallback(self):
        with self.assertRaises(ProtocolError): llm.generate("hello",model="different")
    def test_cached_prefix_preserved(self):
        with patch("urllib.request.urlopen",return_value=self.response()) as m:
            llm.generate("question",cache_prefix="source")
            self.assertEqual(json.loads(m.call_args.args[0].data)["messages"][1]["content"],"source\n\nquestion")
