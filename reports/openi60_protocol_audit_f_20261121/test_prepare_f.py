"""Offline checks that F staging never selects cases using outcomes or prior memory."""
import json
from pathlib import Path
import tempfile
import unittest
from prepare_f import selected_template

ROOT=Path(__file__).resolve().parent
HISTORY=Path(__import__('os').environ.get('OPENI60_HISTORY', str(ROOT.parent/'OpenI60_M5_L1_20261121/autodl/raw/openi60_s20261121_fast')))


class SelectionTests(unittest.TestCase):
    def test_smoke_is_original_first_eight(self):
        frozen,template,ids=selected_template(HISTORY,8)
        self.assertEqual(ids,frozen['cohort']['selected_ids'][:8])
        self.assertEqual([row['question_id'] for row in template['inputs']],ids)
        self.assertEqual([row['question_id'] for row in template['order']],ids)
        self.assertEqual(set(template['reference_files']),set(ids))
    def test_formal_keeps_all_sixty_in_order(self):
        frozen,template,ids=selected_template(HISTORY,60)
        self.assertEqual(ids,frozen['cohort']['selected_ids'])
        self.assertEqual(len(template['inputs']),60)
    def test_inputs_contain_no_released_labels(self):
        frozen,template,ids=selected_template(HISTORY,60)
        forbidden={'answer','reference','feedback','correct','reward','source_label','terminal_raw'}
        for row in template['inputs']:
            self.assertFalse(set(row)&forbidden)
    def test_unsupported_count_is_rejected(self):
        with self.assertRaises(ValueError):selected_template(HISTORY,9)


if __name__=='__main__':unittest.main()
