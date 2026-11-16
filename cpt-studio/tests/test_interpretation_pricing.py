"""The interpreter's cost estimate (Gemini migration slice S06; design/FINAL.md 3.2): gemini-4-carbon's Standard-tier
rates (the interpreter's model since DECISIONS D230), read 2026-11-13 - $2.00 per million input tokens and $10.00 per
million output tokens, thinking included, through 2026-11-30, and $4.00 and $20.00 from 2026-12-01, the rates of
gemini-4-argon, read 2026-11-09, which still price the runs whose requests named it (the trial's seven answers among
them) - priced at the rate of the day the request was sent, from the usageMetadata the response reported, in Decimal;
prompt tokens served from a cache (Google's implicit caching reports them without being asked) priced at the full input
rate, a stated upper bound; no estimate rather than a guessed one. The participants' estimates are unchanged
(tests/test_participants_pricing.py, run beside this). Pure; no I/O.

AMENDMENT-2 1.7 and section 9 (DECISIONS D275; step F5): the interpreter since D275 is claude-fable-5-2, priced at the
claude-api reference's rates of 2026-11-03 (input $8, a 5-minute cache write $10, a cache read $0.20, output $40 per
million tokens, thinking inside the output and never priced apart, undated) from every usage field AMENDMENT-2 E.1
reads, with E.1's real usage objects as vectors; a 1-hour cache write, usage.iterations or a STATED term the rates are
not for leave a usage unpriced, while a term a usage does not state is the request's default (AMENDMENT-2 1.2 names
none), so a usage built before a send - a harness's worst case for its cap (8.3), a constructed answer - is priced.
FablePricingTests below."""
from __future__ import annotations

import itertools
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from django.test import SimpleTestCase

from studio import interpretation
from studio.participants import pricing

GEMINI = 'gemini-4-carbon'  # the interpreter's model (DECISIONS D230)
BASIS = ('estimated from published rates as of 2026-11-13; prompt tokens served from a cache are priced at the full '
         'input rate, so an estimate that reports any is an upper bound; not reconciled to an invoice')
ARGON = 'gemini-4-argon'  # the interpreter's model until D230: the model the trial's requests named
ARGON_BASIS = ('estimated from published rates as of 2026-11-09; prompt tokens served from a cache are priced at the '
               'full input rate, so an estimate that reports any is an upper bound; not reconciled to an invoice')
PERIODS = ((None, date(2026, 11, 30), {'input': Decimal('2.00'), 'output': Decimal('10.00')}),
           (date(2026, 12, 1), None, {'input': Decimal('4.00'), 'output': Decimal('20.00')}))
TRIAL_DAY = date(2026, 11, 9)
# gemini-trial REPORT.md section D: the seven answers of 2026-11-09, (input tokens, output tokens, the report's estimate
# rounded to a ten-thousandth of a dollar). No thinking tokens were reported.
TRIAL = {'note8': (5355, 9183, '0.1025'), 'v1': (1579, 1140, '0.0146'), 'v2': (1518, 1368, '0.0167'),
         'v3': (1533, 1092, '0.0140'), 'v4': (1485, 1094, '0.0139'), 'v5': (1516, 688, '0.0099'),
         'v6': (1556, 1008, '0.0132')}


def usage(prompt, candidates, thoughts=None, **extra):
    """usageMetadata as generateContent reports it (the trial's shape), with a consistent total."""
    reported = {'promptTokenCount': prompt, 'candidatesTokenCount': candidates,
                'totalTokenCount': prompt + candidates + (thoughts or 0),
                'promptTokensDetails': [{'modality': 'TEXT', 'tokenCount': prompt}]}
    if thoughts is not None:
        reported['thoughtsTokenCount'] = thoughts
    reported.update(extra)
    return reported


