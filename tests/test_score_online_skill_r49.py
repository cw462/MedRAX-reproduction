"""Synthetic offline evidence tests; no benchmark labels or endpoints are used."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
import score_online_skill_r49 as scoring
from online_memory_r49 import ReferenceVault, now, read, save_once
from run_online_skill_r49 import ARM, run_stream
from skill_lifecycle_r49 import DEFAULTS
from score_cxr_author_alignment import adapt


class Tests(unittest.TestCase):
    def fixture(self, root):
        inputs = [{'question_id': 'q'+str(i), 'question': 'Is it present?', 'images': ['same.png'],
                   'image_id': 'same', 'source': {'subset': 'toy'}, 'options': {'A': 'Yes', 'B': 'No'}} for i in range(2)]
        order = [{'question_id': 'q'+str(i), 'image_key': 'same', 'previous_ids': ['q0'] if i else []} for i in range(2)]
        data, out, vault_dir = root/'data', root/'run', root/'vault'
        data.mkdir(); (data/'inputs.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in inputs), encoding='utf-8')
        references = root/'references.jsonl'
        references.write_text(''.join(json.dumps({'question_id': row['question_id'], 'answer': 'A'})+'\n' for row in inputs), encoding='utf-8')
        for row in inputs:
            save_once(vault_dir/(row['question_id']+'.json'), {'question_id': row['question_id'], 'answer': 'A'})
        vault = ReferenceVault(vault_dir, {row['question_id']: {'file': row['question_id']+'.json'} for row in inputs})

        class ArchiveService:
            def execute(self, row, policy, data, conditioning):
                qid = row['question_id']; answer = 'A' if qid == 'q0' else 'B'
                raw = json.dumps({'answer': answer, 'reason': 'synthetic observed result'})
                folder = out/'services/calls/R49-AGENT'/qid/'1'; request_id = 'toy:'+qid
                save_once(folder/'request.json', {'messages': [{'role': 'user', 'content': conditioning}] if conditioning else []})
                save_once(folder/'started.json', {'request_id': request_id, 'utc': now()})
                save_once(folder/'response.json', {'choices': [{'message': {'content': raw}}]})
                save_once(folder/'result.json', {'request_id': request_id, 'utc': now(), 'error': None,
                          'response_received': True, 'model_returned': 'synthetic',
                          'usage': {'prompt_tokens': 2, 'completion_tokens': 1},
                          'settlement': {'charged_cny': '0.001'}, 'elapsed_s': 0.1})
                return {'answer': answer, 'reason': 'synthetic observed result', 'status': 'completed',
                        'terminal_raw': raw, 'observations': [], 'main_calls': 1, 'tool_calls': 0}, [{'step_index': 0, 'response': raw}]

        def no_learning(service, snapshot, batch, wi, *args):
            result = copy.deepcopy(snapshot); result['clock'] += len(batch); result['window'] = wi+1
            return result
        run_stream(inputs, order, data, out, ArchiveService(), vault, [], evolver=no_learning)
        save_once(out/'manifest.json', {'dataset': 'chexbench', 'inputs': inputs, 'order': order, 'defaults': copy.deepcopy(DEFAULTS)})
        (out/'generation.exitcode').write_text('0\n', encoding='utf-8')
        baseline = {}
        for row in inputs:
            answer = 'B' if row['question_id'] == 'q0' else 'A'
            raw = json.dumps({'answer': answer, 'reason': 'old synthetic'})
            baseline[row['question_id']] = adapt(row, {'answer': answer, 'status': 'completed'},
                         {'raw': raw, 'call_path': 'synthetic', 'ordinal': '1', 'reuse_chain': [],
                          'evidence_status': 'received_terminal_text', 'technical_stop': False})
        return inputs, data, out, references, baseline

    def test_uniform_adaptation_precedes_labels_and_reports_harms(self):
        with tempfile.TemporaryDirectory() as temp:
            _, data, run, refs, baseline = self.fixture(Path(temp)); phase = []; original_rows = scoring.rows
            def baseline_adapter(*args):
                phase.append('all_baseline_raw_adapted'); return baseline
            def observe_rows(path):
                if Path(path) == refs:
                    self.assertEqual(phase, ['all_current_raw_adapted', 'all_baseline_raw_adapted'])
                return original_rows(path)
            original_adapt = scoring.adapt_current
            def current_adapter(*args):
                value = original_adapt(*args); phase.append('all_current_raw_adapted'); return value
            with patch.dict(scoring.EXPECTED, {'chexbench': (2, 'M43', 1)}), \
                    patch.object(scoring, 'adapt_current', side_effect=current_adapter), \
                    patch.object(scoring, 'adapt_historical', side_effect=baseline_adapter), \
                    patch.object(scoring, 'rows', side_effect=observe_rows):
                summary, detail = scoring.score(data, run, refs, 'chexbench')
            self.assertEqual(summary['arms'][ARM]['correct'], 1)
            self.assertEqual(summary['comparisons']['M43']['corrected'], 1)
            self.assertEqual(summary['comparisons']['M43']['harmed'], 1)
            self.assertEqual(summary['comparisons']['M43']['net'], 0)
            self.assertEqual(summary['resources']['agent']['requests'], 2)
            self.assertEqual(summary['resources']['R49_META']['requests'], 0)
            self.assertEqual(len(detail), 2)

    def test_unclosed_send_stops_before_feedback_or_scoring_labels(self):
        with tempfile.TemporaryDirectory() as temp:
            _, data, run, refs, _ = self.fixture(Path(temp))
            (run/'services/calls/R49-AGENT/q1/1/response.json').unlink()
            original_read = scoring.read
            def observe_read(path):
                self.assertNotIn('feedback', Path(path).parts)
                return original_read(path)
            with patch.dict(scoring.EXPECTED, {'chexbench': (2, 'M43', 1)}), \
                    patch.object(scoring, 'read', side_effect=observe_read):
                with self.assertRaisesRegex(ValueError, 'unclosed_request'):
                    scoring.score(data, run, refs, 'chexbench')

    def test_raw_nonzero_exit_never_scores_complete_record(self):
        with tempfile.TemporaryDirectory() as temp:
            _, data, run, refs, _ = self.fixture(Path(temp))
            (run/'generation.exitcode').write_text('1\n', encoding='utf-8')
            with patch.dict(scoring.EXPECTED, {'chexbench': (2, 'M43', 1)}):
                with self.assertRaisesRegex(ValueError, 'raw_generation_exit_zero_required'):
                    scoring.score(data, run, refs, 'chexbench')


if __name__ == '__main__':
    unittest.main()
