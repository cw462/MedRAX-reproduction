"""Conservative CNY pre-call limit under caller-verified rates and token bounds.

This is not a provider-enforced billing cap or a statement of the actual bill.
Hold one MoneyGuard context for the entire run. Reserve before every network call;
settle with complete usage, or None after an error/unknown response. Pending calls
survive crashes at their full reservation. Existing ledgers cannot be reset here.
No networking, credentials, prompts, responses, or provider account data are used.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from functools import wraps
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import uuid

MODEL = "gpt-4o-2024-11-20"
MAX_INPUT_TOKENS = 128000
MAX_OUTPUT_TOKENS = 512
PRIOR_INPUT_TOKENS = 17995
PRIOR_OUTPUT_TOKENS = 2369
INPUT_USD_PER_MILLION = Decimal("2.5")
OUTPUT_USD_PER_MILLION = Decimal("10")
CNY_PER_USD = Decimal("8")
MAX_BUDGET_CNY = Decimal("100")
PRIOR_CNY = Decimal("0.54942")
RESERVATION_CNY = Decimal("2.60096")


def _exact(function):
    """Do not inherit a caller's low-precision Decimal context for accounting."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        with localcontext() as context:
            context.prec = 80
            return function(*args, **kwargs)
    return wrapped


class BudgetExceeded(RuntimeError):
    """Insufficient remaining conservative budget; do not make the API call."""


BudgetLimitExceeded = BudgetExceeded


class BudgetIntegrityError(RuntimeError):
    """Untrustworthy accounting state; stop all subsequent model calls."""
    def __init__(self, message, *, settlement=None):
        super().__init__(message)
        self.settlement = settlement


class LedgerLocked(BudgetIntegrityError):
    """Another process/context owns this ledger."""


def _decimal(value):
    if isinstance(value, (bool, float)):
        raise ValueError("Use a decimal string, integer, or Decimal for monetary values")
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid decimal amount") from exc
    if not result.is_finite():
        raise ValueError("Money must be finite")
    return result


@_exact
def _money(value):
    return format(_decimal(value).normalize(), "f")


@_exact
def _cost(prompt_tokens, completion_tokens):
    return (Decimal(prompt_tokens) * INPUT_USD_PER_MILLION +
            Decimal(completion_tokens) * OUTPUT_USD_PER_MILLION) * CNY_PER_USD / Decimal(1000000)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BudgetIntegrityError("Duplicate ledger JSON key")
        result[key] = value
    return result


def _metadata(value):
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > 32:
        raise ValueError("Metadata must be a small scalar-only dictionary")
    forbidden = {"api_key", "apikey", "password", "authorization", "secret", "access_token",
                 "refresh_token", "api_token", "headers", "prompt", "messages", "response",
                 "body", "content", "image_path", "base_url", "cookie", "credentials"}
    clean = {}
    for key, item in value.items():
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", key):
            raise ValueError("Invalid metadata key")
        if key.lower() in forbidden:
            raise ValueError("Do not put credentials, content, or paths in ledger metadata")
        if item is not None and not isinstance(item, (str, bool, int, float)):
            raise ValueError("Metadata values must be plain scalars")
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("Metadata numbers must be finite")
        if isinstance(item, str):
            if len(item) > 256 or any(char in item for char in "\r\n\x00"):
                raise ValueError("Metadata text must be a short identifier")
            if item.lower().startswith(("bearer ", "sk-", "sk_")):
                raise ValueError("Credential-like metadata is forbidden")
        clean[key] = item
    return clean


def _usage(value):
    if not isinstance(value, dict):
        return None
    fields = ("prompt_tokens", "completion_tokens")
    if any(type(value.get(key)) is not int or value[key] < 0 for key in fields):
        return None
    return {key: value[key] for key in fields}


