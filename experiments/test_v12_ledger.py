"""Small synthetic-only tests for the user-authorized V12 ledger change."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from provider_ledger import BudgetExceeded, LedgerIntegrityError, LedgerLocked, _digest
from provider_profile import get_profile
from v12_ledger import V12ProviderLedger


class V12LedgerTests(unittest.TestCase):
    def ledger(self,directory,**kwargs):
        return V12ProviderLedger(Path(directory)/'ledger.json',get_profile('qwen3-vl-plus'),**kwargs)

    def test_unchanged_and_reformatted_bytes_do_not_stop_accounting(self):
        with tempfile.TemporaryDirectory() as directory, self.ledger(directory) as ledger:
            before=ledger.remaining
            self.assertEqual(ledger.remaining,before)
            ledger.path.write_text(json.dumps(ledger._state,sort_keys=True,separators=(',',':')),encoding='utf-8')
            self.assertEqual(ledger.remaining,before)
            reservation=ledger.reserve(request_id='synthetic:one',estimated_input_tokens=100,max_output_tokens=20)
            settled=ledger.settle(reservation,usage={'prompt_tokens':90,'completion_tokens':10})
            self.assertEqual(settled['status'],'settled')
            self.assertLess(ledger.remaining,before)

    def test_original_lock_rejects_second_writer(self):
        with tempfile.TemporaryDirectory() as directory, self.ledger(directory):
            with self.assertRaises(LedgerLocked):
                self.ledger(directory)

    def test_original_budget_still_rejects_excess_reservation(self):
        with tempfile.TemporaryDirectory() as directory, self.ledger(directory,cap_cny='0.000001') as ledger:
            with self.assertRaises(BudgetExceeded):
                ledger.reserve(request_id='synthetic:over-cap',estimated_input_tokens=100,max_output_tokens=20)
            self.assertEqual(ledger._state['reservations'],[])

    def test_original_monetary_validation_remains_enabled(self):
        with tempfile.TemporaryDirectory() as directory, self.ledger(directory) as ledger:
            invalid=deepcopy(ledger._state)
            invalid['committed_cny']='1'
            invalid.pop('integrity_sha256')
            invalid['integrity_sha256']=_digest(invalid)
            with self.assertRaisesRegex(LedgerIntegrityError,'total does not reconcile'):
                ledger._validate(invalid)


if __name__=='__main__':unittest.main()
