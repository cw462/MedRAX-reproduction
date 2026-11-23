"""Synthetic software fixtures for the explicitly selected RRSI-only stream."""

import csv
import json
from pathlib import Path
import unittest

from m5rrsi.engine import StreamEngine, primary_arms
from m5rrsi.data import prepare
from m5rrsi.io import ProtocolError, read_json, file_hash
from m5rrsi.report import report
from m5rrsi.validation import budget, validate_config
from test_local import Fixture


class TestSingleArm(Fixture):
    def single_stream(self, n=3):
        original, search = self.stream(n)
        config = {**original.cfg, "primary_arms": ["rrsi_acc"]}
        engine = StreamEngine(config, original.manifest, original.references,
                              self.runtime, self.scorer, search, export=original.export)
        return engine, search

    def test_only_requested_arm_executes(self):
        engine, _ = self.single_stream()
        result = engine.run()
        self.assertEqual(result["correct"], {"rrsi_acc": 0})
        self.assertEqual(sum(row["op"] == "initialize" for row in self.runtime.calls), 1)
        self.assertEqual(sum(row["op"] == "predict" for row in self.runtime.calls), 3)
        self.assertFalse((engine.out / "initial/fixed_m5").exists())
        self.assertFalse(any(engine.out.glob("primary/*/fixed_m5")))

    def test_current_lock_precedes_immediate_feedback(self):
        engine, _ = self.single_stream()
        original = engine.references.after_lock
        release_calls = []

        def release(case_id, paths, expected_locks=2):
            self.assertEqual(expected_locks, 1)
            self.assertEqual(len(paths), 1)
            self.assertTrue(paths[0].is_file())
            self.assertEqual(self.runtime.calls[-1]["op"], "predict")
            self.assertEqual(self.runtime.calls[-1]["id"], case_id)
            self.assertEqual(read_json(paths[0])["result"]["answer"], "A")
            release_calls.append(case_id)
            return original(case_id, paths, expected_locks)

        engine.references.after_lock = release
        engine.run()
        self.assertEqual(release_calls, ["x0", "x1", "x2"])
        ops = [(row["op"], row["id"]) for row in self.runtime.calls if row["id"]]
        self.assertEqual(ops, [(op, f"x{i}") for i in range(3) for op in ("predict", "observe")])
        next_prediction = next(row for row in self.runtime.calls
                               if row["op"] == "predict" and row["id"] == "x1")
        self.assertEqual(next_prediction["memory"], ["x0"])

    def test_resume_keeps_locks_and_runs_pending_search(self):
        engine, _ = self.single_stream(5)

        class InterruptedSearch:
            def __init__(self):
                self.completed = []
                self.interrupted = False

            def advance(self, rows, state, commit):
                n = len(rows)
                if n == 2 and not self.interrupted:
                    self.interrupted = True
                    raise RuntimeError("synthetic search interruption")
                if n not in self.completed:
                    self.completed.append(n)
                return {"commit": commit, "state": state}

        search = InterruptedSearch()
        engine.search = search
        with self.assertRaisesRegex(RuntimeError, "search interruption"):
            engine.run(2)
        saved = [(path, path.read_bytes()) for path in engine.out.glob("primary/*/rrsi_acc/predict/locked.json")]
        self.assertEqual(len(saved), 2)
        self.assertEqual(search.completed, [1])
        result = engine.run()
        self.assertEqual(result["completed"], 5)
        self.assertEqual(search.completed, [1, 2, 3, 4])
        self.assertEqual(sum(row["op"] == "predict" for row in self.runtime.calls), 5)
        for path, content in saved:
            self.assertEqual(path.read_bytes(), content)

    def test_stop_after_still_searches_its_last_completed_question(self):
        engine, search = self.single_stream(5)
        engine.run(2)
        self.assertEqual(search.events, [1, 2])

    def test_report_has_only_observed_arm_and_no_paired_claim(self):
        engine, _ = self.single_stream()
        engine.run(2)
        summary = report(engine.out)
        self.assertEqual(summary["primary_arms"], ["rrsi_acc"])
        self.assertFalse(summary["comparison_available"])
        self.assertFalse(summary["complete"])
        self.assertEqual(set(summary["scores"]["overall"]), {"rrsi_acc"})
        self.assertEqual(summary["scores"]["overall"]["rrsi_acc"]["n"], 2)
        self.assertNotIn("fixed_wrong_rrsi_right", summary)
        self.assertNotIn("fixed_right_rrsi_wrong", summary)
        with (engine.out / "report/primary.csv").open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(len(rows), 2)
        self.assertNotIn("fixed_m5", rows[0])
        self.assertFalse((engine.out / "report/paired_primary.csv").exists())

    def test_budget_uses_active_arms(self):
        config = read_json(Path(__file__).parents[1] / "configs/ttl_official.json")
        config["primary_arms"] = ["rrsi_acc"]
        estimate = budget(config)
        self.assertEqual(estimate["primary_question_predictions"], 848)
        self.assertEqual(estimate["max_sequential_replay_predictions_without_failures_or_retries"], 100500)

    def test_single_lock_requires_explicit_single_arm_release(self):
        engine, _ = self.single_stream()
        lock = self.p / "single.json"
        lock.write_text("{}")
        with self.assertRaises(ProtocolError):
            engine.references.after_lock("x0", [lock])
        self.assertEqual(engine.references.after_lock("x0", [lock], expected_locks=1), "B")
        lock.unlink()
        with self.assertRaises(ProtocolError):
            engine.references.after_lock("x0", [lock], expected_locks=1)

    def test_invalid_arm_selection_stops_before_runtime(self):
        for arms in ([], ["fixed_m5"], ["rrsi_acc", "rrsi_acc"], ["rrsi_acc", "unknown"], "rrsi_acc"):
            with self.subTest(arms=arms), self.assertRaises(ProtocolError):
                primary_arms({"primary_arms": arms})

    def test_open_question_preserves_empty_options_and_original_image(self):
        row = {**self.case, "options": [], "images": [str(self.img)]}
        public = self.p / "open.jsonl"
        public.write_text(json.dumps(row), encoding="utf-8")
        before = self.img.read_bytes()
        manifest = prepare(public, self.p / "open_manifest.json")
        saved = manifest["cases"][0]
        self.assertEqual(saved["options"], [])
        self.assertEqual(saved["question"], self.case["question"])
        self.assertEqual(saved["images"], [{"path": str(self.img.resolve()), "sha256": file_hash(self.img)}])
        self.assertEqual(self.img.read_bytes(), before)

    def test_open_question_still_requires_an_original_image(self):
        row = {**self.case, "options": [], "images": []}
        public = self.p / "open_without_image.jsonl"
        public.write_text(json.dumps(row), encoding="utf-8")
        with self.assertRaisesRegex(ProtocolError, "no original image"):
            prepare(public, self.p / "bad_manifest.json")

    def test_options_must_be_an_ordered_list(self):
        row = {**self.case, "options": {"A": "one"}, "images": [str(self.img)]}
        public = self.p / "unordered.jsonl"
        public.write_text(json.dumps(row), encoding="utf-8")
        with self.assertRaisesRegex(ProtocolError, "ORDERED list"):
            prepare(public, self.p / "bad_manifest.json")


