"""Targeted V12 retrieval contract tests; invented questions only, no API/labels."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from v12_retrieval import (V12Retriever, projected_query, compatible_images,
                          verified_step_benefit, population_from_conditions)


def example(mod='CXR'):
    row={'question_id':'synthetic_current','question':'A 61 years old adult has a pulmonary nodule. Compare Figure 1 and Figure 3.\nA. Nodule with calcification\nB. Nodule without calcification',
         'official_group':'classification,comparison,diagnosis,reasoning'}
    images=[{'image_id':'image:1','path':'/synthetic/figure_1.png','source_filename':'figure_1.png','figure_label':'Figure 1','modality':'unknown'},
            {'image_id':'image:2','path':'/synthetic/figure_3.png','source_filename':'figure_3.png','figure_label':'Figure 3','modality':'unknown'}]
    read={'patient_conditions':[{'name':'age','value':'61 years','source_quote':'61 years'}],
          'image_metadata':[{'image_id':i['image_id'],'modality':mod,'anatomy':'lung'} for i in images],
          'observations':[{'attribute':'morphology','value':'A rounded pulmonary opacity is visible','status':'observed_present','evidence_refs':['image:1']}],
          'hypotheses':[{'hypothesis':'Benign nodule','status':'hypothesis'}],
          'discriminators':[{'attribute':'location','question':'Is the nodule in the lung or chest wall?','image_ids':['image:1'],'option_labels':['A','B']},
                            {'attribute':'comparison','question':'Has its appearance changed between the supplied views?','image_ids':['image:1','image:2'],'option_labels':['A','B'],'comparison_object':'same pulmonary nodule'},
                            {'attribute':'morphology','question':'Is central calcification present within the pulmonary nodule?','image_ids':['image:2'],'option_labels':['A','B']}],
          'uncertainties':['Its etiology remains unresolved']}
    return row,read,images


class QueryContract(unittest.TestCase):
    def test_retains_all_roles_and_third_discriminator(self):
        row,read,images=example('CT')
        q=projected_query(row,read,images)
        self.assertEqual(q['full_question'],row['question'])
        self.assertEqual(len(q['options']),2)
        self.assertEqual(len(q['discriminators']),3)
        self.assertEqual(q['discriminators'][1]['comparison_object'],'same pulmonary nodule')
        self.assertIn('central calcification',q['full_role_query_text'])
        self.assertTrue(q['visible_evidence']);self.assertTrue(q['candidate_hypotheses'])
        self.assertEqual(q['modality'],'ct');self.assertEqual(q['population'],'adult')

    def test_first_answer_is_not_a_retrieval_input(self):
        row,read,images=example();read['first_answer']='A'
        with self.assertRaisesRegex(ValueError,'must_not_receive'):projected_query(row,read,images)

    def test_unknown_errors_and_diagnosis_not_upgraded_to_observed(self):
        row,read,images=example()
        read['observations'] += [
            {'attribute':'finding','value':'No','status':'observed_absent','evidence_refs':['image:1']},
            {'attribute':'finding','value':'CUDA out of memory','status':'observed_absent','evidence_refs':['image:1']},
            {'attribute':'diagnosis','value':'Bacterial pneumonia','status':'observed_present','evidence_refs':['image:1']},
            {'attribute':'margin','value':'Margin cannot be resolved','status':'unresolved','evidence_refs':['image:1']},
            {'attribute':'presence','value':'No visible peripheral line on this supplied image','status':'observed_absent','evidence_refs':['image:1']}]
        q=projected_query(row,read,images)
        self.assertEqual(len(q['visible_evidence']),2)
        self.assertEqual(q['visible_evidence'][-1]['status'],'observed_absent')
        self.assertTrue(any('Bacterial pneumonia' in v for v in q['candidate_hypotheses']))
        self.assertTrue(any('Margin cannot' in v for v in q['candidate_hypotheses']))

    def test_patient_information_requires_a_stem_quote(self):
        row,read,images=example()
        read['patient_conditions'] += [{'name':'immunity','value':'immunocompromised','source_quote':'not provided'},
                                       {'name':'diagnosis','value':'Nodule with calcification','source_quote':'Nodule with calcification'}]
        q=projected_query(row,read,images)
        self.assertEqual(len(q['patient_conditions']),1)
        self.assertEqual(population_from_conditions([]),'unknown')

    def test_actual_ct_and_nonchest_xray_exclude_chest_tools(self):
        for m in ['CT','Xray','unknown']:
            row,read,images=example(m);registry=projected_query(row,read,images)['image_registry']
            self.assertEqual(compatible_images('chest_xray_report_generator',registry),[])
            self.assertTrue(compatible_images('image_visualizer',registry))

    def test_no_step_credit_from_final_success_or_bare_number(self):
        self.assertIsNone(verified_step_benefit({'step_credit':1,'execution':'returned_valid','task_outcome':'correct'}))
        value=verified_step_benefit({'step_credit':.2,'step_credit_verified':True,'step_credit_evidence':['training_delta:1']})
        self.assertEqual(value['value'],.2)


class RetrievalContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=HERE.parent/'local_assets/MedRAX_Knowledge_Pack_v8/retrieval/core.py'
        if not path.exists():
            path=HERE.parent/'reports/history/assets/knowledge_pack/retrieval/core.py'
        spec=importlib.util.spec_from_file_location('v12_test_core',path)
        cls.core=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.core)

    def retriever(self):
        import numpy as np
        obj=object.__new__(V12Retriever);obj.core=self.core;obj.max_chars=8000;obj.top_k=2
        obj.boundary={'synthetic_current':{'split':'validation','case_hash':'current'},'training_1':{'split':'memory_train','case_hash':'training'}}
        obj.b_documents=['Pulmonary nodule morphology and location']
        obj.b_index=self.core.BM25(obj.b_documents)
        obj.records=[{'memory_id':'train_action','source_question_id':'training_1','task_outcome':'correct','steps':[
            {'step_id':1,'tool_name':'chest_xray_report_generator','execution':'returned_valid','step_credit':None},
            {'step_id':2,'tool_name':'llava_med_qa','execution':'returned_valid','step_credit':None}]}]
        obj.cards=[self.core.canonical_card({'knowledge_id':'ct_nodule','source_id':'source_ct','modality':['CT'],
                    'task_scope':['description','diagnosis'],'summary_en':'Central calcification within a pulmonary nodule can be a discriminating feature.',
                    'required_patient_evidence':['Visible internal calcification in the pulmonary nodule on CT'],
                    'limitations':['No calibrated size can be inferred'],'source_pages':['1']}),
                   self.core.canonical_card({'knowledge_id':'cxr_line','source_id':'source_cxr','modality':['CXR'],
                    'task_scope':['detection'],'summary_en':'A pleural line without peripheral markings requires image inspection.',
                    'required_patient_evidence':['Pleural line'],'source_pages':['2']}),
                   self.core.canonical_card({'knowledge_id':'unrelated','source_id':'source_other','modality':['CT'],
                    'task_scope':['diagnosis'],'summary_en':'A renal collecting system calculus requires a urinary tract examination.',
                    'required_patient_evidence':['Urinary tract calculus'],'source_pages':['3']})]
        obj.vectors=np.array([[1.,0.],[1.,0.],[1.,0.]])
        class FakeEncoder:
            def encode(self,texts):
                self.last_texts=texts
                return np.array([[1.,0.] for _ in texts])
        obj.encoder=FakeEncoder();obj.index_dir=Path(tempfile.gettempdir())/'no_v12_test_source_documents'
        return obj

    def test_group_a_does_not_retrieve_knowledge_or_experience(self):
        r=self.retriever();row,read,images=example()
        def unexpected(*a):raise AssertionError('A must not access K/E')
        r._knowledge_v12=unexpected;r._experience_v12=unexpected
        result=r.retrieve(row,read,images,['llava_med_qa'],'A')
        self.assertEqual(result['k_ids'],[]);self.assertEqual(result['action_suggestions'],[])

    def test_ct_k_retrieval_keeps_late_discriminator_and_rejects_unrelated(self):
        r=self.retriever();row,read,images=example('CT')
        read['uncertainties']=['unresolved context '+('detail '*400)]
        q=projected_query(row,read,images)
        block,ids,audit=r._knowledge_v12(q)
        self.assertEqual(ids,['ct_nodule']);self.assertIn('central calcification',block)
        self.assertNotIn('cxr_line',ids);self.assertNotIn('unrelated',ids)
        self.assertGreater(audit['dense_chunk_count'],1)
        self.assertIn('detail',' '.join(r.encoder.last_texts))

    def test_experience_uses_capability_not_first_tool_name(self):
        r=self.retriever();row,read,images=example()
        q=projected_query(row,read,images)
        block,ids,audit,actions=r._experience_v12(row,q,['chest_xray_report_generator','llava_med_qa'])
        self.assertTrue(actions);self.assertEqual(actions[0]['tool'],'llava_med_qa')
        self.assertIsNone(actions[0]['step_credit'])
        self.assertIn('specific_question',actions[0]);self.assertIn('target_image_ids',actions[0])
        self.assertIn('modality_and_capability_match',actions[0]['selection_basis'])

    def test_ct_experience_never_suggests_cxr_report(self):
        r=self.retriever();row,read,images=example('CT')
        q=projected_query(row,read,images)
        _,_,_,actions=r._experience_v12(row,q,['chest_xray_report_generator','llava_med_qa'])
        self.assertTrue(actions)
        self.assertTrue(all(a['tool']=='llava_med_qa' for a in actions))

    def test_no_related_card_returns_empty(self):
        r=self.retriever();row,read,images=example('CT')
        read['discriminators']=[{'attribute':'texture','question':'Does the invented zirconium lattice contain hexagonal nodes?','image_ids':['image:1']}]
        q=projected_query(row,read,images)
        block,ids,audit=r._knowledge_v12(q)
        self.assertEqual(block,'');self.assertEqual(ids,[]);self.assertTrue(audit['abstained'])

    def test_duplicate_knowledge_does_not_displace_complementary_rule(self):
        import numpy as np
        r=self.retriever();row,read,images=example('CT')
        first=r.cards[0]
        duplicate={**first,'knowledge_id':'calcification_copy','source_id':'another_source'}
        complementary=self.core.canonical_card({'knowledge_id':'interval_change','source_id':first['source_id'],
            'modality':['CT'],'task_scope':['comparison'],
            'summary_en':'Interval change in the pulmonary nodule should be determined on corresponding images.',
            'required_patient_evidence':['Change between matched initial and follow-up appearances'],
            'source_pages':['4']})
        r.cards=[first,duplicate,complementary];r.vectors=np.array([[1.,0.]]*3)
        read['discriminators'].append({'attribute':'comparison','question':'Does interval change occur in the pulmonary nodule on corresponding images?',
                                       'image_ids':['image:1','image:2']})
        q=projected_query(row,read,images)
        with patch.object(r.core,'retrieve',return_value={'hits':[{'knowledge_card':c} for c in r.cards],'rejected':[]}):
            _,ids,audit=r._knowledge_v12(q)
        self.assertEqual(ids,['ct_nodule','interval_change'])
        self.assertTrue(any('duplicate_rule_or_required_observation' in item['reasons'] for item in audit['rejected']))

    def test_repeated_action_or_tool_switch_does_not_displace_new_goal(self):
        r=self.retriever();row,read,images=example('CT')
        read['discriminators']=[read['discriminators'][0],dict(read['discriminators'][0]),read['discriminators'][2]]
        r.records[0]['steps']=[{'step_id':1,'tool_name':'llava_med_qa','execution':'returned_valid'},
                              {'step_id':2,'tool_name':'image_visualizer','execution':'returned_valid'}]
        q=projected_query(row,read,images)
        _,_,audit,actions=r._experience_v12(row,q,['llava_med_qa','image_visualizer'])
        self.assertEqual(len(actions),2)
        self.assertEqual(len({a['specific_question'] for a in actions}),2)
        self.assertTrue(any('duplicate_observation_goal_not_complementary' in item['reasons'] for item in audit['rejected']))

    def test_combined_context_is_one_rule_plus_one_action(self):
        r=self.retriever();row,read,images=example('CT')
        result=r.retrieve(row,read,images,['llava_med_qa','image_visualizer'],'B')
        self.assertEqual(result['combined_content_count'],2)
        self.assertEqual(len(result['k_ids']),1)
        self.assertEqual(len(result['action_suggestions']),1)
        self.assertEqual(len(result['e_audit']['selected_actions']),1)
        self.assertLessEqual(len(result['k_block'].splitlines())+len(result['e_block'].splitlines()),4)


if __name__=='__main__':unittest.main()
