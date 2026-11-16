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

The interpreter (Gemini migration, FINAL 3.2; studio/interpretation/adapter.py), read 2026-11-13 (GEMINI_SOURCE):

- gemini-4-carbon (GEMINI, the interpreter's model since DECISIONS D230), Standard tier: input $2.00 and output $10.00
  through 2026-11-30; input $4.00 and output $20.00 from 2026-12-01 - the rates of gemini-4-argon (GEMINI_ARGON), the
  interpreter's model until D230, whose own rates, read 2026-11-09 (GEMINI_ARGON_SOURCE), price the runs whose requests
  named it, so a run is priced by the model its request named and an Argon run keeps its estimate. Each model's
  estimate states its own source, the day it was read and its basis (GEMINI_MODELS). The rates are DATED, so a Gemini
  answer is priced at the rate of the day its request was sent (``on``, a date, or a timezone-aware datetime read in
  UTC) and has no estimate without one - never one at a guessed rate.
  usageMetadata's ``promptTokenCount`` is the input; the output is ``candidatesTokenCount`` plus
  ``thoughtsTokenCount``, since thinking is billed as output (each absent or null count is zero, as the API omits a zero).
  CPT Studio creates no cached content, but Google's implicit caching, on by default, may serve the prefix every
  interpretation request repeats - its instructions and its response schema - from a cache without being asked, and
  report those tokens as ``cachedContentTokenCount``, which ``promptTokenCount`` already includes. The source records
  no cached-input rate, so they are priced with the rest of the prompt at the full input rate: an estimate that reports
  any is an upper bound, on the premise that a cache hit is never billed above the input rate (Google's caching bills
  cache hits at a reduced rate and implicit caching has no storage charge; whether gemini-4-argon caches implicitly at
  all was not observable in the trial, and gemini-4-carbon is not yet measured), and it says how many there were
  (``cached_tokens``) and what that makes it
  (GEMINI_BASIS). A usage stating more cached tokens than prompt tokens has no estimate. CPT Studio offers no tool, and
  no rate is recorded for tool-use prompt tokens, so a usage reporting any has no estimate; nor has one whose
  ``totalTokenCount`` is not its input and output added up (some tokens would be unpriced).

The interpreter since DECISIONS D275 (docs/gemini-migration/AMENDMENT-2.md 1.7 and section 9; step F5):

- claude-fable-5-2 (FABLE_52, interpretation.MODEL_V3; a test pins the two equal) on the Anthropic Messages API, at the
  rates of the claude-api reference cached 2026-11-03 (FABLE_52_SOURCE), which this step checked against that
  reference (its current-models table and its prompt-caching economics; they agree, so no DECISIONS entry): input
  $8.00, a 5-minute cache write $10.00 (1.25 x input), a cache read $0.20, output $40.00. ``input_tokens`` excludes the
  cache's tokens, each counted on its own (``cache_creation_input_tokens``, ``cache_read_input_tokens``);
  ``output_tokens`` includes the thinking tokens, whose count (``output_tokens_details.thinking_tokens``) is reported
  beside the estimate (``thinking_tokens``) and never priced apart. The reference publishes no dated change for this
  model, so the rates are undated and ``on`` is not read; a published change becomes a dated entry as Gemini's are.
- These are the rates of a standard-tier, standard-speed, globally served request whose only cache is the 5-minute one
  the interpreter's request marks (AMENDMENT-2 1.2 and 7.2: the request names no tier, speed or geography, so the API's
  defaults apply). So a usage with tokens no recorded rate covers has no estimate - never one at a guessed rate
  (fail-closed, as Gemini's unpriced tokens): a 1-hour cache write (``cache_creation.ephemeral_1h_input_tokens`` above
  0); a write the 5-minute count does not account for (``cache_creation.ephemeral_5m_input_tokens`` other than
  ``cache_creation_input_tokens``, an absent breakdown counting as zero); ``usage.iterations`` (a server-side step or a
  fallback, whose tokens the top-level counts leave out); a thinking count above the output it is part of; and a usage
  that STATES a term other than the one the rates are for (FABLE_52_TERMS: ``service_tier`` 'standard', ``speed``
  'standard', ``inference_geo`` 'global'), a batch or priority tier, fast mode or US-only inference included. A term a
  usage does not state (absent, or null as every optional field here) is the request's default, the rates' own:
  AMENDMENT-2 E.1 found all three stated on every answer, and a usage built before a send states none - a harness's
  worst case for its cap (AMENDMENT-2 8.3), a constructed answer - so it is priced at these rates, never refused for
  the silence alone.
