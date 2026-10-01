"""Claude Sonnet 5.5 (`claude-sonnet-5-5`): the request profile, the bytes every path sends, outcomes and price.

Offline. The Anthropic SDK (0.125.0, which predates `between_tools` in its types) is constructed for real around an
httpx MockTransport that answers inside this process, so what is checked is what the SDK would put on the wire; no
request leaves the machine. The migration guide these tests follow was fetched 2026-10-01 and is retained beside the
task evidence (rebuild/.runtime/v1-sonnet55-20261001/docs/migration-guide.md).

What each group proves, and how it would fail:
  · PROFILE — 'disabled'/'between_tools' send {"type": "between_tools"} at low/medium/high, 'adaptive' sends adaptive
    with its text omitted; xhigh/max, 'disabled' as a wire value, a stray `display`, other rates and tampered snapshots
    are refused before any hold or request. claude-sonnet-5 and claude-sonnet-4-6 fingerprints are unchanged.
  · WIRE — ordinary (default and complete-sentence), history context, field relations, large forms (batch), mapping and
    narrative: each request as serialized by the SDK, against one closed request shape.
  · OUTCOMES — a leading thinking block is read by type; refusal (any category), max_tokens truncation,
    model_context_window_exceeded and an answer from another model are settled at their metered cost, never adopted,
    and absorbed; the refusal category is recorded and its free text never is.
  · PRICE — the 5.5 pricing versions are new and pinned; thinking tokens are inside output and priced once; cache writes,
    cache reads, US-only inference and the hold.
"""
import contextlib
import copy
import json
import os
import uuid
from decimal import Decimal, ROUND_CEILING
from types import SimpleNamespace
from unittest.mock import patch

import anthropic
import httpx
from anthropic import transform_schema
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from pydantic import TypeAdapter

from core import generation as g
from core.jobs import NoProviderRequest, PLATFORM_FAILURE, enqueue, run_one
from core.management.commands.audit_billing import audit_report, recompute_cost, recompute_list_cost
from core.models import Job, LedgerEntry, PlatformCost, ProviderReceipt, Reservation, Usage
from core.security import private_path
from core.tests.test_anthropic_schema_compatibility import unsupported
from core.tests.test_sonnet5_profile import (FIELDS, NOTES, PRICE_ENV, ROLLBACK_FINGERPRINT, SELECTED, SONNET_46,
                                             SONNET_5, SONNET_5_ADAPTIVE_MEDIUM, SONNET_5_DISABLED_MEDIUM,
                                             SONNET_5_DISABLED_MEDIUM_US, STORAGES, THINKING, OutcomeFixture,
                                             keys_anywhere, message_json, text)

REAL_ANTHROPIC = anthropic.Anthropic
MODEL = 'claude-sonnet-5-5'
#: The default 5.5 configuration: the settings defaults (thinking 'disabled', effort 'medium') at the list rates.
SONNET_55 = dict(SONNET_5, AI_MODEL=MODEL)
BETWEEN = {'type': 'between_tools'}
ADAPTIVE = {'type': 'adaptive', 'display': 'omitted'}

#: Pinned, like Sonnet 5's in test_sonnet5_profile.py: NEW pricing versions for claude-sonnet-5-5 at 2/10/0.20.
#: Computed independently of this code from the price dictionary configuration() hashes (the same computation
#: reproduces SONNET_5_DISABLED_MEDIUM, 8975b158..., for claude-sonnet-5).
SONNET_55_BETWEEN_MEDIUM = 'configured-v1:d15bca4a92a0869453c9fd5fd98d1a38321f21ae0d5f6f2b06b4a01332758ff2'
SONNET_55_ADAPTIVE_HIGH = 'configured-v1:af690181eb8559099eda9f6795c6ec7224cf87ab1fbc61004908a165b9a0f2ec'
SONNET_55_BETWEEN_MEDIUM_US = 'configured-v1:85b25c51d9ebd3e2eeb2c7b6365095879e7de1e10b1bceb6132bef9ca3f22c59'

#: Never at the top of a request, nor inside output_config or thinking: sampling, manual thinking budgets, tools and a
#: forced tool_choice (a 400 on 5.5), the deprecated output_format, and the server-side fallback beta QuillMD never sends.
NEVER_SENT = frozenset({'temperature', 'top_p', 'top_k', 'budget_tokens', 'tools', 'tool_choice', 'output_format',
                        'fallbacks', 'betas', 'stop_sequences', 'stream', 'service_tier', 'speed', 'container',
                        'mcp_servers', 'context_management', 'metadata', 'block_binding'})
SDK_PARAMS = TypeAdapter(MessageCreateParamsNonStreaming)


def message55(*blocks, **kwargs):
    """A provider body for claude-sonnet-5-5 (JSON, as the API returns it)."""
    return message_json(*blocks, **{'model': MODEL, **kwargs})


def sdk_message(body, request_id='req_synthetic'):
    """The SDK's own Message for a body, as a live response is parsed."""
    from anthropic.types import Message
    reply = Message.model_validate(body)
    reply._request_id = request_id
    return reply


class Wire:
    """A REAL anthropic.Anthropic around an in-process MockTransport: records the bytes of each request it is asked to
    send and answers each with the next reply (the last one repeats). Nothing leaves the process."""

    def __init__(self, *replies):
        self.replies, self.bodies, self.constructed = list(replies), [], []

    def handler(self, request):
        assert (request.url.host, request.url.path, request.method) == ('api.anthropic.com', '/v1/messages', 'POST')
        self.bodies.append(request.content)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if callable(reply):
            reply = reply(json.loads(request.content))
        return httpx.Response(200, json=reply)

    def client(self, **kwargs):
        self.constructed.append(kwargs)
        return REAL_ANTHROPIC(api_key='synthetic-no-network',
                              http_client=httpx.Client(transport=httpx.MockTransport(self.handler)), **kwargs)

    def patched(self):
        return patch('anthropic.Anthropic', side_effect=self.client)

    def json(self, index=-1):
        return json.loads(self.bodies[index])


