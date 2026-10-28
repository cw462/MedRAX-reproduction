"""Provider-aware conservative CNY ledger for non-GPT-4o central models.

The historical GPT-4o ledger (`money_guard.py`) is frozen to one model, one price
table and a fixed full-context reservation. A Qwen run needs different prices and
a reservation sized to the actual request, otherwise a 265-call budget would be
blocked by 2.6 CNY reservations for calls that cost a few cents.

This module keeps the same safety properties as `money_guard.py`:
  * one locked ledger file with a persistent identity anchor;
  * a checksummed, atomically replaced state document;
  * a reservation written *before* every network call;
  * settlement only with complete usage; unclear outcomes are charged in full;
  * duplicate request ids refused; existing ledgers never reset;
  * a hard token ceiling per call that cannot be exceeded without blocking.

Difference, recorded in the policy: the pre-call amount comes from an explicit
input-token estimate plus the output bound, not from the 128k full-context bound.
A call whose actual usage exceeds the *reservation* is charged the actual amount
(`settled_over_reservation`) instead of blocking the ledger; exceeding the hard
per-call ceiling still blocks it permanently, because that means the configured
bound was wrong and later reservations cannot be trusted.

Spend is inherited from the historical ledger's committed total so the ¥100
authorisation is shared, not duplicated.
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

from provider_profile import ProviderProfile


def _exact(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with localcontext() as context:
            context.prec = 80
            return function(*args, **kwargs)
    return wrapped


def _now():
    return datetime.now(timezone.utc).isoformat()


def _digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _money(value):
    with localcontext() as context:
        context.prec = 80
        return format(Decimal(value).normalize(), 'f')


def _decimal(value):
    if isinstance(value, (bool, float)):
        raise ValueError('Use decimal strings for money')
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError('Invalid decimal amount') from exc
    if not result.is_finite():
        raise ValueError('Money must be finite')
    return result


class BudgetExceeded(RuntimeError):
    """Not enough remaining budget for the reserve; do not call the API."""


class LedgerIntegrityError(RuntimeError):
    def __init__(self, message, *, settlement=None):
        super().__init__(message)
        self.settlement = settlement


class LedgerLocked(LedgerIntegrityError):
    pass


FORBIDDEN_METADATA = {'api_key', 'apikey', 'password', 'authorization', 'secret', 'access_token',
                      'refresh_token', 'api_token', 'headers', 'prompt', 'messages', 'response',
                      'body', 'content', 'image_path', 'base_url', 'cookie', 'credentials'}


def _metadata(value):
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > 32:
        raise ValueError('Metadata must be a small scalar-only dictionary')
    clean = {}
    for key, item in value.items():
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', key):
            raise ValueError('Invalid metadata key')
        if key.lower() in FORBIDDEN_METADATA:
            raise ValueError('Do not put credentials, content or paths in ledger metadata')
        if item is not None and not isinstance(item, (str, bool, int, float)):
            raise ValueError('Metadata values must be plain scalars')
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError('Metadata numbers must be finite')
        if isinstance(item, str):
            if len(item) > 256 or any(ch in item for ch in '\r\n\x00'):
                raise ValueError('Metadata text must be a short identifier')
            if item.lower().startswith(('bearer ', 'sk-', 'sk_')):
                raise ValueError('Credential-like metadata is forbidden')
        clean[key] = item
    return clean


def _usage(value):
    if not isinstance(value, dict):
        return None
    fields = ('prompt_tokens', 'completion_tokens')
    if any(type(value.get(key)) is not int or value[key] < 0 for key in fields):
        return None
    return {key: value[key] for key in fields}


class ProviderLedger:
    """One lock, one file, one authorised budget shared across providers."""

    SCHEMA = 1

    def __init__(self, path, profile: ProviderProfile, *, cap_cny='100',
                 inherit_ledger_path=None):
        self.profile = profile
        self.cap = _decimal(cap_cny)
        self.path = Path(path).expanduser().resolve()
        self.inherit_path = Path(inherit_ledger_path).expanduser().resolve() if inherit_ledger_path else None
        inherited, inherited_meta = self._read_inherited()
        self._policy = dict(profile.policy_snapshot())
        self._policy.update({
            'policy_id': 'provider_ledger_v1',
            'cap_cny': _money(self.cap),
            'inherited_cny': _money(inherited),
            'inherited_from': inherited_meta,
        })
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
                    state = json.loads(raw)
                    self._validate(state)
                except LedgerIntegrityError:
                    raise
                except Exception as exc:
                    raise LedgerIntegrityError('Invalid existing ledger; refusing to reset it') from exc
                self._state = state
                if anchor is not None and anchor != state['ledger_id']:
                    raise LedgerIntegrityError('Ledger identity changed; refusing a replacement')
                pending = [item for item in state['reservations'] if item['status'] == 'pending']
                if pending:
                    recovered = deepcopy(state)
                    for item in recovered['reservations']:
                        if item['status'] == 'pending':
                            item.update(status='recovered_unknown', settled_utc=_now(),
                                        reason='pending_at_reopen_charged_in_full')
                    self._commit(recovered)
            else:
                if anchor is not None:
                    raise LedgerIntegrityError('Previously initialised ledger is missing; refusing to reset')
                now = _now()
                self._state = {'schema_version': self.SCHEMA, 'ledger_id': uuid.uuid4().hex,
                               'policy': self.policy_snapshot(), 'generation': 0,
                               'created_utc': now, 'updated_utc': now, 'blocked': False,
                               'blocked_reason': None, 'reservations': [],
                               'committed_cny': _money(inherited), 'inherited_cny': _money(inherited)}
                self._commit(deepcopy(self._state))
            if anchor is None:
                self._bind_anchor(self._state['ledger_id'])
        except BaseException:
            self.close()
            raise

    # ---------------------------------------------------------------- inherited
    def _read_inherited(self):
        if self.inherit_path is None:
            return Decimal('0'), None
        if not self.inherit_path.exists():
            raise LedgerIntegrityError('Inherited ledger is absent; refusing to start a fresh budget')
        raw = self.inherit_path.read_bytes()
        state = json.loads(raw)
        unsigned = {k: v for k, v in state.items() if k != 'integrity_sha256'}
        if state.get('integrity_sha256') != _digest(unsigned):
            raise LedgerIntegrityError('Inherited ledger checksum mismatch')
        committed = _decimal(state['committed_cny'])
        return committed, {'path_name': self.inherit_path.name, 'ledger_id': state['ledger_id'],
                           'committed_cny': _money(committed),
                           'sha256': hashlib.sha256(raw).hexdigest()}

    # --------------------------------------------------------------------- lock
    def _acquire_lock(self):
        lock_path = self.path.with_name(self.path.name + '.lock')
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        handle = os.fdopen(descriptor, 'r+b', buffering=0)
        try:
            if os.fstat(handle.fileno()).st_size == 0:
                handle.write(b'0')
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise LedgerLocked('Ledger is locked by another process') from exc
        self._lock_handle = handle
        self._closed = False

    def _read_anchor(self):
        self._lock_handle.seek(1)
        raw = self._lock_handle.read()
        if not raw:
            return None
        value = raw.decode('ascii')
        if not re.fullmatch(r'[0-9a-f]{32}', value):
            raise LedgerIntegrityError('Invalid ledger identity anchor')
        return value

    def _bind_anchor(self, ledger_id):
        try:
            self._lock_handle.seek(1)
            self._lock_handle.write(ledger_id.encode('ascii'))
            self._lock_handle.flush()
            os.fsync(self._lock_handle.fileno())
        except OSError as exc:
            self._poisoned = True
            raise LedgerIntegrityError('Could not persist ledger identity') from exc

    def close(self):
        if self._lock_handle is not None:
            self._lock_handle.close()
            self._lock_handle = None
        self._closed = True

    def __enter__(self):
        self._check_open()
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()
        return False

    # ------------------------------------------------------------------- state
    def policy_snapshot(self):
        return deepcopy(self._policy)

    @property
    def policy(self):
        return self.policy_snapshot()

    def _check_open(self):
        if self._closed or self._poisoned:
            raise LedgerIntegrityError('Ledger is closed or untrusted')

    def _check_disk(self):
        self._check_open()
        if self._disk_hash is not None:
            try:
                current = hashlib.sha256(self.path.read_bytes()).hexdigest()
            except OSError as exc:
                self._poisoned = True
                raise LedgerIntegrityError('Ledger became unavailable') from exc
            if current != self._disk_hash:
                self._poisoned = True
                raise LedgerIntegrityError('Ledger changed outside this guard')

    def _usable(self):
        self._check_disk()
        if self._state['blocked']:
            raise LedgerIntegrityError('Ledger is permanently blocked after an untrusted overrun')

    @property
    @_exact
    def remaining(self):
        self._check_disk()
        return self.cap - _decimal(self._state['committed_cny'])

    @property
    def inherited_cny(self):
        return _decimal(self._state['inherited_cny'])

    @_exact
    def _cost(self, prompt_tokens, completion_tokens):
        return (Decimal(prompt_tokens) * self.profile.input_cny_per_million +
                Decimal(completion_tokens) * self.profile.output_cny_per_million) / Decimal(1000000)

    @_exact
    def _reserve_amount(self, input_tokens, output_tokens):
        return self._cost(input_tokens, output_tokens)

    @_exact
    def _validate(self, state):
        expected = {'schema_version', 'ledger_id', 'policy', 'generation', 'created_utc', 'updated_utc',
                    'blocked', 'blocked_reason', 'reservations', 'committed_cny', 'inherited_cny',
                    'integrity_sha256'}
        if not isinstance(state, dict) or set(state) != expected or state['schema_version'] != self.SCHEMA:
            raise LedgerIntegrityError('Invalid ledger schema')
        unsigned = {k: v for k, v in state.items() if k != 'integrity_sha256'}
        if state['integrity_sha256'] != _digest(unsigned):
            raise LedgerIntegrityError('Ledger checksum mismatch')
        if state['policy'] != self._policy:
            raise LedgerIntegrityError('Ledger policy differs from the requested profile')
        inherited = _decimal(state['inherited_cny'])
        if inherited != self.inherited_cny_value:
            raise LedgerIntegrityError('Inherited amount differs from the frozen policy')
        total = inherited
        for item in state['reservations']:
            fields = {'id', 'request_id', 'metadata', 'status', 'reserved_cny', 'charged_cny', 'usage',
                      'created_utc', 'settled_utc', 'response_received', 'error_type', 'reason',
                      'reserved_input_tokens', 'reserved_output_tokens'}
            if set(item) != fields:
                raise LedgerIntegrityError('Invalid reservation schema')
            if not re.fullmatch(r'[0-9a-f]{32}', item['id']):
                raise LedgerIntegrityError('Invalid reservation id')
            used = _usage(item['usage'])
            status = item['status']
            if status == 'pending' or status == 'recovered_unknown':
                charge = _decimal(item['reserved_cny'])
            elif status == 'settled':
                if used is None:
                    raise LedgerIntegrityError('Settled reservation without usage')
                charge = self._cost(**used)
            elif status == 'settled_over_reservation':
                if used is None:
                    raise LedgerIntegrityError('Over-reservation settlement without usage')
                charge = self._cost(**used)
            elif status == 'unknown':
                charge = _decimal(item['reserved_cny'])
            elif status == 'overrun':
                if used is None:
                    raise LedgerIntegrityError('Overrun without usage')
                charge = max(_decimal(item['reserved_cny']), self._cost(**used))
            else:
                raise LedgerIntegrityError('Unknown reservation status')
            if _decimal(item['charged_cny']) != charge:
                raise LedgerIntegrityError('Reservation charge does not reconcile')
            total += charge
        if _decimal(state['committed_cny']) != total:
            raise LedgerIntegrityError('Ledger total does not reconcile')

    def _commit(self, candidate):
        self._check_disk()
        candidate.pop('integrity_sha256', None)
        candidate['generation'] += 1
        candidate['updated_utc'] = _now()
        candidate['committed_cny'] = _money(self.inherited_cny_value + sum(
            (_decimal(item['charged_cny']) for item in candidate['reservations']), Decimal(0)))
        candidate['integrity_sha256'] = _digest(candidate)
        self._validate(candidate)
        raw = (json.dumps(candidate, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='wb', prefix='.provider-', suffix='.tmp',
                                             dir=self.path.parent, delete=False) as handle:
                temp_path = Path(handle.name)
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
            if os.name != 'nt':
                descriptor = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        except OSError as exc:
            self._poisoned = True
            raise LedgerIntegrityError('Atomic ledger persistence failed') from exc
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()
        self._state = candidate
        self._disk_hash = hashlib.sha256(raw).hexdigest()

    @property
    def inherited_cny_value(self):
        return _decimal(self._policy['inherited_cny'])

    # -------------------------------------------------------------- operations
    def reserve(self, metadata=None, *, request_id, estimated_input_tokens, max_output_tokens,
                model=None):
        self._usable()
        clean = _metadata(metadata)
        if type(estimated_input_tokens) is not int or estimated_input_tokens < 0:
            raise ValueError('estimated_input_tokens must be a non-negative int')
        if estimated_input_tokens > self.profile.max_input_tokens:
            raise BudgetExceeded('Estimated input exceeds the hard profile ceiling')
        if type(max_output_tokens) is not int or not (0 < max_output_tokens <= self.profile.max_output_tokens):
            raise ValueError('max_output_tokens outside the frozen profile bound')
        if model is not None and model != self.profile.model:
            raise LedgerIntegrityError('Call model differs from the frozen profile')
        if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,179}', request_id):
            raise ValueError('A stable non-secret request_id is required')
        if any(item['request_id'] == request_id for item in self._state['reservations']):
            raise LedgerIntegrityError('request_id already reserved; refusing a duplicate call')
        amount = self._reserve_amount(estimated_input_tokens, max_output_tokens)
        if self.remaining < amount:
            raise BudgetExceeded(f'Insufficient remaining budget: need {_money(amount)}')
        candidate = deepcopy(self._state)
        reservation_id = uuid.uuid4().hex
        candidate['reservations'].append({
            'id': reservation_id, 'request_id': request_id, 'metadata': clean, 'status': 'pending',
            'reserved_cny': _money(amount), 'charged_cny': _money(amount), 'usage': None,
            'created_utc': _now(), 'settled_utc': None, 'response_received': None,
            'error_type': None, 'reason': 'reserved_before_call',
            'reserved_input_tokens': estimated_input_tokens,
            'reserved_output_tokens': max_output_tokens,
        })
        self._commit(candidate)
        return reservation_id

    @_exact
    def settle(self, reservation, usage=None, *, response_received=True, error_type=None):
        self._usable()
        if type(response_received) is not bool:
            raise ValueError('response_received must be a boolean')
        if error_type is not None and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]{0,127}', error_type):
            raise ValueError('error_type must be a class name')
        candidate = deepcopy(self._state)
        item = next((entry for entry in candidate['reservations'] if entry['id'] == reservation), None)
        if item is None or item['status'] != 'pending':
            raise LedgerIntegrityError('Reservation absent or already finalised')
        used = _usage(usage) if response_received and error_type is None else None
        reserved = _decimal(item['reserved_cny'])
        if used is None:
            charge, status, reason = reserved, 'unknown', 'missing_usage_or_error_charged_in_full'
        elif used['prompt_tokens'] > self.profile.max_input_tokens or used['completion_tokens'] > self.profile.max_output_tokens:
            charge = max(reserved, self._cost(**used))
            candidate.update(blocked=True, blocked_reason='usage_exceeded_profile_ceiling')
            status, reason = 'overrun', 'usage_exceeded_profile_ceiling'
        else:
            charge = self._cost(**used)
            status = 'settled' if charge <= reserved else 'settled_over_reservation'
            reason = 'complete_usage_at_profile_rates'
        item.update(status=status, reason=reason, charged_cny=_money(charge), usage=used,
                    settled_utc=_now(), response_received=response_received, error_type=error_type)
        self._commit(candidate)
        result = {'reservation_id': reservation, 'status': status, 'currency': 'CNY',
                  'charged_cny': _money(charge), 'remaining_cny': _money(self.remaining),
                  'reserved_cny': _money(reserved), 'provider_bill_amount': False}
        if status == 'overrun':
            raise LedgerIntegrityError('Usage exceeded the frozen profile ceiling; ledger blocked',
                                       settlement=result)
        return result
