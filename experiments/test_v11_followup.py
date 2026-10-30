import json
from pathlib import Path
import tempfile
import unittest

from v11_followup import apply_plan, planner_content, parse_plan, reader_content, comparison_with_observation, parse_observation


class FollowupTests(unittest.TestCase):
    def test_reader_blind_and_single_crop(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'original.png'
            Image.new('RGB', (100, 100), 'red').save(path)
            image = {'image_id': 'image_1', 'path': str(path), 'role': 'original', 'size': [100, 100]}
            packet = {'content': [{'type': 'text', 'text': json.dumps({'question': 'Which finding?', 'choices': {'X': 'secret_alpha', 'Y': 'secret_beta'}})}],
                      'images': [image], 'private_mapping': {'X': 'A', 'Y': 'B'}, 'refs': ['image_1']}
            question = 'Is the visible border smooth or irregular?'
            plan = parse_plan('{"action":"crop_original","image_ids":["image_1"],"box":[0,0,0.1,0.05]}', packet)
            action = apply_plan(packet, plan, Path(tmp)/'new')
            self.assertEqual(action['tool_attempts'], 1)
            self.assertEqual(action['images'][-1]['size'], [32, 32])
            content = reader_content(packet, question, action)
            text = ''.join(part['text'] for part in content if part['type']=='text')
            self.assertNotIn('secret_alpha', text)
            self.assertNotIn('choices', text)
            self.assertNotIn(str(path), text)
            observation = parse_observation('{"observation":"Border not resolved","evidence_refs":["image_1"],"unresolved":["pixel detail"]}', ['image_1'])
            comparison = comparison_with_observation(packet, question, observation, action)
            self.assertIn('secret_alpha', comparison[0]['text'])
            self.assertEqual(len([item for item in comparison if item['type']=='image_url']), 1)
            with self.assertRaisesRegex(ValueError, 'option_identity'):
                reader_content(packet, 'Is X or Y correct?', action)


if __name__ == '__main__':
    unittest.main()