def assert_sonnet_55_request(test, body, *, thinking, effort, max_tokens, schema=None):
    """One closed request shape for claude-sonnet-5-5, read from the bytes the SDK serialized."""
    test.assertEqual(body['model'], MODEL)
    required = {'model', 'max_tokens', 'system', 'messages', 'output_config', 'thinking'}
    test.assertEqual(set(body) - {'inference_geo'}, required)
    test.assertFalse((set(body) | set(body['output_config']) | set(keys_anywhere(body['thinking']))) & NEVER_SENT)
    test.assertEqual(body['thinking'], thinking)
    if thinking['type'] == 'between_tools':
        # Accepted at low/medium/high only, and with no other field (`display` with it is a 400).
        test.assertEqual(body['thinking'], {'type': 'between_tools'})
        test.assertIn(effort, ('low', 'medium', 'high'))
    else:
        test.assertEqual(body['thinking'], {'type': 'adaptive', 'display': 'omitted'})
    test.assertEqual(set(body['output_config']), {'format', 'effort'})
    test.assertEqual(body['output_config']['effort'], effort)
    test.assertEqual(body['max_tokens'], max_tokens)
    test.assertLessEqual(body['max_tokens'], g.NONSTREAMING_MAX_OUTPUT_TOKENS)
    test.assertEqual([m['role'] for m in body['messages']], ['user'])          # no assistant prefill
    test.assertIsInstance(body['messages'][0]['content'], str)
    test.assertIsInstance(body['system'], str)
    sent_schema = body['output_config']['format']
    test.assertEqual(sent_schema['type'], 'json_schema')
    test.assertEqual(unsupported(sent_schema['schema']), [])                    # native structured-output subset
    test.assertEqual(transform_schema(sent_schema['schema']), sent_schema['schema'])
    if schema is not None:
        test.assertEqual(sent_schema['schema'], schema)
    # Everything but `thinking` is valid against the SDK's own request type (0.125.0 has no between_tools member).
    SDK_PARAMS.validate_python({**body, 'thinking': {'type': 'adaptive'}})


def fingerprint(**overrides):
    with override_settings(**{**SONNET_55, **overrides}), patch.dict(os.environ, PRICE_ENV):
        return g.configuration()


