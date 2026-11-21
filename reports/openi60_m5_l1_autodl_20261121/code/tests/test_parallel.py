import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openi60.common import ExperimentError
from openi60.parallel import run_parallel


class ParallelArmsTests(unittest.TestCase):
    def exercise(self, failure=False):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            for arm in ('B0', 'L1'):
                (work / arm).mkdir()
            barrier = threading.Barrier(2, timeout=5)
            finished = set()

            def generate(phase, directory, arm, cfg, attempt, credentials):
                self.assertEqual(phase, 'generate')
                self.assertEqual(directory, work)
                self.assertEqual(attempt, work / 'jobs' / arm / 'attempt-001')
                barrier.wait()
                finished.add(arm)
                return 1 if failure and arm == 'B0' else 0

            def score(directory, execute, resume, arm):
                self.assertEqual(finished, {'B0', 'L1'})
                self.assertEqual((execute, resume, arm), (True, False, 'all'))
                return {'paired': 'complete'}

            cfg = {'n': 60, 'main_key_env': 'OPENI60_TEST_MAIN', 'memory_key_env': 'OPENI60_TEST_MEMORY'}
            with patch('openi60.parallel.verify_frozen', return_value={'config': cfg}), \
                 patch('openi60.parallel.preflight'), \
                 patch('openi60.parallel.child', side_effect=generate), \
                 patch('openi60.parallel.run', side_effect=score) as scorer, \
                 patch.dict(os.environ, {'OPENI60_TEST_MAIN': 'offline', 'OPENI60_TEST_MEMORY': 'offline'}):
                if failure:
                    with self.assertRaises(ExperimentError):
                        run_parallel(work, True)
                    scorer.assert_not_called()
                else:
                    self.assertEqual(run_parallel(work, True), {'paired': 'complete'})
                    scorer.assert_called_once()
            self.assertEqual((work / 'B0/generation.exitcode').read_text().strip(), '1' if failure else '0')
            self.assertEqual((work / 'L1/generation.exitcode').read_text().strip(), '0')

    def test_arms_overlap_and_scoring_waits_for_both(self):
        self.exercise()

    def test_failed_arm_preserves_exit_and_prevents_comparison(self):
        self.exercise(failure=True)
