"""Offline checks for metadata leakage, crossfit isolation, and missing training output."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from history_skills import clinical_record,history_block,retrieve,parse_reflection,folds_and_reflections,merge_skills


class Contracts(unittest.TestCase):
    def test_history_never_copies_diagnosis_or_forbidden_fields(self):
        policy={'risk_terms':['mass'],'diagnosis_overlap':{'stopwords':[]}}
        safe,flag=clinical_record({'age':'old','gender':'female','history':'A mediastinal mass','diagnosis':'mass diagnosis secret','title':'secret diagnosis','discussion':'gold'},policy)
        self.assertEqual(set(safe),{'age','gender','history'})
        self.assertNotIn('secret',history_block(safe));self.assertTrue(flag['flagged'])
        self.assertEqual(set(flag),{'flagged','rule_codes'})

    def test_history_rejects_extra_field(self):
        with self.assertRaises(ValueError):history_block({'age':'','gender':'','history':'','diagnosis':'leak'})

    def test_crossfit_cannot_use_target_patient_even_if_wrong_fold_tag(self):
        skill={'skill_id':'x','source_fold':'B','source_case_id':'target','trigger':'opacity','steps':['inspect opacity'],'category':'general'}
        with self.assertRaises(ValueError):retrieve({'question_id':'q','case_id':'target','question':'opacity'},['detection'],'A',{'A':[],'B':[skill]})

    def test_crossfit_retrieves_other_fold_without_reference(self):
        skill={'skill_id':'x','source_fold':'B','source_case_id':'other','trigger':'opacity','steps':['inspect opacity'],'category':'detection'}
        result=retrieve({'question_id':'q','case_id':'target','question':'opacity'},['detection'],'A',{'A':[],'B':[skill]})
        self.assertEqual([s['skill_id'] for s in result],['x'])

    def test_reflection_invalid_json_stays_unparsed(self):
        self.assertEqual(parse_reflection('bad',['detection'])['status'],'unparsed')
        self.assertIsNone(parse_reflection('bad',['detection'])['answer'])

    def test_reflection_cannot_emit_unapproved_category(self):
        data={'skills':[{'category':'diagnosis','trigger':'x','steps':['check boundaries']} ]}
        self.assertEqual(parse_reflection(json.dumps(data),['detection'])['status'],'unparsed')

    def test_empty_reflection_is_success_not_failure(self):
        self.assertEqual(parse_reflection('{"skills":[]}',[])['status'],'completed')

    def test_case_folds_and_reflection_sampling_deterministic(self):
        rows=[{'question_id':str(i),'case_id':str(i//4)} for i in range(396)]
        b={str(i):{'correct':i%4!=0} for i in range(396)}
        a=folds_and_reflections(rows,b);self.assertEqual(a,folds_and_reflections(rows,b))
        self.assertEqual(sum(v=='A' for v in a[0].values()),50)
        self.assertEqual(len(a[1]),99+297//3)

    def test_final_cap_respects_utility_before_id(self):
        skills=[{'skill_id':'a','utility':0,'trigger':'opacity','steps':['evaluate opacity']},{'skill_id':'z','utility':2,'trigger':'fracture','steps':['inspect cortical edges']}]
        kept,_=merge_skills(skills,1,utility_order=True);self.assertEqual(kept[0]['skill_id'],'z')


if __name__=='__main__':unittest.main()