class GeminiPricingTests(SimpleTestCase):
    def usd(self, reported, on=TRIAL_DAY, model=GEMINI):
        result = pricing.estimate(model, reported, on=on)
        self.assertIsNotNone(result, reported)
        self.assertEqual(set(result), {'estimated_usd', 'rates', 'basis'})
        self.assertEqual(result['basis'], BASIS if model == GEMINI else ARGON_BASIS)
        return result['estimated_usd']

    def test_the_rates_are_the_published_ones_read_2026_11_13(self):
        # DECISIONS D230: gemini-4-carbon at gemini-4-argon's rates, through 2026-11-30 and from 2026-12-01 alike
        self.assertEqual(pricing.GEMINI, interpretation.MODEL)
        self.assertEqual(pricing.GEMINI, 'gemini-4-carbon')
        self.assertEqual(pricing.GEMINI_RATES_AS_OF, '2026-11-13')
        self.assertEqual(pricing.GEMINI_BASIS, BASIS)
        self.assertEqual(pricing.GEMINI_PERIODS, PERIODS)
        for stated in ("Google's Gemini API pricing page, read 2026-11-13", 'gemini-4-carbon', 'Standard tier',
                       '$2.00', '$10.00', 'thinking included', '2026-11-30', '$4.00', '$20.00', '2026-12-01',
                       'the rates of gemini-4-argon'):
            with self.subTest(stated=stated):
                self.assertIn(stated, pricing.GEMINI_SOURCE)
        result = pricing.estimate(GEMINI, usage(5355, 9183), on=date(2026, 11, 20))
        self.assertEqual(result['estimated_usd'], '0.102540')  # 5,355 x $2 + 9,183 x $10, per million: argon's rates
        self.assertEqual(result['rates'], {
            'model': GEMINI, 'as_of': '2026-11-13', 'usd_per_million_tokens': {'input': '2.00', 'output': '10.00'},
            'priced_tokens': {'input': 5355, 'output': 9183}, 'priced_on': '2026-11-20', 'effective': 'through 2026-11-30',
            'source': pricing.GEMINI_SOURCE, 'thinking_tokens': 0, 'cached_tokens': 0})

    def test_a_run_whose_request_named_gemini_4_argon_keeps_argons_rates_and_source(self):
        # the interpreter's model until D230: its runs are priced by the model their request named, at its rates as
        # read 2026-11-09 - the same rates as GEMINI's, with their own date, basis and source
        self.assertEqual((pricing.GEMINI_ARGON, pricing.GEMINI_ARGON_RATES_AS_OF, pricing.GEMINI_ARGON_BASIS),
                         (ARGON, '2026-11-09', ARGON_BASIS))
        self.assertEqual(pricing.GEMINI_MODELS, {
            GEMINI: ('2026-11-13', BASIS, pricing.GEMINI_SOURCE),
            ARGON: ('2026-11-09', ARGON_BASIS, pricing.GEMINI_ARGON_SOURCE)})
        for stated in ('gemini-4-argon', 'Standard tier', '$2.00', '$10.00', 'thinking included', '2026-11-30', '$4.00',
                       '$20.00', '2026-12-01', 'read 2026-11-09'):
            with self.subTest(stated=stated):
                self.assertIn(stated, pricing.GEMINI_ARGON_SOURCE)
        for on in (date(2026, 11, 9), date(2026, 12, 3)):
            with self.subTest(on=on):
                argon, carbon = (pricing.estimate(model, usage(1000, 500, thoughts=250), on=on) for model in (ARGON, GEMINI))
                self.assertEqual(argon['estimated_usd'], carbon['estimated_usd'])
                self.assertEqual((argon['rates']['model'], argon['rates']['as_of'], argon['rates']['source'],
                                  argon['basis']), (ARGON, '2026-11-09', pricing.GEMINI_ARGON_SOURCE, ARGON_BASIS))
                loop = pricing.estimate_loop(ARGON, [usage(1000, 500, thoughts=250), usage(10, 5)], on=on)
                self.assertEqual((loop['rates']['thinking_tokens'], loop['rates']['cached_tokens'], loop['basis']),
                                 (250, 0, ARGON_BASIS))

    def test_the_trials_seven_answers_price_as_the_report_states(self):
        # the trial's requests named gemini-4-argon (2026-11-09), so its answers are priced as Argon's
        total = Decimal(0)
        for case, (prompt, candidates, reported) in TRIAL.items():
            with self.subTest(case=case):
                estimated = Decimal(self.usd(usage(prompt, candidates), model=ARGON))
                self.assertEqual(estimated, (prompt * 2 + candidates * 10) / Decimal(1_000_000))
                self.assertEqual(f'{estimated.quantize(Decimal("0.0001"), rounding="ROUND_HALF_UP")}', reported)
                total += estimated
        self.assertEqual(total, Decimal('0.184814'))  # REPORT.md D: $0.185
        result = pricing.estimate(ARGON, usage(5355, 9183), on=TRIAL_DAY)
        self.assertEqual(result['estimated_usd'], '0.102540')
        self.assertEqual(result['rates'], {
            'model': ARGON, 'as_of': '2026-11-09', 'usd_per_million_tokens': {'input': '2.00', 'output': '10.00'},
            'priced_tokens': {'input': 5355, 'output': 9183}, 'priced_on': '2026-11-09', 'effective': 'through 2026-11-30',
            'source': pricing.GEMINI_ARGON_SOURCE, 'thinking_tokens': 0, 'cached_tokens': 0})

    def test_thinking_is_priced_as_output(self):
        result = pricing.estimate(GEMINI, usage(1000, 500, thoughts=1500), on=TRIAL_DAY)
        self.assertEqual(result['estimated_usd'], '0.022000')  # 1,000 x $2 + (500 + 1,500) x $10, per million
        self.assertEqual((result['rates']['priced_tokens'], result['rates']['thinking_tokens']),
                         ({'input': 1000, 'output': 2000}, 1500))

    def test_the_rate_is_the_one_of_the_day_the_request_was_sent(self):
        reported = usage(1_000_000, 1_000_000)
        cases = ((date(2026, 11, 30), '12.000000', 'through 2026-11-30'),
                 (date(2026, 12, 1), '24.000000', 'from 2026-12-01'),
                 (date(2025, 1, 1), '12.000000', 'through 2026-11-30'),
                 (date(2031, 6, 1), '24.000000', 'from 2026-12-01'),
                 # a time is read in UTC: 2026-12-01 01:00 at UTC+05:00 is still 2026-11-30 in UTC, and the reverse
                 (datetime(2026, 12, 1, 1, 0, tzinfo=timezone(timedelta(hours=5))), '12.000000', 'through 2026-11-30'),
                 (datetime(2026, 11, 30, 20, 0, tzinfo=timezone(timedelta(hours=-5))), '24.000000', 'from 2026-12-01'),
                 (datetime(2026, 11, 30, 23, 59, 59, tzinfo=timezone.utc), '12.000000', 'through 2026-11-30'),
                 (datetime(2026, 12, 1, 0, 0, tzinfo=timezone.utc), '24.000000', 'from 2026-12-01'))
        for on, expected, effective in cases:
            with self.subTest(on=on):
                result = pricing.estimate(GEMINI, reported, on=on)
                self.assertEqual((result['estimated_usd'], result['rates']['effective']), (expected, effective))
                self.assertEqual(result['rates']['priced_on'], on.astimezone(timezone.utc).date().isoformat()
                                 if isinstance(on, datetime) else on.isoformat())

    def test_no_estimate_without_the_day_the_request_was_sent(self):
        reported = usage(5355, 9183)
        for on in (None, datetime(2026, 11, 9, 12, 0), '2026-11-09', 20261109, 1762646400.0):
            with self.subTest(on=on):
                self.assertIsNone(pricing.estimate(GEMINI, reported, on=on))
        self.assertIsNone(pricing.estimate(GEMINI, reported))  # a caller that passes no day gets no guessed rate
        self.assertIsNone(pricing.estimate_loop(GEMINI, [reported]))

    def test_an_absent_or_null_output_or_thinking_count_is_zero(self):
        self.assertEqual(self.usd({'promptTokenCount': 1000}), '0.002000')  # a zero is omitted by the API
        self.assertEqual(self.usd({'promptTokenCount': 1000, 'candidatesTokenCount': None, 'thoughtsTokenCount': None,
                                   'cachedContentTokenCount': 0, 'toolUsePromptTokenCount': None}), '0.002000')
        self.assertEqual(self.usd({'promptTokenCount': 0, 'candidatesTokenCount': 0}), '0.000000')

    def test_no_estimate_rather_than_a_guess(self):
        cases = {'no input count': {'candidatesTokenCount': 10},
                 'input as text': {'promptTokenCount': '10', 'candidatesTokenCount': 5},
                 'input as a float': usage(10.0, 5), 'a boolean': usage(10, True),
                 'negative': usage(-1, 5), 'beyond any answer': usage(10 ** 15, 5),
                 'thinking as text': {'promptTokenCount': 10, 'candidatesTokenCount': 5, 'thoughtsTokenCount': '3'},
                 'more cached tokens than the prompt holds': usage(10, 5, cachedContentTokenCount=11),
                 'cached tokens as text': usage(10, 5, cachedContentTokenCount='4'),
                 'cached tokens negative': usage(10, 5, cachedContentTokenCount=-1),
                 'cached tokens as a float': usage(10, 5, cachedContentTokenCount=4.0),
                 'tool-use prompt': usage(10, 5, toolUsePromptTokenCount=4),
                 'a total that does not add up': dict(usage(10, 5), totalTokenCount=16),
                 'a total that leaves thinking unpriced': dict(usage(10, 5), totalTokenCount=1015),
                 'a total as text': dict(usage(10, 5), totalTokenCount='15'),
                 'not an object': [10, 5], 'nothing': None}
        for label, reported in cases.items():
            with self.subTest(label):
                self.assertIsNone(pricing.estimate(GEMINI, reported, on=TRIAL_DAY))
        self.assertIsNotNone(pricing.estimate(GEMINI, {'promptTokenCount': 10}, on=TRIAL_DAY))  # control

    def test_prompt_tokens_served_from_a_cache_are_priced_at_the_full_input_rate_an_upper_bound(self):
        # Google's implicit caching may serve the prefix every request repeats (the instructions and the schema) from a
        # cache without being asked; promptTokenCount already includes those tokens. No cached-input rate is recorded,
        # so they are priced at the input rate, and the estimate says how many there were.
        reported = {'promptTokenCount': 8000, 'cachedContentTokenCount': 4096, 'candidatesTokenCount': 3000,
                    'totalTokenCount': 11000, 'promptTokensDetails': [{'modality': 'TEXT', 'tokenCount': 8000}],
                    'cacheTokensDetails': [{'modality': 'TEXT', 'tokenCount': 4096}]}
        day = date(2026, 11, 20)
        result = pricing.estimate(GEMINI, reported, on=day)
        self.assertIsNotNone(result)
        self.assertEqual(result['estimated_usd'], '0.046000')  # 8,000 x $2 + 3,000 x $10, per million
        self.assertEqual((result['rates']['priced_tokens'], result['rates']['cached_tokens'], result['basis']),
                         ({'input': 8000, 'output': 3000}, 4096, BASIS))
        uncached = {key: value for key, value in reported.items()
                    if key not in ('cachedContentTokenCount', 'cacheTokensDetails')}
        plain = pricing.estimate(GEMINI, uncached, on=day)
        self.assertEqual(result, {**plain, 'rates': {**plain['rates'], 'cached_tokens': 4096}})  # only the count differs
        # a prompt served whole from the cache (the same request sent again), at the rate of its day
        whole = dict(usage(5000, 1000), cachedContentTokenCount=5000)
        self.assertEqual(self.usd(whole, on=date(2026, 12, 2)), '0.040000')  # 5,000 x $4 + 1,000 x $20, per million
        # a loop adds the cached tokens up, as it adds the thinking tokens
        loop = pricing.estimate_loop(GEMINI, [reported, whole, usage(100, 10)], on=day)
        self.assertEqual((loop['estimated_usd'], loop['rates']['cached_tokens'], loop['rates']['priced_tokens'],
                          loop['basis']),
                         ('0.066300', 9096, {'input': 13100, 'output': 4010}, BASIS))
        # tool-use prompt tokens stay unpriced: no tool is offered, and no rate is recorded for them
        self.assertIsNone(pricing.estimate(GEMINI, dict(reported, toolUsePromptTokenCount=1), on=day))

    def test_only_these_models_are_priced_at_these_rates(self):
        reported = usage(1000, 100)
        for model in ('gemini-4-argon-001', 'Gemini-4-Argon', 'gemini-4', '', None, 'gpt-6-astra', 'claude-fable-5-1',
                      'gemini-4-carbon-001', 'Gemini-4-Carbon', 'gemini-4-carbon ', 'carbon', 'argon', 7,
                      ('gemini-4-carbon',), 'claude-fable-5-2'):
            with self.subTest(model=model):
                self.assertIsNone(pricing.estimate(model, reported, on=TRIAL_DAY))
                self.assertIsNone(pricing.estimate_loop(model, [reported, reported], on=TRIAL_DAY))
        for model in (GEMINI, ARGON):  # the control: each priced model, exactly
            with self.subTest(model=model):
                self.assertIsNotNone(pricing.estimate(model, reported, on=TRIAL_DAY))

    def test_one_exchange_is_estimate_exactly_and_a_loop_prices_each_exchange(self):
        first, second = usage(1000, 100, thoughts=50), usage(2000, 200)
        self.assertEqual(pricing.estimate_loop(GEMINI, [first], on=TRIAL_DAY),
                         pricing.estimate(GEMINI, first, on=TRIAL_DAY))
        loop = pricing.estimate_loop(GEMINI, [first, {}, second], on=date(2026, 12, 5))
        self.assertEqual(loop['estimated_usd'], f'{(Decimal(3000 * 4) + Decimal(350 * 20)) / 1_000_000:.6f}')
        self.assertEqual((loop['rates']['exchanges'], loop['rates']['exchanges_priced'], loop['rates']['thinking_tokens'],
                          loop['rates']['priced_tokens'], loop['rates']['effective'], loop['basis']),
                         (3, 2, 50, {'input': 3000, 'output': 350}, 'from 2026-12-01', BASIS))
        self.assertIsNone(pricing.estimate_loop(GEMINI, [first, {'promptTokenCount': 'x'}], on=TRIAL_DAY))

    def test_the_participants_estimates_are_unchanged_and_ignore_the_day(self):
        astra = {'input_tokens': 2412, 'output_tokens': 911, 'input_tokens_details': {'cached_tokens': 0}}
        fable = {'input_tokens': 2650, 'output_tokens': 1034}
        for model, reported, expected in (('gpt-6-astra', astra, '0.069670'), ('claude-fable-5-1', fable, '0.078200')):
            with self.subTest(model=model):
                plain = pricing.estimate(model, reported)
                self.assertEqual(plain['estimated_usd'], expected)
                self.assertEqual((plain['rates']['as_of'], plain['basis']),
                                 ('2026-11-01', 'estimated from published rates as of 2026-11-01; not reconciled to '
                                                'an invoice'))
                self.assertNotIn('priced_on', plain['rates'])
                for on in (TRIAL_DAY, date(2026, 12, 5), datetime(2026, 12, 5, tzinfo=timezone.utc), 'not a day'):
                    self.assertEqual(pricing.estimate(model, reported, on=on), plain)
                    self.assertEqual(pricing.estimate_loop(model, [reported, reported], on=on),
                                     pricing.estimate_loop(model, [reported, reported]))


