"""Focused tests for V12 evidence binding and known parser failure boundaries."""
import json
from pathlib import Path
import tempfile
import unittest

from v12_evidence import (build_images,multimodal_content,parse_first_read,
    observation_projection,parse_final,parse_action_plan,classify_tool_return,parse_targeted_read)


ROW={'question':'A 60-year-old woman is shown at presentation in Figure 1 and at follow-up in Figure 7b.\nA. Small left lesion\nB. Large right lesion\nC. No lesion',
     'images':['figures/1/figure_1.jpg','figures/1/figure_7b.jpg']}
IMAGES=[{'image_id':'image:1','figure_label':'Figure 1','source_filename':ROW['images'][0]},
        {'image_id':'image:2','figure_label':'Figure 7b','source_filename':ROW['images'][1]}]


def first():
    return {'first_answer':'A','observations':[{'attribute':'margin','value':'An irregular border is visible.',
        'status':'observed_present','evidence_refs':['image:1']}],
        'hypotheses':[{'name':'possible mass','basis':'requires verification','evidence_refs':['image:1']}],
        'patient_conditions':[{'name':'age','value':'60-year-old','source_quote':'A 60-year-old woman'}],
        'discriminators':[{'attribute':str(n),'question':'Compare attribute '+str(n),'option_labels':['A','B','C'],'image_ids':['image:1']} for n in range(4)],
        'image_metadata':[{'image_id':'image:1','modality':'CT','anatomy':'thorax','timepoint':'at presentation',
            'timepoint_source_quote':'at presentation in Figure 1'},
            {'image_id':'image:2','modality':'chest x-ray','timepoint':'at follow-up','timepoint_source_quote':'at follow-up in Figure 7b'}],
        'uncertainties':['No metric scale supplied.']}


