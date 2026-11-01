"""Estimated cost of one participant answer, from fixed vendor rates dated 2026-11-01 (HARNESS.md 6).

An estimate is computed from the token counts the vendor reported (ProviderRun.usage, as stored), in Decimal, and is
never an invoice: its basis says so. Rates are US dollars per million tokens, read from the vendors' published pricing
on 2026-11-01 (docs/cpt-harness/vendor-and-reference-facts-20261101.md):

- gpt-6-astra: input $10, cached input $1, output $50. A request with more than 272,000 input tokens is priced whole at
  2x input (cached input included) and 1.5x output. ``input_tokens`` counts the cached tokens too, so they are
  subtracted before the input rate applies; ``output_tokens`` includes reasoning tokens.
- claude-fable-5-1: input $10, cache write $12.50 (5-minute), cache read $0.25, output $50. ``input_tokens`` excludes
  cache reads and writes, each counted on its own; ``output_tokens`` includes thinking tokens. The harness asks for no
  caching and no fallback, so the top-level counts are the whole request (usage.iterations is not priced).

Corti reports credits, not tokens, and has no estimate here. An answer whose usage lacks a token count, or states one
that is not a whole number of tokens, has no estimate (None) rather than a guessed one.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

RATES_AS_OF = '2026-11-01'
BASIS = 'estimated from published rates as of 2026-11-01; not reconciled to an invoice'
ASTRA, FABLE = 'gpt-6-astra', 'claude-fable-5-1'
RATES = {  # US dollars per million tokens
    ASTRA: {'input': Decimal('10'), 'cached_input': Decimal('1'), 'output': Decimal('50')},
    FABLE: {'input': Decimal('10'), 'cache_write': Decimal('12.50'), 'cache_read': Decimal('0.25'),
            'output': Decimal('50')},
}
ASTRA_LONG_INPUT_TOKENS = 272_000  # above this many input tokens a request is priced as long context
ASTRA_LONG_MULTIPLIERS = {'input': Decimal('2'), 'output': Decimal('1.5')}
_MILLION = Decimal(1_000_000)
_PRECISION = Decimal('0.000001')  # estimates are stated to a millionth of a dollar
_MAX_TOKENS = 10 ** 15  # beyond any real answer; keeps every product inside Decimal's 28 digits


class _Invalid(Exception):
    pass


def estimate(model: str, usage) -> Optional[dict]:
    """{'estimated_usd': '0.040690', 'rates': {...}, 'basis': BASIS} for an answer of ``model`` (the model the request
    named) with ``usage`` as the vendor reported it; None when there is nothing to estimate from."""
    if not isinstance(usage, dict):
        return None
    try:
        if model == ASTRA:
            return _astra(usage)
        if model == FABLE:
            return _fable(usage)
    except _Invalid:
        return None
    return None


def _astra(usage: dict) -> dict:
    rates = RATES[ASTRA]
    total_input, output = _count(usage, 'input_tokens'), _count(usage, 'output_tokens')
    details = usage.get('input_tokens_details')
    if details is not None and not isinstance(details, dict):
        raise _Invalid
    cached = _count(details or {}, 'cached_tokens', optional=True)
    if cached > total_input:
        raise _Invalid
    long_context = total_input > ASTRA_LONG_INPUT_TOKENS
    input_multiplier = ASTRA_LONG_MULTIPLIERS['input'] if long_context else Decimal(1)
    output_multiplier = ASTRA_LONG_MULTIPLIERS['output'] if long_context else Decimal(1)
    tokens = {'input': total_input - cached, 'cached_input': cached, 'output': output}
    cost = (tokens['input'] * rates['input'] * input_multiplier
            + tokens['cached_input'] * rates['cached_input'] * input_multiplier
            + tokens['output'] * rates['output'] * output_multiplier) / _MILLION
    return _result(ASTRA, cost, tokens, {'long_context': long_context,
                                         'multipliers': {'input': str(input_multiplier),
                                                         'output': str(output_multiplier)}})


def _fable(usage: dict) -> dict:
    rates = RATES[FABLE]
    tokens = {'input': _count(usage, 'input_tokens'),
              'cache_write': _count(usage, 'cache_creation_input_tokens', optional=True),
              'cache_read': _count(usage, 'cache_read_input_tokens', optional=True),
              'output': _count(usage, 'output_tokens')}
    cost = sum(tokens[kind] * rates[kind] for kind in tokens) / _MILLION
    return _result(FABLE, cost, tokens, {})


def _count(usage: dict, key: str, *, optional: bool = False) -> int:
    """A token count as reported: a whole number, zero or more. An optional count that is absent or null is zero."""
    value = usage.get(key)
    if value is None and optional:
        return 0
    if type(value) is not int or not 0 <= value < _MAX_TOKENS:
        raise _Invalid
    return value


def _result(model: str, cost: Decimal, tokens: dict, extra: dict) -> dict:
    return {'estimated_usd': f'{cost.quantize(_PRECISION, rounding=ROUND_HALF_UP):f}',
            'rates': {'model': model, 'as_of': RATES_AS_OF,
                      'usd_per_million_tokens': {kind: str(rate) for kind, rate in RATES[model].items()},
                      'priced_tokens': dict(tokens), **extra},
            'basis': BASIS}