# --- AMENDMENT-2 1.7 (DECISIONS D275): claude-fable-5-2, the interpreter since D275 -----------------------------------

FABLE_52 = 'claude-fable-5-2'
FABLE_52_RATES = {'input': Decimal('8.00'), 'cache_write': Decimal('10.00'), 'cache_read': Decimal('0.20'),
                  'output': Decimal('40.00')}
FABLE_52_BASIS = ('estimated from published rates as of 2026-11-03, for a standard-tier, standard-speed, globally '
                  'served request with a 5-minute cache write; thinking is counted in the output; not reconciled to '
                  'an invoice')
TERMS = {'service_tier': 'standard', 'speed': 'standard', 'inference_geo': 'global'}


def anthropic(input_tokens, output_tokens, *, thinking, write_5m=0, write_1h=0, read=0, **extra):
    """A usage object as AMENDMENT-2 E.1 reads every Fable answer's: all its fields, in its shape."""
    return {'input_tokens': input_tokens, 'cache_creation_input_tokens': write_5m + write_1h,
            'cache_read_input_tokens': read,
            'cache_creation': {'ephemeral_5m_input_tokens': write_5m, 'ephemeral_1h_input_tokens': write_1h},
            'output_tokens': output_tokens, **TERMS, 'output_tokens_details': {'thinking_tokens': thinking}, **extra}


