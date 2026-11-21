import json
from pathlib import Path
import tempfile
import unittest
from audit_protocol import audit, classify, final_only, message_from_response

ACTION = '{"calls":[{"tool":"chest_xray_expert","args":{"question":"Describe side"}}],"reason":"Locate"}'
FINAL = '{"answer":"A","reason":"Evidence"}'

class AuditTests(unittest.TestCase):
    def test_valid_call(self):
        self.assertEqual(classify(ACTION)["lexical_class"], "whole_json_calls")
    def test_valid_answer(self):
        self.assertEqual(classify(FINAL)["lexical_class"], "whole_json_answer")
    def test_prose_then_call(self):
        self.assertEqual(classify("Please inspect.\n" + ACTION)["lexical_class"], "mixed_text_one_calls")
    def test_fence(self):
        self.assertEqual(classify("```json\n" + ACTION + "\n```")["lexical_class"], "mixed_text_one_calls")
    def test_ambiguous_objects(self):
        self.assertEqual(classify(ACTION + "\n" + FINAL)["lexical_class"], "mixed_text_multiple_action_candidates")
    def test_both_modes(self):
        self.assertEqual(classify('{"calls":[],"answer":"A"}')["lexical_class"], "whole_json_ambiguous")
    def test_extra_call_field(self):
        obj=json.loads(ACTION);obj["calls"][0]["reason"]="wrong level"
        self.assertEqual(classify(json.dumps(obj))["lexical_class"], "whole_json_calls_bad_shape")
    def test_duplicate_key_not_whole(self):
        self.assertFalse(classify('{"answer":"A","answer":"B","reason":"x"}')["whole_json"])
    def test_non_json(self):
        self.assertEqual(classify("I think so")["lexical_class"], "non_json_without_clear_action")
    def test_envelope(self):
        msg,finish=message_from_response({"choices":[{"message":{"content":ACTION},"finish_reason":"stop"}]})
        self.assertEqual(msg["content"],ACTION);self.assertEqual(finish,"stop")
    def test_forced_final_request(self):
        self.assertTrue(final_only({"messages":[{"role":"user","content":'Your previous response was invalid. Return answer and reason. No tools.'}]}))
        self.assertFalse(final_only({"messages":[{"role":"user","content":'Use tools or answer/reason.'}]}))
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"run";out=Path(temp)/"audit"
            for arm in ("B0","L1"):
                for n,text in ((1,ACTION if arm=="B0" else "Commentary\n"+ACTION),(2,FINAL)):
                    d=root/arm/"services/calls/R49-AGENT/q1"/str(n);d.mkdir(parents=True)
                    (d/"response.json").write_text(json.dumps({"choices":[{"message":{"content":text},"finish_reason":"stop"}]}))
                    request='Your previous response was invalid. Return answer and reason. No tools.' if arm=="L1" and n==2 else 'Use tools or answer.'
                    (d/"request.json").write_text(json.dumps({"messages":[{"role":"user","content":request}]}))
            result=audit(root,out,["B0","L1"])
            self.assertEqual(result["coverage"]["L1"]["calls_candidate_then_final_only_flags"],1)
            self.assertEqual(result["coverage"]["B0"]["calls_candidate_then_final_only_flags"],0)
            self.assertEqual(result["model_calls_made_by_this_script"],0)
            self.assertTrue((out/"response_audit.csv").is_file())
            with self.assertRaises(ValueError): audit(root,out,["B0","L1"])

if __name__ == '__main__':unittest.main()