class Sonnet55Profile(SimpleTestCase):
    def test_the_default_is_between_tools_at_medium_and_names_what_is_sent(self):
        config = fingerprint()
        self.assertEqual(config['request_profile'], {'profile': 'claude-sonnet-5-5-v1', 'max_output_tokens': 8000,
                                                     'timeout_seconds': 120, 'thinking': BETWEEN, 'effort': 'medium'})
        self.assertEqual(config['pricing_version'], SONNET_55_BETWEEN_MEDIUM)
        # 'between_tools' is the explicit spelling of the same request: same profile, same price.
        self.assertEqual(fingerprint(AI_THINKING='between_tools'), config)
        adaptive = fingerprint(AI_THINKING='adaptive', AI_EFFORT='high')
        self.assertEqual(adaptive['request_profile'], {'profile': 'claude-sonnet-5-5-v1', 'max_output_tokens': 16000,
                                                       'timeout_seconds': 120, 'thinking': ADAPTIVE, 'effort': 'high'})
        self.assertEqual(adaptive['pricing_version'], SONNET_55_ADAPTIVE_HIGH)
        us = fingerprint(AI_INFERENCE_GEO='us')
        self.assertEqual(us['request_profile']['inference_geo'], 'us')
        self.assertEqual(us['pricing_version'], SONNET_55_BETWEEN_MEDIUM_US)

    def test_every_choice_is_a_distinct_new_price_and_old_prices_are_untouched(self):
        seen = {}
        for thinking in ('between_tools', 'adaptive'):
            for effort in g.SONNET_5_5_EFFORT_LEVELS:
                seen[(thinking, effort)] = fingerprint(AI_THINKING=thinking, AI_EFFORT=effort)['pricing_version']
        self.assertEqual(len(set(seen.values())), 6)
        with override_settings(**SONNET_5), patch.dict(os.environ, PRICE_ENV):
            sonnet_5 = {g.configuration()['pricing_version']}
            for thinking in g.THINKING_MODES:
                for effort in g.EFFORT_LEVELS:
                    with override_settings(AI_THINKING=thinking, AI_EFFORT=effort):
                        sonnet_5.add(g.configuration()['pricing_version'])
        self.assertFalse(set(seen.values()) & sonnet_5)
        # The pins of the earlier models are exactly what they were.
        with override_settings(**SONNET_5), patch.dict(os.environ, PRICE_ENV):
            self.assertEqual(g.configuration()['pricing_version'], SONNET_5_DISABLED_MEDIUM)
            with override_settings(AI_THINKING='adaptive'):
                self.assertEqual(g.configuration()['pricing_version'], SONNET_5_ADAPTIVE_MEDIUM)
            with override_settings(AI_INFERENCE_GEO='us'):
                self.assertEqual(g.configuration()['pricing_version'], SONNET_5_DISABLED_MEDIUM_US)
        with override_settings(**SONNET_46), patch.dict(os.environ, PRICE_ENV):
            self.assertEqual(g.configuration()['pricing_version'], ROLLBACK_FINGERPRINT)
            self.assertEqual(g.configuration()['request_profile'], g.LEGACY_PROFILE)

    def test_sonnet_5_profiles_are_byte_identical_to_the_base_commit(self):
        """The literal profiles f5fe720f produced for claude-sonnet-5, every thinking x effort x geography."""
        for thinking in g.THINKING_MODES:
            for effort in g.EFFORT_LEVELS:
                for geo in ('', 'us'):
                    with self.subTest(thinking=thinking, effort=effort, geo=geo):
                        expected = {'profile': 'claude-sonnet-5-v1',
                                    'max_output_tokens': 8000 if thinking == 'disabled' else 16000,
                                    'timeout_seconds': 120,
                                    'thinking': {'type': 'disabled'} if thinking == 'disabled' else ADAPTIVE,
                                    'effort': effort, **({'inference_geo': 'us'} if geo else {})}
                        self.assertEqual(g.request_profile('anthropic', 'claude-sonnet-5', thinking, effort, geo), expected)
        for invalid in (('between_tools', 'medium'), ('disabled', 'xhigh'), ('Disabled', 'medium')):
            with self.subTest(sonnet_5_invalid=invalid):
                self.assertIn('invalid', g.request_profile('anthropic', 'claude-sonnet-5', *invalid, ''))

    def test_choices_the_model_refuses_or_that_exceed_the_bounds_are_invalid_and_never_sent(self):
        cases = [dict(AI_THINKING='enabled'), dict(AI_THINKING='Disabled'), dict(AI_THINKING='none'),
                 dict(AI_THINKING='between-tools'), dict(AI_THINKING=''), dict(AI_EFFORT='xhigh'),
                 dict(AI_EFFORT='max'), dict(AI_EFFORT='Medium'), dict(AI_THINKING='adaptive', AI_EFFORT='xhigh'),
                 dict(AI_THINKING='adaptive', AI_EFFORT='max'), dict(AI_INFERENCE_GEO='eu'),
                 # Not the list prices: the 4.6 rates left in place, a missing rate, a half-configured switch.
                 dict(AI_INPUT_RATE='3', AI_OUTPUT_RATE='15', AI_CACHED_RATE='0.30'), dict(AI_OUTPUT_RATE=''),
                 dict(AI_CACHED_RATE='0.25'), dict(AI_INPUT_RATE='NaN'), dict(AI_INPUT_RATE='2.000001')]
        for overrides in cases:
            with self.subTest(overrides=overrides), override_settings(**{**SONNET_55, **overrides}), \
                    patch.dict(os.environ, PRICE_ENV), patch('anthropic.Anthropic') as client:
                config = g.configuration()
                self.assertIn('invalid', config['request_profile'])
                for attempt in (lambda: g.maximum_cost(NOTES, FIELDS), lambda: g.generate(NOTES, FIELDS)):
                    with self.assertRaises((NoProviderRequest, ValidationError)):
                        attempt()
                client.assert_not_called()
        # Positive control: the list prices written another way are the list prices.
        for rates in (('2', '10', '0.2'), ('2.00', '10.0', '0.200')):
            with self.subTest(rates=rates):
                config = fingerprint(AI_INPUT_RATE=rates[0], AI_OUTPUT_RATE=rates[1], AI_CACHED_RATE=rates[2])
                self.assertNotIn('invalid', config['request_profile'])

    def test_a_stored_profile_that_is_not_one_this_model_takes_is_refused_before_any_request(self):
        good = fingerprint()
        adaptive = fingerprint(AI_THINKING='adaptive', AI_EFFORT='high')
        with override_settings(**SONNET_5), patch.dict(os.environ, PRICE_ENV):
            sonnet_5 = g.configuration()
        profile = good['request_profile']
        tampered = [
            {**profile, 'thinking': {'type': 'disabled'}},                                  # a 400 on 5.5
            {**profile, 'thinking': {'type': 'between_tools', 'display': 'omitted'}},       # a 400 on 5.5
            {**profile, 'thinking': {'type': 'adaptive'}},                                  # summary could be stored
            {**profile, 'thinking': {'type': 'adaptive', 'display': 'summarized'}},
            {**profile, 'thinking': {'type': 'enabled', 'budget_tokens': 4000}},
            {**profile, 'effort': 'xhigh'}, {**profile, 'effort': 'max'},
            {**adaptive['request_profile'], 'effort': 'max'},
            {**profile, 'max_output_tokens': 16000},                                        # not this type's bound
            {**adaptive['request_profile'], 'max_output_tokens': 8000},
            {**profile, 'timeout_seconds': 60}, {**profile, 'profile': 'claude-sonnet-5-v1'},
            {**profile, 'temperature': 0}, {**profile, 'inference_geo': 'eu'},
            sonnet_5['request_profile'], g.LEGACY_PROFILE, 'legacy-v1',
            {**profile, 'profile': g.SONNET_5_5_ORDINARY_PROFILE, 'max_output_tokens': 20000},  # no relations contract
        ]
        for stored in tampered:
            with self.subTest(profile=stored), patch('anthropic.Anthropic') as client:
                with self.assertRaises(NoProviderRequest):
                    g.generate(NOTES, FIELDS, {**good, 'request_profile': stored})
                client.assert_not_called()
        # A snapshot priced at other rates, or with no profile at all, is refused the same way.
        for edit in ({'input_rate': '3'}, {'output_rate': '15'}, {'cached_rate': '0.30'}, {'input_rate': None}):
            with self.subTest(rates=edit), patch('anthropic.Anthropic') as client:
                with self.assertRaises(NoProviderRequest):
                    g.generate(NOTES, FIELDS, {**good, **edit})
                client.assert_not_called()
        with patch('anthropic.Anthropic') as client, self.assertRaises(NoProviderRequest):
            g.generate(NOTES, FIELDS, {k: v for k, v in good.items() if k != 'request_profile'})
        client.assert_not_called()
        # And the 5.5 profile is not accepted on claude-sonnet-5 or on the rollback model.
        for model in ('claude-sonnet-5', 'claude-sonnet-4-6'):
            with self.subTest(model=model), patch('anthropic.Anthropic') as client, self.assertRaises(NoProviderRequest):
                g.generate(NOTES, FIELDS, {**good, 'model': model})
            client.assert_not_called()

    def test_the_model_is_admitted_exactly_and_nothing_near_it_is(self):
        self.assertNotIn('invalid', g.request_profile('anthropic', MODEL, 'disabled', 'medium', ''))
        self.assertFalse(g.unprofiled('anthropic', MODEL))
        for model in ('claude-sonnet-5-5-20261001', 'Claude-Sonnet-5-5', 'claude-sonnet-5.5', 'claude-sonnet-55',
                      'claude-sonnet-5-5 ', 'claude-opus-5-5', 'claude-sonnet-5-6'):
            with self.subTest(model=model):
                self.assertIn('invalid', g.request_profile('anthropic', model, 'disabled', 'medium', ''))
        self.assertIn('invalid', g.request_profile('openai', MODEL, 'disabled', 'medium', ''))
        self.assertTrue(g.us_inference_priced('anthropic:' + MODEL))

    def test_the_production_renderer_and_profile_carry_the_settings_for_this_model(self):
        """No model allowlist exists in the deployment profile or the renderer: they accept environment NAMES (and the
        values of flags and voice settings only). The 5.5 values pass through, and the application reads them."""
        from ops import deployment_profile, render_production_environment as renderer
        secret = {'QUILLMD_DEPLOYMENT_PROFILE': 'production', 'QUILLMD_AI_MODE': 'live', 'QUILLMD_AI_PROVIDER': 'anthropic',
                  'QUILLMD_AI_MODEL': MODEL, 'QUILLMD_AI_THINKING': 'between_tools', 'QUILLMD_AI_EFFORT': 'medium',
                  'QUILLMD_AI_INPUT_RATE': '2', 'QUILLMD_AI_OUTPUT_RATE': '10', 'QUILLMD_AI_CACHED_RATE': '0.20',
                  'QUILLMD_AI_INFERENCE_GEO': 'us'}
        self.assertLessEqual(set(secret), deployment_profile.ENVIRONMENT_NAMES)
        parsed = renderer.parse(json.dumps(secret))
        self.assertEqual(parsed, secret)
        rendered = renderer.render(parsed).decode()
        self.assertIn("QUILLMD_AI_MODEL='claude-sonnet-5-5'\n", rendered)
        self.assertIn("QUILLMD_AI_THINKING='between_tools'\n", rendered)
        settings = {name[len('QUILLMD_'):]: value for name, value in parsed.items() if name.startswith('QUILLMD_AI_')}
        with override_settings(**settings), patch.dict(os.environ, PRICE_ENV):
            config = g.configuration()
        self.assertEqual(config['request_profile'], {'profile': 'claude-sonnet-5-5-v1', 'max_output_tokens': 8000,
                                                     'timeout_seconds': 120, 'thinking': BETWEEN, 'effort': 'medium',
                                                     'inference_geo': 'us'})


