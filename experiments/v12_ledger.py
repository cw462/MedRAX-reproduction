"""V12 ledger with the raw-byte drift sentinel explicitly disabled by the user.

This changes no budget, price, reservation, settlement, or reopening policy.
The original process lock, startup identity/checksum validation, monetary
validation on every commit, and conservative recovery of pending calls remain
inherited from ProviderLedger. No replacement drift scan or synchronization is
performed. As in the original lock contract, writers must respect its lock.
"""
from provider_ledger import ProviderLedger


class V12ProviderLedger(ProviderLedger):
    """Same constructor and accounting protocol; no byte-equality stop rule."""

    def _check_disk(self):
        self._check_open()
