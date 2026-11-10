"""Offline budget/accounting tests; no provider calls or billed usage."""
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from money_guard import (BudgetExceeded, BudgetIntegrityError, BudgetLimitExceeded,
                         LedgerLocked, MoneyGuard, MODEL, PRIOR_CNY, RESERVATION_CNY)


class MoneyGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "ledger.json"

    def tearDown(self):
        self.temp.cleanup()

    def load(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def rewrite_with_checksum(self, state):
        state.pop("integrity_sha256")
        raw = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        state["integrity_sha256"] = hashlib.sha256(raw.encode()).hexdigest()
        self.path.write_text(json.dumps(state), encoding="utf-8")

    def test_exact_decimal_prior_reservation_and_uncached_settlement(self):
        self.assertIs(BudgetLimitExceeded, BudgetExceeded)
        self.assertEqual(PRIOR_CNY, Decimal("0.54942"))
        self.assertEqual(RESERVATION_CNY, Decimal("2.60096"))
        with MoneyGuard(self.path) as guard:
            self.assertEqual(guard.remaining, Decimal("99.45058"))
            reservation = guard.reserve({"request_id": "fictional-1", "model": MODEL,
                                         "question_id": "offline_fixture", "arm": "B0", "phase": 1})
            self.assertEqual(guard.remaining, Decimal("96.84962"))
            result = guard.settle(reservation, {"prompt_tokens": 1000, "completion_tokens": 200,
                                                "prompt_tokens_details": {"cached_tokens": 1000}})
            self.assertEqual(result["charged_cny"], "0.036")
            self.assertEqual(result["released_cny"], "2.56496")
            self.assertEqual(guard.remaining, Decimal("99.41458"))
            self.assertFalse(result["provider_bill_amount"])
            self.assertEqual(self.load()["committed_cny"], "0.58542")

    def test_exact_cap_boundary_and_one_millionth_below(self):
        exact = PRIOR_CNY + RESERVATION_CNY
        with MoneyGuard(self.path, budget_cny=exact) as guard:
            reservation = guard.reserve(request_id="boundary", model=MODEL)
            self.assertEqual(guard.remaining, Decimal(0))
            with self.assertRaises(BudgetExceeded):
                guard.reserve(request_id="too-much")
            guard.settle(reservation, None)
        with MoneyGuard(self.path, budget_cny=exact) as guard:
            self.assertEqual(guard.remaining, Decimal(0))
            with self.assertRaises(BudgetExceeded):
                guard.reserve(request_id="still-too-much")
        other = self.path.with_name("lower.json")
        with MoneyGuard(other, budget_cny=exact - Decimal("0.000001")) as guard:
            with self.assertRaises(BudgetExceeded):
                guard.reserve(request_id="one-quantum-short")

    def test_callers_decimal_context_cannot_round_accounting(self):
        with localcontext() as context:
            context.prec = 4
            with MoneyGuard(self.path) as guard:
                reservation = guard.reserve(request_id="low-precision-caller")
                self.assertEqual(guard.remaining, Decimal("96.84962"))
                result = guard.settle(reservation, {"prompt_tokens": 1000, "completion_tokens": 200})
                self.assertEqual(result["charged_cny"], "0.036")
                self.assertEqual(guard.remaining, Decimal("99.41458"))

    def test_unknown_invalid_and_error_usage_never_refund(self):
        cases = [(None, {}), ({"prompt_tokens": 1}, {}),
                 ({"prompt_tokens": -1, "completion_tokens": 1}, {}),
                 ({"prompt_tokens": True, "completion_tokens": 1}, {}),
                 ({"prompt_tokens": 1, "completion_tokens": 1}, {"response_received": False}),
                 ({"prompt_tokens": 1, "completion_tokens": 1}, {"error_type": "TimeoutError"})]
        with MoneyGuard(self.path) as guard:
            for index, (usage, kwargs) in enumerate(cases):
                reservation = guard.reserve(request_id=f"unknown-{index}")
                result = guard.settle(reservation, usage, **kwargs)
                self.assertEqual(result["status"], "unknown")
                self.assertEqual(result["charged_cny"], "2.60096")
                self.assertEqual(result["released_cny"], "0")
                with self.assertRaises(BudgetIntegrityError):
                    guard.settle(reservation, {"prompt_tokens": 0, "completion_tokens": 0})

    def test_pending_crash_recovery_keeps_full_charge_and_request_identity(self):
        with MoneyGuard(self.path) as guard:
            reservation = guard.reserve(request_id="interrupted-call")
            remaining = guard.remaining
        with MoneyGuard(self.path) as guard:
            self.assertEqual(guard.remaining, remaining)
            self.assertEqual(self.load()["reservations"][0]["status"], "recovered_unknown")
            with self.assertRaises(BudgetIntegrityError):
                guard.settle(reservation, {"prompt_tokens": 1, "completion_tokens": 1})
            with self.assertRaises(BudgetIntegrityError):
                guard.reserve(request_id="interrupted-call")
        with MoneyGuard(self.path) as guard:
            self.assertEqual(guard.remaining, remaining)

    def test_process_exclusion_and_lock_release(self):
        code = (
            "import sys\nfrom money_guard import MoneyGuard, LedgerLocked\n"
            "try:\n    guard = MoneyGuard(sys.argv[1])\n"
            "except LedgerLocked:\n    sys.exit(0)\n"
            "else:\n    guard.close()\n    sys.exit(9)\n"
        )
        with MoneyGuard(self.path):
            with self.assertRaises(LedgerLocked):
                MoneyGuard(self.path)
            process = subprocess.run([sys.executable, "-B", "-c", code, str(self.path)],
                                     cwd=Path(__file__).parent, capture_output=True, text=True, timeout=15)
            self.assertEqual(process.returncode, 0, process.stderr)
        with MoneyGuard(self.path) as guard:
            self.assertEqual(guard.remaining, Decimal("99.45058"))

    def test_usage_overrun_is_persisted_and_cannot_reset_or_resume(self):
        with MoneyGuard(self.path) as guard:
            reservation = guard.reserve(request_id="provider-overrun")
            with self.assertRaises(BudgetIntegrityError) as caught:
                guard.settle(reservation, {"prompt_tokens": 5000001, "completion_tokens": 0})
            self.assertEqual(caught.exception.settlement["charged_cny"], "100.00002")
            self.assertEqual(guard.remaining, Decimal("-0.54944"))
            self.assertTrue(self.load()["blocked"])
            with self.assertRaises(BudgetIntegrityError):
                guard.reserve(request_id="must-not-call")
        with MoneyGuard(self.path) as guard:
            with self.assertRaises(BudgetIntegrityError):
                guard.reserve(request_id="restart-must-not-call")
        with self.assertRaises(ValueError):
            MoneyGuard(self.path, initial_spent_cny="0")
        with self.assertRaises(ValueError):
            MoneyGuard(self.path, budget_cny="101")

    def test_token_bound_violation_blocks_even_below_money_reservation(self):
        with MoneyGuard(self.path) as guard:
            reservation = guard.reserve(request_id="output-bound-broken")
            with self.assertRaises(BudgetIntegrityError) as caught:
                guard.settle(reservation, {"prompt_tokens": 0, "completion_tokens": 513})
            self.assertEqual(caught.exception.settlement["charged_cny"], "2.60096")
            self.assertTrue(self.load()["blocked"])

    def test_policy_freeze_metadata_hygiene_and_duplicate_settlement(self):
        with MoneyGuard(self.path) as guard:
            policy = guard.policy_snapshot()
            policy["budget_cny"] = "0"
            self.assertEqual(guard.policy["budget_cny"], "100")
            for metadata in ({"api_key": "secret"}, {"prompt": "body"}, {"tag": "Bearer secret"},
                             {"tag": {"nested": "body"}}):
                with self.assertRaises(ValueError):
                    guard.reserve(metadata, request_id="unsafe")
            with self.assertRaises(BudgetIntegrityError):
                guard.reserve(request_id="underestimate", max_input_tokens=1000)
            with self.assertRaises(BudgetIntegrityError):
                guard.reserve(request_id="wrong-model", model="other-model")
            reservation = guard.reserve(request_id="once")
            guard.settle(reservation, {"prompt_tokens": 1, "completion_tokens": 1})
            with self.assertRaises(BudgetIntegrityError):
                guard.reserve(request_id="once")
            with self.assertRaises(BudgetIntegrityError):
                guard.settle(reservation, {"prompt_tokens": 0, "completion_tokens": 0})
        with self.assertRaises(BudgetIntegrityError):
            MoneyGuard(self.path, budget_cny="99")
        with self.assertRaises(ValueError):
            MoneyGuard(self.path, cny_per_usd="7.3")
        with self.assertRaises(ValueError):
            MoneyGuard(self.path, budget_cny=100.0)

    def test_tampering_is_detected_on_live_reads_and_reopen(self):
        with MoneyGuard(self.path) as guard:
            guard.reserve(request_id="preserve-this-debit")
            state = self.load()
            state["committed_cny"] = "0"
            self.path.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaises(BudgetIntegrityError):
                _ = guard.remaining
            with self.assertRaises(BudgetIntegrityError):
                guard.reserve(request_id="cannot-ignore-tamper")
        with self.assertRaises(BudgetIntegrityError):
            MoneyGuard(self.path)
        self.rewrite_with_checksum(state)
        with self.assertRaises(BudgetIntegrityError):
            MoneyGuard(self.path)

    def test_failed_atomic_settlement_retains_prepaid_amount_on_restart(self):
        with MoneyGuard(self.path) as guard:
            reservation = guard.reserve(request_id="persist-failure")
            before = self.path.read_bytes()
            with patch("money_guard.os.replace", side_effect=OSError("fictional disk error")):
                with self.assertRaises(BudgetIntegrityError):
                    guard.settle(reservation, {"prompt_tokens": 1, "completion_tokens": 1})
            self.assertEqual(self.path.read_bytes(), before)
            with self.assertRaises(BudgetIntegrityError):
                guard.reserve(request_id="no-call-after-persistence-failure")
        with MoneyGuard(self.path) as guard:
            self.assertEqual(guard.remaining, Decimal("96.84962"))
            self.assertEqual(self.load()["reservations"][0]["status"], "recovered_unknown")

    def test_malformed_existing_ledger_never_reinitialized(self):
        self.path.write_text('{"broken":', encoding="utf-8")
        before = self.path.read_bytes()
        with self.assertRaises(BudgetIntegrityError):
            MoneyGuard(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_deleted_or_replaced_ledger_cannot_reset_spending(self):
        with MoneyGuard(self.path) as guard:
            guard.reserve(request_id="debit-before-deletion")
        original = self.path.read_bytes()
        self.path.unlink()
        with self.assertRaises(BudgetIntegrityError):
            MoneyGuard(self.path)
        self.assertFalse(self.path.exists())
        replacement = self.path.with_name("replacement.json")
        with MoneyGuard(replacement):
            pass
        self.path.write_bytes(replacement.read_bytes())
        with self.assertRaises(BudgetIntegrityError):
            MoneyGuard(self.path)
        self.path.write_bytes(original)
        with MoneyGuard(self.path) as guard:
            self.assertEqual(guard.remaining, Decimal("96.84962"))


if __name__ == "__main__":
    unittest.main()