class Sonnet55Console(TestCase):
    """The operator screen reads the job table, so this one needs the test database."""

    def test_the_console_names_the_request_and_its_price(self):
        from core import admin_console
        with override_settings(**SONNET_55), patch.dict(os.environ, PRICE_ENV):
            rows = {row['name']: row for row in admin_console.language_model_rows()}
            config = g.configuration()
        self.assertEqual(rows['QUILLMD_AI_MODEL']['value'], MODEL)
        self.assertEqual(rows['QUILLMD_AI_THINKING']['value'], 'disabled (read only for claude-sonnet-5 and claude-sonnet-5-5)')
        self.assertEqual(rows['request profile'], {'name': 'request profile', 'severity': 'success',
                                                   'value': 'explicit ' + json.dumps(config['request_profile'], sort_keys=True)})
        self.assertIn('"thinking": {"type": "between_tools"}', rows['request profile']['value'])
        self.assertEqual(rows['pricing_version']['value'], SONNET_55_BETWEEN_MEDIUM)
        with override_settings(**dict(SONNET_55, AI_INPUT_RATE='3')), patch.dict(os.environ, PRICE_ENV):
            row = next(r for r in admin_console.language_model_rows() if r['name'] == 'request profile')
        self.assertTrue(row['value'].startswith('INVALID — every generation is refused'), row['value'])
        self.assertEqual(row['severity'], 'error')