- Gemini's dated entries stay and price Gemini's stored runs by the model their request named (DECISIONS D289, G2-05);
  a run is never priced at another model's rates.

Corti reports credits, not tokens, and has no estimate here. An answer whose usage lacks a token count, or states one
that is not a whole number of tokens, has no estimate (None) rather than a guessed one.

A tool loop (HARNESS.md 11.2) is several requests, each priced on its own (estimate_loop): the long-context rate is a
property of one request, so a loop's summed usage is never priced as if it were one.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional

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

GEMINI = 'gemini-4-carbon'  # the interpreter's model (studio.interpretation.MODEL; a test pins the two equal)
GEMINI_RATES_AS_OF = '2026-11-13'
GEMINI_BASIS = ('estimated from published rates as of 2026-11-13; prompt tokens served from a cache are priced at the '
                'full input rate, so an estimate that reports any is an upper bound; not reconciled to an invoice')
GEMINI_SOURCE = ("Google's Gemini API pricing page, read 2026-11-13 (DECISIONS D230): gemini-4-carbon, Standard tier, "
                 '$2.00 per million input tokens and $10.00 per million output tokens (thinking included) through '
                 '2026-11-30; $4.00 and $20.00 from 2026-12-01, the rates of gemini-4-argon.')
# The interpreter's model until DECISIONS D230 (2026-11-13): a run whose request named it is priced at its rates as read
# while it was the interpreter's, so the runs it answered keep their estimates and their stated source.
GEMINI_ARGON = 'gemini-4-argon'
GEMINI_ARGON_RATES_AS_OF = '2026-11-09'
GEMINI_ARGON_BASIS = ('estimated from published rates as of 2026-11-09; prompt tokens served from a cache are priced at '
                      'the full input rate, so an estimate that reports any is an upper bound; not reconciled to an '
                      'invoice')
GEMINI_ARGON_SOURCE = ("Google's Gemini API pricing page, read 2026-11-09 (gemini-trial REPORT.md section D): "
                       'gemini-4-argon, Standard tier, $2.00 per million input tokens and $10.00 per million output '
                       'tokens (thinking included) through 2026-11-30; $4.00 and $20.00 from 2026-12-01.')
# Each Gemini model priced here: (the day its rates were read, the basis, the source) its estimates state; both models'
# rates are GEMINI_PERIODS. Any other model name, a near-miss included, has no Gemini estimate.
GEMINI_MODELS = {GEMINI: (GEMINI_RATES_AS_OF, GEMINI_BASIS, GEMINI_SOURCE),
                 GEMINI_ARGON: (GEMINI_ARGON_RATES_AS_OF, GEMINI_ARGON_BASIS, GEMINI_ARGON_SOURCE)}
# (first day, last day, US dollars per million tokens), in order; None is open-ended. A day is a UTC calendar day.
GEMINI_PERIODS: tuple[tuple[Optional[date], Optional[date], dict[str, Decimal]], ...] = (
    (None, date(2026, 11, 30), {'input': Decimal('2.00'), 'output': Decimal('10.00')}),
    (date(2026, 12, 1), None, {'input': Decimal('4.00'), 'output': Decimal('20.00')}),
)

# AMENDMENT-2 1.7 (DECISIONS D275): the interpreter's model on the Anthropic Messages API since D275, its rates undated.
FABLE_52 = 'claude-fable-5-2'  # studio.interpretation.MODEL_V3 (a test pins the two equal)
FABLE_52_RATES_AS_OF = '2026-11-03'
FABLE_52_RATES = {'input': Decimal('8.00'), 'cache_write': Decimal('10.00'), 'cache_read': Decimal('0.20'),
                  'output': Decimal('40.00')}  # US dollars per million tokens; cache_write is the 5-minute write
# The terms those rates are for, as a usage states them (AMENDMENT-2 E.1): a usage that states another value has no
# estimate; one that states none (absent or null) is the request's default, these terms (the request names none, 1.2).
FABLE_52_TERMS = {'service_tier': 'standard', 'speed': 'standard', 'inference_geo': 'global'}
FABLE_52_BASIS = ('estimated from published rates as of 2026-11-03, for a standard-tier, standard-speed, globally '
                  'served request with a 5-minute cache write; thinking is counted in the output; not reconciled '
                  'to an invoice')