class MoneyGuard:
    def __init__(self, path, *, budget_cny="100", initial_spent_cny="0.54942",
                 input_usd_per_million="2.5", output_usd_per_million="10", cny_per_usd="8",
                 model=MODEL, cap_cny=None, max_input_tokens=MAX_INPUT_TOKENS,
                 max_output_tokens=MAX_OUTPUT_TOKENS):
        if cap_cny is not None:
            if _decimal(budget_cny) != MAX_BUDGET_CNY and _decimal(budget_cny) != _decimal(cap_cny):
                raise ValueError("Conflicting budget arguments")
            budget_cny = cap_cny
        budget = _decimal(budget_cny)
        if not PRIOR_CNY <= budget <= MAX_BUDGET_CNY:
            raise ValueError("Budget must include prior spending and cannot exceed 100 CNY")
        if (model != MODEL or _decimal(initial_spent_cny) != PRIOR_CNY or
                _decimal(input_usd_per_million) != INPUT_USD_PER_MILLION or
                _decimal(output_usd_per_million) != OUTPUT_USD_PER_MILLION or
                _decimal(cny_per_usd) != CNY_PER_USD or
                type(max_input_tokens) is not int or max_input_tokens != MAX_INPUT_TOKENS or
                type(max_output_tokens) is not int or max_output_tokens != MAX_OUTPUT_TOKENS):
            raise ValueError("Model, rates, FX, prior charge, and full-context token bounds are frozen")
        self._policy = {
            "currency": "CNY", "budget_cny": _money(budget), "model": MODEL,
            "input_usd_per_million": _money(INPUT_USD_PER_MILLION),
            "output_usd_per_million": _money(OUTPUT_USD_PER_MILLION),
            "cny_per_usd": _money(CNY_PER_USD), "cached_input_charged_at_full_rate": True,
            "max_input_tokens": MAX_INPUT_TOKENS, "max_output_tokens": MAX_OUTPUT_TOKENS,
            "reservation_cny": _money(RESERVATION_CNY), "initial_spent_cny": _money(PRIOR_CNY),
            "initial_usage": {"prompt_tokens": PRIOR_INPUT_TOKENS,
                              "completion_tokens": PRIOR_OUTPUT_TOKENS},
            "price_basis": "caller_verified_apiyi_api_pricing_default_svip_group_1",
            "model_ratio": "1.25", "completion_ratio": "4", "quota_per_usd": 500000,
            "provider_enforced_limit": False,
        }
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._closed = True
        self._poisoned = False
        self._lock_handle = None
        self._disk_hash = None
        self._acquire_lock()
        try:
            anchor = self._read_anchor()
            if self.path.exists():
                raw = self.path.read_bytes()
                self._disk_hash = hashlib.sha256(raw).hexdigest()
                try:
                    state = json.loads(raw, object_pairs_hook=_unique_object)
                    self._validate(state)
                except BudgetIntegrityError:
                    raise
                except Exception as exc:
                    raise BudgetIntegrityError("Invalid existing ledger; refusing to reset it") from exc
                self._state = state
                if anchor is not None and anchor != state["ledger_id"]:
                    raise BudgetIntegrityError("Ledger identity changed; refusing a replacement/reset")
                pending = [item for item in state["reservations"] if item["status"] == "pending"]
                if pending:
                    recovered = deepcopy(state)
                    for item in recovered["reservations"]:
                        if item["status"] == "pending":
                            item.update(status="recovered_unknown", settled_utc=_now(),
                                        reason="pending_at_reopen_charged_in_full")
                    self._commit(recovered)
            else:
                if anchor is not None:
                    raise BudgetIntegrityError("Previously initialized ledger is missing; refusing to reset spending")
                now = _now()
                self._state = {"schema_version": 1, "ledger_id": uuid.uuid4().hex,
                               "policy": self.policy_snapshot(), "generation": 0,
                               "created_utc": now, "updated_utc": now, "blocked": False,
                               "blocked_reason": None, "reservations": [],
                               "committed_cny": _money(PRIOR_CNY)}
                self._commit(deepcopy(self._state))
            if anchor is None:
                self._bind_anchor(self._state["ledger_id"])
        except BaseException:
            self.close()
            raise

    def _acquire_lock(self):
        lock_path = self.path.with_name(self.path.name + ".lock")
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        handle = os.fdopen(descriptor, "r+b", buffering=0)
        try:
            if os.fstat(handle.fileno()).st_size == 0:
                handle.write(b"0")
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise LedgerLocked("Ledger is locked by another process or context") from exc
        self._lock_handle = handle
        self._closed = False

    def _read_anchor(self):
        self._lock_handle.seek(1)
        raw = self._lock_handle.read()
        if not raw:
            return None
        try:
            value = raw.decode("ascii")
        except UnicodeDecodeError as exc:
            raise BudgetIntegrityError("Invalid ledger identity anchor") from exc
        if not re.fullmatch(r"[0-9a-f]{32}", value):
            raise BudgetIntegrityError("Invalid ledger identity anchor")
        return value

    def _bind_anchor(self, ledger_id):
        # Keep this file after close: an accidentally deleted ledger must not
        # silently become a fresh budget. This is not an adversarial MAC/signature.
        try:
            self._lock_handle.seek(1)
            self._lock_handle.write(ledger_id.encode("ascii"))
            self._lock_handle.flush()
            os.fsync(self._lock_handle.fileno())
        except OSError as exc:
            self._poisoned = True
            raise BudgetIntegrityError("Could not persist ledger identity; refusing further calls") from exc

    def close(self):
        if self._lock_handle is not None:
            self._lock_handle.close()  # OS releases the lock; keep its inode for other processes.
            self._lock_handle = None
        self._closed = True

    def __enter__(self):
        self._check_open()
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()
        return False

    def policy_snapshot(self):
        return deepcopy(self._policy)

    @property
    def policy(self):
        return self.policy_snapshot()

    def _check_open(self):
        if self._closed or self._poisoned:
            raise BudgetIntegrityError("Ledger is closed or its accounting state is untrusted")

    def _check_disk(self):
        self._check_open()
        if self._disk_hash is not None:
            try:
                current = hashlib.sha256(self.path.read_bytes()).hexdigest()
            except OSError as exc:
                self._poisoned = True
                raise BudgetIntegrityError("Ledger became unavailable; stopping") from exc
            if current != self._disk_hash:
                self._poisoned = True
                raise BudgetIntegrityError("Ledger changed outside this guard; stopping")
        elif self.path.exists():
            self._poisoned = True
            raise BudgetIntegrityError("Unexpected ledger appeared; refusing to overwrite")

    def _usable(self):
        self._check_disk()
        if self._state["blocked"]:
            raise BudgetIntegrityError("Ledger is permanently blocked after an untrusted usage overrun")

    @property
    @_exact
    def remaining(self):
        self._check_disk()
        return _decimal(self._policy["budget_cny"]) - _decimal(self._state["committed_cny"])

    @_exact
    def _validate(self, state):
        expected = {"schema_version", "ledger_id", "policy", "generation", "created_utc", "updated_utc",
                    "blocked", "blocked_reason", "reservations", "committed_cny", "integrity_sha256"}
        if not isinstance(state, dict) or set(state) != expected or state["schema_version"] != 1:
            raise BudgetIntegrityError("Invalid ledger schema")
        digest = state["integrity_sha256"]
        unsigned = {key: value for key, value in state.items() if key != "integrity_sha256"}
        if digest != _digest(unsigned):
            raise BudgetIntegrityError("Ledger checksum mismatch; refusing to reset")
        if state["policy"] != self._policy:
            raise BudgetIntegrityError("Ledger policy differs from the frozen requested policy")
        if (type(state["generation"]) is not int or state["generation"] < 1 or
                type(state["blocked"]) is not bool or not isinstance(state["reservations"], list) or
                not isinstance(state["ledger_id"], str) or not re.fullmatch(r"[0-9a-f]{32}", state["ledger_id"])):
            raise BudgetIntegrityError("Invalid ledger state")
        ids, requests = set(), set()
        total = PRIOR_CNY
        saw_overrun = False
        fields = {"id", "request_id", "metadata", "status", "reserved_cny", "charged_cny", "usage",
                  "created_utc", "settled_utc", "response_received", "error_type", "reason"}
        for item in state["reservations"]:
            if not isinstance(item, dict) or set(item) != fields:
                raise BudgetIntegrityError("Invalid reservation schema")
            if (not isinstance(item["id"], str) or not re.fullmatch(r"[0-9a-f]{32}", item["id"]) or
                    item["id"] in ids or not isinstance(item["request_id"], str) or
                    not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,179}", item["request_id"]) or
                    item["request_id"] in requests or _decimal(item["reserved_cny"]) != RESERVATION_CNY):
                raise BudgetIntegrityError("Invalid or duplicate reservation identity/bound")
            ids.add(item["id"])
            requests.add(item["request_id"])
            _metadata(item["metadata"])
            used = _usage(item["usage"])
            status = item["status"]
            if status == "settled":
                if used is None or used["prompt_tokens"] > MAX_INPUT_TOKENS or used["completion_tokens"] > MAX_OUTPUT_TOKENS:
                    raise BudgetIntegrityError("Invalid settled usage")
                expected_charge = _cost(**used)
            elif status in ("pending", "unknown", "recovered_unknown"):
                if item["usage"] is not None:
                    raise BudgetIntegrityError("Unknown charge cannot claim known usage")
                expected_charge = RESERVATION_CNY
            elif status == "overrun":
                if used is None or not (used["prompt_tokens"] > MAX_INPUT_TOKENS or used["completion_tokens"] > MAX_OUTPUT_TOKENS):
                    raise BudgetIntegrityError("Invalid overrun usage")
                expected_charge = max(RESERVATION_CNY, _cost(**used))
                saw_overrun = True
            else:
                raise BudgetIntegrityError("Unknown reservation status")
            if _decimal(item["charged_cny"]) != expected_charge:
                raise BudgetIntegrityError("Reservation charge does not reconcile")
            total += expected_charge
        if (_decimal(state["committed_cny"]) != total or
                state["blocked"] != saw_overrun or
                state["blocked_reason"] != ("usage_exceeded_token_bound" if saw_overrun else None) or
                (total > _decimal(self._policy["budget_cny"]) and not saw_overrun)):
            raise BudgetIntegrityError("Ledger totals or blocking status do not reconcile")

    @_exact
    def _commit(self, candidate):
        self._check_disk()
        candidate.pop("integrity_sha256", None)
        candidate["generation"] += 1
        candidate["updated_utc"] = _now()
        candidate["committed_cny"] = _money(PRIOR_CNY + sum(
            (_decimal(item["charged_cny"]) for item in candidate["reservations"]), Decimal(0)))
        candidate["integrity_sha256"] = _digest(candidate)
        self._validate(candidate)
        raw = (json.dumps(candidate, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="wb", prefix=".money-", suffix=".tmp",
                                             dir=self.path.parent, delete=False) as handle:
                temp_path = Path(handle.name)
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
            if os.name != "nt":
                descriptor = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        except OSError as exc:
            self._poisoned = True
            raise BudgetIntegrityError("Atomic ledger persistence failed; do not make further calls") from exc
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()
        self._state = candidate
        self._disk_hash = hashlib.sha256(raw).hexdigest()

    def reserve(self, metadata=None, *, request_id=None, model=None,
                max_input_tokens=MAX_INPUT_TOKENS, max_output_tokens=MAX_OUTPUT_TOKENS):
        self._usable()
        clean = _metadata(metadata)
        request_id = clean.get("request_id") if request_id is None else request_id
        model = clean.get("model", MODEL) if model is None else model
        if (model != MODEL or clean.get("model", model) != model or
                clean.get("request_id", request_id) != request_id or
                type(max_input_tokens) is not int or max_input_tokens != MAX_INPUT_TOKENS or
                type(max_output_tokens) is not int or max_output_tokens != MAX_OUTPUT_TOKENS):
            raise BudgetIntegrityError("Call model or token bound differs from frozen policy")
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,179}", request_id):
            raise ValueError("A stable non-secret request_id is required")
        if any(item["request_id"] == request_id for item in self._state["reservations"]):
            raise BudgetIntegrityError("request_id already reserved; refusing a duplicate call")
        if self.remaining < RESERVATION_CNY:
            raise BudgetExceeded("Insufficient conservative CNY budget for a full-context reservation")
        reservation_id = uuid.uuid4().hex
        candidate = deepcopy(self._state)
        candidate["reservations"].append({
            "id": reservation_id, "request_id": request_id, "metadata": clean, "status": "pending",
            "reserved_cny": _money(RESERVATION_CNY), "charged_cny": _money(RESERVATION_CNY),
            "usage": None, "created_utc": _now(), "settled_utc": None,
            "response_received": None, "error_type": None, "reason": "reserved_before_call",
        })
        self._commit(candidate)
        return reservation_id

    @_exact
    def settle(self, reservation, usage=None, *, response_received=True, error_type=None):
        self._usable()
        if type(response_received) is not bool:
            raise ValueError("response_received must be a boolean")
        if error_type is not None and (not isinstance(error_type, str) or not re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_.]{0,127}", error_type)):
            raise ValueError("error_type must be a class name, never an error message")
        candidate = deepcopy(self._state)
        item = next((entry for entry in candidate["reservations"] if entry["id"] == reservation), None)
        if item is None or item["status"] != "pending":
            raise BudgetIntegrityError("Reservation is absent or already finalized; no refund allowed")
        used = _usage(usage) if response_received and error_type is None else None
        overrun = used is not None and (used["prompt_tokens"] > MAX_INPUT_TOKENS or
                                       used["completion_tokens"] > MAX_OUTPUT_TOKENS)
        if overrun:
            charge = max(RESERVATION_CNY, _cost(**used))
            candidate.update(blocked=True, blocked_reason="usage_exceeded_token_bound")
            status, reason = "overrun", "usage_exceeded_token_bound"
        elif used is None:
            charge, status, reason = RESERVATION_CNY, "unknown", "missing_usage_or_error_charged_in_full"
        else:
            charge, status, reason = _cost(**used), "settled", "complete_usage_at_uncached_rates"
        item.update(status=status, reason=reason, charged_cny=_money(charge), usage=used,
                    settled_utc=_now(), response_received=response_received, error_type=error_type)
        self._commit(candidate)
        result = {"reservation_id": reservation, "status": status, "currency": "CNY",
                  "charged_cny": _money(charge), "released_cny": _money(max(Decimal(0), RESERVATION_CNY - charge)),
                  "remaining_cny": _money(self.remaining), "provider_bill_amount": False}
        if overrun:
            raise BudgetIntegrityError("Usage exceeded the prepaid bound; ledger blocked permanently",
                                       settlement=result)
        return result
