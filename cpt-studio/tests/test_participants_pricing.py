"""Participant cost estimates (HARNESS.md 6): fixed rates dated 2026-11-01, Decimal arithmetic, Astra's long-context
multipliers, and no estimate rather than a guessed one when the usage lacks a token count. Pure; no I/O."""
from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase

from studio.participants import pricing

BASIS = 'estimated from published rates as of 2026-11-01; not reconciled to an invoice'


def astra(input_tokens, output_tokens, cached=None, **extra):
    usage = {'input_tokens': input_tokens, 'output_tokens': output_tokens, **extra}
    if cached is not None:
        usage['input_tokens_details'] = {'cached_tokens': cached}
    return usage


def fable(input_tokens, output_tokens, cache_write=0, cache_read=0, **extra):
    return {'input_tokens': input_tokens, 'cache_creation_input_tokens': cache_write,
            'cache_read_input_tokens': cache_read, 'output_tokens': output_tokens, **extra}


class PricingTests(SimpleTestCase):
    def usd(self, model, usage):
        result = pricing.estimate(model, usage)
        self.assertIsNotNone(result, usage)
        self.assertEqual(set(result), {'estimated_usd', 'rates', 'basis'})
        self.assertEqual(result['basis'], BASIS)
        return result['estimated_usd']

    def test_the_rates_are_the_published_ones_of_2026_11_01(self):
        self.assertEqual(pricing.RATES_AS_OF, '2026-11-01')
        self.assertEqual(pricing.RATES['gpt-6-astra'], {'input': Decimal('10'), 'cached_input': Decimal('1'),
                                                        'output': Decimal('50')})
        self.assertEqual(pricing.RATES['claude-fable-5-1'], {'input': Decimal('10'), 'cache_write': Decimal('12.50'),
                                                             'cache_read': Decimal('0.25'), 'output': Decimal('50')})

    def test_astra(self):
        # The fixture answer's usage: 2,412 input and 911 output tokens, nothing cached.
        self.assertEqual(self.usd('gpt-6-astra', astra(2412, 911, cached=0, total_tokens=3323,
                                                       output_tokens_details={'reasoning_tokens': 448})),
                         '0.069670')
        # input_tokens includes the cached tokens: 6,000 at $10 and 4,000 at $1, then 1,000 output at $50.
        self.assertEqual(self.usd('gpt-6-astra', astra(10_000, 1_000, cached=4_000)), '0.114000')
        self.assertEqual(self.usd('gpt-6-astra', astra(10_000, 1_000)), '0.150000')  # no details: nothing cached

    def test_astra_long_context_prices_the_whole_request_at_2x_input_and_1_5x_output(self):
        self.assertEqual(self.usd('gpt-6-astra', astra(272_000, 2_000)), '2.820000')  # at the threshold: standard
        self.assertEqual(self.usd('gpt-6-astra', astra(272_001, 2_000)), '5.590020')
        result = pricing.estimate('gpt-6-astra', astra(300_000, 2_000, cached=100_000))
        # (200,000 x $10 + 100,000 x $1) x 2 + 2,000 x $50 x 1.5, per million
        self.assertEqual(result['estimated_usd'], '4.350000')
        self.assertEqual((result['rates']['long_context'], result['rates']['multipliers']),
                         (True, {'input': '2', 'output': '1.5'}))
        self.assertEqual(result['rates']['priced_tokens'], {'input': 200_000, 'cached_input': 100_000, 'output': 2_000})

    def test_fable(self):
        self.assertEqual(self.usd('claude-fable-5-1', fable(2650, 1034)), '0.078200')
        self.assertEqual(self.usd('claude-fable-5-1', fable(1000, 100, cache_write=2000, cache_read=4000)),
                         '0.041000')
        absent = {'input_tokens': 1000, 'output_tokens': 100, 'cache_creation_input_tokens': None}
        self.assertEqual(self.usd('claude-fable-5-1', absent), '0.015000')  # an absent or null cache count is zero

    def test_estimates_are_stated_to_a_millionth_rounding_half_up(self):
        self.assertEqual(self.usd('claude-fable-5-1', fable(0, 0, cache_read=1)), '0.000000')  # $0.00000025
        self.assertEqual(self.usd('claude-fable-5-1', fable(0, 0, cache_read=2)), '0.000001')  # $0.0000005
        self.assertEqual(self.usd('claude-fable-5-1', fable(0, 0)), '0.000000')

    def test_no_estimate_without_trustworthy_token_counts(self):
        cases = (('gpt-6-astra', {}), ('gpt-6-astra', {'input_tokens': 10}), ('gpt-6-astra', {'output_tokens': 10}),
                 ('gpt-6-astra', astra(10, True)), ('gpt-6-astra', astra(10.0, 5)), ('gpt-6-astra', astra(-1, 5)),
                 ('gpt-6-astra', astra('10', 5)), ('gpt-6-astra', astra(10, 5, cached=11)),
                 ('gpt-6-astra', astra(10, 5, cached=-1)), ('gpt-6-astra', astra(10, 5, input_tokens_details=[1])),
                 ('gpt-6-astra', astra(10 ** 15, 5)), ('claude-fable-5-1', fable(10, None)),
                 ('claude-fable-5-1', fable(10, 5, cache_read='2')), ('claude-fable-5-1', {'output_tokens': 5}),
                 ('gpt-6-astra', None), ('gpt-6-astra', [10, 5]))
        for model, usage in cases:
            with self.subTest(model=model, usage=usage):
                self.assertIsNone(pricing.estimate(model, usage))

    def test_only_the_two_participants_models_are_priced(self):
        usage = astra(1000, 100)
        for model in ('corti', '', 'gpt-6-astra-2026-09-15', 'claude-opus-5-5', None):
            with self.subTest(model=model):
                self.assertIsNone(pricing.estimate(model, usage))
        self.assertIsNone(pricing.estimate('corti', {'creditsConsumed': 0.019524}))  # credits, not tokens


