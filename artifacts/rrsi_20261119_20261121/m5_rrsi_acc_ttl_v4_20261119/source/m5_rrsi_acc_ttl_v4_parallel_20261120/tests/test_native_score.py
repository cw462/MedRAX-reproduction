"""Contract checks for the preserved R55 explicit-answer metric."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "integration/native_score.py"
spec = importlib.util.spec_from_file_location("native_score", path)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class NativeScoreTest(unittest.TestCase):
    def record(self, raw, reference="A", options=None):
        return {"id": "example", "dataset": "contract_fixture",
                "answer": "deliberately different strict field", "terminal_raw": raw,
                "options": options if options is not None else [{"label": "A", "text": "one"}, {"label": "B", "text": "two"}],
                "reference": reference}

    def test_terminal_response_is_authoritative(self):
        self.assertEqual(native.score(self.record('{"answer":"A","reason":"fixture"}'))["correct"], 1)

    def test_invalid_choice_is_in_denominator_and_incorrect(self):
        self.assertEqual(native.score(self.record('{"answer":"C"}'))["correct"], 0)

    def test_conflicting_fields_are_incorrect(self):
        self.assertEqual(native.score(self.record('{"answer":"A","answer":"B"}'))["correct"], 0)

    def test_open_answer_uses_native_normalization(self):
        self.assertEqual(native.score(self.record('{"answer":"[INST] One. [/INST]"}', "one", []))["correct"], 1)

    def test_missing_raw_is_not_regraded_from_answer(self):
        with self.assertRaises(ValueError): native.score(self.record(None))

    def test_reason_is_not_an_answer(self):
        self.assertEqual(native.score(self.record('{"reason":"A"}'))["correct"], 0)

    def test_native_feedback_annotation_preserves_answer_text(self):
        reference = {"answer": "A", "answer_text": "one"}
        self.assertEqual(native.score(self.record('{"answer":"A"}', reference))["correct"], 1)
        self.assertEqual(reference, {"answer": "A", "answer_text": "one"})


if __name__ == "__main__": unittest.main()
