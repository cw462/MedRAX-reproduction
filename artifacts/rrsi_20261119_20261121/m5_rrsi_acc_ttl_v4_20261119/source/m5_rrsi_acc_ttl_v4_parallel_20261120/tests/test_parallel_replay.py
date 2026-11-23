"""Software fixtures for concurrent historical replay and official draft hooks."""
from concurrent.futures import ThreadPoolExecutor
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from m5rrsi.domain import MedM5Domain
from m5rrsi.io import read_json, tree_hash, write_json
from m5rrsi.search import official_round
from m5rrsi import llm


def official_module(name):
    checkout = Path(os.environ.get("M5_RRSI_TEST_UPSTREAM",
                    str(Path(__file__).resolve().parents[3] / "upstream/rrsi")))
    if not (checkout / "rrsi").is_dir():
        raise unittest.SkipTest("the official checkout is required")
    sys.path.insert(0, str(checkout))
    return importlib.import_module("rrsi." + name)


class ConcurrentRuntime:
    def __init__(self, parties):
        self.barrier = threading.Barrier(parties)
        self.lock = threading.Lock()
        self.events = []
        self.fail_observe_once = False

    def call(self, harness, state, op, *, case=None, prediction=None, feedback=None, seed=0):
        state = Path(state)
        memory = read_json(state / "memory.json")
        trial = next((part for part in state.parts if part.startswith("trial_")), "live")
        job = state.parts[state.parts.index("jobs") + 1]
        key = (job, trial)
        result = {"usage": {"total_tokens": 1, "model_calls": 1, "tool_calls": 0}}
        if op == "predict":
            if case["id"] == "q1":
                self.barrier.wait(timeout=5)
            if feedback is not None:
                raise AssertionError("predict received feedback")
            expected = [] if case["id"] == "q1" else ["q1"]
            if memory != expected:
                raise AssertionError((key, memory, expected))
            result.update(answer="fixture", trace={"memory": memory,
                          "prediction_root": str(state.parent), "key": key})
        if op == "observe":
            if not Path(prediction["trace"]["prediction_root"], "locked.json").is_file():
                raise AssertionError("observe preceded the immutable prediction lock")
            with self.lock:
                if self.fail_observe_once and trial == "trial_0" and case["id"] == "q2":
                    self.fail_observe_once = False
                    raise RuntimeError("fixture observe interruption")
            memory.append(case["id"])
            write_json(state / "memory.json", memory)
        with self.lock:
            self.events.append((key, op, case["id"] if case else None))
        return result


class LockedScorer:
    metric_id = "fixture_exact"

    def score(self, case, prediction, reference):
        if not Path(prediction["trace"]["prediction_root"], "locked.json").is_file():
            raise AssertionError("scoring preceded the immutable prediction lock")
        return 1


class ParallelReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source_state"
        self.source.mkdir()
        write_json(self.source / "memory.json", [])
        self.live = self.root / "live_state"
        self.live.mkdir()
        write_json(self.live / "memory.json", ["released_history"])
        self.checkout = self.root / "checkout"
        harness = self.checkout / "domains/med_m5/harness"
        harness.mkdir(parents=True)
        (harness / "agent.py").write_text("fixture = True\n")
        self.rows = [{"task_id": name, "case": {"id": name, "dataset": "software_fixture"},
                      "reference": "fixture", "before_evolving": str(self.source)}
                     for name in ("q1", "q2")]

    def tearDown(self):
        self.temp.cleanup()

    def domain(self, parties=2):
        runtime = ConcurrentRuntime(parties)
        domain = MedM5Domain(self.checkout, runtime, LockedScorer(), repeat_parallel=2)
        domain.bind(self.rows, self.live, 20)
        return domain, runtime

    def test_two_trials_overlap_and_each_keeps_question_order(self):
        domain, runtime = self.domain()
        original = tree_hash(self.source)
        domain.run(self.checkout, self.root, "parent", ["q1", "q2"], 2)
        for trial in ("trial_0", "trial_1"):
            sequence = [(op, q) for key, op, q in runtime.events
                        if key == ("parent", trial) and q]
            self.assertEqual(sequence, [("predict", "q1"), ("observe", "q1"),
                                        ("predict", "q2"), ("observe", "q2")])
            state = self.root / "jobs/parent" / trial / "q2/observe/state/memory.json"
            self.assertEqual(read_json(state), ["q1", "q2"])
        self.assertEqual(tree_hash(self.source), original)
        self.assertEqual(read_json(self.live / "memory.json"), ["released_history"])

    def test_official_evaluations_share_domain_without_state_collisions(self):
        evaluate = official_module("evaluate").evaluate
        domain, runtime = self.domain(parties=4)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(evaluate, domain, self.checkout, self.root, job,
                                   ["q1", "q2"], 2) for job in ("r1A", "r1B")]
            results = [future.result() for future in futures]
        self.assertEqual([(ev.job, ev.S, ev.n_expected, ev.missing) for ev in results],
                         [("r1A", 1.0, 4, 0), ("r1B", 1.0, 4, 0)])
        self.assertEqual(len([row for row in runtime.events if row[1] == "predict"]), 8)
        self.assertEqual(results[0].extra["panel_id"], results[1].extra["panel_id"])
        self.assertNotEqual(results[0].extra["live_migration"]["state"],
                            results[1].extra["live_migration"]["state"])

    def test_resume_reuses_locked_predictions_after_one_trial_interruption(self):
        domain, runtime = self.domain()
        runtime.fail_observe_once = True
        with self.assertRaisesRegex(RuntimeError, "observe interruption"):
            domain.run(self.checkout, self.root, "resumed", ["q1", "q2"], 2)
        locks = {path: path.read_bytes() for path in (self.root / "jobs/resumed").glob("trial_*/q*/predict/locked.json")}
        self.assertEqual(len(locks), 4)
        predictions = len([event for event in runtime.events if event[1] == "predict"])
        domain.run(self.checkout, self.root, "resumed", ["q1", "q2"], 2)
        self.assertEqual(len([event for event in runtime.events if event[1] == "predict"]), predictions)
        for path, data in locks.items():
            self.assertEqual(path.read_bytes(), data)

