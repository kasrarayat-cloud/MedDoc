"""Settlement fidelity for NEW Anthropic receipts, and the audit recompute that must move in lockstep with it.

New receipts record the metered `usage.inference_geo`, the thinking share of the output, the stop reason and the refusal
category. US-only inference is billed 1.1× — "for Claude 4.6 and later models … on all token pricing categories"
(pricing page, read 2026-09-27) — only when the provider METERED it, and only on Claude 4.6+. Historical receipts carry
none of the new keys, so `audit_billing` recomputes them to the identical Decimal it always did; that is pinned against a
verbatim copy of the formula as it stood before this change. Fakes only: no provider request leaves the process.
"""
import json
import os
from decimal import Decimal
from unittest.mock import patch

import anthropic
import httpx
from django.test import SimpleTestCase, TestCase, override_settings

from core import generation as g
from core.management.commands.audit_billing import audit_report, recompute_cost, recompute_list_cost
from core.models import Usage
from core.tests.test_sonnet5_profile import (FIELDS, NOTES, PRICE_ENV, SELECTED, SONNET_46, SONNET_5, STORAGES, THINKING,
                                             OutcomeFixture, captured, message, message_json, text)


def old_recompute_list_cost(provider, units, rates):
    """audit_billing.recompute_list_cost as it stood before 2026-09-27, verbatim. Historical rows must still match it."""
    if provider.startswith(('anthropic:', 'openai:')):
        inputs = Decimal(units['input_tokens'])
        cached = Decimal(units.get('cached_input_tokens', 0))
        outputs = Decimal(units['output_tokens'])
        written = Decimal(units.get('cache_creation_tokens', 0))
        if provider.startswith('openai:'):
            inputs -= cached
        return (inputs * Decimal(rates['input_per_million']) + cached * Decimal(rates['cached_per_million'])
                + outputs * Decimal(rates['output_per_million'])
                + written * Decimal(rates['input_per_million']) * Decimal('1.25')) / 1000000
    raise ValueError('No audited cost formula for provider')


