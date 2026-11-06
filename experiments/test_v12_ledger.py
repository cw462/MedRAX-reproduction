"""Small synthetic-only tests for the user-authorized V12 ledger change."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from threading import Barrier
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
from provider_ledger import BudgetExceeded, LedgerIntegrityError, LedgerLocked
from provider_profile import get_profile
from run_cxr_vqa_toolsets import PaidCalls, save
from v12_ledger import ConcurrentV12Ledger, LedgerSnapshotChanged, V12ProviderLedger


class V12LedgerTests(unittest.TestCase):
    def ledger(self,directory,**kwargs):
        return V12ProviderLedger(Path(directory)/'ledger.json',get_profile('qwen3-vl-plus'),**kwargs)

    def sqlite_ledger(self, directory, **kwargs):
        with self.ledger(directory, **kwargs) as ledger:
            path = ledger.path
        with closing(sqlite3.connect(path.with_suffix('.sqlite3'))) as db, db:
            db.execute('CREATE TABLE ledger_state (id INTEGER PRIMARY KEY, payload BLOB)')
            db.execute('INSERT INTO ledger_state VALUES (1, ?)', (path.read_bytes(),))
        path.unlink()
        return path

    def test_conflicting_reservations_do_not_overwrite_each_other(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.sqlite_ledger(directory)
            profile = get_profile('qwen3-vl-plus')
            kwargs = dict(estimated_input_tokens=100, max_output_tokens=20)
            with ConcurrentV12Ledger(path, profile) as first, ConcurrentV12Ledger(path, profile) as second:
                first.reserve(request_id='synthetic:one', **kwargs)
                with self.assertRaises(LedgerSnapshotChanged):
                    second.reserve(request_id='synthetic:two', **kwargs)
            with ConcurrentV12Ledger(path, profile) as ledger:
                self.assertEqual(ledger._state['reservations'][0]['status'], 'in_flight')
                with self.assertRaisesRegex(LedgerIntegrityError, 'already reserved'):
                    ledger.reserve(request_id='synthetic:one', **kwargs)

    def test_two_paid_calls_can_overlap_and_both_settle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inherited = root / 'parent.json'
            inherited.write_text(json.dumps(dict(committed_cny='0', ledger_id='a' * 32)), encoding='utf-8')
            path = self.sqlite_ledger(directory, inherit_ledger_path=inherited)
            barrier = Barrier(2, timeout=5)
            protocol = dict(experiment_id='fixture', model='qwen3-vl-plus', temperature=0,
                            top_p=1, max_output_tokens=2048)

            def fake_invoke(client, payload, folder):
                barrier.wait()
                raw = dict(model=protocol['model'], choices=[{'message': {'content': 'ok'}}],
                           usage={'prompt_tokens': 90, 'completion_tokens': 10})
                save(folder / 'response.json', raw)
                return raw

            def call(arm):
                paid = PaidCalls.__new__(PaidCalls)
                paid.cfg = dict(root=str(root), ledger=path.name, cap_cny='100', inherit_ledger=inherited.name)
                paid.protocol, paid.out, paid.parallel = protocol, root / 'run', True
                paid.profile, paid.client, paid.key = get_profile(protocol['model']), None, ''
                return paid.call({'question_id': 'fixture'}, arm, 1, [])

            with patch('run_cxr_vqa_toolsets.invoke', side_effect=fake_invoke), ThreadPoolExecutor(2) as pool:
                self.assertEqual(list(pool.map(call, ('O', 'M-R'))), ['ok', 'ok'])
            with ConcurrentV12Ledger(path, get_profile(protocol['model']), inherit_ledger_path=inherited) as ledger:
                self.assertEqual([r['status'] for r in ledger._state['reservations']], ['settled', 'settled'])
                self.assertEqual(ledger.remaining, Decimal('99.99904'))

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

    def test_stale_checksum_schema_and_total_do_not_block_open_or_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.ledger(directory):
                pass
            path=Path(directory)/'ledger.json'
            state=json.loads(path.read_text(encoding='utf-8'))
            state.update(integrity_sha256='stale',schema_version=999,
                         committed_cny='1',historical_extra_field='retained')
            path.write_text(json.dumps(state),encoding='utf-8')
            with self.ledger(directory) as ledger:
                # Opening uses the stored amount, without a full reconciliation.
                self.assertEqual(ledger.remaining,Decimal('99'))
                reservation=ledger.reserve(request_id='synthetic:one',estimated_input_tokens=100,
                                           max_output_tokens=20)
                result=ledger.settle(reservation,usage={'prompt_tokens':90,'completion_tokens':10})
                self.assertEqual(Decimal(result['charged_cny']),Decimal('.00048'))
                self.assertEqual(ledger.remaining,Decimal('100')-Decimal('.00048'))
            saved=json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(saved['schema_version'],999)
            self.assertEqual(saved['historical_extra_field'],'retained')

    def test_inherited_checksum_is_ignored_without_resetting_inherited_spend(self):
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory)/'parent.json'
            parent.write_text(json.dumps({'ledger_id':'a'*32,'committed_cny':'.02',
                                          'integrity_sha256':'stale'}),encoding='utf-8')
            with self.ledger(directory,inherit_ledger_path=parent,cap_cny='.025') as ledger:
                self.assertEqual(ledger.remaining,Decimal('.005'))
                with self.assertRaises(BudgetExceeded):
                    ledger.reserve(request_id='synthetic:excess',estimated_input_tokens=1000,
                                   max_output_tokens=100)

    def test_pending_recovery_and_duplicate_guard_remain_after_stale_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.ledger(directory) as ledger:
                ledger.reserve(request_id='synthetic:pending',estimated_input_tokens=100,
                               max_output_tokens=20)
                remaining=ledger.remaining
            path=Path(directory)/'ledger.json'
            state=json.loads(path.read_text(encoding='utf-8'));state['integrity_sha256']='stale'
            path.write_text(json.dumps(state),encoding='utf-8')
            with self.ledger(directory) as ledger:
                self.assertEqual(ledger.remaining,remaining)
                self.assertEqual(ledger._state['reservations'][0]['status'],'recovered_unknown')
                with self.assertRaisesRegex(LedgerIntegrityError,'already reserved'):
                    ledger.reserve(request_id='synthetic:pending',estimated_input_tokens=100,
                                   max_output_tokens=20)

    def test_identity_anchor_and_hard_token_ceiling_remain(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.ledger(directory) as ledger:
                with self.assertRaises(BudgetExceeded):
                    ledger.reserve(request_id='synthetic:too-large',estimated_input_tokens=32001,
                                   max_output_tokens=20)
                reservation=ledger.reserve(request_id='synthetic:overrun',estimated_input_tokens=100,
                                           max_output_tokens=20)
                with self.assertRaisesRegex(LedgerIntegrityError,'profile ceiling'):
                    ledger.settle(reservation,usage={'prompt_tokens':32001,'completion_tokens':10})
                with self.assertRaisesRegex(LedgerIntegrityError,'permanently blocked'):
                    ledger.reserve(request_id='synthetic:after-overrun',estimated_input_tokens=100,
                                   max_output_tokens=20)
            path=Path(directory)/'ledger.json'
            state=json.loads(path.read_text(encoding='utf-8'));state['ledger_id']='b'*32
            path.write_text(json.dumps(state),encoding='utf-8')
            with self.assertRaisesRegex(LedgerIntegrityError,'identity changed'):
                self.ledger(directory)


if __name__=='__main__':unittest.main()
