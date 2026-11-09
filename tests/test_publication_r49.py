"""Portable synthetic R49 evidence round trip, without provider or target data."""
import base64
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image
import test_score_online_skill_r49 as scoring_fixture
import score_online_skill_r49 as scorer
import export_online_skill_r49 as exporter
from verify_public_online_skill_r49 import verify
from online_memory_r49 import read
from run_online_skill_r49 import ARM


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


class Tests(unittest.TestCase):
    def test_self_contained_actual_raw_answers_and_image_paths_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inputs, data, run, references, baseline = scoring_fixture.Tests().fixture(root)
            buffer = BytesIO(); Image.new('RGB', (2, 2), 'white').save(buffer, format='PNG')
            image_bytes = buffer.getvalue(); (data/'same.png').write_bytes(image_bytes)
            uri = 'data:image/png;base64,'+base64.b64encode(image_bytes).decode('ascii')
            manifest = read(run/'manifest.json'); manifest.update(arm=ARM, implementation_files=[])
            write(run/'manifest.json', manifest)
            for row in inputs:
                qid = row['question_id']
                predpath = run/'predictions'/ARM/(qid+'.json')
                prediction = read(predpath); prediction['source_image_note'] = str(data/'same.png')
                write(predpath, prediction)
                for folder in ('prediction_events', 'feedback'):
                    path = run/folder/(qid+'.json'); value = read(path)
                    value['saved_prediction'] = prediction; write(path, value)
                path = run/'services/calls/R49-AGENT'/row['question_id']/'1/request.json'
                request = read(path)
                request['messages'].append({'role': 'user', 'content': [
                    {'type': 'text', 'text': 'BOUND CURRENT IMAGE: '+json.dumps({'source_filename': 'same.png', 'path': str(data/'same.png')})},
                    {'type': 'image_url', 'image_url': {'url': uri}}]})
                write(path, request)
            sources = {'M43': {row['question_id']: {
                        'prediction': {'answer': 'B' if row['question_id'] == 'q0' else 'A', 'status': 'completed'},
                        'source': {'raw': json.dumps({'answer': 'B' if row['question_id'] == 'q0' else 'A', 'reason': 'old synthetic'}),
                                   'call_path': 'synthetic', 'ordinal': '1', 'reuse_chain': [],
                                   'evidence_status': 'received_terminal_text', 'technical_stop': False}}
                        for row in inputs}}
            with patch.dict(scorer.EXPECTED, {'chexbench': (2, 'M43', 1)}), \
                    patch.object(scorer, 'adapt_historical', return_value=baseline):
                summary, detail = scorer.score(data, run, references, 'chexbench')
            scores = root/'scores'; write(scores/'summary.json', summary); write(scores/'per_question.json', detail)
            evidence = root/'public/evidence'
            recovery = root/'recovery/dependency_1'
            for name in ('controller', 'chexbench', 'generation'):
                path = recovery/'original'/(name+'.exitcode'); path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('1\n', encoding='utf-8')
            write(recovery/'diagnosis.json', {'scope': 'synthetic preserved dependency failure'})
            write(recovery/'generation/request.json', read(run/'services/calls/R49-AGENT/q0/1/request.json'))
            jobs = root/'jobs'
            write(jobs/'queue_status.json', {'recovery': 'dependency_1', 'initial_controller_exit': 1,
                  'initial_chexbench_exit': 1, 'state': 'all_three_datasets_exited_zero_after_known_dependency_repair'})
            with patch.dict(scorer.EXPECTED, {'chexbench': (2, 'M43', 1)}), \
                    patch.object(exporter, 'baseline_sources', return_value=sources):
                result = exporter.export(data, run, scores, references, root/'vault', evidence, 'chexbench',
                                         jobs=jobs, recovery_root=root/'recovery')
            self.assertEqual(result['images'], 1)
            shared = evidence.parent/'recovery/dependency_1/original/controller.exitcode'
            self.assertEqual(shared.read_text(encoding='utf-8').strip(), '1')
            self.assertFalse(read(evidence/'publication_manifest.json')['all_attempts_exit_zero_claim'])
            # The public verifier cannot fall back to the synthetic private
            # inputs, archived requests or vault once those are renamed away.
            data.rename(root/'private_data_unavailable'); run.rename(root/'private_run_unavailable')
            (root/'vault').rename(root/'private_vault_unavailable')
            (root/'recovery').rename(root/'private_recovery_unavailable')
            with patch.dict(scorer.EXPECTED, {'chexbench': (2, 'M43', 1)}), \
                    patch.object(scorer, 'historical_predictions', side_effect=AssertionError('private historical archive used')):
                reproduction = verify(evidence, root/'public/reproduction')
            self.assertTrue(reproduction['matches_published_primary_scores_and_extractions'])
            self.assertEqual(reproduction['comparisons']['M43']['harmed'], 1)
            self.assertFalse(reproduction['image_or_file_digests_checked'])
            for path in evidence.rglob('*.json'):
                self.assertNotIn('data:image/', path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
