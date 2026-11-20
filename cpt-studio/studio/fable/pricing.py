"""claude-fable-5-2's prices, the priced cost of a stored answer and the worst case of a send (BUILD-SPEC 3.2).

Rates are US dollars per million tokens (the claude-api reference, cached 2026-11-03): input $8.00, a 5-minute cache
write $10.00, a cache read $0.20, output $40.00 (thinking is counted in the output). A cost is priced at read time
from the usage the API reported, in Decimal, and is an estimate, never an invoice.

With server-side fallbacks the response's ``usage.iterations`` lists every attempt (a declined one and the fallback's)
and the top-level counts cover only the attempt that produced the message, so the iterations are summed instead. Every
attempt is priced at claude-fable-5-2's rates: the fallback models are priced lower, so a served-by-fallback answer's
estimate is an upper bound.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional

MODEL = 'claude-fable-5-2'
RATES = {'input': Decimal('8.00'), 'cache_write': Decimal('10.00'), 'cache_read': Decimal('0.20'),
         'output': Decimal('40.00')}
COUNTS = {'input': 'input_tokens', 'cache_write': 'cache_creation_input_tokens',
          'cache_read': 'cache_read_input_tokens', 'output': 'output_tokens'}
REQUIRED = ('input', 'output')
USAGE_BASIS = 'as reported in the final message usage'  # ProviderRun.usage_basis (60 characters at most)
BASIS = ('estimated from published claude-fable-5-2 rates as of 2026-11-03 (fallback attempts priced at the same '
         'rates, an upper bound); not reconciled to an invoice')
# The worst case of one send (3.2, FIX-SPEC 4): every attempt it may make - the requested model's own and, with
# server-side fallbacks, each fallback's (studio.fable.client.Request.attempts) - priced at claude-fable-5-2's rates,
# which no fallback model passes. Each attempt reads the request's input tokens as the API's free token count counted
# them, plus a 2,000-token margin, and - after the first - the partial answer of every attempt before it, which a
# streamed fallback continues from (at most max_tokens each); each attempt writes at most max_tokens. There is no
# estimate without the count: a PDF is billed by its pages, which its bytes do not bound.
MARGIN_TOKENS = 2_000
_MILLION = Decimal(1_000_000)
_PRECISION = Decimal('0.000001')
_MAX_TOKENS = 10 ** 15  # beyond any real answer; keeps every product inside Decimal's precision


def cost_usd(usage: object) -> Optional[Decimal]:
    """The priced cost of an answer whose ``usage`` is as the API reported it; None when it cannot be priced (not an
    object, a missing input or output count, a count that is not a whole number of tokens)."""
    if not isinstance(usage, dict):
        return None
    parts = usage.get('iterations')
    if parts is None:
        parts = [usage]
    elif not isinstance(parts, list) or not parts:
        return None
    total = Decimal(0)
    for part in parts:
        if not isinstance(part, dict):
            return None
        for kind, key in COUNTS.items():
            value = part.get(key)
            if value is None and kind not in REQUIRED:
                continue
            if type(value) is not int or not 0 <= value < _MAX_TOKENS:
                return None
            total += value * RATES[kind]
    return total / _MILLION


def worst_case_usd(input_tokens: int, max_tokens: int, *, attempts: int = 1) -> Decimal:
    """The most one send can cost (see above): ``attempts`` attempts of a request whose input the API counted at
    ``input_tokens`` tokens, each writing at most ``max_tokens``. ValueError when a figure is not a whole positive
    number - with no count there is no worst case, and the send is not made."""
    for name, value in (('input_tokens', input_tokens), ('max_tokens', max_tokens), ('attempts', attempts)):
        if type(value) is not int or value < 1:
            raise ValueError(f'the worst case of a send needs {name} as a whole positive number')
    read = attempts * (input_tokens + MARGIN_TOKENS) + max_tokens * (attempts * (attempts - 1) // 2)
    written = attempts * max_tokens
    return (Decimal(read) * RATES['input'] + Decimal(written) * RATES['output']) / _MILLION


def usd(amount: Optional[Decimal]) -> Optional[str]:
    """An amount as a string to a millionth of a dollar (None stays None)."""
    return None if amount is None else f'{amount.quantize(_PRECISION, rounding=ROUND_HALF_UP):f}'


def estimate(usage: Any) -> Optional[dict[str, Any]]:
    """{'estimated_usd', 'basis'} of an answer for the operator, or None when its usage cannot be priced."""
    amount = cost_usd(usage)
    return None if amount is None else {'estimated_usd': usd(amount), 'basis': BASIS}
