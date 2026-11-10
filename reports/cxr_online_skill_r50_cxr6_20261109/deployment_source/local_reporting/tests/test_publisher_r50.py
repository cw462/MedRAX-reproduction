"""New publication scope and source-index isolation, no Git/remote operations."""
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'local_assets'))
import publish_cxr6_r50 as publisher
import finalize_r50_report as report


class PublicationRules(unittest.TestCase):
    def test_only_own_code_and_report_scope_admitted(self):
        self.assertEqual(publisher.allowed_path('experiments/r50_baseline_controls.py'),ROOT/'experiments/r50_baseline_controls.py')
        for path in ('data/vqarad_cxr/open_questions_for_later.jsonl','experiments/score_online_skill_r49.py',
          '.aris/IMPROVEMENT_STATE.json',publisher.REPORT_REL+'/../outside.json',
          publisher.REPORT_REL+'/model.safetensors',publisher.REPORT_REL+'/.secrets/private.txt'):
            with self.subTest(path=path),self.assertRaises(ValueError):publisher.allowed_path(path)

    def test_secret_literals_rejected_but_model_usage_retained(self):
        self.assertTrue(publisher.text_has_secret('sk-'+'a'*32))
        self.assertTrue(publisher.text_has_secret('{"api_key":"'+'opaque-secret-value'+'"}'))
        self.assertFalse(publisher.text_has_secret('{"total_tokens":123,"model":"qwen3.7-plus"}'))
        self.assertFalse(publisher.text_has_secret('{"api_key":"[REDACTED]"}'))

    def test_R50_index_replacement_preserves_unrelated_user_text(self):
        old='unrelated user text\n\n'+report.INDEX_START+'\nold\n'+report.INDEX_END+'\n\nother work\n'
        block=report.INDEX_START+'\nnew\n'+report.INDEX_END
        updated=report.replace_index_block(old,block)
        self.assertEqual(publisher.outside_index_block(old),publisher.outside_index_block(updated))
        self.assertIn('new',updated);self.assertNotIn('\nold\n',updated)


if __name__=='__main__':unittest.main()
