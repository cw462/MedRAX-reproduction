import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from r1_evidence import crop_audit, explicit_answer, normalize_plan, planning_payload, observer_payload


class R1Evidence(unittest.TestCase):
    def setUp(self):
        self.images=[{'image_id':'image:1','size':[200,100],'path':'synthetic.png'}]
        self.plan={'kind':'crop','attribute':'side','target_region':'patient right lung','neutral_question':'Describe the side.',
            'image_ids':['image:1'],'target_patient_side':'right','box':[0.05,0.1,0.45,0.9],
            'image_metadata':[{'image_id':'image:1','modality':'CXR','view':'frontal','marker':{'text':'R','box':[0.01,0.01,0.08,0.08]}}]}

    def test_patient_right_not_display_right(self):
        self.assertTrue(crop_audit(self.plan,self.images)['allowed'])
        self.plan['box']=[0.55,0.1,0.95,0.9]
        self.assertFalse(crop_audit(self.plan,self.images)['allowed'])

    def test_explicit_opposite_marker_orientation(self):
        self.plan['image_metadata'][0]['marker']['box']=[0.92,0.01,0.99,0.08]
        self.plan['box']=[0.55,0.1,0.95,0.9]
        self.assertTrue(crop_audit(self.plan,self.images)['allowed'])

    def test_unknown_lateral_and_multiview_do_not_assume_convention(self):
        for view in ('lateral','montage','unknown'):
            self.plan['image_metadata'][0]['view']=view
            self.assertFalse(crop_audit(self.plan,self.images)['allowed'])
        self.plan['image_metadata'][0]['view']='frontal';self.plan['image_metadata'][0]['marker']={}
        self.assertFalse(crop_audit(self.plan,self.images)['allowed'])

    def test_actual_crop_bytes_follow_checked_display_coordinates(self):
        from PIL import Image
        from v10_visual import crop_image
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);image=Image.new('RGB',(200,100),'blue')
            image.paste('red',(0,0,100,100));source=root/'original.png';image.save(source)
            images=[dict(self.images[0],path=str(source))]
            self.assertTrue(crop_audit(self.plan,images)['allowed'])
            result=crop_image('image:1',self.plan['box'],images,root/'crops',crop_id='crop:synthetic')
            with Image.open(result['path']) as crop:self.assertEqual(crop.getpixel((0,0)),(255,0,0))

    def test_model_payloads_ignore_prior_answer_and_reason(self):
        row={'question':'Full question\nA) one\nB) two','D0_answer':'SECRET_CHOICE','D0_reason':'SECRET_REASON'}
        payloads=[planning_payload(row,self.images),observer_payload(row,self.images,self.plan,{'kind':'visual'})]
        for payload in payloads:
            self.assertNotIn('SECRET_',json.dumps(payload))
            self.assertEqual(payload['full_question_and_all_options'],row['question'])

    def test_neutral_question_and_explicit_answer_parser(self):
        value=dict(self.plan,neutral_question='Confirm the expected lesion is on the right.')
        result=normalize_plan(json.dumps(value),self.images)
        self.assertTrue(result['warnings'])
        self.assertEqual(explicit_answer('Answer: B) complete option\nReason: one observation',{'A','B'}),'B')
        self.assertIsNone(explicit_answer('Answer: A or B',{'A','B'}))
        self.assertIsNone(explicit_answer('Answer: A\nAnswer: B',{'A','B'}))


if __name__=='__main__':unittest.main()
