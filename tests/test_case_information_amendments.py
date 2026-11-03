"""Focused checks of the three newly requested behaviors; no API/tool calls."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from build_caption_modalities import caption_modality
from case_tool_projection import project_evidence, CLASSIFIER, REPORT
from run_case_information import first_image_gate, ImageUseReviewRequired, ImageInputIneligible


class Amendments(unittest.TestCase):
    def test_caption_specific_modality(self):
        self.assertEqual(caption_modality('Lateral chest film shows a mass.'),'CXR')
        self.assertEqual(caption_modality('CT chest shows an opacity.'),'CT')
        self.assertEqual(caption_modality('Chest radiograph and CT show nodules.'),'unknown')
        self.assertEqual(caption_modality('Opacity in the right lung.'),'unknown')

    def test_temporal_CT_is_not_current_image(self):
        self.assertEqual(caption_modality('AP chest radiographs after the first chest CT showing atelectasis.'),'CXR')
        self.assertEqual(caption_modality('Chest radiograph taken prior to the CT scan in figure 1 shows a sign.'),'CXR')

    def evidence(self):
        return {'evidence_for_model':{'limitations':['Unverified'], 'images':[
            {'source_filename':'f.jpg','tool_hypotheses':[
                {'tool':CLASSIFIER,'result':[{'Effusion':.9,'Pneumothorax':.95,'Edema':.79},{}]},
                {'tool':REPORT,'result':['Small pleural effusion. No pneumothorax.',{}]}]}]}}

    def test_three_separate_projections(self):
        c=project_evidence(self.evidence(),'classifier')
        self.assertEqual(c['images'][0]['tool_hypotheses'][0]['strong_findings'],{'Effusion':.9,'Pneumothorax':.95})
        self.assertEqual(len(c['images'][0]['tool_hypotheses']),1)
        r=project_evidence(self.evidence(),'report')
        self.assertEqual(r['images'][0]['tool_hypotheses'][0]['tool'],REPORT)
        b=project_evidence(self.evidence(),'combined')
        self.assertEqual([x['finding'] for x in b['images'][0]['positive_tool_agreement']],['Effusion'])

    def test_no_strong_signal_is_no_evidence(self):
        e=self.evidence();e['evidence_for_model']['images'][0]['tool_hypotheses'][0]['result'][0]={'Edema':.79}
        self.assertEqual(project_evidence(e,'classifier')['status'],'NO_EVIDENCE')

    def test_first_paid_sample_only_then_review(self):
        cfg={'model':'qwen3.8-flash','first_real_image_gate':True}
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);folder=out/'checkpoints/q1/sample_1';folder.mkdir(parents=True)
            (folder/'terminal.json').write_text(json.dumps({'ended_utc':'time'}))
            first_image_gate(cfg,out,'q1','q1')
            with self.assertRaises(ImageUseReviewRequired):first_image_gate(cfg,out,'q1','q2')
            record={'model':cfg['model'],'question_id':'q1','terminal_ended_utc':'time','reviewed_by':'operator',
                    'observations':['Saved image compared with real response'],'extra_paid_probes':0,
                    'image_accepted':True,'image_use_supported':False}
            (out/'first_image_use_review.json').write_text(json.dumps(record))
            with self.assertRaises(ImageInputIneligible):first_image_gate(cfg,out,'q1','q2')
            record['image_use_supported']=True
            (out/'first_image_use_review.json').write_text(json.dumps(record))
            first_image_gate(cfg,out,'q1','q2')


if __name__=='__main__':unittest.main()
