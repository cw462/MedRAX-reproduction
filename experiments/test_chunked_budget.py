"""Offline synthetic accounting tests; no provider requests or real usage."""
from decimal import Decimal, localcontext
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import money_guard
from chunked_budget import (BudgetExceeded, BudgetIntegrityError, ChunkedBudgetGuard,
                            LOGICAL_MAX_OUTPUT_TOKENS)
from money_guard import LedgerLocked, MoneyGuard, MODEL, PRIOR_CNY, RESERVATION_CNY


class ChunkedBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "existing-ledger.json"

    def tearDown(self):
        self.temp.cleanup()

    def state(self, path=None):
        return json.loads((self.path if path is None else path).read_text(encoding="utf-8"))

    def test_legacy_argument_reserves_two_blocks_for_one_logical_invocation(self):
        with MoneyGuard(self.path) as base:
            guard = ChunkedBudgetGuard(base, max_output_tokens=1024)
            reservation = guard.reserve(metadata={"request_id": "fictional-run:qid:1", "model": MODEL,
                                                   "question_id": "fictional-qid", "arm": "B0"},
                                        request_id="fictional-run:qid:1", model=MODEL,
                                        max_input_tokens=128000, max_output_tokens=512)
            self.assertEqual(guard.remaining, Decimal("94.24866"))
            entries = self.state()["reservations"]
            self.assertEqual(len(entries), 2)
            self.assertEqual([item["metadata"]["reservation_part"] for item in entries], [1, 2])
            self.assertTrue(all(item["status"] == "pending" for item in entries))
            for item in entries:
                self.assertEqual(item["metadata"]["logical_request_id"], "fictional-run:qid:1")
                self.assertEqual(item["metadata"]["logical_reservation_id"], reservation)
                self.assertEqual(item["metadata"]["effective_max_output_tokens"], 1024)
                self.assertEqual(item["metadata"]["accounting_unit"], "reservation_block")
                self.assertEqual(item["reserved_cny"], "2.60096")
            self.assertNotEqual(entries[0]["request_id"], entries[1]["request_id"])
            result = guard.settle(reservation, {"prompt_tokens": 1000, "completion_tokens": 1024})
            self.assertEqual(result["logical_api_requests"], 1)
            self.assertEqual(result["reservation_blocks"], 2)
            self.assertEqual(result["charged_cny"], "0.10192")
            self.assertEqual([block["charged_cny"] for block in result["blocks"]], ["0.06096", "0.04096"])
            self.assertEqual(guard.remaining, Decimal("99.34866"))
            self.assertFalse(result["provider_bill_amount"])
            entries = self.state()["reservations"]
            self.assertEqual(entries[0]["usage"], {"prompt_tokens": 1000, "completion_tokens": 512})
            self.assertEqual(entries[1]["usage"], {"prompt_tokens": 0, "completion_tokens": 512})

    def test_policy_delegation_preserves_old_policy_and_exposes_distinct_chunk_policy(self):
        with MoneyGuard(self.path) as base:
            guard = ChunkedBudgetGuard(base)
            self.assertEqual(guard.policy_snapshot(), base.policy_snapshot())
            self.assertEqual(guard.policy["max_output_tokens"], 512)
            self.assertEqual(guard.chunk_policy_snapshot()["effective_max_output_tokens"], 1024)
            self.assertEqual(guard.chunk_policy_snapshot()["logical_reservation_cny"], "5.20192")
            guard.policy["budget_cny"] = "0"
            guard.chunk_policy_snapshot()["effective_max_output_tokens"] = 999999
            self.assertEqual(guard.policy["budget_cny"], "100")
            self.assertEqual(guard.chunk_policy_snapshot()["effective_max_output_tokens"], 1024)
            with self.assertRaises(LedgerLocked): MoneyGuard(self.path)
        with self.assertRaises(BudgetIntegrityError): _ = guard.remaining
        with self.assertRaises(TypeError): ChunkedBudgetGuard(self.path)

    def test_complete_usage_allocates_input_once_at_output_boundaries(self):
        with MoneyGuard(self.path) as base:
            guard = ChunkedBudgetGuard(base)
            for count in (0, 511, 512, 513, LOGICAL_MAX_OUTPUT_TOKENS):
                reservation = guard.reserve(request_id=f"fictional-boundary-{count}", max_output_tokens=1024)
                result = guard.settle(reservation, {"prompt_tokens": 128000, "completion_tokens": count,
                                                     "prompt_tokens_details": {"cached_tokens": 128000}})
                self.assertEqual(Decimal(result["charged_cny"]), Decimal("2.56") + Decimal(count) * Decimal("0.00008"))
                first, second = self.state()["reservations"][-2:]
                self.assertEqual(first["usage"]["prompt_tokens"], 128000)
                self.assertEqual(second["usage"]["prompt_tokens"], 0)
                self.assertEqual(first["usage"]["completion_tokens"], min(512, count))
                self.assertEqual(second["usage"]["completion_tokens"], max(0, count - 512))
                self.assertTrue(first["response_received"] and second["response_received"])
                self.assertFalse(self.state()["blocked"])

    def test_unknown_incomplete_invalid_and_error_usage_keep_both_blocks_in_full(self):
        cases = [(None, {}), ({"prompt_tokens": 1}, {}),
                 ({"prompt_tokens": True, "completion_tokens": 1}, {}),
                 ({"prompt_tokens": -1, "completion_tokens": 1}, {}),
                 ({"prompt_tokens": 1, "completion_tokens": 1}, {"response_received": False}),
                 ({"prompt_tokens": 1, "completion_tokens": 1}, {"error_type": "TimeoutError"})]
        with MoneyGuard(self.path) as base:
            guard = ChunkedBudgetGuard(base)
            for index, (usage, kwargs) in enumerate(cases):
                reservation = guard.reserve(request_id=f"fictional-unknown-{index}")
                result = guard.settle(reservation, usage, **kwargs)
                self.assertEqual(result["status"], "unknown")
                self.assertEqual(result["charged_cny"], "5.20192")
                self.assertEqual(result["released_cny"], "0")
                for entry in self.state()["reservations"][-2:]:
                    self.assertEqual(entry["status"], "unknown")
                    self.assertIsNone(entry["usage"])

    def test_second_reserve_failure_never_authorizes_send_or_refunds_first_block(self):
        cap = PRIOR_CNY + RESERVATION_CNY
        with MoneyGuard(self.path, budget_cny=cap) as base:
            guard = ChunkedBudgetGuard(base)
            with self.assertRaises(BudgetExceeded) as caught:
                guard.reserve(request_id="fictional-only-one-block-fits")
            entries = self.state()["reservations"]
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["status"], "unknown")
            self.assertEqual(entries[0]["error_type"], "before_send_blocked")
            self.assertFalse(entries[0]["response_received"])
            self.assertEqual(entries[0]["charged_cny"], "2.60096")
            self.assertEqual(caught.exception.settlement["logical_api_requests"], 0)
            self.assertEqual(caught.exception.settlement["reservation_blocks"], 1)
            self.assertEqual(guard.remaining, Decimal(0))
            with self.assertRaises(BudgetIntegrityError): guard.reserve(request_id="fictional-no-send")
        with MoneyGuard(self.path, budget_cny=cap) as base:
            self.assertEqual(base.remaining, Decimal(0))
            with self.assertRaises(BudgetExceeded): base.reserve(request_id="fictional-still-no-funds")

    def test_exact_two_block_boundary_and_first_block_failure(self):
        exact = PRIOR_CNY + 2 * RESERVATION_CNY
        with MoneyGuard(self.path, budget_cny=exact) as base:
            guard = ChunkedBudgetGuard(base)
            reservation = guard.reserve(request_id="fictional-exact-two-blocks")
            self.assertEqual(guard.remaining, Decimal(0))
            self.assertEqual(guard.settle(reservation, None)["charged_cny"], "5.20192")
        other = self.path.with_name("no-block-fits.json")
        with MoneyGuard(other, budget_cny=PRIOR_CNY + RESERVATION_CNY - Decimal("0.000001")) as base:
            guard = ChunkedBudgetGuard(base)
            before = other.read_bytes()
            with self.assertRaises(BudgetExceeded): guard.reserve(request_id="fictional-no-block")
            self.assertEqual(other.read_bytes(), before)

    def test_total_overrun_is_unsplit_keeps_full_blocks_and_blocks_after_restart(self):
        for index, used in enumerate(({"prompt_tokens": 128001, "completion_tokens": 0},
                                      {"prompt_tokens": 0, "completion_tokens": 1025},
                                      {"prompt_tokens": 5000001, "completion_tokens": 0})):
            path = self.path.with_name(f"overrun-{index}.json")
            with self.subTest(usage=used):
                with MoneyGuard(path) as base:
                    guard = ChunkedBudgetGuard(base)
                    reservation = guard.reserve(request_id="fictional-overrun")
                    with self.assertRaises(BudgetIntegrityError) as caught:
                        guard.settle(reservation, used)
                    self.assertEqual(caught.exception.settlement["status"], "overrun")
                    self.assertGreaterEqual(Decimal(caught.exception.settlement["charged_cny"]), 2 * RESERVATION_CNY)
                    state = self.state(path)
                    self.assertTrue(state["blocked"])
                    first, second = state["reservations"]
                    self.assertEqual(first["status"], "overrun")
                    self.assertEqual(first["usage"], used)  # Never clip/split the total-bound violation.
                    self.assertEqual(second["status"], "unknown")
                    self.assertEqual(second["error_type"], "logical_token_bound_exceeded")
                    self.assertEqual(second["charged_cny"], "2.60096")
                    with self.assertRaises(BudgetIntegrityError): guard.reserve(request_id="fictional-no-next-call")
                    with self.assertRaises(BudgetIntegrityError): base.reserve(request_id="fictional-no-bypass")
                with MoneyGuard(path) as base:
                    guard = ChunkedBudgetGuard(base)
                    with self.assertRaises(BudgetIntegrityError): guard.reserve(request_id="fictional-no-restart")

    def test_pending_restart_keeps_both_charges_and_rejects_replayed_logical_request(self):
        with MoneyGuard(self.path) as base:
            guard = ChunkedBudgetGuard(base)
            token = guard.reserve(request_id="fictional-crash")
            remaining = guard.remaining
        with MoneyGuard(self.path) as base:
            guard = ChunkedBudgetGuard(base)
            self.assertEqual(guard.remaining, remaining)
            self.assertTrue(all(item["status"] == "recovered_unknown" for item in self.state()["reservations"]))
            with self.assertRaises(BudgetIntegrityError): guard.reserve(request_id="fictional-crash")
            self.assertEqual(len(self.state()["reservations"]), 2)
        with MoneyGuard(self.path) as base:
            guard = ChunkedBudgetGuard(base)
            with self.assertRaises(BudgetIntegrityError): guard.settle(token, {"prompt_tokens": 0, "completion_tokens": 0})
            self.assertEqual(base.remaining, remaining)

    def test_interrupted_second_settlement_keeps_pending_block_and_stops_adapter(self):
        with MoneyGuard(self.path) as base:
            guard = ChunkedBudgetGuard(base)
            token = guard.reserve(request_id="fictional-write-failure")
            original = money_guard.os.replace
            replacements = []

            def replace(source, destination):
                replacements.append(1)
                if len(replacements) == 2:
                    raise OSError("synthetic second-commit failure")
                return original(source, destination)

            with patch("money_guard.os.replace", side_effect=replace):
                with self.assertRaises(BudgetIntegrityError):
                    guard.settle(token, {"prompt_tokens": 1000, "completion_tokens": 1024})
            first, second = self.state()["reservations"]
            self.assertEqual(first["charged_cny"], "0.06096")
            self.assertEqual(second["status"], "pending")
            self.assertEqual(second["charged_cny"], "2.60096")
            with self.assertRaises(BudgetIntegrityError): guard.reserve(request_id="fictional-stop")
        with MoneyGuard(self.path) as base:
            self.assertEqual(self.state()["reservations"][1]["status"], "recovered_unknown")
            self.assertEqual(base.remaining, Decimal("96.78866"))

    def test_duplicate_settlement_and_request_cannot_release_or_send_twice(self):
        with MoneyGuard(self.path) as base:
            guard = ChunkedBudgetGuard(base)
            token = guard.reserve(request_id="fictional-once")
            guard.settle(token, {"prompt_tokens": 0, "completion_tokens": 0})
            before = self.path.read_bytes()
            with self.assertRaises(BudgetIntegrityError): guard.settle(token, {"prompt_tokens": 0, "completion_tokens": 0})
            self.assertEqual(self.path.read_bytes(), before)
            with self.assertRaises(BudgetIntegrityError): ChunkedBudgetGuard(base).reserve(request_id="fictional-once")
            self.assertEqual(self.path.read_bytes(), before)

    def test_rejects_unsafe_metadata_and_changed_bounds_before_any_reservation(self):
        with MoneyGuard(self.path) as base:
            guard = ChunkedBudgetGuard(base)
            for metadata in ({"api_key": "secret"}, {"request_id": "fictional", "reservation_part": 9},
                             {"request_id": "fictional", "tag": "Bearer secret"},
                             {"request_id": "fictional", "prompt": "text"}):
                with self.assertRaises(ValueError): guard.reserve(metadata=metadata)
            for kwargs in ({"max_input_tokens": 127999}, {"max_output_tokens": 2048},
                           {"max_output_tokens": True}, {"model": "different-model"}):
                with self.assertRaises(BudgetIntegrityError): guard.reserve(request_id="fictional", **kwargs)
            with self.assertRaises(ValueError): ChunkedBudgetGuard(base, max_output_tokens=512)
            self.assertEqual(self.state()["reservations"], [])
            token = guard.reserve(request_id="x" * 180)
            self.assertTrue(all(len(item["request_id"]) <= 180 for item in self.state()["reservations"]))
            guard.settle(token, None)

    def test_low_decimal_precision_does_not_round_logical_totals(self):
        with localcontext() as context:
            context.prec = 4
            with MoneyGuard(self.path) as base:
                guard = ChunkedBudgetGuard(base)
                token = guard.reserve(request_id="fictional-precision")
                result = guard.settle(token, {"prompt_tokens": 128000, "completion_tokens": 1024})
                self.assertEqual(result["charged_cny"], "2.64192")
                self.assertEqual(result["released_cny"], "2.56")
                self.assertEqual(guard.remaining, Decimal("96.80866"))


if __name__ == "__main__":
    unittest.main()
