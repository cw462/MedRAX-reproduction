"""Regression tests for the saved MAIRA normalized-coordinate failure.

The fixture is the raw second P tool result of 11624_8353800763402,
not a hand-authored pixel box. No answer/reference fields are read.
"""
import base64
import copy
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from official_gain.observations import normalize
from official_gain.visual_inspection import content, manual_box_allowed, roi


SAVED_NORMALIZED = [0.525, 0.03333333333333333, 0.89375, 0.8833333333333333]
SAVED_MODEL = [0.525, 0.035, 0.895, 0.885]
BENCHMARK_IMAGE = (Path(__file__).resolve().parents[1] / 'reports/v12/results/assets/'
                   'f17255b072778032c258791739dcaca2a1dfe04f5bfb3d353fdceab3ea437827.png')


def saved_result(source, box=None):
    """Only the fixture's source path is rebound to the temporary image."""
    return ({'predictions': [{
        'phrase': 'Left hemithorax has a higher lung volume than the right.',
        'bounding_boxes': {'model_coordinates': [list(SAVED_MODEL)],
                           'image_coordinates': [list(SAVED_NORMALIZED if box is None else box)]}}],
             'visualization_path': None},
            {'image_path': source['path'], 'analysis_status': 'completed',
             'phrase': 'left hemithorax', 'n_boxes': 1,
             'tool_version': 'maira-2@795a2b1c+bf16+negative-safe-v1',
             'clinical_evidence': 'unknown', 'step_credit': None})


class CoordinateRegression(unittest.TestCase):
    def source(self, folder, image):
        path = Path(folder) / 'original.png'
        image.save(path)
        return {'image_id': 'image:2', 'path': str(path), 'role': 'original',
                'size': list(image.size), 'source_filename': 'figure_3.jpg'}

    def test_saved_normalized_grounding_to_actual_benchmark_pixels(self):
        with tempfile.TemporaryDirectory() as directory:
            with Image.open(BENCHMARK_IMAGE) as loaded:
                original = loaded.convert('RGB')
            self.assertEqual(original.size, (480, 480))
            source = self.source(directory, original)
            raw = saved_result(source)
            before = copy.deepcopy(raw)
            observation = normalize('xray_phrase_grounding', source, raw, directory)
            self.assertEqual(observation['execution'], 'returned')
            self.assertEqual(raw, before)
            self.assertEqual(observation['original_pixel_boxes'], [[252.0, 16.0, 429.0, 424.0]])
            coordinates = observation['grounding_coordinates']
            self.assertEqual(coordinates['input_coordinate_space'], 'original_image_normalized_xyxy')
            self.assertEqual(coordinates['source_size'], [480, 480])
            self.assertEqual(coordinates['source_image_id'], 'image:2')
            self.assertEqual(coordinates['original_normalized_boxes'], [SAVED_NORMALIZED])
            views = roi(source, observation['original_pixel_boxes'][0], directory,
                        'saved_maira', normalized=False)
            # 15% context, minimum 8 px; all padding stays in original pixels.
            self.assertEqual(views[0]['original_pixel_box'], [225, 0, 456, 480])
            with Image.open(views[0]['path']) as cropped:
                self.assertEqual(cropped.size, (231, 480))
                self.assertEqual(cropped.tobytes(), original.crop((225, 0, 456, 480)).tobytes())
            with Image.open(views[1]['path']) as location:
                self.assertEqual(location.size, original.size)
                self.assertEqual(location.getpixel((10, 10)), original.getpixel((10, 10)))
                self.assertEqual(location.getpixel((225, 0)), (255, 255, 0))
            urls = [part['image_url']['url'] for part in content({}, [source] + views)
                    if part['type'] == 'image_url']
            self.assertEqual(base64.b64decode(urls[1].split(',', 1)[1]),
                             Path(views[0]['path']).read_bytes())
            self.assertEqual(views[0]['parent_image_ids'], ['image:2'])

    def test_asymmetric_pixels_are_never_flipped_or_resampled(self):
        with tempfile.TemporaryDirectory() as directory:
            pixels = bytes(component for y in range(480) for x in range(480)
                           for component in (x % 256, y % 256, (x + y) % 256))
            original = Image.frombytes('RGB', (480, 480), pixels)
            source = self.source(directory, original)
            observation = normalize('xray_phrase_grounding', source, saved_result(source), directory)
            views = roi(source, observation['original_pixel_boxes'][0], directory, 'asymmetric', normalized=False)
            with Image.open(views[0]['path']) as cropped:
                self.assertEqual(cropped.getpixel((0, 11)), original.getpixel((225, 11)))
                self.assertEqual(cropped.getpixel((230, 400)), original.getpixel((455, 400)))
                self.assertEqual(cropped.tobytes(), original.crop((225, 0, 456, 480)).tobytes())

    def test_bad_coordinates_and_wrong_source_are_not_guessed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source(directory, Image.new('RGB', (480, 480)))
            for box in ([252, 16, 429, 424], [-0.01, 0, 0.8, 0.9],
                        [0.1, 0, 1.01, 0.9], [0.8, 0, 0.1, 0.9],
                        [0.1, 0, float('nan'), 0.9]):
                with self.subTest(box=box):
                    value = normalize('xray_phrase_grounding', source, saved_result(source, box), directory)
                    self.assertEqual(value['execution'], 'failed')
                    self.assertEqual(value['original_pixel_boxes'], [])
            raw = saved_result(source)
            raw[1]['image_path'] = str(Path(directory) / 'different-original.png')
            value = normalize('xray_phrase_grounding', source, raw, directory)
            self.assertIn('grounding_coordinate_error:grounding_result_source_mismatch', value['errors'])
            changed_size = dict(source, size=[200, 100])
            self.assertEqual(normalize('xray_phrase_grounding', changed_size,
                                       saved_result(source), directory)['execution'], 'failed')
            derived = dict(source, role='derived', parent_image_id='image:1')
            self.assertEqual(normalize('xray_phrase_grounding', derived,
                                       saved_result(source), directory)['execution'], 'failed')

    def test_pixel_crop_rejects_out_of_bounds_before_context_padding(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source(directory, Image.new('RGB', (480, 480)))
            for box in ([-1, 20, 30, 60], [20, 20, 481, 60], [40, 20, 30, 60]):
                with self.subTest(box=box), self.assertRaises(ValueError):
                    roi(source, box, directory, 'invalid', normalized=False)

    def test_patient_side_is_bound_to_visible_marker_not_display_convention(self):
        action = {'box': [.55, .1, .9, .9], 'target_patient_side': 'left'}
        self.assertFalse(manual_box_allowed(action, {'view': 'frontal'}))
        self.assertTrue(manual_box_allowed(action, {
            'view': 'frontal', 'marker': {'text': 'R', 'box': [.01, .01, .1, .1]}}))
        self.assertFalse(manual_box_allowed(action, {
            'view': 'frontal', 'marker': {'text': 'L', 'box': [.01, .01, .1, .1]}}))


if __name__ == '__main__':
    unittest.main()