class Sonnet55Wire(SimpleTestCase):
    """The bytes of every path, through the real SDK."""

    @contextlib.contextmanager
    def live(self, base, **overrides):
        """The settings of one path at claude-sonnet-5-5, with the pinned price environment."""
        with override_settings(**{**base, 'AI_MODEL': MODEL, **overrides}), patch.dict(os.environ, PRICE_ENV):
            yield

    def generate(self, wire, notes=NOTES, fields=FIELDS, **kwargs):
        with wire.patched():
            config = g.configuration(fields)
            result = g.generate(notes, fields, config, **kwargs)
        bound = g.maximum_cost(notes, fields, config, **{k: v for k, v in kwargs.items() if k == 'requirements'})
        return config, result, bound

    def test_ordinary_default_request_every_choice(self):
        for thinking, sent in (('disabled', BETWEEN), ('between_tools', BETWEEN), ('adaptive', ADAPTIVE)):
            for effort in g.SONNET_5_5_EFFORT_LEVELS:
                tokens = 8000 if sent == BETWEEN else 16000
                with self.subTest(thinking=thinking, effort=effort), \
                        self.live(SONNET_55, AI_THINKING=thinking, AI_EFFORT=effort):
                    wire = Wire(message55(text(SELECTED)))
                    config, result, bound = self.generate(wire)
                    assert_sonnet_55_request(self, wire.json(), thinking=sent, effort=effort, max_tokens=tokens,
                                             schema=transform_schema(g.Selections.model_json_schema()))
                    self.assertEqual(wire.constructed, [{'timeout': 120, 'max_retries': 0}])
                    self.assertEqual(len(wire.bodies), 1)
                    # The hold prices exactly the max_tokens sent, at the 5.5 list rates.
                    payload = len(json.dumps({'notes': NOTES, 'fields': FIELDS, 'context_labels': [],
                                              'source_units': []}).encode())
                    self.assertEqual(bound, (Decimal(payload + 12000) * 2 + Decimal(tokens) * 10) / 1000000)
                    raw, cost, units, rates, provider, request_id, simulated = result
                    self.assertEqual((provider, simulated), ('anthropic:' + MODEL, False))
                    self.assertEqual(raw['requested_model'], MODEL)
                    self.assertEqual(g.validated(raw)['symptoms']['text'], 'no chest pain')
                    self.assertLessEqual(cost, bound)

    def test_complete_sentence_v3_request(self):
        from core.tests.test_v3_ordinary_notes import LIVE, field
        fields = [field('cc', 'Chief complaint'), field('plan', 'Plan')]
        notes = 'Patient presents with a cough. Plan is rest and fluids.'

        def answer(body):
            payload = json.loads(body['messages'][0]['content'])
            by_quote = {u['quote']: u['id'] for u in payload['source_units']}
            picks = {'cc': ['Patient presents with a cough.'], 'plan': ['Plan is rest and fluids.']}
            return message55(text(json.dumps({'fields': [{'key': q['key'], 'conflict': False,
                                                          'unit_ids': [by_quote[x] for x in picks[q['key']]]}
                                                         for q in payload['questions']]})))

        with self.live(LIVE, V3_HISTORY_CONTEXT=False, V3_FIELD_RELATIONS=False):
            wire = Wire(answer)
            config, result, bound = self.generate(wire, notes=notes, fields=fields)
            answers = g.validated(result[0])
        body = wire.json()
        assert_sonnet_55_request(self, body, thinking=BETWEEN, effort='medium', max_tokens=8000,
                                 schema=transform_schema(g.UnitSelections.model_json_schema()))
        self.assertIn('source_units', json.loads(body['messages'][0]['content']))
        self.assertEqual(answers['cc']['text'], 'Patient presents with a cough.')
        self.assertLessEqual(result[1], bound)

    def test_history_context_request(self):
        from core import v3_history_context as h
        from core.tests.test_v3_history_context import body as history_body, cases
        from core.tests.test_v3_ordinary_notes import LIVE
        case = cases()[0]
        reply = message55(text(json.dumps(history_body(case['notes'], case['fields'], case['original_all_picks']))))
        with self.live(LIVE, V3_HISTORY_CONTEXT=True, V3_FIELD_RELATIONS=False):
            wire = Wire(reply)
            config, result, bound = self.generate(wire, notes=case['notes'], fields=case['fields'])
            answers = g.validated(result[0])
        self.assertEqual(config['history_context_contract'], h.CONTRACT)
        body = wire.json()
        assert_sonnet_55_request(self, body, thinking=BETWEEN, effort='medium', max_tokens=8000,
                                 schema=transform_schema(h.HistorySelections.model_json_schema()))
        self.assertIn('history_context_targets', json.loads(body['messages'][0]['content']))
        self.assertTrue(body['system'].endswith(h.INSTRUCTIONS))
        self.assertEqual(result[0]['history_context_contract'], h.CONTRACT)
        self.assertTrue(any(a['status'] == 'supported' for a in answers.values()))
        self.assertLessEqual(result[1], bound)
        with override_settings(**dict(LIVE, AI_MODEL='claude-sonnet-4-6', V3_HISTORY_CONTEXT=True)), \
                patch.dict(os.environ, PRICE_ENV):
            with self.assertRaisesMessage(ValidationError, 'exact native claude-sonnet-5'):
                h.refuse_request(g.configuration())

    def test_field_relations_request(self):
        from core import v3_field_relations as r
        from core.tests.test_v3_field_relations import relation_wire
        from core.tests.test_v3_ordinary_notes import LIVE, field
        fields = [field('smoking', 'Smoker', 'choice', ['Yes', 'No']), field('cc', 'Chief complaint')]
        notes = 'Patient presents with a cough. The patient does not smoke.'
        reply = message55(text(json.dumps(relation_wire(notes, fields, {'cc': ['Patient presents with a cough.']}))))
        with self.live(LIVE, V3_HISTORY_CONTEXT=False, V3_FIELD_RELATIONS=True):
            wire = Wire(reply)
            config, result, bound = self.generate(wire, notes=notes, fields=fields)
            compiled = r.compile_request(notes, fields, config)
            answers = g.validated(result[0])
            wrong = {**result[0], 'anthropic_response': sdk_message({**reply, 'model': 'claude-sonnet-5'})}
            with self.assertRaisesMessage(ValidationError, 'unqualified'):
                g.validated(wrong)                                   # an answer from another model is never adopted
            with override_settings(AI_THINKING='adaptive'):
                # The same contract under adaptive thinking keeps the base 16000 profile, as on Sonnet 5.
                self.assertEqual(g.configuration(fields)['request_profile']['profile'], 'claude-sonnet-5-5-v1')
        self.assertEqual(config['request_profile'], {'profile': 'claude-sonnet-5-5-ordinary-v1', 'max_output_tokens': 20000,
                                                     'timeout_seconds': 120, 'thinking': BETWEEN, 'effort': 'medium'})
        self.assertEqual(config['ordinary_field_contract'], r.CONTRACT)
        body = wire.json()
        assert_sonnet_55_request(self, body, thinking=BETWEEN, effort='medium', max_tokens=20000,
                                 schema=compiled['wire']['output_config']['format']['schema'])
        self.assertEqual(body, json.loads(json.dumps(compiled['wire'])))
        self.assertEqual(result[0]['requested_model'], MODEL)
        self.assertEqual((answers['cc']['status'], answers['cc']['text']), ('supported', 'Patient presents with a cough.'))
        self.assertEqual(answers['smoking']['status'], 'missing')
        self.assertLessEqual(result[1], bound)

    def test_narrative_request(self):
        from core import wm_narrative as wm
        from core.tests.test_wm_narrative import FIELDS as WM_FIELDS, REQUIREMENTS, SFJ, selections
        body_text = selections(SFJ, {'measurement_1_1': ('7.4 mm', [SFJ], {})}).model_dump_json()
        with self.live(SONNET_55, WM_NARRATIVE=True):
            wire = Wire(message55(THINKING, text(body_text)))
            config, result, bound = self.generate(wire, notes=SFJ, fields=WM_FIELDS, requirements=REQUIREMENTS)
            answers, _ = g.adoption(result[0])
            wrong = {**result[0], 'anthropic_response': sdk_message(message_json(text(body_text)))}
            with self.assertRaisesMessage(ValidationError, 'differs from the requested model'):
                g.adoption(wrong)
        assert_sonnet_55_request(self, wire.json(), thinking=BETWEEN, effort='medium', max_tokens=8000,
                                 schema=transform_schema(wm.NarrativeSelections.model_json_schema()))
        self.assertEqual(answers['measurement_1_1']['text'], '7.4 mm')
        self.assertLessEqual(result[1], bound)

    def test_large_form_batch_requests(self):
        from core import generation_batch as b
        from core.tests.test_generation_batch import SETTINGS as BATCH, response as batch_response, sample
        with self.live(BATCH):
            config = g.configuration()
            self.assertEqual(config['request_profile']['thinking'], BETWEEN)
            plan = b.plan_for(sample(), config)
            replies = [message55(text(batch_response(plan, n, model=MODEL)['content'][0]['text']), ident=f'msg_part_{n}')
                       for n in (1, 2)]
            wire = Wire(*replies)
            raws = []
            with wire.patched():
                for ordinal in (1, 2):
                    request = b.request(plan, ordinal)
                    self.assertEqual(b.digest(request), plan['parts'][ordinal - 1]['request_sha256'])
                    client = anthropic.Anthropic(timeout=120, max_retries=0)
                    raws.append(client.messages.create(**request).model_dump(mode='json'))
                    assert_sonnet_55_request(self, wire.json(), thinking=BETWEEN, effort='medium', max_tokens=8000,
                                             schema=transform_schema(b.BatchSelections.model_json_schema()))
                    self.assertEqual(wire.json(), json.loads(json.dumps(request)))
            answers, _ = b.assemble(plan, raws)
            self.assertEqual(len(answers), 101)
            # A part answered by another model, or stopped by anything but end_turn, refuses the whole form.
            for key, value in (('model', 'claude-sonnet-5'), ('stop_reason', 'refusal'), ('stop_reason', 'max_tokens'),
                               ('stop_reason', 'model_context_window_exceeded')):
                with self.subTest(**{key: value}), self.assertRaises(ValidationError):
                    b.assemble(plan, [raws[0], {**raws[1], key: value}])
            # A thinking block before the text is read by type.
            thought = {**raws[0], 'content': [THINKING] + raws[0]['content']}
            self.assertEqual(b.assemble(plan, [thought, raws[1]])[0], answers)


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, **SONNET_55)
class Sonnet55Outcomes(OutcomeFixture, TestCase):
    """Through enqueue + run_one with the real SDK: what the document and the books look like after each outcome."""

    def run_real(self, encounter, reply):
        wire = Wire(reply)
        with wire.patched():
            job = enqueue(encounter, self.user)
            self.assertTrue(run_one())
        job.refresh_from_db()
        encounter.refresh_from_db()
        return job, wire

    def test_a_leading_thinking_block_adopts_the_same_answers(self):
        plain_encounter, thinking_encounter = self.fresh_encounter(), self.fresh_encounter()
        plain, wire = self.run_real(plain_encounter, message55(text(SELECTED), ident='msg_plain'))
        assert_sonnet_55_request(self, wire.json(), thinking=BETWEEN, effort='medium', max_tokens=8000)
        with override_settings(AI_THINKING='adaptive', AI_EFFORT='high'):
            thought, wire = self.run_real(thinking_encounter, message55(
                THINKING, text(SELECTED), ident='msg_thought', usage={'output_tokens': 650,
                                                                     'output_tokens_details': {'thinking_tokens': 600}}))
        assert_sonnet_55_request(self, wire.json(), thinking=ADAPTIVE, effort='high', max_tokens=16000)
        self.assertEqual((plain.state, thought.state), ('succeeded', 'succeeded'))
        self.assertEqual(thinking_encounter.answers, plain_encounter.answers)
        usage = Usage.objects.get(job=thought)
        self.assertEqual((usage.units['thinking_tokens'], usage.units['output_tokens']), (600, 650))
        # Thinking is inside output_tokens and priced once, at the output rate.
        self.assertEqual(usage.actual_cost, (Decimal(100) * 2 + Decimal(650) * 10) / 1000000)
        self.assertEqual(usage.charged_cost, usage.actual_cost * Decimal('1.5'))
        self.assertNotIn('response_model', usage.units)
        stored = json.loads(private_path(thought.result_path).read_text())
        self.assertEqual(stored['provider_output']['content'][0], THINKING)
        self.assertTrue(audit_report()['all_checks_pass'])

    def test_refusal_truncation_overflow_and_another_model_are_settled_never_adopted_and_absorbed(self):
        outcomes = {
            'refusal before output': (message55(stop_reason='refusal', ident='msg_r0', usage={'output_tokens': 0},
                stop_details={'type': 'refusal', 'category': 'general_harms', 'explanation': 'synthetic never recorded'}),
                'refusal', 'general_harms', BETWEEN),
            'refusal mid-output': (message55(text('{"fields":[{"key":"symptoms","quotes":["no'), stop_reason='refusal',
                ident='msg_r1', usage={'output_tokens': 37},
                stop_details={'type': 'refusal', 'category': 'bio', 'explanation': None}), 'refusal', 'bio', BETWEEN),
            'refusal, no category': (message55(stop_reason='refusal', ident='msg_r2', stop_details=None), 'refusal', None,
                                     BETWEEN),
            'max_tokens, thinking only': (message55(THINKING, stop_reason='max_tokens', ident='msg_m',
                usage={'output_tokens': 16000, 'output_tokens_details': {'thinking_tokens': 16000}}), 'max_tokens', None,
                ADAPTIVE),
            'max_tokens, parseable text': (message55(text(SELECTED), stop_reason='max_tokens', ident='msg_p',
                usage={'output_tokens': 8000}), 'max_tokens', None, BETWEEN),
            'context window': (message55(text('{"fields":['), stop_reason='model_context_window_exceeded',
                ident='msg_w'), 'model_context_window_exceeded', None, BETWEEN),
            'another model answered': (message_json(text(SELECTED), model='claude-sonnet-5', ident='msg_fallback'),
                                       'end_turn', None, BETWEEN),
        }
        for label, (reply, stop, category, thinking) in outcomes.items():
            with self.subTest(outcome=label), override_settings(AI_THINKING='adaptive' if thinking == ADAPTIVE else 'disabled'):
                encounter = self.fresh_encounter()
                before = (encounter.answers, encounter.status, encounter.revision, encounter.notes)
                job, wire = self.run_real(encounter, reply)
                self.assertEqual(wire.json()['thinking'], thinking)
                self.assertEqual((encounter.answers, encounter.status, encounter.revision, encounter.notes), before)
                self.assertEqual(job.state, 'failed')
                self.assertTrue(job.error.startswith(PLATFORM_FAILURE), job.error)
                usage = Usage.objects.get(job=job)
                receipt = ProviderReceipt.objects.get(job=job)
                self.assertEqual(receipt.provider, 'anthropic:' + MODEL)
                metered = Decimal(reply['usage']['input_tokens']) * 2 + Decimal(reply['usage']['output_tokens']) * 10
                self.assertEqual(usage.actual_cost, metered / 1000000)          # the true cost, never zeroed
                self.assertEqual(receipt.actual_cost, usage.actual_cost)
                self.assertEqual((usage.units['stop_reason'], usage.units['stop_details_category']), (stop, category))
                self.assertNotIn('synthetic never recorded', json.dumps(usage.units))
                if label == 'another model answered':
                    self.assertEqual(usage.units['response_model'], 'claude-sonnet-5')
                else:
                    self.assertNotIn('response_model', usage.units)
                # Absorbed: the customer's debit is reversed and QuillMD carries the provider cost.
                self.assertEqual(sum(LedgerEntry.objects.filter(job=job, kind__in=['usage', 'absorbed'])
                                     .values_list('amount', flat=True), Decimal(0)), 0)
                self.assertEqual(PlatformCost.objects.get(job=job, kind='absorbed_failure').amount, usage.actual_cost)
                self.assertFalse(Reservation.objects.filter(job=job, state='held').exists())
        self.assertTrue(audit_report()['all_checks_pass'])

    def test_a_queued_job_keeps_its_profile_and_price(self):
        encounter = self.fresh_encounter()
        with override_settings(AI_THINKING='adaptive', AI_EFFORT='high'), patch('anthropic.Anthropic'):
            job = enqueue(encounter, self.user)
        self.assertEqual(job.config['pricing_version'], SONNET_55_ADAPTIVE_HIGH)
        hold = sum(Reservation.objects.filter(job=job).values_list('amount', flat=True), Decimal(0))
        self.assertGreaterEqual(hold, Decimal(16000) * 10 / 1000000 * Decimal('1.5'))
        wire = Wire(message55(text(SELECTED), ident='msg_queued'))
        with wire.patched():                                         # settings now say disabled / medium
            self.assertTrue(run_one())
        assert_sonnet_55_request(self, wire.json(), thinking=ADAPTIVE, effort='high', max_tokens=16000)
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded', job.error)

    def test_a_stored_job_at_other_rates_is_refused_and_released(self):
        encounter = self.fresh_encounter()
        config = {**g.configuration(), 'input_rate': '3', 'output_rate': '15', 'cached_rate': '0.30'}
        job = Job.objects.create(encounter=encounter, user=self.user, request_key=f'generation:{encounter.pk}:rates',
                                 revision=encounter.revision, config=config)
        from core.billing import reserve
        reserve(job, Decimal('0.2'))
        with patch('anthropic.Anthropic') as client:
            self.assertTrue(run_one())
            client.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        self.assertTrue(job.error.startswith('Not processed: '), job.error)
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.assertFalse(Reservation.objects.filter(job=job, state='held').exists())


