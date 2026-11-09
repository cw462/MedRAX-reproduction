"""Two existing 512-output ledger blocks for ONE <=1024-output API request.

Wrap an already-open MoneyGuard on the original ledger; this module never opens,
resets, replaces, or edits that ledger directly. A successful reserve means both
blocks have been durably reserved. Only then may the caller send one API request.
The provider model must separately be configured with max_tokens=1024 and no
retries. These are conservative accounting amounts, not provider bill amounts.

Usage::

    with MoneyGuard(existing_ledger) as base:
        guard = ChunkedBudgetGuard(base, max_output_tokens=1024)
        token = guard.reserve(metadata={"request_id": stable_request_id})
        # Send exactly one model request, then always settle (None on any error).
        guard.settle(token, usage=complete_usage_or_none)

policy_snapshot() deliberately preserves the existing ledger's frozen policy.
Also freeze chunk_policy_snapshot() in the caller's experiment manifest. Never
count the two ledger entries as two API requests. Pending blocks survive crashes
at full value through MoneyGuard's existing recovery and identity protections.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, localcontext
import hashlib
import re
import uuid

from money_guard import (BudgetExceeded, BudgetIntegrityError, BudgetLimitExceeded,
                         MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS, MODEL, MoneyGuard,
                         RESERVATION_CNY, _metadata, _usage)

LOGICAL_MAX_OUTPUT_TOKENS = 1024
BLOCKS_PER_REQUEST = 2
_RESERVED_METADATA = {"logical_request_id", "logical_reservation_id", "reservation_part",
                      "reservation_parts", "accounting_unit", "provider_response_shared",
                      "effective_max_output_tokens"}


def _amount(value):
    with localcontext() as context:
        context.prec = 80
        return format(Decimal(value).normalize(), "f")


def _sum_amount(blocks, field):
    with localcontext() as context:
        context.prec = 80
        return _amount(sum((Decimal(item[field]) for item in blocks), Decimal(0)))


class ChunkedBudgetGuard:
    """An adapter, not a separate ledger or lock owner.

    Keep the supplied MoneyGuard context alive for the complete run. The legacy
    reserve argument max_output_tokens=512 is accepted only for API compatibility;
    this adapter ALWAYS reserves two blocks and enforces a logical bound of 1024.
    A settlement/reservation integrity failure poisons this adapter for new calls.
    """

    def __init__(self, guard, *, max_output_tokens=LOGICAL_MAX_OUTPUT_TOKENS):
        if not isinstance(guard, MoneyGuard):
            raise TypeError("Wrap an existing locked MoneyGuard, never a path or a replacement ledger")
        if type(max_output_tokens) is not int or max_output_tokens != LOGICAL_MAX_OUTPUT_TOKENS:
            raise ValueError("The logical output bound is fixed at 1024")
        policy = guard.policy_snapshot()
        if (policy["model"] != MODEL or policy["max_input_tokens"] != MAX_INPUT_TOKENS or
                policy["max_output_tokens"] != MAX_OUTPUT_TOKENS or
                Decimal(policy["reservation_cny"]) != RESERVATION_CNY):
            raise BudgetIntegrityError("Underlying ledger is not the frozen 512-token-block policy")
        _ = guard.remaining  # Validate the live lock/disk state without changing it.
        self._guard = guard
        self._pending = {}
        self._blocked = False

    @property
    def remaining(self):
        return self._guard.remaining

    @property
    def policy(self):
        return self.policy_snapshot()

    def policy_snapshot(self):
        return self._guard.policy_snapshot()

    def chunk_policy_snapshot(self):
        return {
            "schema_version": 1, "accounting_unit": "reservation_block",
            "logical_api_requests_per_successful_reserve": 1,
            "reservation_blocks_per_request": BLOCKS_PER_REQUEST,
            "max_input_tokens": MAX_INPUT_TOKENS,
            "effective_max_output_tokens": LOGICAL_MAX_OUTPUT_TOKENS,
            "accepted_reserve_output_arguments": [MAX_OUTPUT_TOKENS, LOGICAL_MAX_OUTPUT_TOKENS],
            "block_max_input_tokens": MAX_INPUT_TOKENS,
            "block_max_output_tokens": MAX_OUTPUT_TOKENS,
            "block_reservation_cny": _amount(RESERVATION_CNY),
            "logical_reservation_cny": _sum_amount(
                [{"amount": str(RESERVATION_CNY)}] * BLOCKS_PER_REQUEST, "amount"),
            "known_usage_allocation": "all_input_in_part_1_output_first_512_then_remainder",
            "unknown_or_error": "both_blocks_charged_in_full",
            "second_reserve_failure": "part_1_charged_in_full_no_api_request",
            "overrun": "part_2_unknown_then_unsplit_usage_part_1_permanent_ledger_block",
            "provider_bill_amount": False, "provider_enforced_limit": False,
        }

    def _active(self):
        if self._blocked:
            raise BudgetIntegrityError("Chunked guard is blocked; stop all further model calls")

    def _summary(self, logical_id, request_id, blocks, *, status, logical_api_requests=1):
        return {
            "reservation_id": logical_id, "logical_request_id": request_id,
            "status": status, "currency": "CNY", "accounting_unit": "reservation_block",
            "logical_api_requests": logical_api_requests,
            "reservation_blocks": len(blocks), "expected_reservation_blocks": BLOCKS_PER_REQUEST,
            "effective_max_output_tokens": LOGICAL_MAX_OUTPUT_TOKENS,
            "charged_cny": _sum_amount(blocks, "charged_cny"),
            "released_cny": _sum_amount(blocks, "released_cny"),
            "remaining_cny": _amount(self.remaining), "provider_bill_amount": False,
            "blocks": deepcopy(blocks),
        }

    def reserve(self, metadata=None, *, request_id=None, model=None,
                max_input_tokens=MAX_INPUT_TOKENS, max_output_tokens=MAX_OUTPUT_TOKENS):
        self._active()
        clean = _metadata(metadata)
        request_id = clean.get("request_id") if request_id is None else request_id
        model = clean.get("model", MODEL) if model is None else model
        if (model != MODEL or clean.get("model", model) != model or
                clean.get("request_id", request_id) != request_id or
                type(max_input_tokens) is not int or max_input_tokens != MAX_INPUT_TOKENS or
                type(max_output_tokens) is not int or max_output_tokens not in
                (MAX_OUTPUT_TOKENS, LOGICAL_MAX_OUTPUT_TOKENS)):
            raise BudgetIntegrityError("Call model/token bounds differ from the fixed logical policy")
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,179}", request_id):
            raise ValueError("A stable non-secret logical request_id is required")
        if _RESERVED_METADATA.intersection(clean):
            raise ValueError("Chunk accounting metadata fields are reserved by this adapter")
        logical_id = uuid.uuid4().hex
        identity = hashlib.sha256(request_id.encode("utf-8")).hexdigest()
        block_metadata = []
        for part in (1, 2):
            block = dict(clean, request_id=f"chunked1024:{identity}:part{part}", model=MODEL,
                         logical_request_id=request_id, logical_reservation_id=logical_id,
                         reservation_part=part, reservation_parts=BLOCKS_PER_REQUEST,
                         accounting_unit="reservation_block", provider_response_shared=True,
                         effective_max_output_tokens=LOGICAL_MAX_OUTPUT_TOKENS)
            block_metadata.append(_metadata(block))  # Validate both before reserving either.
        first = None
        try:
            first = self._guard.reserve(metadata=block_metadata[0], model=MODEL,
                                        max_input_tokens=MAX_INPUT_TOKENS, max_output_tokens=MAX_OUTPUT_TOKENS)
            second = self._guard.reserve(metadata=block_metadata[1], model=MODEL,
                                         max_input_tokens=MAX_INPUT_TOKENS, max_output_tokens=MAX_OUTPUT_TOKENS)
        except BaseException as exc:
            self._blocked = True
            if first is not None:
                try:
                    settlement = self._guard.settle(first, None, response_received=False,
                                                    error_type="before_send_blocked")
                    exc.settlement = self._summary(logical_id, request_id, [settlement],
                                                   status="before_send_blocked", logical_api_requests=0)
                except BaseException:
                    # Pending is already fully reserved and survives restart. Do
                    # not replace the original reserve error or attempt refunds.
                    pass
            raise
        self._pending[logical_id] = {"request_id": request_id, "blocks": [first, second]}
        return logical_id

    def settle(self, reservation, usage=None, *, response_received=True, error_type=None):
        self._active()
        if type(response_received) is not bool:
            raise ValueError("response_received must be a boolean")
        if error_type is not None and (not isinstance(error_type, str) or not re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_.]{0,127}", error_type)):
            raise ValueError("error_type must be a class name, never response/error text")
        if not isinstance(reservation, str) or reservation not in self._pending:
            self._blocked = True
            raise BudgetIntegrityError("Logical reservation absent or already settled; no duplicate refund")
        entry = self._pending.pop(reservation)
        first, second = entry["blocks"]
        used = _usage(usage) if response_received and error_type is None else None
        overrun = used is not None and (used["prompt_tokens"] > MAX_INPUT_TOKENS or
                                       used["completion_tokens"] > LOGICAL_MAX_OUTPUT_TOKENS)
        try:
            if overrun:
                # Preserve block 2 BEFORE the old guard becomes permanently
                # blocked. Do not split/clip a total-bound violation into valid
                # looking per-block usage. Its full original usage goes to part 1.
                second_result = self._guard.settle(second, None, response_received=response_received,
                                                    error_type="logical_token_bound_exceeded")
                try:
                    self._guard.settle(first, used, response_received=True)
                except BudgetIntegrityError as exc:
                    first_result = getattr(exc, "settlement", None)
                    if first_result is not None:
                        summary = self._summary(reservation, entry["request_id"],
                                                [first_result, second_result], status="overrun")
                        raise BudgetIntegrityError(
                            "Logical token bound exceeded; original ledger permanently blocked",
                            settlement=summary) from exc
                    raise
                raise BudgetIntegrityError("Underlying guard failed to block an unsplit token overrun")
            if used is None:
                allocations = [None, None]
            else:
                allocations = [
                    {"prompt_tokens": used["prompt_tokens"],
                     "completion_tokens": min(used["completion_tokens"], MAX_OUTPUT_TOKENS)},
                    {"prompt_tokens": 0,
                     "completion_tokens": max(0, used["completion_tokens"] - MAX_OUTPUT_TOKENS)},
                ]
            results = [self._guard.settle(block, allocated, response_received=response_received,
                                          error_type=error_type)
                       for block, allocated in zip((first, second), allocations)]
            return self._summary(reservation, entry["request_id"], results,
                                 status="unknown" if used is None else "settled")
        except BaseException:
            # If interrupted between settlements, the remaining pending block
            # retains its full charge. Never retry settlement or send another call.
            self._blocked = True
            raise