# E.1's real usage objects, read from the probes' frozen bodies (probe.anthropic_usage; anthropic-project/batches), each
# with the estimate 1.7's rates give it: (usage, estimated_usd or None). A 1-hour write has no estimate (F3all's probe
# cached with a 1-hour TTL; the interpreter's request marks only the 5-minute cache, AMENDMENT-2 7.2).
RECORDED = {
    'F2high, a short note, pass 1, no cache': (anthropic(44749, 10663, thinking=5766), '0.784512'),
    'F2high, a 19.4 KB note, pass 1 cut at max_tokens 64,000': (anthropic(52150, 64000, thinking=29109), '2.977200'),
    'F2high-p2, a short note, pass 2 under structured outputs': (anthropic(7538, 12562, thinking=8832), '0.562784'),
    # 472 x $8 + 44,466 x $0.20 + 10,824 x $40 = $0.4456292, stated to a millionth half up
    'F3all, a short note, pass 1 reading the cached instruction': (anthropic(472, 10824, thinking=6120, read=44466),
                                                                   '0.445629'),
    # 34,860 x $8 + 3,253 x $0.20 + 77,483 x $40 = $3.3788506
    'F3long, a 19.4 KB note, pass 2 over 756 claims': (anthropic(34860, 77483, thinking=43623, read=3253), '3.378851'),
    'F3all, the first pass 1: a 1-hour cache write': (anthropic(411, 9716, thinking=5023, write_1h=44466), None),
    'F3all, the first pass 2: a 1-hour cache write': (anthropic(2376, 3636, thinking=1487, write_1h=3253), None),
}


