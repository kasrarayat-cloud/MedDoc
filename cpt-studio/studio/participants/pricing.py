"""Estimated cost of one participant or interpreter answer, from fixed, dated vendor rates (HARNESS.md 6).

An estimate is computed from the token counts the vendor reported (ProviderRun.usage, as stored), in Decimal, and is
never an invoice: its basis says so. Rates are US dollars per million tokens, read from the vendors' published pricing
on 2026-11-01 (docs/cpt-harness/vendor-and-reference-facts-20261101.md):

- gpt-6-astra: input $10, cached input $1, output $50. A request with more than 272,000 input tokens is priced whole at
  2x input (cached input included) and 1.5x output. ``input_tokens`` counts the cached tokens too, so they are
  subtracted before the input rate applies; ``output_tokens`` includes reasoning tokens.
- claude-fable-5-1: input $10, cache write $12.50 (5-minute), cache read $0.25, output $50. ``input_tokens`` excludes
  cache reads and writes, each counted on its own; ``output_tokens`` includes thinking tokens. The harness asks for no
  caching and no fallback, so the top-level counts are the whole request (usage.iterations is not priced).

The interpreter (Gemini migration, FINAL 3.2; studio/interpretation/adapter.py), read 2026-11-09 (GEMINI_SOURCE):

- gemini-4-argon, Standard tier: input $2.00 and output $10.00 through 2026-11-30; input $4.00 and output $20.00 from
  2026-12-01. Its rates are DATED, so a Gemini answer is priced at the rate of the day its request was sent (``on``, a
  date, or a timezone-aware datetime read in UTC) and has no estimate without one - never one at a guessed rate.
  usageMetadata's ``promptTokenCount`` is the input; the output is ``candidatesTokenCount`` plus
  ``thoughtsTokenCount``, since thinking is billed as output (each absent or null count is zero, as the API omits a zero).
  CPT Studio creates no cached content, but Google's implicit caching, on by default, may serve the prefix every
  interpretation request repeats - its instructions and its response schema - from a cache without being asked, and
  report those tokens as ``cachedContentTokenCount``, which ``promptTokenCount`` already includes. The source records
  no cached-input rate, so they are priced with the rest of the prompt at the full input rate: an estimate that reports
  any is an upper bound, on the premise that a cache hit is never billed above the input rate (Google's caching bills
  cache hits at a reduced rate and implicit caching has no storage charge; whether gemini-4-argon caches implicitly at
  all was not observable in the trial), and it says how many there were (``cached_tokens``) and what that makes it
  (GEMINI_BASIS). A usage stating more cached tokens than prompt tokens has no estimate. CPT Studio offers no tool, and
  no rate is recorded for tool-use prompt tokens, so a usage reporting any has no estimate; nor has one whose
  ``totalTokenCount`` is not its input and output added up (some tokens would be unpriced).

Corti reports credits, not tokens, and has no estimate here. An answer whose usage lacks a token count, or states one
that is not a whole number of tokens, has no estimate (None) rather than a guessed one.

A tool loop (HARNESS.md 11.2) is several requests, each priced on its own (estimate_loop): the long-context rate is a
property of one request, so a loop's summed usage is never priced as if it were one.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
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

GEMINI = 'gemini-4-argon'  # the interpreter's model (studio.interpretation.MODEL; a test pins the two equal)
GEMINI_RATES_AS_OF = '2026-11-09'
GEMINI_BASIS = ('estimated from published rates as of 2026-11-09; prompt tokens served from a cache are priced at the '
                'full input rate, so an estimate that reports any is an upper bound; not reconciled to an invoice')
GEMINI_SOURCE = ("Google's Gemini API pricing page, read 2026-11-09 (gemini-trial REPORT.md section D): gemini-4-argon, "
                 'Standard tier, $2.00 per million input tokens and $10.00 per million output tokens (thinking '
                 'included) through 2026-11-30; $4.00 and $20.00 from 2026-12-01.')
# (first day, last day, US dollars per million tokens), in order; None is open-ended. A day is a UTC calendar day.
GEMINI_PERIODS = (
    (None, date(2026, 11, 30), {'input': Decimal('2.00'), 'output': Decimal('10.00')}),
    (date(2026, 12, 1), None, {'input': Decimal('4.00'), 'output': Decimal('20.00')}),
)

_MILLION = Decimal(1_000_000)
_PRECISION = Decimal('0.000001')  # estimates are stated to a millionth of a dollar
_MAX_TOKENS = 10 ** 15  # beyond any real answer; keeps every product inside Decimal's 28 digits


class _Invalid(Exception):
    pass


@dataclass(frozen=True)
class _Terms:
    """The rates one answer is priced at, and what its estimate says about them."""
    rates: dict
    as_of: str = RATES_AS_OF
    basis: str = BASIS
    stated: dict = field(default_factory=dict)  # added to the estimate's rates (Gemini's: the day priced and why)


def estimate(model: str, usage, *, on=None) -> Optional[dict]:
    """{'estimated_usd': '0.040690', 'rates': {...}, 'basis': BASIS} for an answer of ``model`` (the model the request
    named) with ``usage`` as the vendor reported it; None when there is nothing to estimate from. ``on``: the day the
    request was sent (a date, or a timezone-aware datetime read in UTC), which a dated rate needs (Gemini's); Astra's
    and Fable's rates are undated and do not read it."""
    priced = _priced(model, usage, on)
    return None if priced is None else _result(model, *priced)


def estimate_loop(model: str, usages, *, on=None) -> Optional[dict]:
    """The estimate for a tool loop whose exchanges reported ``usages`` (each exchange's usage as reported, in order):
    each exchange priced on its own and the costs added up (Astra's long-context rate applies per request). One
    exchange's estimate is estimate()'s exactly. An exchange that reported no usage ({}: one never answered, say) is
    counted and not priced; None when no exchange can be priced or a reported usage cannot be. ``on`` as estimate()'s:
    every exchange of one run is priced at the rate of the day its run was sent."""
    if not isinstance(usages, (list, tuple)):
        return None
    if len(usages) == 1:
        return estimate(model, usages[0], on=on)
    reported = [usage for usage in usages if usage != {}]
    priced = [_priced(model, usage, on) for usage in reported]
    if not priced or any(item is None for item in priced):
        return None
    tokens = {}
    for _, counts, _, _ in priced:
        for kind, count in counts.items():
            tokens[kind] = tokens.get(kind, 0) + count
    extra = {'exchanges': len(usages), 'exchanges_priced': len(priced)}
    if model == ASTRA:
        extra['long_context_exchanges'] = sum(1 for _, _, details, _ in priced if details['long_context'])
    if model == GEMINI:
        extra['thinking_tokens'] = sum(details['thinking_tokens'] for _, _, details, _ in priced)
        extra['cached_tokens'] = sum(details['cached_tokens'] for _, _, details, _ in priced)
    return _result(model, sum(cost for cost, _, _, _ in priced), tokens, extra, priced[0][3])


def _priced(model: str, usage, on) -> Optional[tuple]:
    """(unrounded cost, priced tokens, extra rate details, terms) of one answer, or None."""
    if not isinstance(usage, dict):
        return None
    try:
        if model == ASTRA:
            return (*_astra(usage), _Terms(RATES[ASTRA]))
        if model == FABLE:
            return (*_fable(usage), _Terms(RATES[FABLE]))
        if model == GEMINI:
            return _gemini(usage, on)
    except _Invalid:
        return None
    return None


def _astra(usage: dict) -> tuple:
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
    return cost, tokens, {'long_context': long_context,
                          'multipliers': {'input': str(input_multiplier), 'output': str(output_multiplier)}}


def _fable(usage: dict) -> tuple:
    rates = RATES[FABLE]
    tokens = {'input': _count(usage, 'input_tokens'),
              'cache_write': _count(usage, 'cache_creation_input_tokens', optional=True),
              'cache_read': _count(usage, 'cache_read_input_tokens', optional=True),
              'output': _count(usage, 'output_tokens')}
    cost = sum(tokens[kind] * rates[kind] for kind in tokens) / _MILLION
    return cost, tokens, {}


def _gemini(usage: dict, on) -> tuple:
    day = _day(on)
    if day is None:
        raise _Invalid  # a dated rate needs the day the request was sent
    first, last, rates = next(period for period in GEMINI_PERIODS
                              if (period[0] is None or day >= period[0]) and (period[1] is None or day <= period[1]))
    prompt = _count(usage, 'promptTokenCount')
    candidates = _count(usage, 'candidatesTokenCount', optional=True)
    thoughts = _count(usage, 'thoughtsTokenCount', optional=True)
    cached = _count(usage, 'cachedContentTokenCount', optional=True)
    if cached > prompt:
        raise _Invalid  # the cached tokens are counted inside the prompt's: more of them states no usage that adds up
    if _count(usage, 'toolUsePromptTokenCount', optional=True):
        raise _Invalid  # no tool is offered, and no rate for tool-use prompt tokens is recorded here
    total = usage.get('totalTokenCount')
    if total is not None and (type(total) is not int or total != prompt + candidates + thoughts):
        raise _Invalid  # tokens this estimate would leave unpriced
    # the prompt is priced whole at the input rate, its cached tokens included: an upper bound (GEMINI_BASIS)
    tokens = {'input': prompt, 'output': candidates + thoughts}
    cost = (tokens['input'] * rates['input'] + tokens['output'] * rates['output']) / _MILLION
    effective = f'through {last.isoformat()}' if first is None else f'from {first.isoformat()}'
    terms = _Terms(rates, GEMINI_RATES_AS_OF, GEMINI_BASIS,
                   {'priced_on': day.isoformat(), 'effective': effective, 'source': GEMINI_SOURCE})
    return cost, tokens, {'thinking_tokens': thoughts, 'cached_tokens': cached}, terms


def _day(on) -> Optional[date]:
    """The UTC calendar day of ``on``: a date as given, a timezone-aware datetime converted to UTC; None otherwise (a
    naive datetime names no day anywhere in particular)."""
    if isinstance(on, datetime):
        if on.tzinfo is None or on.utcoffset() is None:
            return None
        return on.astimezone(timezone.utc).date()
    if isinstance(on, date):
        return on
    return None


def _count(usage: dict, key: str, *, optional: bool = False) -> int:
    """A token count as reported: a whole number, zero or more. An optional count that is absent or null is zero."""
    value = usage.get(key)
    if value is None and optional:
        return 0
    if type(value) is not int or not 0 <= value < _MAX_TOKENS:
        raise _Invalid
    return value


def _result(model: str, cost: Decimal, tokens: dict, extra: dict, terms: _Terms) -> dict:
    return {'estimated_usd': f'{cost.quantize(_PRECISION, rounding=ROUND_HALF_UP):f}',
            'rates': {'model': model, 'as_of': terms.as_of,
                      'usd_per_million_tokens': {kind: str(rate) for kind, rate in terms.rates.items()},
                      'priced_tokens': dict(tokens), **terms.stated, **extra},
            'basis': terms.basis}
