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

from provider_ledger import LedgerIntegrityError, ProviderLedger, _decimal, _money


class V12ProviderLedger(ProviderLedger):
    """Keep operational budget guards without ledger-integrity validation."""

    def _check_disk(self):
        self._check_open()

    def _validate(self, state):
        """Intentionally omit startup/commit integrity and reconciliation scans."""

    def _read_inherited(self):
        """Read the inherited amount without validating its stored checksum."""
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
