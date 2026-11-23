"""Check that V10 crops contain real expected pixels and parsers never invent a choice."""
import base64
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v10_visual as visual


class CropTests(unittest.TestCase):
    def test_crop_pixels_and_full_original_are_both_encoded(self):
        from PIL import Image
        with TemporaryDirectory() as folder:
            path = Path(folder)/'source.png'
            original = Image.new('RGB', (20, 12), (10, 20, 30))
            for x in range(10, 20):
                for y in range(6, 12):
                    original.putpixel((x,y), (x,y,99))
            original.save(path)
            images = [{'image_id': 'image:1', 'path': str(path), 'role': 'original_current_case'}]
            crop = visual.crop_image('image:1', [.5,.5,1,1], images, Path(folder)/'crops', crop_id='crop:test')
            self.assertEqual(crop['pixel_box'], [10,6,20,12])
            self.assertEqual(crop['crop_size'], [10,6])
            with Image.open(crop['path']) as actual:
                self.assertEqual(actual.tobytes(), original.crop((10,6,20,12)).tobytes())
            parts = visual.multimodal_content('inspect current detail', images, [crop])
            payloads = [x['image_url']['url'] for x in parts if x['type']=='image_url']
            self.assertEqual(len(payloads), 2)
            decoded = [Image.open(io.BytesIO(base64.b64decode(x.split(',',1)[1]))) for x in payloads]
            self.assertEqual([x.size for x in decoded], [(20,12),(10,6)])
            self.assertEqual(decoded[1].getpixel((0,0)), (10,6,99))
            self.assertEqual(crop['orientation'], 'unresolved')

    def test_crop_rejects_other_case_and_invalid_boxes(self):
        from PIL import Image
        with TemporaryDirectory() as folder:
            path=Path(folder)/'source.png'
            Image.new('RGB',(20,20)).save(path)
            images=[{'image_id':'image:1','path':str(path)}]
            with self.assertRaises(ValueError):
                visual.crop_image('other-case', [0,0,1,1], images, folder)
            for box in ([0,0,1.01,1], [0,0,0,1], [0,0,float('nan'),1], [False,0,1,1], [0,0,.01,.01]):
                with self.subTest(box=box),self.assertRaises(ValueError):
                    visual.crop_image('image:1', box, images, folder)
            with self.assertRaises(ValueError):
                visual.crop_image('image:1',[0,0,1,1],images,folder,crop_id='../outside')

    def test_adapter_uses_existing_image_path_authorization_contract(self):
        from PIL import Image
        with TemporaryDirectory() as folder:
            path=Path(folder)/'source.png'
            Image.new('RGB',(20,20)).save(path)
            images=[{'image_id':'image:1','path':str(path)}]
            tool=visual.make_crop_tool(images,Path(folder)/'crops')
            result=tool.invoke({'image_path':str(path),'box':[0,0,.5,.5]})
            self.assertEqual(result['parent_image_id'],'image:1')
            self.assertEqual(result['crop_size'],[10,10])
            self.assertEqual(set(tool.args_schema.model_json_schema()['properties']),{'image_path','box'})
            with self.assertRaises(ValueError):
                tool.invoke({'image_path':str(Path(folder)/'other.png'),'box':[0,0,.5,.5]})


class CandidateTests(unittest.TestCase):
    def parse(self, text):
        return visual.parse_candidate(text, {'A':'one','B':'two'}, {'image:1','crop:detail','V:tool:1'})

    def test_uncertainty_keeps_best_candidate_and_no_evidence_is_fabricated(self):
        answer,payload=self.parse('{"answer":"B","uncertain":true}')
        self.assertEqual(answer,'B')
        self.assertTrue(payload['uncertain'])
        self.assertEqual(payload['evidence_refs'],[])
        self.assertEqual(payload['observations'],[])

    def test_format_repair_and_unknown_evidence_remain_audited(self):
        text='Result:\n```json\n'+json.dumps({'answer':'B. second','uncertain':'maybe',
            'evidence_refs':['image:1','invented'], 'observations':[{'attribute':'line','status':'observed_present',
            'image_ids':['made-up-image'], 'evidence_refs':['invented'], 'value':'present'}]})+'\n```'
        answer,payload=self.parse(text)
        self.assertEqual(answer,'B')
        self.assertTrue(payload['uncertain'])
        self.assertEqual(payload['evidence_refs'],['image:1'])
        self.assertEqual(payload['discarded_evidence_refs'],['invented'])
        self.assertEqual(payload['observations'][0]['status'],'hypothesis')
        self.assertEqual(payload['observations'][0]['evidence_refs'],[])
        self.assertIn('unknown_evidence_refs_removed',payload['parse_warnings'])

    def test_explicit_plain_answer_can_recover_without_mining_option_prose(self):
        for text in ('B','Answer: B','Final answer: B. second'):
            self.assertEqual(self.parse(text)[0],'B')
        for text in ('A and B both possible','The answer might be B but A is possible',
                     '{"answer":null,"uncertain":true}', '{"answer":"C"}',
                     '{"answer":"A","candidate":"B"}',
                     '{"answer":"A","answer":"B"}',
                     '{"answer":"A"} {"answer":"B"}'):
            with self.subTest(text=text),self.assertRaises(ValueError):
                self.parse(text)


if __name__=='__main__':
    unittest.main()