class FablePricingTests(SimpleTestCase):
    def test_the_rates_are_the_claude_api_references_of_2026_11_03(self):
        # AMENDMENT-2 section 9: "a new one pins pricing.FABLE_52 == interpretation.MODEL_V3"
        self.assertEqual(pricing.FABLE_52, interpretation.MODEL_V3)
        self.assertEqual(pricing.FABLE_52, FABLE_52)
        self.assertEqual(pricing.FABLE_52_RATES, FABLE_52_RATES)
        self.assertEqual(pricing.FABLE_52_RATES['cache_write'], pricing.FABLE_52_RATES['input'] * Decimal('1.25'))
        self.assertEqual((pricing.FABLE_52_RATES_AS_OF, pricing.FABLE_52_BASIS, pricing.FABLE_52_TERMS),
                         ('2026-11-03', FABLE_52_BASIS, TERMS))
        for stated in ('the claude-api reference, cached 2026-11-03', 'claude-fable-5-2', '$8.00', '$40.00',
                       'thinking included', '$0.20', '5-minute cache writes $10.00', 'no dated change'):
            with self.subTest(stated=stated):
                self.assertIn(stated, pricing.FABLE_52_SOURCE)
        self.assertEqual(pricing.GEMINI, interpretation.MODEL)  # Gemini's pin stays (section 9)

    def test_e1s_recorded_usage_objects_price_at_1_7s_rates(self):
        for label, (reported, expected) in RECORDED.items():
            with self.subTest(label):
                found = pricing.estimate(FABLE_52, reported)
                if expected is None:
                    self.assertIsNone(found)
                    continue
                self.assertEqual(found['estimated_usd'], expected)
                tokens = found['rates']['priced_tokens']
                self.assertEqual(tokens, {'input': reported['input_tokens'],
                                          'cache_write': reported['cache_creation_input_tokens'],
                                          'cache_read': reported['cache_read_input_tokens'],
                                          'output': reported['output_tokens']})
                self.assertEqual(Decimal(found['estimated_usd']), (sum(
                    (tokens[kind] * FABLE_52_RATES[kind] for kind in tokens), Decimal(0)) / 1_000_000).quantize(
                    Decimal('0.000001'), rounding='ROUND_HALF_UP'))
                self.assertEqual(found['rates']['thinking_tokens'],
                                 reported['output_tokens_details']['thinking_tokens'])
                self.assertEqual(found['basis'], FABLE_52_BASIS)
        whole = pricing.estimate(FABLE_52, RECORDED['F2high, a short note, pass 1, no cache'][0])
        self.assertEqual(whole['rates'], {
            'model': FABLE_52, 'as_of': '2026-11-03',
            'usd_per_million_tokens': {'input': '8.00', 'cache_write': '10.00', 'cache_read': '0.20',
                                       'output': '40.00'},
            'priced_tokens': {'input': 44749, 'cache_write': 0, 'cache_read': 0, 'output': 10663},
            'source': pricing.FABLE_52_SOURCE, 'terms': TERMS, 'thinking_tokens': 5766})

    def test_a_5_minute_write_is_priced_at_1_25_times_input(self):
        # the cache the interpreter's request writes (AMENDMENT-2 7.2): F3all's first pass 1 as a 5-minute write -
        # 411 x $8 + 44,466 x $10 + 9,716 x $40
        five = anthropic(411, 9716, thinking=5023, write_5m=44466)
        self.assertEqual(pricing.estimate(FABLE_52, five)['estimated_usd'], '0.836588')
        self.assertEqual(pricing.estimate(FABLE_52, five)['rates']['priced_tokens']['cache_write'], 44466)
        # the same counts with the write named only in the total: the breakdown absent counts as no 5-minute write
        bare = {key: value for key, value in five.items() if key != 'cache_creation'}
        self.assertIsNone(pricing.estimate(FABLE_52, bare))
        self.assertIsNotNone(pricing.estimate(FABLE_52, {**bare, 'cache_creation_input_tokens': 0}))  # control

    def test_thinking_is_reported_beside_the_estimate_and_never_priced_apart(self):
        base = anthropic(1000, 5000, thinking=0)
        for thinking in (0, 1, 2500, 5000):
            with self.subTest(thinking=thinking):
                found = pricing.estimate(FABLE_52, {**base, 'output_tokens_details': {'thinking_tokens': thinking}})
                self.assertEqual(found['estimated_usd'], '0.208000')  # 1,000 x $8 + 5,000 x $40, thinking inside
                self.assertEqual(found['rates']['thinking_tokens'], thinking)
        absent = {key: value for key, value in base.items() if key != 'output_tokens_details'}
        self.assertEqual(pricing.estimate(FABLE_52, absent)['rates']['thinking_tokens'], 0)  # an absent count is zero

    def test_no_rate_no_estimate(self):
        # 1.7: a 1-hour write, a 5-minute count that is not the whole write, usage.iterations; a stated term other than
        # E.1's; counts that do not add up or are not whole numbers - each refused, never priced at a guessed rate
        good = anthropic(1000, 500, thinking=200, write_5m=300, read=40)
        self.assertIsNotNone(pricing.estimate(FABLE_52, good))
        cases = {
            'a 1-hour write beside the 5-minute one': {**good, 'cache_creation_input_tokens': 301,
                                                       'cache_creation': {'ephemeral_5m_input_tokens': 300,
                                                                          'ephemeral_1h_input_tokens': 1}},
            # the 1-hour rule alone (refutation VF51-3): the 5-minute count IS the whole write, a 1-hour count beside it
            'a 1-hour count beside a 5-minute count that is the whole write': {
                **good, 'cache_creation_input_tokens': 300,
                'cache_creation': {'ephemeral_5m_input_tokens': 300, 'ephemeral_1h_input_tokens': 1}},
            'a 1-hour count with no write at all': {
                **good, 'cache_creation_input_tokens': 0,
                'cache_creation': {'ephemeral_5m_input_tokens': 0, 'ephemeral_1h_input_tokens': 7}},
            'a 5-minute count short of the write': {**good, 'cache_creation': {'ephemeral_5m_input_tokens': 299,
                                                                              'ephemeral_1h_input_tokens': 0}},
            'a 5-minute count beyond the write': {**good, 'cache_creation': {'ephemeral_5m_input_tokens': 301}},
            'iterations (a fallback)': {**good, 'iterations': [{'type': 'fallback_message', 'input_tokens': 9}]},
            'iterations (a server-side step)': {**good, 'iterations': [{'type': 'compaction', 'input_tokens': 9}]},
            'iterations, empty': {**good, 'iterations': []},
            'the batch tier': {**good, 'service_tier': 'batch'},
            'the priority tier': {**good, 'service_tier': 'priority'},
            'fast mode': {**good, 'speed': 'fast'},
            'US-only inference': {**good, 'inference_geo': 'us'},
            # a stated term is read as stated, whatever its form: only the rates' own value is theirs
            'a tier stated as empty text': {**good, 'service_tier': ''},
            'a speed stated in capitals': {**good, 'speed': 'STANDARD'},
            'a geography stated as a list': {**good, 'inference_geo': ['global']},
            'a speed stated as a number': {**good, 'speed': 1},
            'fast mode stated on a usage that states no other term': {
                **{key: value for key, value in good.items() if key not in TERMS}, 'speed': 'fast'},
            'more thinking than output': {**good, 'output_tokens_details': {'thinking_tokens': 501}},
            'thinking as text': {**good, 'output_tokens_details': {'thinking_tokens': '200'}},
            'a breakdown that is not an object': {**good, 'cache_creation': [300, 0]},
            'output details that are not an object': {**good, 'output_tokens_details': 200},
            'no input count': {key: value for key, value in good.items() if key != 'input_tokens'},
            'no output count': {key: value for key, value in good.items() if key != 'output_tokens'},
            'input as a float': {**good, 'input_tokens': 1000.0}, 'a boolean': {**good, 'output_tokens': True},
            'negative': {**good, 'cache_read_input_tokens': -1},
            'beyond any answer': {**good, 'input_tokens': 10 ** 15},
            'a 1-hour count as text': {**good, 'cache_creation': {'ephemeral_5m_input_tokens': 300,
                                                                 'ephemeral_1h_input_tokens': '0'}},
            'not an object': [1000, 500], 'nothing': None, 'no usage at all (a stream without message_delta)': {},
        }
        for label, reported in cases.items():
            with self.subTest(label):
                self.assertIsNone(pricing.estimate(FABLE_52, reported))
        # a null iterations, a null breakdown and a null cache count are absent ones (as the module reads every count)
        self.assertEqual(pricing.estimate(FABLE_52, {**good, 'iterations': None}), pricing.estimate(FABLE_52, good))
        nulls = {**good, 'cache_creation_input_tokens': None, 'cache_creation': None, 'cache_read_input_tokens': None}
        self.assertEqual(pricing.estimate(FABLE_52, nulls)['rates']['priced_tokens'],
                         {'input': 1000, 'cache_write': 0, 'cache_read': 0, 'output': 500})

    def test_a_term_a_usage_does_not_state_is_the_requests_default(self):
        """Refutation VF51-1: AMENDMENT-2 1.2's request names no tier, speed or geography, so a term a usage does not
        state - absent or null - is the API's default, the rates' own, and a usage built before a send states none.
        Such a usage is priced exactly as the one stating all three, never refused for the silence alone (a STATED
        other value is: test_no_rate_no_estimate)."""
        good = anthropic(1000, 500, thinking=200, write_5m=300, read=40)
        stated = pricing.estimate(FABLE_52, good)
        self.assertEqual(stated['estimated_usd'], '0.031008')  # 1,000 x $8 + 300 x $10 + 40 x $0.20 + 500 x $40
        for size in (1, 2, 3):
            for silent in itertools.combinations(TERMS, size):
                for form in ('absent', 'null'):
                    reported = {key: value for key, value in good.items() if key not in silent}
                    if form == 'null':
                        reported.update({term: None for term in silent})
                    with self.subTest(silent=silent, form=form):
                        self.assertEqual(pricing.estimate(FABLE_52, reported), stated)
        # the worst case a harness reserves before a send (AMENDMENT-2 8.3): the cached prefix as a 5-minute write, the
        # rest of the body as input, max_tokens as output - Anthropic's count fields only, no term
        reserved = {'input_tokens': 9000, 'cache_creation_input_tokens': 180000, 'cache_read_input_tokens': 0,
                    'output_tokens': 128000,
                    'cache_creation': {'ephemeral_5m_input_tokens': 180000, 'ephemeral_1h_input_tokens': 0}}
        found = pricing.estimate(FABLE_52, reserved)
        self.assertEqual(found['estimated_usd'], '6.992000')  # 9,000 x $8 + 180,000 x $10 + 128,000 x $40
        self.assertEqual(found['rates']['terms'], TERMS)  # the terms the estimate is for, stated beside it
        unmarked = {**reserved, 'input_tokens': 160000, 'cache_creation_input_tokens': 0,
                    'cache_creation': {'ephemeral_5m_input_tokens': 0, 'ephemeral_1h_input_tokens': 0}}
        self.assertEqual(pricing.estimate(FABLE_52, unmarked)['estimated_usd'], '6.400000')  # pass 2: no marker
        self.assertEqual(pricing.estimate_loop(FABLE_52, [reserved, unmarked])['estimated_usd'], '13.392000')
        # ... while a prefix written at a 1-hour time-to-live still has no rate (1.7), and a stated term still decides
        self.assertIsNone(pricing.estimate(FABLE_52, {**reserved, 'cache_creation': {
            'ephemeral_5m_input_tokens': 0, 'ephemeral_1h_input_tokens': 180000}}))
        self.assertIsNone(pricing.estimate(FABLE_52, {**reserved, 'speed': 'fast'}))
        # a constructed answer stating the tier alone (message_start's usage with message_delta's merged over it)
        answer = {'input_tokens': 4210, 'cache_creation_input_tokens': 44466, 'cache_read_input_tokens': 0,
                  'cache_creation': {'ephemeral_5m_input_tokens': 44466, 'ephemeral_1h_input_tokens': 0},
                  'output_tokens': 15210, 'service_tier': 'standard', 'output_tokens_details': {'thinking_tokens': 9120}}
        self.assertEqual(pricing.estimate(FABLE_52, answer)['estimated_usd'], '1.086740')  # 4,210x8+44,466x10+15,210x40

    def test_the_rates_are_undated(self):
        reported = RECORDED['F3all, a short note, pass 1 reading the cached instruction'][0]
        plain = pricing.estimate(FABLE_52, reported)
        self.assertNotIn('priced_on', plain['rates'])
        for on in (TRIAL_DAY, date(2026, 12, 5), datetime(2027, 1, 1, tzinfo=timezone.utc), datetime(2026, 12, 5),
                   'not a day', None):
            with self.subTest(on=on):
                self.assertEqual(pricing.estimate(FABLE_52, reported, on=on), plain)

    def test_a_run_is_priced_only_by_the_model_its_request_named(self):
        reported = RECORDED['F2high, a short note, pass 1, no cache'][0]
        for model in ('claude-fable-5-2-preview', 'Claude-Fable-5-2', 'claude-fable-5-2 ', 'claude-fable-5', 'fable',
                      'claude-mythos-5-2', '', None, 7, (FABLE_52,), GEMINI, ARGON):
            with self.subTest(model=model):
                self.assertIsNone(pricing.estimate(model, reported, on=TRIAL_DAY))
        # the participant's Fable 5.1 prices the same counts at its own rates, never at 5.2's (and the reverse)
        older = pricing.estimate('claude-fable-5-1', reported)
        self.assertEqual(older['estimated_usd'], '0.980640')  # 44,749 x $10 + 10,663 x $50
        self.assertNotEqual(older['estimated_usd'], pricing.estimate(FABLE_52, reported)['estimated_usd'])

    def test_one_exchange_is_estimate_exactly_and_a_loop_adds_up_each_exchange(self):
        first = RECORDED['F2high, a short note, pass 1, no cache'][0]
        second = RECORDED['F3all, a short note, pass 1 reading the cached instruction'][0]
        self.assertEqual(pricing.estimate_loop(FABLE_52, [first]), pricing.estimate(FABLE_52, first))
        loop = pricing.estimate_loop(FABLE_52, [first, {}, second])
        self.assertEqual(loop['estimated_usd'], '1.230141')  # $0.784512 + $0.4456292, rounded once
        self.assertEqual((loop['rates']['exchanges'], loop['rates']['exchanges_priced'],
                          loop['rates']['thinking_tokens'], loop['rates']['priced_tokens']),
                         (3, 2, 5766 + 6120, {'input': 44749 + 472, 'cache_write': 0, 'cache_read': 44466,
                                              'output': 10663 + 10824}))
        self.assertIsNone(pricing.estimate_loop(FABLE_52, [first, RECORDED[
            'F3all, the first pass 1: a 1-hour cache write'][0]]))  # one unpriceable exchange: no estimate