class TestNativeLimits(unittest.TestCase):
    def config(self):
        template = read_json(Path(__file__).parents[1] / "configs/ttl_official.json")
        config = json.loads(json.dumps(template).replace("REPLACE", "native"))
        config["initial_commit"] = "0" * 40
        config["primary_arms"] = ["rrsi_acc"]
        config["runtime"]["limits"] = {"model_calls": None, "tool_calls": None, "output_tokens": 2048}
        return config

    def test_native_unlimited_counts_are_preserved(self):
        config = self.config()
        self.assertIs(validate_config(config), config)
        self.assertIsNone(config["runtime"]["limits"]["model_calls"])
        self.assertIsNone(config["runtime"]["limits"]["tool_calls"])

    def test_positive_native_limits_remain_supported(self):
        config = self.config()
        config["runtime"]["limits"].update(model_calls=30, tool_calls=40)
        self.assertIs(validate_config(config), config)

    def test_invalid_call_limits_are_rejected(self):
        for key in ("model_calls", "tool_calls"):
            for value in (-1, 0, False, True, 1.5, "unlimited"):
                config = self.config()
                config["runtime"]["limits"][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ProtocolError):
                    validate_config(config)

    def test_per_response_token_limit_is_required(self):
        for value in (None, -1, 0, False, True, 2048.5, "2048"):
            config = self.config()
            config["runtime"]["limits"]["output_tokens"] = value
            with self.subTest(value=value), self.assertRaises(ProtocolError):
                validate_config(config)

    def test_missing_native_limit_fields_are_rejected(self):
        for key in ("model_calls", "tool_calls", "output_tokens"):
            config = self.config()
            del config["runtime"]["limits"][key]
            with self.subTest(key=key), self.assertRaises(ProtocolError):
                validate_config(config)

    def test_template_is_still_rejected(self):
        config = self.config()
        config["runtime"]["image"] = "REPLACE_NATIVE_IMAGE"
        with self.assertRaises(ProtocolError):
            validate_config(config)


if __name__ == "__main__":
    unittest.main()