class ParallelDraftTests(unittest.TestCase):
    def test_original_drafts_overlap_preserving_reserved_slot_and_result_order(self):
        gitops = official_module("gitops")
        barrier = threading.Barrier(2)
        seen = []
        critical = {"active": 0, "peak": 0}

        def worktree_add(*args):
            critical["active"] += 1
            critical["peak"] = max(critical["peak"], critical["active"])
            time.sleep(0.01)
            critical["active"] -= 1

        class Round:
            cfg = SimpleNamespace(m=2, m_draft=1)

            def _draft(self, t, vid, rdir, report, digests, traces, inc_ev, budget,
                       explore, reserved, prune, hist_rows, skill_md, patterns_md):
                gitops.worktree_add(vid)
                barrier.wait(timeout=5)
                seen.append((vid, reserved))
                return vid

            def round(self, t):
                return [self._draft(t, vid, None, {}, {}, {}, None, 2,
                        {"sigma": 1, "untried": ["memory"]}, vid == "B", [], [], "", "")
                        for vid in ("A", "B")]

        run = Round()
        original = run._draft
        with patch.object(gitops, "worktree_add", worktree_add):
            self.assertEqual(official_round(run, 7, draft_parallel=2), ["A", "B"])
            self.assertIs(gitops.worktree_add, worktree_add)
        self.assertCountEqual(seen, [("A", False), ("B", True)])
        self.assertEqual(critical["peak"], 1)
        self.assertEqual(run._draft, original)
        self.assertEqual(run.cfg.m_draft, 1)


class ParallelRoleTests(unittest.TestCase):
    def test_inflight_role_receipt_stays_with_its_configuration(self):
        entered, release = threading.Event(), threading.Event()
        payload = {"model": "fixture", "usage": {"total_tokens": 3},
                   "choices": [{"message": {"content": "done"}, "finish_reason": "stop"}]}

        class Response:
            def __enter__(self):
                entered.set()
                if not release.wait(5):
                    raise AssertionError("test release timed out")
                return self

            def __exit__(self, *args):
                pass

            def read(self, *args):
                return json.dumps(payload).encode()

        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first.jsonl", Path(directory) / "second.jsonl"
            config = {"api_key_env": "M5_TEST_KEY", "base_url_env": "M5_TEST_URL",
                      "model": "fixture", "max_tokens": 10, "retries": 1}
            llm.configure(config, first)
            with patch.dict(os.environ, {"M5_TEST_KEY": "fixture", "M5_TEST_URL": "https://example.invalid/v1"}), \
                 patch("urllib.request.urlopen", return_value=Response()), ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(llm.generate, "fixture")
                self.assertTrue(entered.wait(5))
                llm.configure(config, second)
                release.set()
                self.assertEqual(future.result(), "done")
            self.assertEqual(json.loads(first.read_text())["usage"]["total_tokens"], 3)
            self.assertFalse(second.exists())


if __name__ == "__main__":
    unittest.main()
