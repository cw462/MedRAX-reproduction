import json
from pathlib import Path
import tempfile
import unittest

from v11_selection import anonymous_mapping, build_comparison, parse_choice


class SelectionTests(unittest.TestCase):
    def test_choice_survives_optional_metadata_but_conflicts_fail(self):
        answer, record = parse_choice('{"choice":"Y","observations":42,"needs_followup":"yes"}')
        self.assertEqual(answer, 'Y')
        self.assertFalse(record['needs_followup'])
        self.assertTrue(record['parse_warnings'])
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            parse_choice('{"choice":"X"} {"choice":"Y"}')
        with self.assertRaises(ValueError):
            parse_choice('X is plausible but Y is also possible.')
        self.assertEqual(parse_choice('{"choice":"X", "observations": broken}')[0], 'X')
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            parse_choice('{"choice":"X","choice":"Y"}')

    def test_anonymous_projection_and_original_pixel_crop_repair(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root/'original.png'
            small = root/'small.png'
            Image.new('RGB', (100, 100), 'red').save(original)
            Image.new('RGB', (48, 5), 'red').save(small)
            record = {'tool_name': 'crop_current_image', 'evidence_ref': 'VKE:tool:1',
                      'arguments': {'image_path': str(original), 'box': [0, 0, .48, .05]},
                      'result': {'path': str(small), 'parent_path': str(original),
                                 'pixel_box': [0, 0, 48, 5], 'source_size': [100, 100],
                                 'crop_size': [48, 5]},
                      'artifacts': [{'image_id': 'VKE:tool:1:image:1', 'path': str(small)}]}
            row = {'question_id': 'synthetic', 'question': 'Which finding?\nA) complete alpha\nB) complete beta',
                   'images': ['original.png']}
            p0 = {'initial': 'A', 'raw_tools': []}
            branch = {'candidate': 'B', 'new_observations': [record],
                      'candidate_payload': {'answer': 'B', 'claim': 'SHOULD NEVER APPEAR'},
                      'gate': {'decision': 'retain'}}
            result = build_comparison(row, p0, branch, root, root/'new', 'fixed')
            text = '\n'.join(part['text'] for part in result['content'] if part['type']=='text')
            self.assertNotIn('VKE', text)
            self.assertNotIn(str(root), text)
            self.assertNotIn('SHOULD NEVER APPEAR', text)
            self.assertNotIn('A)', text)
            self.assertEqual(result['images'][1]['size'], [48, 32])
            self.assertEqual(len(result['repairs']), 1)
            self.assertEqual(result['private_mapping'], anonymous_mapping('synthetic', 'A', 'B', 'fixed'))
            with Image.open(small) as saved:
                self.assertEqual(saved.size, (48, 5))
            self.assertEqual(len([x for x in result['content'] if x['type']=='image_url']), 2)


if __name__ == '__main__':
    unittest.main()
