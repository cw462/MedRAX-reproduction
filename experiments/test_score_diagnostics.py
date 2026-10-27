"""Independent synthetic scoring oracles; no real labels, models, or network."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_diagnostics as scoring


def inputs(count=4, letters="ABCDEF"):
    question = "QUESTION_SENTINEL_NOT_FOR_REPORT\n" + "\n".join(f"{letter}) option {number}" for number, letter in enumerate(letters))
    return [{"question_id": f"q{number}", "question": question, "images": [f"image_{number}.png"]}
            for number in range(1, count+1)]


def labels(count=4):
    return [{"question_id": f"q{number}", "answer": "ABCDEF"[(number-1) % 6]} for number in range(1, count+1)]


def terminal(qid, arm, letter=None, status="completed", **extra):
    return {"record_type": "terminal", "question_id": qid, "arm": arm, "status": status,
            "answer_letter": letter, **extra}


class ScoringTests(unittest.TestCase):
    def score(self, rows, *, planned=None, key=None, cases=None):
        planned = inputs() if planned is None else planned
        key = labels(len(planned)) if key is None else key
        cases = {row["question_id"]: row["question_id"] for row in planned} if cases is None else cases
        return scoring.score_diagnostics(planned, rows, key, cases, resamples=1000)

    def test_fixed_denominator_includes_invalid_error_unrun_and_started_is_ignored(self):
        rows = [
            {"record_type": "started", "question_id": "q2", "arm": "direct"},
            {"record_type": "started", "question_id": "q4", "arm": "direct"},
            terminal("q1", "direct", "A"), terminal("q1", "agent", "B"),
            terminal("q2", "direct", "A or B"), terminal("q2", "agent", "B"),
            terminal("q3", "direct", "C", "model_error"), terminal("q4", "agent", "D"),
        ]
        report = self.score(rows)
        direct, agent = report["arms"]["direct"], report["arms"]["agent"]
        self.assertEqual(direct["planned_denominator"], 4)
        self.assertEqual(direct["accuracy"], 0.25)
        self.assertEqual(agent["accuracy"], 0.5)
        self.assertEqual(direct["counts"], {"correct": 1, "incorrect_answer": 0, "invalid": 1, "unrun": 1, "error": 1})
        self.assertEqual(agent["counts"], {"correct": 2, "incorrect_answer": 1, "invalid": 0, "unrun": 1, "error": 0})
        self.assertEqual(direct["started_without_terminal_question_ids"], ["q4"])
        self.assertEqual(report["paired"]["counts"], {"improved": 2, "worsened": 1, "same": 1, "both_correct": 0, "both_not_correct": 1})
        self.assertEqual(report["paired"]["accuracy_difference_agent_minus_direct"], 0.25)
        self.assertEqual(report["paired"]["qid_indices"]["improved"], ["q2", "q4"])

    def test_duplicate_terminals_are_rejected_including_arm_aliases(self):
        with self.assertRaises(ValueError):
            self.score([terminal("q1", "B0", "A"), terminal("q1", "direct", "A")])
        report = self.score([terminal("q1", "B0", "A"), terminal("q1", "R0", "A")])
        self.assertEqual(report["arms"]["direct"]["correct"], 1)
        self.assertEqual(report["arms"]["agent"]["correct"], 1)

    def test_unknown_question_arm_or_record_type_does_not_change_denominator(self):
        bad = [terminal("outside-plan", "direct", "A"), terminal("q1", "other", "A"),
               dict(terminal("q1", "direct", "A"), record_type="unexpected")]
        for row in bad:
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.score([row])

    def test_choice_membership_and_strict_letter_parser(self):
        planned = inputs(1, letters="ABCDE")
        for answer in ("F", "The answer is A", "A, B", "a", None, ["A"]):
            with self.subTest(answer=answer):
                result = self.score([terminal("q1", "direct", answer)], planned=planned)
                self.assertEqual(result["arms"]["direct"]["counts"]["invalid"], 1)
        result = self.score([terminal("q1", "direct", " A. \n")], planned=planned)
        self.assertEqual(result["arms"]["direct"]["correct"], 1)

    def test_failed_or_invalid_terminal_cannot_receive_credit_for_a_letter(self):
        for status, expected in (("interrupted_no_retry", "error"), ("case_budget_exceeded", "error"),
                                 ("invalid_answer", "invalid"), ("not_run_budget", "unrun")):
            report = self.score([terminal("q1", "direct", "A", status)], planned=inputs(1))
            self.assertEqual(report["arms"]["direct"]["correct"], 0)
            self.assertEqual(report["arms"]["direct"]["counts"][expected], 1)

    def test_missing_duplicate_or_out_of_choices_labels_fail_closed(self):
        for key in (labels()[:-1], labels()+[labels()[0]], [{"question_id": "q1", "answer": "Narrative A"}]+labels()[1:]):
            with self.assertRaises(ValueError):
                self.score([], key=key)
        with self.assertRaises(ValueError):
            self.score([], planned=inputs(1, "ABCDE"), key=[{"question_id": "q1", "answer": "F"}])
        with self.assertRaises(ValueError):
            self.score([], planned=inputs()+[inputs()[0]])
        with self.assertRaises(ValueError):
            self.score([], cases={"q1": "one-case"})

    def test_no_question_answer_response_or_freeform_error_text_in_report(self):
        row = terminal("q1", "direct", "A", raw_response="RESPONSE_SECRET_SENTINEL", explanation="EXPLANATION_SECRET_SENTINEL",
                       issue_tags=["UNTRUSTED_FREEFORM_SENTINEL"], ledger_settlements=["LEDGER_RAW_SENTINEL"])
        report = self.score([row])
        rendered = json.dumps(report)
        for forbidden in ("QUESTION_SENTINEL_NOT_FOR_REPORT", "RESPONSE_SECRET_SENTINEL", "EXPLANATION_SECRET_SENTINEL",
                          "UNTRUSTED_FREEFORM_SENTINEL", "LEDGER_RAW_SENTINEL", '"answer"', '"answer_letter"', '"question"'):
            self.assertNotIn(forbidden, rendered)

    def test_partial_usage_is_observed_only_and_unknown_is_not_zero(self):
        rows = [terminal("q1", "direct", "A", observed_usage_sum={"input_tokens": 10, "output_tokens": 3, "total_tokens": 13},
                         usage_complete=True, actual_model_calls=1),
                terminal("q2", "direct", "B", observed_usage_sum={"input_tokens": 4, "output_tokens": None, "total_tokens": None},
                         usage_complete=False, actual_model_calls=1)]
        usage = self.score(rows)["arms"]["direct"]["usage"]
        self.assertEqual(usage["records_with_complete_usage"], 1)
        self.assertEqual(usage["records_with_partial_or_unknown_usage"], 1)
        self.assertEqual(usage["observed_sums"]["input_tokens"], 14)
        self.assertEqual(usage["observed_sums"]["total_tokens"], 13)
        self.assertIsNone(usage["observed_sums"]["actual_tool_attempts"])
        self.assertEqual(usage["records_reporting_each_count"]["total_tokens"], 1)
        for changes in ({"usage_complete": True, "observed_usage_sum": None},
                        {"observed_usage_sum": {"input_tokens": True}},
                        {"usage_complete": True, "observed_usage_sum": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 10}}):
            with self.assertRaises(ValueError):
                self.score([terminal("q1", "direct", "A", **changes)])
        partial = self.score([terminal("q1", "direct", "A", usage_complete=False,
                                      observed_usage_sum={"input_tokens": 15, "output_tokens": 3, "total_tokens": 8})])
        self.assertEqual(partial["arms"]["direct"]["usage"]["records_with_partial_or_unknown_usage"], 1)

    def test_cluster_resampling_keeps_whole_cases_and_pairs_together(self):
        differences = {f"plus{i}": 1 for i in range(10)} | {f"minus{i}": -1 for i in range(10)}
        cases = {qid: "positive-case" if value == 1 else "negative-case" for qid, value in differences.items()}
        result = scoring.paired_cluster_bootstrap(differences, cases, seed=7, resamples=1000)
        # Two case clusters: drawing both positive or both negative has 25% mass
        # at each endpoint. Question-level resampling would have a narrow interval.
        self.assertEqual(result["case_count"], 2)
        self.assertEqual((result["lower"], result["upper"]), (-1.0, 1.0))
        self.assertEqual(result["estimate_agent_minus_direct"], 0)
        self.assertEqual(result, scoring.paired_cluster_bootstrap(dict(reversed(list(differences.items()))), cases, seed=7, resamples=1000))

    def test_cluster_denominator_is_questions_not_number_of_cases(self):
        class AlternatingCases:
            def __init__(self, seed): self.next = 0
            def randrange(self, maximum):
                result = self.next
                self.next = 1-self.next
                return result
        # Force each bootstrap replicate to contain both full clusters once.
        with patch.object(scoring.random, "Random", AlternatingCases):
            result = scoring.paired_cluster_bootstrap({"a1": 1, "a2": 1, "b1": -1}, {"a1": "A", "a2": "A", "b1": "B"}, resamples=100)
        self.assertEqual(result["estimate_agent_minus_direct"], 1/3)
        self.assertEqual((result["lower"], result["upper"]), (1/3, 1/3))

    def test_single_case_is_marked_degenerate_and_invalid_resamples_rejected(self):
        result = scoring.paired_cluster_bootstrap({"a": 1, "b": -1}, {"a": "same", "b": "same"}, resamples=100)
        self.assertTrue(result["single_case_degenerate"])
        self.assertEqual((result["lower"], result["upper"]), (0, 0))
        for value in (1, 0, -1, True):
            with self.assertRaises(ValueError):
                scoring.paired_cluster_bootstrap({"q": 1}, {"q": "case"}, resamples=value)

    def test_cli_checks_frozen_plan_before_labels_and_never_mutates_sources(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            inference, result, key, audit, output = [root/name for name in ("inference.jsonl", "results.jsonl", "labels.jsonl", "audit.json", "score.json")]
            for path, rows in ((inference, inputs(1)), (result, [terminal("q1", "direct", "A")]), (key, labels(1))):
                path.write_text("".join(json.dumps(row)+"\n" for row in rows), encoding="utf-8")
            manifest = {"status": "complete", "inference_sha256": hashlib.sha256(inference.read_bytes()).hexdigest(),
                        "sample_count": 1, "distinct_case_count": 1,
                        "records": [{"question_id": "q1", "split": "memory_train", "case_hash": "a"*64}]}
            audit.write_text(json.dumps(manifest), encoding="utf-8")
            arguments = ["--results", str(result), "--labels", str(key), "--inference", str(inference),
                         "--audit-manifest", str(audit), "--output", str(output), "--bootstrap-resamples", "100"]
            originals = {path: path.read_bytes() for path in (inference, result, key, audit)}
            with redirect_stdout(io.StringIO()):
                self.assertEqual(scoring.main(arguments), 0)
            for path, data in originals.items(): self.assertEqual(path.read_bytes(), data)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["arms"]["agent"]["counts"]["unrun"], 1)
            self.assertNotIn('"answer":', output.read_text(encoding="utf-8"))
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit): scoring.main(arguments)
            # A changed planned input must be rejected before opening labels.
            manifest["inference_sha256"] = "0"*64
            audit.write_text(json.dumps(manifest), encoding="utf-8")
            original_read_text = Path.read_text
            def guarded_read_text(path, *args, **kwargs):
                if path == key: raise AssertionError("Labels read before frozen input verified")
                return original_read_text(path, *args, **kwargs)
            with patch.object(Path, "read_text", guarded_read_text), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                scoring.main(arguments)

    def test_json_decoder_rejects_duplicate_keys(self):
        with self.assertRaises(ValueError): scoring._decode('{"question_id":"q1","question_id":"q2"}')


if __name__ == "__main__":
    unittest.main()