class SettlementFidelity(SimpleTestCase):
    USAGE = {'input_tokens': 1234, 'output_tokens': 567, 'cache_read_input_tokens': 89, 'cache_creation_input_tokens': 12}

    def settle(self, overrides, geo, discount='0', **usage):
        reply = message(text(SELECTED), usage={**self.USAGE, 'inference_geo': geo, **usage})
        _, _, result = captured(overrides, reply=reply, env={**PRICE_ENV, 'QUILLMD_PROVIDER_DISCOUNT_RATE': discount})
        _, cost, units, rates, provider, _, simulated = result
        return cost, units, rates, provider, simulated

    def standard(self, rates_in, rates_out, rates_cached):
        u = self.USAGE
        return (u['input_tokens'] * Decimal(rates_in) + u['cache_read_input_tokens'] * Decimal(rates_cached)
                + u['cache_creation_input_tokens'] * Decimal(rates_in) * Decimal('1.25')
                + u['output_tokens'] * Decimal(rates_out)) / 1000000

    def test_a_new_receipt_records_geography_thinking_and_why_it_stopped(self):
        cost, units, rates, provider, _ = self.settle(SONNET_5, 'global', output_tokens_details={'thinking_tokens': 40})
        self.assertEqual(provider, 'anthropic:claude-sonnet-5')
        self.assertEqual({k: units[k] for k in ('inference_geo', 'thinking_tokens', 'stop_reason', 'stop_details_category')},
                         {'inference_geo': 'global', 'thinking_tokens': 40, 'stop_reason': 'end_turn',
                          'stop_details_category': None})
        self.assertEqual(cost, self.standard('2', '10', '0.20'))       # thinking is inside output_tokens: not re-priced
        self.assertNotIn('inference_geo_multiplier', rates)
        _, units, _, _, _ = self.settle(SONNET_5, 'global')
        self.assertNotIn('thinking_tokens', units)                    # recorded only when the provider reports it

    def test_mixed_cache_lifetimes_are_metered_at_their_actual_rates(self):
        cost,units,rates,provider,_=self.settle(SONNET_5,'us',cache_creation={
            'ephemeral_5m_input_tokens':5,'ephemeral_1h_input_tokens':7})
        expected=(self.standard('2','10','.2')+Decimal(7)*2*Decimal('.75')/1000000)*Decimal('1.1')
        self.assertEqual(cost,expected)
        self.assertEqual((units['cache_creation_5m_tokens'],units['cache_creation_1h_tokens']),(5,7))
        self.assertEqual(recompute_cost(provider,units,rates,False),cost)
        for edit in ({'cache_creation_1h_tokens':8},{'cache_creation_5m_tokens':None},
                     {'cache_creation_5m_tokens':-1,'cache_creation_1h_tokens':13}):
            with self.subTest(edit=edit),self.assertRaises(ValueError):
                recompute_list_cost(provider,{**units,**edit},rates)

    def test_inconsistent_provider_cache_lifetimes_cannot_be_settled(self):
        with self.assertRaises(ValueError):
            self.settle(SONNET_5,'global',cache_creation={
                'ephemeral_5m_input_tokens':5,'ephemeral_1h_input_tokens':8})

    def test_metered_us_inference_is_billed_at_1_1_on_claude_4_6_and_later_only(self):
        for overrides, rate in ((SONNET_5, ('2', '10', '0.20')), (SONNET_46, ('3', '15', '0.30'))):
            with self.subTest(model=overrides['AI_MODEL']):
                # Not configured: the WORKSPACE default made it US-only, and that is what is billed.
                cost, units, rates, provider, _ = self.settle(overrides, 'us')
                self.assertEqual(cost, self.standard(*rate) * Decimal('1.1'))
                self.assertEqual(rates['inference_geo_multiplier'], '1.1')
                self.assertEqual(Decimal(rates['list_cost_usd']), cost)
                self.assertEqual(recompute_cost(provider, units, rates, False), cost)
        # A pre-4.6 or unknown model is never multiplied, whatever it reports.
        cost, units, rates, provider, _ = self.settle(dict(SONNET_46, AI_MODEL='claude-haiku-4-5'), 'us')
        self.assertEqual(cost, self.standard('3', '15', '0.30'))
        self.assertNotIn('inference_geo_multiplier', rates)
        self.assertEqual(recompute_cost(provider, units, rates, False), cost)

    def test_the_4_6_plus_rule_reads_the_model_generation(self):
        for provider, expected in (('anthropic:claude-sonnet-4-6', True), ('anthropic:claude-sonnet-5', True),
                                   ('anthropic:claude-opus-4-8', True), ('anthropic:claude-fable-5-1', True),
                                   ('anthropic:claude-opus-4-6-20260101', True),
                                   ('anthropic:claude-haiku-4-5', False), ('anthropic:claude-sonnet-4-5-20250929', False),
                                   ('anthropic:claude-sonnet-4-20250514', False), ('anthropic:claude-opus-4-1', False),
                                   ('anthropic:claude-3-7-sonnet-20250219', False), ('anthropic:synthetic-model', False),
                                   ('openai:claude-sonnet-5', False), ('anthropic:claude-sonnet-5x', False)):
            with self.subTest(provider=provider):
                self.assertIs(g.us_inference_priced(provider), expected)

    def test_settlement_and_the_audit_recompute_in_lockstep(self):
        models = (SONNET_5, SONNET_46, dict(SONNET_46, AI_MODEL='claude-haiku-4-5'))
        for overrides in models:
            for geo in ('us', 'global', None):
                for discount in ('0', '0.2', '0.3333333'):
                    with self.subTest(model=overrides['AI_MODEL'], geo=geo, discount=discount):
                        cost, units, rates, provider, simulated = self.settle(overrides, geo, discount)
                        self.assertEqual(recompute_list_cost(provider, units, rates), Decimal(rates['list_cost_usd']))
                        self.assertEqual(recompute_cost(provider, units, rates, simulated), cost)
                        self.assertEqual(cost, cost.quantize(g.COST_QUANTUM))   # 1.5× still fits the ledger

    def test_historical_receipts_recompute_exactly_as_before(self):
        historical = [
            ('anthropic:claude-sonnet-4-6', {'input_tokens': 4210, 'cached_input_tokens': 0, 'cache_creation_tokens': 0,
                                             'output_tokens': 911}, {'input_per_million': '3', 'output_per_million': '15',
                                                                     'cached_per_million': '0.30', 'discount_rate': '0'}),
            ('anthropic:claude-sonnet-4-6', {'input_tokens': 17, 'cached_input_tokens': 5, 'cache_creation_tokens': 3,
                                             'output_tokens': 2}, {'input_per_million': '3', 'output_per_million': '15',
                                                                   'cached_per_million': '.3'}),
            ('anthropic:synthetic-model', {'input_tokens': 100, 'output_tokens': 10},
             {'input_per_million': '1000', 'output_per_million': '0', 'cached_per_million': '0'}),
            ('openai:gpt-4.1-mini', {'input_tokens': 100, 'cached_input_tokens': 40, 'output_tokens': 10},
             {'input_per_million': '0.4', 'output_per_million': '1.6', 'cached_per_million': '0.1'}),
        ]
        for provider, units, rates in historical:
            with self.subTest(provider=provider, units=units):
                self.assertEqual(recompute_list_cost(provider, units, rates), old_recompute_list_cost(provider, units, rates))
                # Same Decimal, not merely an equal value: the old rows' recorded strings keep comparing identically.
                self.assertEqual(str(recompute_list_cost(provider, units, rates)),
                                 str(old_recompute_list_cost(provider, units, rates)))
        # A new receipt at standard geography is priced by the old formula too.
        _, units, rates, provider, _ = self.settle(SONNET_5, 'global')
        self.assertEqual(recompute_list_cost(provider, units, rates), old_recompute_list_cost(provider, units, rates))

    def test_a_recorded_multiplier_must_agree_with_the_metered_geography(self):
        _, units, rates, provider, _ = self.settle(SONNET_5, 'us')
        self.assertEqual(recompute_list_cost(provider, units, rates), Decimal(rates['list_cost_usd']))
        for units_edit, rates_edit in (({'inference_geo': 'global'}, {}),            # multiplier without US metering
                                       ({}, {'inference_geo_multiplier': None}),     # US metering, multiplier stripped
                                       ({}, {'inference_geo_multiplier': '1.2'})):
            with self.subTest(units=units_edit, rates=rates_edit):
                edited_rates = {k: v for k, v in {**rates, **rates_edit}.items() if v is not None}
                with self.assertRaises(ValueError):
                    recompute_list_cost(provider, {**units, **units_edit}, edited_rates)

    def test_the_real_sdk_response_is_read_for_geography_and_thinking(self):
        """Parsed by the real SDK from JSON, not built by hand: the attribute names are the live response's."""
        Real = anthropic.Anthropic

        def handler(request):
            return httpx.Response(200, json=message_json(THINKING, text(SELECTED), usage={
                'output_tokens_details': {'thinking_tokens': 7}, 'inference_geo': 'us'}))

        def real_client(**kwargs):
            return Real(api_key='synthetic-no-network', http_client=httpx.Client(transport=httpx.MockTransport(handler)),
                        **kwargs)

        with override_settings(**dict(SONNET_5, AI_THINKING='adaptive')), patch.dict(os.environ, PRICE_ENV), \
                patch('anthropic.Anthropic', side_effect=real_client):
            _, cost, units, rates, provider, _, _ = g.generate(NOTES, FIELDS)
        self.assertEqual((units['thinking_tokens'], units['inference_geo'], units['stop_reason']), (7, 'us', 'end_turn'))
        self.assertEqual(rates['inference_geo_multiplier'], '1.1')
        self.assertEqual(recompute_cost(provider, units, rates, False), cost)


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, **SONNET_5)
class Sonnet5ReceiptUnits(OutcomeFixture, TestCase):
    """Through enqueue + run_one: what a new receipt records, and that the billing audit accepts it."""

    def test_metered_us_inference_settles_at_1_1_and_audits_clean(self):
        encounter = self.fresh_encounter()
        job, _ = self.run_job(encounter, message(text(SELECTED), ident='msg_us', usage={'inference_geo': 'us'}))
        self.assertEqual(job.state, 'succeeded')
        usage = Usage.objects.get(job=job)
        self.assertEqual(usage.actual_cost, (Decimal(100) * 2 + Decimal(10) * 10) / 1000000 * Decimal('1.1'))
        self.assertEqual(usage.rates['inference_geo_multiplier'], '1.1')
        self.assertEqual(usage.units['inference_geo'], 'us')
        self.assertEqual(usage.charged_cost, usage.actual_cost * Decimal('1.5'))
        report = audit_report()
        self.assertTrue(report['all_checks_pass'])
        self.assertTrue(report['rows'][0]['checks']['recorded_list_cost_matches'])


    def test_every_stop_is_recorded_with_its_refusal_category(self):
        outcomes = [('end_turn', message(THINKING, text(SELECTED), ident='msg_units_ok',
                                         usage={'output_tokens_details': {'thinking_tokens': 9}}), None),
                    ('refusal', message(stop_reason='refusal', ident='msg_units_refusal', usage={'output_tokens': 0},
                                        stop_details={'type': 'refusal', 'category': 'cyber',
                                                      'explanation': 'synthetic free text never recorded'}), 'cyber'),
                    ('max_tokens', message(text('{"fields":['), stop_reason='max_tokens', ident='msg_units_max'), None),
                    ('model_context_window_exceeded', message(text('{'), stop_reason='model_context_window_exceeded',
                                                              ident='msg_units_window'), None)]
        for stop_reason, reply, category in outcomes:
            with self.subTest(stop_reason=stop_reason):
                job, _ = self.run_job(self.fresh_encounter(), reply)
                units = Usage.objects.get(job=job).units
                self.assertEqual((units['stop_reason'], units['stop_details_category']), (stop_reason, category))
                self.assertIsNone(units['inference_geo'])
                self.assertNotIn('synthetic free text', json.dumps(units))
                if stop_reason == 'end_turn':
                    self.assertEqual((job.state, units['thinking_tokens']), ('succeeded', 9))
                else:
                    self.assertNotIn('thinking_tokens', units)
        self.assertTrue(audit_report()['all_checks_pass'])