FABLE_52_SOURCE = ('the claude-api reference, cached 2026-11-03 (AMENDMENT-2 1.7; DECISIONS D275): claude-fable-5-2, '
                   '$8.00 per million input tokens and $40.00 per million output tokens (thinking included), cache '
                   'reads $0.20 and 5-minute cache writes $10.00 (1.25 x input); no dated change is published.')

_MILLION = Decimal(1_000_000)
_PRECISION = Decimal('0.000001')  # estimates are stated to a millionth of a dollar
_MAX_TOKENS = 10 ** 15  # beyond any real answer; keeps every product inside Decimal's 28 digits


class _Invalid(Exception):
    pass


@dataclass(frozen=True)
class _Terms:
    """The rates one answer is priced at, and what its estimate says about them."""
    rates: dict[str, Decimal]
    as_of: str = RATES_AS_OF
    basis: str = BASIS
    # added to the estimate's rates (Gemini's: the day priced and why; Fable 5.2's: its source and terms)
    stated: dict[str, Any] = field(default_factory=dict)


# (unrounded cost, priced tokens, extra rate details, terms) of one answer
_Priced = tuple[Decimal, dict[str, int], dict[str, Any], _Terms]


def estimate(model: object, usage: object, *, on: object = None) -> Optional[dict[str, Any]]:
    """{'estimated_usd': '0.040690', 'rates': {...}, 'basis': BASIS} for an answer of ``model`` (the model the request
    named) with ``usage`` as the vendor reported it; None when there is nothing to estimate from. ``on``: the day the
    request was sent (a date, or a timezone-aware datetime read in UTC), which a dated rate needs (Gemini's); Astra's
    and both Fables' rates are undated and do not read it."""
    priced = _priced(model, usage, on)
    return None if priced is None else _result(model, *priced)


def estimate_loop(model: object, usages: object, *, on: object = None) -> Optional[dict[str, Any]]:
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
    found = [_priced(model, usage, on) for usage in reported]
    priced = [item for item in found if item is not None]
    if not priced or len(priced) != len(found):
        return None
    tokens: dict[str, int] = {}
    for _, counts, _, _ in priced:
        for kind, count in counts.items():
            tokens[kind] = tokens.get(kind, 0) + count
    extra: dict[str, Any] = {'exchanges': len(usages), 'exchanges_priced': len(priced)}
    if model == ASTRA:
        extra['long_context_exchanges'] = sum(1 for _, _, details, _ in priced if details['long_context'])
    if isinstance(model, str) and model in GEMINI_MODELS:
        extra['thinking_tokens'] = sum(details['thinking_tokens'] for _, _, details, _ in priced)
        extra['cached_tokens'] = sum(details['cached_tokens'] for _, _, details, _ in priced)
    if model == FABLE_52:
        extra['thinking_tokens'] = sum(details['thinking_tokens'] for _, _, details, _ in priced)
    return _result(model, sum((cost for cost, _, _, _ in priced), Decimal(0)), tokens, extra, priced[0][3])


def _priced(model: object, usage: object, on: object) -> Optional[_Priced]:
    """(unrounded cost, priced tokens, extra rate details, terms) of one answer, or None."""
    if not isinstance(usage, dict):
        return None
    try:
        if model == ASTRA:
            return (*_astra(usage), _Terms(RATES[ASTRA]))
        if model == FABLE:
            return (*_fable(usage), _Terms(RATES[FABLE]))
        if model == FABLE_52:
            return _fable_52(usage)
        if isinstance(model, str) and model in GEMINI_MODELS:
            return _gemini(model, usage, on)
    except _Invalid:
        return None
    return None


def _astra(usage: dict[str, Any]) -> tuple[Decimal, dict[str, int], dict[str, Any]]:
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


def _fable(usage: dict[str, Any]) -> tuple[Decimal, dict[str, int], dict[str, Any]]:
    rates = RATES[FABLE]
    tokens = {'input': _count(usage, 'input_tokens'),
              'cache_write': _count(usage, 'cache_creation_input_tokens', optional=True),
              'cache_read': _count(usage, 'cache_read_input_tokens', optional=True),
              'output': _count(usage, 'output_tokens')}
    cost = sum((tokens[kind] * rates[kind] for kind in tokens), Decimal(0)) / _MILLION
    return cost, tokens, {}


