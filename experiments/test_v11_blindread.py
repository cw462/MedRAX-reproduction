import base64
import json
from pathlib import Path
import tempfile
import unittest

from v11_blindread import blind_reader_content, matching_content, parse_blind_observation


class BlindReadTests(unittest.TestCase):
    def test_originals_only_without_answer_or_prior_context(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            originals = [root/'first.png', root/'second.png']
            for path in originals:
                Image.new('RGB', (32, 40), 'red').save(path)
            original_bytes = [path.read_bytes() for path in originals]
            row = {'question_id': 'private_qid', 'question': 'Describe the image relationship.\nA) UNIQUE_OPTION_ALPHA\nB) UNIQUE_OPTION_BETA',
                   'images': ['first.png', 'second.png'],
                   'candidate': 'UNIQUE_CANDIDATE', 'tool_observations': 'UNIQUE_DIAGNOSIS',
                   'prior_result': 'UNIQUE_PRIOR_SELECTION', 'knowledge': 'UNIQUE_KNOWLEDGE'}
            result = blind_reader_content(row, root)
            text = '\n'.join(item['text'] for item in result['content'] if item['type']=='text')
            for hidden in ('UNIQUE_', 'private_qid', str(root), 'A)', 'B)'):
                self.assertNotIn(hidden, text)
            self.assertEqual(result['refs'], ['image_1', 'image_2'])
            self.assertEqual([item['role'] for item in result['images']], ['original', 'original'])
            payloads = [item['image_url']['url'] for item in result['content'] if item['type']=='image_url']
            self.assertEqual([base64.b64decode(value.split(',', 1)[1]) for value in payloads], original_bytes)
            self.assertEqual([path.read_bytes() for path in originals], original_bytes)

    def test_reference_cleanup_and_unchanged_matching_evidence(self):
        observation = parse_blind_observation(json.dumps({'observations': [
            {'attribute': 'border', 'value': 'Boundary is not resolved', 'status': 'observed_present', 'evidence_refs': ['fake_id']},
            {'attribute': 'location', 'value': 'Visible region', 'status': 'observed_present', 'evidence_refs': ['image_1', 'image_1']}],
            'uncertainties': 'Pixel resolution limits detail'}), ['image_1'])
        self.assertEqual(observation['observations'][0]['status'], 'hypothesis')
        self.assertEqual(observation['observations'][0]['evidence_refs'], [])
        self.assertEqual(observation['observations'][1]['evidence_refs'], ['image_1'])
        packet = {'content': [{'type': 'text', 'text': '{"choices":{"X":"alpha","Y":"beta"}}'}]}
        original = json.loads(json.dumps(packet))
        matched = matching_content(packet, observation)
        self.assertEqual(matched[:-1], original['content'])
        self.assertEqual(packet, original)
        self.assertIn('blind_observation_1', matched[-1]['text'])
        with self.assertRaises(ValueError):
            parse_blind_observation('{"observations":[]}', ['image_1'])


if __name__ == '__main__':
    unittest.main()