class Sonnet55Price(SimpleTestCase):
    USAGE = {'input_tokens': 2000, 'output_tokens': 900, 'cache_read_input_tokens': 100, 'cache_creation_input_tokens': 70,
             'cache_creation': {'ephemeral_5m_input_tokens': 50, 'ephemeral_1h_input_tokens': 20},
             'output_tokens_details': {'thinking_tokens': 600}}

    def settle(self, geo=None, discount='0'):
        wire = Wire(message55(THINKING, text(SELECTED), usage={**self.USAGE, 'inference_geo': geo}))
        with override_settings(**dict(SONNET_55, AI_THINKING='adaptive')), \
                patch.dict(os.environ, {**PRICE_ENV, 'QUILLMD_PROVIDER_DISCOUNT_RATE': discount}), wire.patched():
            return g.generate(NOTES, FIELDS)

    def test_the_list_prices_with_thinking_cache_writes_reads_and_geography(self):
        # $2 input, $2.50 5-minute and $4 1-hour cache writes, $0.20 cache reads, $10 output (600 of the 900 are thinking).
        list_cost = (Decimal(2000) * 2 + Decimal(100) * Decimal('0.20') + Decimal(50) * Decimal('2.50')
                     + Decimal(20) * 4 + Decimal(900) * 10) / 1000000
        self.assertEqual(list_cost, Decimal('0.013225'))
        _, cost, units, rates, provider, _, _ = self.settle()
        self.assertEqual(cost, list_cost)
        self.assertEqual((units['thinking_tokens'], units['output_tokens'], units['cache_creation_5m_tokens'],
                          units['cache_creation_1h_tokens'], units['cached_input_tokens']), (600, 900, 50, 20, 100))
        self.assertEqual(recompute_cost(provider, units, rates, False), cost)
        self.assertEqual(recompute_list_cost(provider, units, rates), Decimal(rates['list_cost_usd']))
        _, us, units, rates, provider, _, _ = self.settle(geo='us')
        self.assertEqual(us, list_cost * Decimal('1.1'))
        self.assertEqual(rates['inference_geo_multiplier'], '1.1')
        self.assertEqual(recompute_cost(provider, units, rates, False), us)
        _, discounted, units, rates, provider, _, _ = self.settle(discount='0.2')
        self.assertEqual(discounted, list_cost * Decimal('0.8'))
        self.assertEqual(recompute_cost(provider, units, rates, False), discounted)

    def test_the_hold_bounds_the_worst_metered_charge(self):
        with override_settings(**dict(SONNET_55, AI_THINKING='adaptive', AI_INFERENCE_GEO='us')), \
                patch.dict(os.environ, PRICE_ENV):
            bound = g.maximum_cost(NOTES, FIELDS)
            config = g.configuration()
        payload = len(json.dumps({'notes': NOTES, 'fields': FIELDS, 'context_labels': [], 'source_units': []}).encode())
        expected = ((Decimal(payload + 12000) * 2 + Decimal(16000) * 10) / 1000000 * Decimal('1.1')).quantize(
            g.COST_QUANTUM, rounding=ROUND_CEILING)
        self.assertEqual(bound, expected)
        # The worst a request this size can meter: every input byte a token, every output token (thinking included) used.
        worst = Wire(message55(THINKING, stop_reason='max_tokens', usage={
            'input_tokens': payload + 12000, 'output_tokens': 16000, 'inference_geo': 'us',
            'output_tokens_details': {'thinking_tokens': 16000}}))
        with override_settings(**dict(SONNET_55, AI_THINKING='adaptive', AI_INFERENCE_GEO='us')), \
                patch.dict(os.environ, PRICE_ENV), worst.patched():
            _, cost, *_ = g.generate(NOTES, FIELDS, config)
        self.assertLessEqual(cost, bound)


