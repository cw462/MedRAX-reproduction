"""V12 accounting with user-authorized integrity checks disabled.

Startup and commit no longer validate checksums, schemas, policy snapshots or
whole-ledger amount reconciliation; inherited-ledger checksums are not checked
either. No replacement scan is performed. Existing checksum fields may still
be written as metadata, but are never compared by this subclass.

JSON must remain readable and accounting fields usable. The inherited process
lock, identity anchor, configured cap, reservation/settlement arithmetic, hard
token ceilings, duplicate-request refusal and conservative pending recovery
remain unchanged. This no longer establishes historical ledger consistency.
ProviderLedger itself retains its original validation behavior.
"""
import hashlib
import json
import sqlite3
from contextlib import closing

from provider_ledger import LedgerIntegrityError, ProviderLedger, _decimal, _money


class LedgerReadError(LedgerIntegrityError):
    """The budget snapshot could not be read."""


class V12ProviderLedger(ProviderLedger):
    """Keep operational budget guards without ledger-integrity validation."""

    def _check_disk(self):
        self._check_open()

    @property
    def sqlite_path(self):
        return self.path.with_suffix('.sqlite3')

    def _uses_sqlite(self):
        return not self.path.exists() and self.sqlite_path.is_file()

    def _state_exists(self):
        return super()._state_exists() or self._uses_sqlite()

    def _read_state(self):
        try:
            if not self._uses_sqlite():
                return super()._read_state()
            with closing(sqlite3.connect(self.sqlite_path.as_uri()+'?mode=ro', uri=True)) as db:
                row = db.execute('SELECT payload FROM ledger_state WHERE id=1').fetchone()
        except (OSError, sqlite3.Error) as exc:
            raise LedgerReadError('Cannot read the shared ledger snapshot') from exc
        if row is None:
            raise LedgerReadError('SQLite ledger has no accounting snapshot')
        return row[0]

    def _persist_state(self, raw):
        if not self._uses_sqlite():
            return super()._persist_state(raw)
        with closing(sqlite3.connect(self.sqlite_path.as_uri()+'?mode=rw', uri=True)) as db, db:
            result = db.execute('UPDATE ledger_state SET payload=? WHERE id=1', (raw,))
            if result.rowcount != 1:
                raise LedgerIntegrityError('SQLite ledger has no accounting snapshot')

    def _validate(self, state):
        """Intentionally omit startup/commit integrity and reconciliation scans."""

    def _read_inherited(self):
        """Read the inherited amount without validating its stored checksum."""
        if self._uses_sqlite():
            state = json.loads(self._read_state())
            inherited = state['policy']['inherited_from']
            expected = self.inherit_path.name if self.inherit_path else None
            if (inherited['path_name'] if inherited else None) != expected:
                raise LedgerIntegrityError('Configured inherited ledger differs from the migrated budget')
            return _decimal(state['inherited_cny']), inherited
        if self.inherit_path is None:
            return _decimal('0'), None
        if not self.inherit_path.exists():
            raise LedgerIntegrityError('Inherited ledger is absent; refusing to start a fresh budget')
        raw = self.inherit_path.read_bytes()
        state = json.loads(raw)
        committed = _decimal(state['committed_cny'])
        # Preserve the existing provenance shape, using these already-read
        # bytes only. This digest is metadata, never a comparison/stop rule.
        return committed, {'path_name': self.inherit_path.name, 'ledger_id': state['ledger_id'],
                           'committed_cny': _money(committed),
                           'sha256': hashlib.sha256(raw).hexdigest()}
