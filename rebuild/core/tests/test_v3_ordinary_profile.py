"""New bounded ordinary response profile; old immutable profiles retain identity."""
import copy
import json
from decimal import Decimal, ROUND_CEILING
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings
from core import generation as g, v3_field_relations as r, generation_batch as b
from core.jobs import NoProviderRequest
from .test_v3_ordinary_notes import LIVE, field


@override_settings(**dict(LIVE, V3_FIELD_RELATIONS=True, V3_HISTORY_CONTEXT=False))
class OrdinaryResponseProfile(SimpleTestCase):
    def test_new_disabled_profile_has_a_distinct_identity_and_old_snapshots_are_unchanged(self):
        current = g.configuration(); profile = g.job_request_profile(current)
        self.assertEqual((profile['profile'], profile['max_output_tokens'], profile['thinking']),
                         (g.ORDINARY_RESPONSE_PROFILE, 20000, {'type': 'disabled'}))
        self.assertLessEqual(profile['max_output_tokens'], g.NONSTREAMING_MAX_OUTPUT_TOKENS)
        for thinking, limit in (('disabled', 8000), ('adaptive', 16000)):
            old = g.request_profile('anthropic', g.SONNET_5, thinking, 'medium', '')
            config = {**current, 'request_profile': old}
            self.assertEqual(g.job_request_profile(config), old)
            self.assertEqual(old['max_output_tokens'], limit)
        non_v3 = g.configuration([{'key': 'legacy', 'label': 'Chief complaint'}])
        self.assertEqual(non_v3['request_profile']['max_output_tokens'], 8000)
        with override_settings(V3_FIELD_RELATIONS=False):
            off = g.configuration()
            self.assertEqual(off['request_profile']['profile'], 'claude-sonnet-5-v1')
            self.assertEqual(off['request_profile']['max_output_tokens'], 8000)
            self.assertNotEqual(off['pricing_version'], current['pricing_version'])
        for mutate in (lambda c: c['request_profile'].update(max_output_tokens=20001),
                       lambda c: c['request_profile'].update(thinking={'type': 'adaptive', 'display': 'omitted'}),
                       lambda c: c.pop('ordinary_field_contract'),
                       lambda c: c['request_profile'].update(timeout_seconds=121)):
            changed = copy.deepcopy(current); mutate(changed)
            with self.assertRaises(NoProviderRequest): g.job_request_profile(changed)

    def test_capacity_boundary_is_exact_serialized_response_not_an_arbitrary_matrix_size(self):
        # (90 fields: the v4 body states each unit once per field in its context partition - "answer": [1, 2, ...] - so
        # 90 x 10 fits one bounded response, where v3 held 30 and v2 60)
        fields = [field('q' + str(i), 'Question ' + str(i)) for i in range(90)]
        notes = ' '.join('The patient reports symptom ' + str(i) + '.' for i in range(10))
        config = g.configuration(); units = g.source_units(notes, fields)[0]
        self.assertGreater(len(fields) * len(units), 256)
        self.assertLess(r.response_bound(fields, units), 20000)
        fields[-1]['key'] += 'x' * (20000 - r.response_bound(fields, units))
        compiled = r.compile_request(notes, fields, config)
        self.assertEqual(compiled['response_byte_bound'], 20000)
        self.assertFalse(b.needed(fields, notes, config))
        fields[-1]['key'] += 'x'
        self.assertTrue(b.needed(fields, notes, config))
        with patch('anthropic.Anthropic') as provider:
            with self.assertRaises(ValidationError): g.maximum_cost(notes, fields, config)
            provider.assert_not_called()

    def test_exact_sdk_bytes_new_cap_us_geography_and_retail_reservation_share_the_price(self):
        notes = 'The patient does not smoke.'
        fields = [field('smoking', 'Smoker', 'choice', ['Yes', 'No'])]
        for geography in ('', 'us'):
            with self.subTest(geography=geography), override_settings(AI_INFERENCE_GEO=geography):
                config = g.configuration(); compiled = r.compile_request(notes, fields, config)
                wire = compiled['wire']; rate = g.rates(config)
                amount = (Decimal(len(json.dumps(wire).encode()) + 12000) * rate['input_per_million']
                          + Decimal(20000) * rate['output_per_million']) / 1000000
                if geography == 'us': amount *= Decimal('1.1')
                self.assertEqual(g.maximum_cost(notes, fields, config), amount.quantize(g.COST_QUANTUM, rounding=ROUND_CEILING))
                old = {**config, 'request_profile': g.request_profile('anthropic', g.SONNET_5, 'disabled', 'medium', geography)}
                delta = g.maximum_cost(notes, fields, config) - g.maximum_cost(notes, fields, old)
                # 12k additional output tokens plus one serialized max_tokens digit.
                expected_delta = Decimal('0.120002') * (Decimal('1.1') if geography == 'us' else 1)
                self.assertEqual(delta, expected_delta)
                self.assertEqual(delta * Decimal('1.5'), expected_delta * Decimal('1.5'))
                with patch('anthropic.Anthropic') as provider:
                    provider.return_value.messages.create.side_effect = RuntimeError('captured SDK boundary')
                    with self.assertRaisesRegex(RuntimeError, 'captured SDK'): g.generate(notes, fields, config)
                    self.assertEqual(provider.return_value.messages.create.call_args.kwargs, wire)
                self.assertEqual(wire['max_tokens'], 20000)
                self.assertEqual(wire['thinking'], {'type': 'disabled'})

    def test_request_byte_boundary_never_silently_shortens_catalogue(self):
        notes = 'The patient reports pain.'; fields = [field('f', 'Clinical observations')]
        config = g.configuration(); first = r.compile_request(notes, fields, config)
        size = len(json.dumps(first['wire']).encode())
        fields[0]['context'] = 'x' * (r.MAX_REQUEST_BYTES - size)
        compiled = r.compile_request(notes, fields, config)
        self.assertEqual(len(json.dumps(compiled['wire']).encode()), r.MAX_REQUEST_BYTES)
        fields[0]['context'] += 'x'
        with self.assertRaises(ValidationError): r.compile_request(notes, fields, config)