def mapping_settings():
    from core.tests.test_mapping_assistance import SETTINGS
    return {**SETTINGS, 'AI_MODEL': MODEL}


def mapping_fixture():
    from core.tests.test_mapping_assistance import MappingAssistance
    return MappingAssistance


@override_settings(**mapping_settings())
class Sonnet55Mapping(TestCase):
    """Mapping assistance on claude-sonnet-5-5: the separately bound envelope, sent with between_tools at medium."""
    setUp = mapping_fixture().setUp
    body = mapping_fixture().body
    enqueue = mapping_fixture().enqueue

    def live(self, reply):
        from core import generation, mapping_assistance as mapping, jobs
        self.config = generation.configuration()
        self.compiled = mapping.compile_request(self.version, self.config)
        job = self.enqueue()
        wire = Wire(reply(self.body()) if callable(reply) else reply)
        with wire.patched():
            self.assertTrue(jobs.run_one())
        job.refresh_from_db()
        return job, wire

    @override_settings(AI_MODE='live', QUILLMD_MAPPING_ASSISTANCE_LIVE=True)
    def test_the_mapping_request_receipt_and_adoption(self):
        from core import mapping_assistance as mapping
        job, wire = self.live(lambda body: message55(text(json.dumps(body)), ident='msg_mapping_adopted'))
        self.assertEqual(self.compiled['profile'], {'profile': mapping.PROFILE, 'max_output_tokens': 20000,
                                                    'timeout_seconds': 120, 'thinking': BETWEEN, 'effort': 'medium'})
        assert_sonnet_55_request(self, wire.json(), thinking=BETWEEN, effort='medium', max_tokens=20000,
                                 schema=transform_schema(mapping.wire.Proposal.model_json_schema()))
        self.assertEqual(wire.json(), json.loads(json.dumps(self.compiled['request'])))
        self.assertEqual(wire.constructed, [{'timeout': 120, 'max_retries': 0}])
        self.assertEqual(job.state, 'succeeded', job.error)
        receipt = ProviderReceipt.objects.get(job=job)
        self.assertEqual((receipt.provider, receipt.units['response_model']), ('anthropic:' + MODEL, MODEL))
        self.assertEqual(Usage.objects.get(job=job).actual_cost, (Decimal(100) * 2 + Decimal(10) * 10) / 1000000)
        self.assertEqual(self.template.versions.count(), 2)

    @override_settings(AI_MODE='live', QUILLMD_MAPPING_ASSISTANCE_LIVE=True)
    def test_another_model_a_refusal_or_a_truncation_is_receipted_absorbed_and_never_adopted(self):
        for model, stop in ((MODEL, 'refusal'), (MODEL, 'max_tokens'), (MODEL, 'model_context_window_exceeded'),
                            ('claude-sonnet-5', 'end_turn')):
            with self.subTest(model=model, stop=stop):
                job, _ = self.live(lambda body: message_json(text(json.dumps(body)), model=model, stop_reason=stop,
                                                             ident=f'msg_mapping_{model}_{stop}'))
                self.assertEqual(job.state, 'failed', job.error)
                self.assertTrue(PlatformCost.objects.filter(job=job, kind='absorbed_failure').exists())
                self.assertEqual(sum(LedgerEntry.objects.filter(job=job).values_list('amount', flat=True)), Decimal(0))
                self.assertEqual(self.template.versions.count(), 1)

    def test_adaptive_thinking_is_refused_for_mapping_before_any_request(self):
        from core import generation, mapping_assistance as mapping
        with override_settings(AI_THINKING='adaptive'), patch('anthropic.Anthropic') as client:
            with self.assertRaises(NoProviderRequest):
                mapping.compile_request(self.version, generation.configuration())
            client.assert_not_called()