def _fable_52(usage: dict[str, Any]) -> _Priced:
    """claude-fable-5-2's estimate (AMENDMENT-2 1.7): the four counts at FABLE_52_RATES, the thinking count beside them;
    _Invalid for a usage with tokens no recorded rate covers or that states a term the rates are not for (the module's
    docstring; a term it does not state is the request's default, the rates' own)."""
    if usage.get('iterations') is not None:
        raise _Invalid  # a server-side step or a fallback: tokens the top-level counts leave out, at no recorded rate
    for term, value in FABLE_52_TERMS.items():
        stated = usage.get(term)
        if stated is not None and stated != value:
            raise _Invalid  # another tier, speed or geography stated: not these rates' terms
    tokens = {'input': _count(usage, 'input_tokens'),
              'cache_write': _count(usage, 'cache_creation_input_tokens', optional=True),
              'cache_read': _count(usage, 'cache_read_input_tokens', optional=True),
              'output': _count(usage, 'output_tokens')}
    written = _details(usage, 'cache_creation')
    if _count(written, 'ephemeral_1h_input_tokens', optional=True) > 0:
        raise _Invalid  # a 1-hour cache write: no rate is recorded for it
    if _count(written, 'ephemeral_5m_input_tokens', optional=True) != tokens['cache_write']:
        raise _Invalid  # a write the 5-minute count does not account for
    thinking = _count(_details(usage, 'output_tokens_details'), 'thinking_tokens', optional=True)
    if thinking > tokens['output']:
        raise _Invalid  # thinking is counted inside the output: more of it states no usage that adds up
    cost = sum((tokens[kind] * FABLE_52_RATES[kind] for kind in tokens), Decimal(0)) / _MILLION
    terms = _Terms(FABLE_52_RATES, FABLE_52_RATES_AS_OF, FABLE_52_BASIS,
                   {'source': FABLE_52_SOURCE, 'terms': dict(FABLE_52_TERMS)})
    return cost, tokens, {'thinking_tokens': thinking}, terms


def _gemini(model: str, usage: dict[str, Any], on: object) -> _Priced:
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
    if first is not None:
        effective = f'from {first.isoformat()}'
    elif last is not None:
        effective = f'through {last.isoformat()}'
    else:  # pragma: no cover - GEMINI_PERIODS bounds every period on one side
        raise _Invalid
    as_of, basis, source = GEMINI_MODELS[model]
    terms = _Terms(rates, as_of, basis, {'priced_on': day.isoformat(), 'effective': effective, 'source': source})
    return cost, tokens, {'thinking_tokens': thoughts, 'cached_tokens': cached}, terms


def _day(on: object) -> Optional[date]:
    """The UTC calendar day of ``on``: a date as given, a timezone-aware datetime converted to UTC; None otherwise (a
    naive datetime names no day anywhere in particular)."""
    if isinstance(on, datetime):
        if on.tzinfo is None or on.utcoffset() is None:
            return None
        return on.astimezone(timezone.utc).date()
    if isinstance(on, date):
        return on
    return None


def _count(usage: dict[str, Any], key: str, *, optional: bool = False) -> int:
    """A token count as reported: a whole number, zero or more. An optional count that is absent or null is zero."""
    value = usage.get(key)
    if value is None and optional:
        return 0
    if type(value) is not int or not 0 <= value < _MAX_TOKENS:
        raise _Invalid
    return value


def _details(usage: dict[str, Any], key: str) -> dict[str, Any]:
    """An optional object of a usage (a breakdown of its counts): {} when absent or null; _Invalid when it is not an
    object."""
    value = usage.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise _Invalid
    return value


def _result(model: object, cost: Decimal, tokens: dict[str, int], extra: dict[str, Any],
            terms: _Terms) -> dict[str, Any]:
    return {'estimated_usd': f'{cost.quantize(_PRECISION, rounding=ROUND_HALF_UP):f}',
            'rates': {'model': model, 'as_of': terms.as_of,
                      'usd_per_million_tokens': {kind: str(rate) for kind, rate in terms.rates.items()},
                      'priced_tokens': dict(tokens), **terms.stated, **extra},
            'basis': terms.basis}