class EvidenceTests(unittest.TestCase):
    def test_first_preserves_all_discriminators_and_figure_mapping(self):
        result=parse_first_read(json.dumps(first()),ROW,IMAGES)
        self.assertEqual(len(result['discriminators']),4)
        self.assertEqual(result['image_metadata'][1]['figure_label'],'Figure 7b')
        self.assertEqual([x['modality'] for x in result['image_metadata']],['CT','CXR'])
        self.assertEqual(result['image_metadata'][1]['timepoint'],'at follow-up')
        self.assertEqual(result['patient_conditions'][0]['value'],'60-year-old')

    def test_literal_newline_outer_json_retains_metadata(self):
        raw=json.dumps(first()).replace('An irregular border is visible.','An irregular\nborder is visible.')
        result=parse_first_read(raw,ROW,IMAGES)
        self.assertEqual(len(result['discriminators']),4)
        self.assertIn('\n',result['observations'][0]['value'])

    def test_malformed_outer_never_uses_valid_inner(self):
        raw='{"first_answer":"A", BROKEN '+json.dumps(first())+'}'
        with self.assertRaisesRegex(ValueError,'invalid_outer_json'):
            parse_first_read(raw,ROW,IMAGES)

    def test_incomplete_outer_does_not_default_metadata(self):
        with self.assertRaisesRegex(ValueError,'missing_outer_fields'):
            parse_first_read('{"first_answer":"A","observations":[]}',ROW,IMAGES)

    def test_duplicates_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_action_plan('{"actions":[],"actions":[]}',IMAGES,[])

    def test_conditions_cannot_come_from_options_or_invented_facts(self):
        value=first();value['patient_conditions'] += [
            {'name':'finding','value':'Large right lesion','source_quote':'Large right lesion'},
            {'name':'immune','value':'immunocompromised','source_quote':'A 60-year-old woman'}]
        result=parse_first_read(json.dumps(value),ROW,IMAGES)
        self.assertEqual(len(result['patient_conditions']),1)

    def test_unsupported_time_and_unknown_refs_stay_unknown(self):
        value=first();value['image_metadata'][1]['timepoint_source_quote']='five years later'
        value['observations'][0]['evidence_refs']=['imaginary']
        result=parse_first_read(json.dumps(value),ROW,IMAGES)
        self.assertEqual(result['image_metadata'][1]['timepoint'],'unknown')
        self.assertEqual(result['observations'][0]['status'],'hypothesis')

    def test_projection_never_exposes_first_choice_or_choice_claim(self):
        result=parse_first_read(json.dumps(first()),ROW,IMAGES)
        result['observations'].append({'value':'My first answer is A.','status':'hypothesis'})
        projected=observation_projection(result)
        self.assertNotIn('first_answer',projected)
        self.assertEqual(len(projected['observations']),1)
        self.assertEqual(projected['discriminators'][0]['option_labels'],['A','B','C'])

    def test_final_may_choose_third_option_and_records_missing_checks(self):
        raw={'answer':'C','uncertain':True,'observations':[],
             'option_checks':[{'option':'C','support':[],'conflict':[],'unknown':['scale']}],'missing_evidence':['scale']}
        result=parse_final(json.dumps(raw),ROW,['image:1'])
        self.assertEqual(result['answer'],'C')
        self.assertEqual(result['missing_option_checks'],['A','B'])

    def test_action_limit_unknown_tool_and_same_object_binding(self):
        good={'kind':'visual','image_id':'image:1','image_ids':['image:1','image:2'],
              'question':'Is the same nodule larger?','expected_attribute':'relative size','comparison_object':'same nodule'}
        result=parse_action_plan(json.dumps({'actions':[good]}),IMAGES,[])
        self.assertEqual(result['actions'][0]['image_ids'],['image:1','image:2'])
        bad=dict(good,comparison_object='')
        self.assertEqual(parse_action_plan(json.dumps({'actions':[bad]}),IMAGES,[])['actions'],[])
        with self.assertRaisesRegex(ValueError,'action_budget_exceeded'):
            parse_action_plan(json.dumps({'actions':[good,good,good]}),IMAGES,[])

    def test_nested_error_and_single_word_are_not_evidence(self):
        self.assertEqual(classify_tool_return({'status':'hypothesis','result':[{'error':'CUDA out of memory'}]})['evidence_kind'],'execution_error')
        for value in ['No','Not matched','pneumothorax',{'answer':'No','status':'completed'}]:
            self.assertFalse(classify_tool_return(value)['usable'])
        self.assertEqual(classify_tool_return({'phrase':'gastric bubble','box':[.1,.2,.3,.4]})['reason'],
                         'conditional_localization_requires_pixel_verification_not_presence_proof')

    def test_targeted_read_accepts_pixels_but_rejects_answer(self):
        raw={'candidate_answer':'C','observations':[{'attribute':'border','value':'Boundary is unresolved.',
             'status':'unresolved','evidence_refs':['image:1']}],'hypotheses':[],'uncertainties':['resolution']}
        result=parse_targeted_read(json.dumps(raw),ROW,IMAGES)
        self.assertEqual(result['observations'][0]['status'],'unresolved')
        self.assertEqual(result['candidate_answer'],'C')
        self.assertNotIn('candidate_answer',observation_projection(result))
        raw['answer']='C'
        with self.assertRaisesRegex(ValueError,'contains_answer_selection'):
            parse_targeted_read(json.dumps(raw),ROW,IMAGES)

    def test_bad_targeted_candidate_does_not_erase_valid_observations(self):
        raw={'candidate_answer':'Z','observations':[{'attribute':'size','value':'Size comparison is unresolved.',
             'status':'unresolved','evidence_refs':['image:1']}],'hypotheses':[],'uncertainties':['scale']}
        result=parse_targeted_read(json.dumps(raw),ROW,IMAGES)
        self.assertIsNone(result['candidate_answer'])
        self.assertEqual(len(result['observations']),1)
        self.assertIn('targeted_candidate_missing_or_invalid',result['parse_warnings'])

    def test_classification_scores_are_only_hypotheses(self):
        result=classify_tool_return({'scores':{'pneumothorax':.9,'effusion':.1}})
        self.assertTrue(result['usable'])
        self.assertEqual(result['evidence_kind'],'hypothesis')
        self.assertEqual(result['reason'],'class_scores_cannot_establish_presence_size_or_change')

    def test_tool_args_survive_for_execution_schema_validation(self):
        action={'kind':'tool','image_id':'image:1','tool':'xray_phrase_grounding',
                'question':'Where is the visible left apex?','expected_attribute':'location',
                'tool_args':{'phrase':'left apex','image_path':'some-path'}}
        parsed=parse_action_plan(json.dumps({'actions':[action]}),IMAGES,['xray_phrase_grounding'])
        self.assertEqual(parsed['actions'][0]['tool_args']['phrase'],'left apex')

    def test_images_retain_figure_labels_and_require_parent_and_size(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'figures/1').mkdir(parents=True)
            for path in ROW['images']:Image.new('RGB',(50,60),'black').save(root/path)
            images=build_images(ROW,root)
            self.assertEqual(images[1]['figure_label'],'Figure 7b')
            content=multimodal_content({'question':ROW['question']},images)
            self.assertTrue(content[2]['image_url']['url'].startswith('data:image/jpeg;base64,'))
            crop=root/'crop.png';Image.new('RGB',(20,20),'black').save(crop)
            with self.assertRaisesRegex(ValueError,'crop_parent_original_missing'):
                multimodal_content({},images,[{'image_id':'crop:1','path':str(crop),'parent_image_id':'missing'}])
            Image.new('RGB',(5,20),'black').save(crop)
            with self.assertRaisesRegex(ValueError,'image_below_model_minimum'):
                multimodal_content({},images,[{'image_id':'crop:1','path':str(crop),'parent_image_id':'image:1'}])


if __name__=='__main__':unittest.main()
