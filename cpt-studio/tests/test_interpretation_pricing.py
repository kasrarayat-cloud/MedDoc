"""The interpreter's cost estimate (Gemini migration slice S06; design/FINAL.md 3.2): gemini-4-argon's Standard-tier rates,
read 2026-11-09 - $2.00 per million input tokens and $10.00 per million output tokens, thinking included, through
2026-11-30, and $4.00 and $20.00 from 2026-12-01 - priced at the rate of the day the request was sent, from the
usageMetadata the response reported, in Decimal; no estimate rather than a guessed one. The participants' estimates are
unchanged (tests/test_participants_pricing.py, run beside this). Pure; no I/O."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from django.test import SimpleTestCase

from studio import interpretation
from studio.participants import pricing

GEMINI = 'gemini-4-argon'
BASIS = 'estimated from published rates as of 2026-11-09; not reconciled to an invoice'
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
    def usd(self, reported, on=TRIAL_DAY):
        result = pricing.estimate(GEMINI, reported, on=on)
        self.assertIsNotNone(result, reported)
        self.assertEqual(set(result), {'estimated_usd', 'rates', 'basis'})
        self.assertEqual(result['basis'], BASIS)
        return result['estimated_usd']

    def test_the_rates_are_the_published_ones_read_2026_11_09(self):
        self.assertEqual(pricing.GEMINI, interpretation.MODEL)
        self.assertEqual(pricing.GEMINI_RATES_AS_OF, '2026-11-09')
        self.assertEqual(pricing.GEMINI_PERIODS, (
            (None, date(2026, 11, 30), {'input': Decimal('2.00'), 'output': Decimal('10.00')}),
            (date(2026, 12, 1), None, {'input': Decimal('4.00'), 'output': Decimal('20.00')})))
        for stated in ('gemini-4-argon', 'Standard tier', '$2.00', '$10.00', 'thinking included', '2026-11-30', '$4.00',
                       '$20.00', '2026-12-01', 'read 2026-11-09'):
            with self.subTest(stated=stated):
                self.assertIn(stated, pricing.GEMINI_SOURCE)

    def test_the_trials_seven_answers_price_as_the_report_states(self):
        total = Decimal(0)
        for case, (prompt, candidates, reported) in TRIAL.items():
            with self.subTest(case=case):
                estimated = Decimal(self.usd(usage(prompt, candidates)))
                self.assertEqual(estimated, (prompt * 2 + candidates * 10) / Decimal(1_000_000))
                self.assertEqual(f'{estimated.quantize(Decimal("0.0001"), rounding="ROUND_HALF_UP")}', reported)
                total += estimated
        self.assertEqual(total, Decimal('0.184814'))  # REPORT.md D: $0.185
        result = pricing.estimate(GEMINI, usage(5355, 9183), on=TRIAL_DAY)
        self.assertEqual(result['estimated_usd'], '0.102540')
        self.assertEqual(result['rates'], {
            'model': GEMINI, 'as_of': '2026-11-09', 'usd_per_million_tokens': {'input': '2.00', 'output': '10.00'},
            'priced_tokens': {'input': 5355, 'output': 9183}, 'priced_on': '2026-11-09', 'effective': 'through 2026-11-30',
            'source': pricing.GEMINI_SOURCE, 'thinking_tokens': 0})

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
                 'cached content': usage(10, 5, cachedContentTokenCount=4),
                 'tool-use prompt': usage(10, 5, toolUsePromptTokenCount=4),
                 'a total that does not add up': dict(usage(10, 5), totalTokenCount=16),
                 'a total that leaves thinking unpriced': dict(usage(10, 5), totalTokenCount=1015),
                 'a total as text': dict(usage(10, 5), totalTokenCount='15'),
                 'not an object': [10, 5], 'nothing': None}
        for label, reported in cases.items():
            with self.subTest(label):
                self.assertIsNone(pricing.estimate(GEMINI, reported, on=TRIAL_DAY))
        self.assertIsNotNone(pricing.estimate(GEMINI, {'promptTokenCount': 10}, on=TRIAL_DAY))  # control

    def test_only_this_model_is_priced_at_these_rates(self):
        reported = usage(1000, 100)
        for model in ('gemini-4-argon-001', 'Gemini-4-Argon', 'gemini-4', '', None, 'gpt-6-astra', 'claude-fable-5-1'):
            with self.subTest(model=model):
                self.assertIsNone(pricing.estimate(model, reported, on=TRIAL_DAY))

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
