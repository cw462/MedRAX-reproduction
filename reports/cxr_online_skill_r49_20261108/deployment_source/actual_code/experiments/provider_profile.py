"""Frozen provider profiles for non-OpenAI central models.

A profile pins the endpoint, the model identity, the token bounds and the CNY
price used by the conservative ledger. Prices here are *accounting assumptions*
for the local budget guard, not provider quotes; every manifest records the
basis string so a later bill can be reconciled rather than silently trusted.

The 2026-10-28 Qwen profile was validated against the live compatible endpoint:
`qwen3-vl-plus` accepted an image data URL and returned a well-formed tool call.
The workspace key used for that check cannot access `qwen-vl-max`,
`qwen-vl-max-latest`, `qwen2.5-vl-72b-instruct` (HTTP 404/403), so those model
names are deliberately absent.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ProviderProfile:
    name: str
    base_url: str
    model: str
    identity_prefixes: tuple[str, ...]
    input_cny_per_million: Decimal
    output_cny_per_million: Decimal
    price_basis: str
    max_input_tokens: int
    max_output_tokens: int
    supports_vision: bool
    notes: str

    def policy_snapshot(self) -> dict:
        return {
            'profile': self.name,
            'base_url': self.base_url,
            'model': self.model,
            'identity_prefixes': list(self.identity_prefixes),
            'currency': 'CNY',
            'input_cny_per_million': str(self.input_cny_per_million),
            'output_cny_per_million': str(self.output_cny_per_million),
            'price_basis': self.price_basis,
            'max_input_tokens': self.max_input_tokens,
            'max_output_tokens': self.max_output_tokens,
            'supports_vision': self.supports_vision,
        }

    def identity_ok(self, returned: str | None) -> bool:
        if not returned:
            return True
        return any(returned == p or returned.startswith(p) for p in self.identity_prefixes)


PROFILES = {
    # Conservative upper bound: 2x the public "plus" tier rates this account's
    # model list implies. Actual list price could not be read from the provider
    # (no pricing endpoint) and the documentation host was unreachable from this
    # machine, so the guard deliberately over-reserves. Reconcile against the
    # provider bill; never present the ledger as the bill.
    'qwen3-vl-plus': ProviderProfile(
        name='qwen3-vl-plus',
        base_url='https://dashscope.aliyuncs.com/compatible-mode/v1',
        model='qwen3-vl-plus',
        identity_prefixes=('qwen3-vl-plus',),
        input_cny_per_million=Decimal('4'),
        output_cny_per_million=Decimal('12'),
        price_basis='assumed_upper_bound_plus_tier_unverified_2026-10-28',
        max_input_tokens=32000,
        max_output_tokens=8192,
        supports_vision=True,
        notes='Vision and tool calling verified live 2026-10-28; reasoning text is '
              'returned inline; no separate text-only fallback. The completion ceiling is 8192 '
              'because the model sometimes exceeds the requested max_tokens (observed 4469).',
    ),
    'qwen3.8-flash': ProviderProfile(
        name='qwen3.8-flash',
        base_url='https://dashscope.aliyuncs.com/compatible-mode/v1',
        model='qwen3.8-flash',
        identity_prefixes=('qwen3.8-flash',),
        input_cny_per_million=Decimal('2'),
        output_cny_per_million=Decimal('6'),
        price_basis='assumed_upper_bound_flash_tier_unverified_2026-10-28',
        max_input_tokens=32000,
        max_output_tokens=2048,
        supports_vision=False,
        notes='Text-only summariser/credit candidate; not validated for this run.',
    ),
}


def get_profile(name: str) -> ProviderProfile:
    try:
        return PROFILES[name]
    except KeyError as exc:
        raise ValueError(f'Unknown provider profile {name!r}; known: {sorted(PROFILES)}') from exc