class LoopEstimateTests(SimpleTestCase):
    """A tool loop (HARNESS.md 11.2) is several requests, each priced on its own."""

    def test_one_exchange_is_estimate_exactly(self):
        for model, usage in (('gpt-6-astra', astra(2412, 911, cached=0)), ('claude-fable-5-1', fable(2650, 1034))):
            with self.subTest(model=model):
                self.assertEqual(pricing.estimate_loop(model, [usage]), pricing.estimate(model, usage))

    def test_each_exchange_is_priced_on_its_own_never_as_one_long_request(self):
        each = astra(200_000, 1_000, cached=0)
        loop = pricing.estimate_loop('gpt-6-astra', [each, each])
        self.assertEqual(Decimal(loop['estimated_usd']), 2 * Decimal(pricing.estimate('gpt-6-astra', each)['estimated_usd']))
        self.assertEqual(loop['estimated_usd'], '4.100000')
        summed = pricing.estimate('gpt-6-astra', astra(400_000, 2_000, cached=0))  # what pricing the sum would claim
        self.assertEqual(summed['estimated_usd'], '8.150000')
        self.assertEqual((loop['rates']['exchanges'], loop['rates']['exchanges_priced'],
                          loop['rates']['long_context_exchanges']), (2, 2, 0))
        self.assertEqual(loop['rates']['priced_tokens'], {'input': 400_000, 'cached_input': 0, 'output': 2_000})
        long = astra(300_000, 1_000, cached=0)
        self.assertEqual(pricing.estimate_loop('gpt-6-astra', [each, long])['rates']['long_context_exchanges'], 1)
        self.assertEqual(loop['basis'], BASIS)

    def test_fable_exchanges_add_up(self):
        loop = pricing.estimate_loop('claude-fable-5-1', [fable(1_000, 100), fable(2_000, 200, cache_read=1_000)])
        self.assertEqual(loop['estimated_usd'], f'{(Decimal(3000 * 10 + 300 * 50) + Decimal("250")) / 1_000_000:.6f}')
        self.assertEqual(loop['rates']['priced_tokens'], {'input': 3_000, 'cache_write': 0, 'cache_read': 1_000,
                                                          'output': 300})

    def test_an_exchange_that_reported_nothing_is_counted_not_priced(self):
        usage = astra(2412, 911, cached=0)
        loop = pricing.estimate_loop('gpt-6-astra', [usage, {}])
        self.assertEqual(loop['estimated_usd'], pricing.estimate('gpt-6-astra', usage)['estimated_usd'])
        self.assertEqual((loop['rates']['exchanges'], loop['rates']['exchanges_priced']), (2, 1))

    def test_no_estimate_rather_than_a_guess(self):
        usage = astra(2412, 911, cached=0)
        for usages in ([usage, {'input_tokens': 'many'}], [{}, {}], [], 'not a list', None, [usage, None]):
            with self.subTest(usages=usages):
                self.assertIsNone(pricing.estimate_loop('gpt-6-astra', usages))
        self.assertIsNone(pricing.estimate_loop('another-model', [usage, usage]))
