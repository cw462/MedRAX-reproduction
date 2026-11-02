import base64
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from experiments.export_vote_phase import export_phase


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def png(color):
    out = BytesIO()
    Image.new('RGB', (20, 16), color).save(out, format='PNG')
    return out.getvalue()


class PublicExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.image_a, self.image_b = png('red'), png('blue')
        self.row = {'question_id': 'q1', 'case_id': 'case1',
                    'question': 'Compare Figure 1 and Figure 2.\nA. First complete option\ncontinued detail\nB. Second complete option',
                    'images': ['case1/figure1.png', 'case1/figure2.png'], 'figure_labels': ['Figure 1', 'Figure 2']}
        self.run = self.root / 'private_run'
        self.manifest = self.root / 'phase.json'
        write(self.manifest, {'phase': 1, 'split': 'tune', 'baseline': 'D', 'arms': [{'id': 'D', 'run': 'private_run'}]})
        self.make_run()

    def tearDown(self):
        self.temp.cleanup()

    def make_run(self, text_only=False, samples=2):
        write(self.run / 'protocol.json', {'model': 'synthetic', 'samples': samples, 'prompt_variant': 'text_only' if text_only else 'answer',
              'temperature': .2, 'top_p': .95, 'max_tokens': 2048, 'root': '/home/privateuser/project',
              'ledger': 'private_ledgers/account.json', 'api_key': 'synthetic-secret', 'profile': {'base_url': 'https://api.example/v1', 'auth_token': 'synthetic-secret'}})
        write(self.run / 'status.json', {'status': 'generation_complete'})
        write(self.run / 'selection.json', {'rows': [self.row]})
        # These are deliberately invalid JSON; any access would fail the test.
        (self.run / 'private_ledgers').mkdir(exist_ok=True)
        (self.run / 'private_ledgers' / 'account.json').write_text('NEVER READ PRIVATE ACCOUNT')
        (self.run / 'ledger_start.json').write_text('NEVER READ ACCOUNT TOTALS')
        records = []
        for sample in range(1, samples + 1):
            folder = self.run / 'checkpoints' / 'q1' / f'sample_{sample}'
            content = [{'type': 'text', 'text': self.row['question']}]
            if not text_only:
                # Deliberately reverse request order: binding must follow metadata.
                for index, data in [(2, self.image_b), (1, self.image_a)]:
                    metadata = {'source_filename': f'case1/figure{index}.png', 'path': f'/home/privateuser/project/images/case1/figure{index}.png',
                                'image_id': f'image:{index}', 'figure_label': f'Figure {index}', 'size': [20, 16]}
                    content.extend([{'type': 'text', 'text': 'BOUND CURRENT IMAGE: ' + json.dumps(metadata)},
                                    {'type': 'text', 'text': f'Figure {index}:'},
                                    {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(data).decode(), 'detail': 'high'}}])
            request = {'model': 'synthetic', 'temperature': .2, 'top_p': .95, 'max_tokens': 2048,
                       'messages': [{'role': 'user', 'content': content}], 'extra_body': {'enable_thinking': False},
                       'headers': {'Authorization': 'Bearer hidden-token-12345'}}
            write(folder / 'request.json', request)
            attempt = {'ordinal': 1, 'usage': {'prompt_tokens': 20, 'completion_tokens': 5},
                       'raw_content': 'Answer: A', 'reasoning_content': 'Preserved observation about Figure 2.',
                       'settlement': {'charged_cny': '0.01', 'remaining_cny': '123.45'}}
            terminal = {'question_id': 'q1', 'case_id': 'case1', 'sample_index': sample,
                        'answer': 'A', 'status': 'completed', 'attempts': [attempt], 'raw_response': 'Answer: A'}
            write(folder / 'terminal.json', terminal)
            write(folder / 'attempt_1' / 'result.json', attempt)
            write(folder / 'attempt_1' / 'response.json', {'choices': [{'message': {'content': 'Answer: A',
                  'reasoning_content': 'Preserved detailed reasoning. api_key=synthetic-secret /home/privateuser/cache/file'}}]})
            records.append(terminal)
        (self.run / 'predictions.jsonl').write_text('\n'.join(json.dumps(r) for r in records), encoding='utf-8')
        write(self.run / 'ledger_final_summary.json', {'run_increment_cny': '0.03', 'price_basis': 'synthetic'})

    def test_export_preserves_native_bytes_binding_parameters_and_reasoning(self):
        source = (self.run / 'predictions.jsonl').read_bytes()
        result = export_phase(self.manifest, self.root / 'report')
        out = self.root / 'report' / 'evidence'
        self.assertEqual(result['asset_count'], 2)
        self.assertFalse(result['private_account_ledgers_read'])
        self.assertEqual(source, (self.run / 'predictions.jsonl').read_bytes())
        cases = json.loads((out / 'cases.json').read_text())['cases']
        self.assertEqual(cases[0]['options']['A'], 'First complete option\ncontinued detail')
        self.assertEqual((out / cases[0]['native_images'][0]['image']).read_bytes(), self.image_a)
        bindings = cases[0]['samples']['D'][0]['request_image_bindings']
        self.assertEqual(bindings[0]['figure_label'], 'Figure 2')
        self.assertEqual((out / bindings[0]['image']).read_bytes(), self.image_b)
        request_path = out / cases[0]['samples']['D'][0]['request']
        request = json.loads(request_path.read_text())
        self.assertEqual(request['temperature'], .2)
        self.assertEqual(request['max_tokens'], 2048)
        blocks = request['messages'][0]['content']
        self.assertEqual((request_path.parent / blocks[3]['image_url']['url']).read_bytes(), self.image_b)
        metadata = json.loads(blocks[1]['text'].split(': ', 1)[1])
        self.assertEqual((request_path.parent / metadata['path']).read_bytes(), self.image_b)
        response = (request_path.parent / 'attempt_1' / 'response.json').read_text()
        self.assertIn('Preserved detailed reasoning.', response)
        self.assertIn('reasoning_content', response)
        for filename in result['files']:
            if filename.endswith(('.json', '.jsonl')):
                text = (out / filename).read_text(encoding='utf-8')
                for secret in ('synthetic-secret', 'hidden-token', '/home/privateuser', '123.45', 'data:image'):
                    self.assertNotIn(secret, text)
        costs = json.loads((out / 'cost_summary.json').read_text())
        self.assertEqual(costs['arms']['D']['guard_minus_saved_settlement_cny'], '0.01')

    def test_explicit_public_image_reuse_requires_exact_bytes(self):
        public = self.root / 'public' / 'figure1.png'
        public.parent.mkdir()
        public.write_bytes(self.image_a)
        manifest = json.loads(self.manifest.read_text())
        manifest['public_image_map'] = {'case1/figure1.png': 'public/figure1.png'}
        write(self.manifest, manifest)
        export_phase(self.manifest, self.root / 'report')
        out = self.root / 'report' / 'evidence'
        case = json.loads((out / 'cases.json').read_text())['cases'][0]
        self.assertEqual((out / case['native_images'][0]['image']).resolve(), public.resolve())
        self.assertEqual(len(list((out / 'assets').iterdir())), 1)
        public.write_bytes(self.image_b)
        with self.assertRaisesRegex(ValueError, 'does_not_match_request_bytes'):
            export_phase(self.manifest, self.root / 'bad_report')

    def test_incomplete_phase_is_not_exported(self):
        write(self.run / 'status.json', {'status': 'running'})
        with self.assertRaisesRegex(ValueError, 'generation_not_complete'):
            export_phase(self.manifest, self.root / 'report')
        self.assertFalse((self.root / 'report').exists())

    def test_text_only_archive_still_requires_full_case_images(self):
        self.make_run(text_only=True)
        with self.assertRaisesRegex(FileNotFoundError, 'missing_native_image'):
            export_phase(self.manifest, self.root / 'report')
        images = self.root / 'native'
        (images / 'case1').mkdir(parents=True)
        (images / 'case1' / 'figure1.png').write_bytes(self.image_a)
        (images / 'case1' / 'figure2.png').write_bytes(self.image_b)
        result = export_phase(self.manifest, self.root / 'report', [images])
        self.assertEqual(result['asset_count'], 2)
        case = json.loads((self.root / 'report' / 'evidence' / 'cases.json').read_text())['cases'][0]
        self.assertEqual(case['samples']['D'][0]['request_image_bindings'], [])

    def test_unknown_image_binding_is_rejected(self):
        path = self.run / 'checkpoints' / 'q1' / 'sample_1' / 'request.json'
        value = json.loads(path.read_text())
        value['messages'][0]['content'][1]['text'] = value['messages'][0]['content'][1]['text'].replace('case1/figure2.png', 'other/figure2.png')
        write(path, value)
        with self.assertRaisesRegex(ValueError, 'not_in_question_selection'):
            export_phase(self.manifest, self.root / 'report')

    def test_checkpoint_aggregate_disagreement_is_rejected(self):
        path = self.run / 'checkpoints' / 'q1' / 'sample_1' / 'terminal.json'
        value = json.loads(path.read_text())
        value['answer'] = 'B'
        write(path, value)
        with self.assertRaisesRegex(ValueError, 'terminal_disagree'):
            export_phase(self.manifest, self.root / 'report')


if __name__ == '__main__':
    unittest.main()