def batch_fixture():
    from core.tests.test_generation_batch import BatchFixture
    return BatchFixture


def batch_settings():
    from core.tests.test_generation_batch import SETTINGS
    return {**SETTINGS, 'AI_MODEL': MODEL}


@override_settings(**batch_settings())
class Sonnet55BatchWorker(batch_fixture(), TestCase):
    """A complete large form through admission and the batch worker, the real SDK answering in-process."""

    def test_every_part_is_sent_as_quoted_receipted_as_5_5_and_the_whole_form_adopted(self):
        from core import batch_jobs as jobs, generation_batch as b
        from core.tests.test_generation_batch import response as batch_response
        batch = self.admit()
        self.assertEqual(batch.plan['config']['model'], MODEL)
        replies = [message55(text(batch_response(batch.plan, n, model=MODEL)['content'][0]['text']),
                             ident=f'msg_batch_part_{n}') for n in (1, 2)]
        wire = Wire(*replies)
        with wire.patched():                     # the environment the batch was admitted under, unchanged
            for _ in range(3):
                self.assertTrue(jobs.run_one())
        batch.refresh_from_db()
        self.assertEqual(batch.state, 'succeeded', batch.error)
        self.assertEqual(len(wire.bodies), 2)
        for ordinal, sent in enumerate(wire.bodies, 1):
            body = json.loads(sent)
            assert_sonnet_55_request(self, body, thinking=BETWEEN, effort='medium', max_tokens=8000)
            self.assertEqual(b.digest(body), batch.parts.get(ordinal=ordinal).request_sha256)
        receipts = ProviderReceipt.objects.filter(job__generation_part__batch=batch)
        self.assertEqual(sorted(receipts.values_list('provider', flat=True)), ['anthropic:' + MODEL] * 2)
        self.assertEqual(sorted(batch.parts.values_list('response__model', flat=True)), [MODEL] * 2)
        self.encounter.refresh_from_db()
        self.assertEqual(len(self.encounter.answers), 101)
