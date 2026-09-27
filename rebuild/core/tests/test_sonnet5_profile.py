"""Claude Sonnet 5 migration: the model-keyed request profile and a byte-identical rollback.

Fakes only. The Anthropic client is either replaced outright, or constructed for real around an httpx MockTransport that
answers inside this process — so the SDK's own serialization is exercised and still nothing leaves the machine.

What each group proves, stated so a reader can see how it would fail:
  · ROLLBACK — claude-sonnet-4-6 sends exactly the pre-profile call (kwargs AND HTTP body bytes) and keeps its recorded
    pricing fingerprint; a regression that leaks a Sonnet 5 field into it fails here.
  · PROFILE — Sonnet 5 always states thinking and effort, never a forbidden parameter, and prices the max_tokens it sends.
  · OUTCOMES — a thinking block changes nothing; refusal / max_tokens / context-window stops never touch the encounter,
    settle, fail as a platform failure and are absorbed.
Settlement fidelity (metered geography, receipt units) is in test_sonnet5_settlement.py; the operator screen in
test_configuration_status.py.
"""
import json
import os
import re
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import anthropic
import httpx
from anthropic.types import Message
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings

from core import generation as g
from core.jobs import NoProviderRequest, PLATFORM_FAILURE, enqueue, run_one
from core.management.commands.audit_billing import audit_report
from core.models import Encounter, Job, LedgerEntry, PlatformCost, ProviderReceipt, Reservation, Usage
from core.billing import reserve
from core.security import private_path
from core.tests.test_security import SyntheticFixture

#: The fingerprint the live claude-sonnet-4-6 configuration has carried since the discount key landed (3/15/0.30,
#: Deepgram 0.0043/min, no per-second rate, no discount). Rolling back must land on exactly this string.
ROLLBACK_FINGERPRINT = 'configured-v1:fcc802676fc66faa1dca2e574588ab96d9ee90cba679f047d6a80bb7924583ae'
#: The same price dict for claude-sonnet-5 at 2/10/0.20 WITHOUT a profile — what a config-only switch would have
#: produced. It must NOT be what the profiled configuration yields: the request shape is part of the price.
UNPROFILED_SONNET_5 = 'configured-v1:64e88144a3d7d7e1592c371c9fe6680ba4204a4f0d9538573f10b5ee3ab121f3'
#: Pinned in docs/rebuild/v1/sonnet5-migration.md for the operator to compare against configuration_status.
SONNET_5_DISABLED_MEDIUM = 'configured-v1:8975b1585770620ede7d015cb4945abebf872845c4a6648f0d74f4de9d1be77d'
SONNET_5_ADAPTIVE_MEDIUM = 'configured-v1:359a0737160deaf1f0c07168c63dd12012929f0d2498189feaa814afaa67419a'
SONNET_5_DISABLED_MEDIUM_US = 'configured-v1:f95e38269021772b2800c48ce729e149a0f27f272bf3ec63b122dde81f6d609e'

PRICE_ENV = {'QUILLMD_DEEPGRAM_RATE_PER_MINUTE': '0.0043', 'QUILLMD_DEEPGRAM_RATE_PER_SECOND': '',
             'QUILLMD_PROVIDER_DISCOUNT_RATE': '0'}
SONNET_46 = dict(AI_MODE='live', AI_PROVIDER='anthropic', AI_MODEL='claude-sonnet-4-6', AI_INPUT_RATE='3',
                 AI_OUTPUT_RATE='15', AI_CACHED_RATE='0.30', AI_THINKING='disabled', AI_EFFORT='medium',
                 AI_INFERENCE_GEO='')
SONNET_5 = dict(SONNET_46, AI_MODEL='claude-sonnet-5', AI_INPUT_RATE='2', AI_OUTPUT_RATE='10', AI_CACHED_RATE='0.20')
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}

FIELDS = [{'key': 'symptoms', 'label': 'Symptoms', 'kind': 'text', 'locator': {'cell': 0}}]
NOTES = 'Symptoms: no chest pain'
SELECTED = json.dumps({'fields': [{'key': 'symptoms', 'quotes': ['no chest pain'], 'conflict': False}]})
THINKING = {'type': 'thinking', 'thinking': '', 'signature': 'synthetic-opaque-signature'}


def text(value):
    return {'type': 'text', 'text': value}


def message_json(*blocks, stop_reason='end_turn', stop_details=None, usage=None, ident='msg_synthetic',
                 model='claude-sonnet-5'):
    return {'id': ident, 'type': 'message', 'role': 'assistant', 'model': model, 'content': list(blocks),
            'stop_reason': stop_reason, 'stop_details': stop_details, 'stop_sequence': None,
            'usage': {'input_tokens': 100, 'output_tokens': 10, 'cache_read_input_tokens': 0,
                      'cache_creation_input_tokens': 0, **(usage or {})}}


def message(*blocks, **kwargs):
    """A real SDK Message, so attribute access, model_dump and block types behave exactly as a live response's do."""
    reply = Message.model_validate(message_json(*blocks, **kwargs))
    reply._request_id = 'req_' + kwargs.get('ident', 'msg_synthetic')
    return reply


def keys_anywhere(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from keys_anywhere(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from keys_anywhere(item)


def captured(overrides, reply=None, notes=NOTES, fields=FIELDS, config=None, env=None):
    """Run generate() against a replaced client; return (client kwargs, create kwargs, generate's result)."""
    with override_settings(**overrides), patch.dict(os.environ, env or PRICE_ENV), \
            patch('anthropic.Anthropic') as client:
        client.return_value.messages.create.return_value = reply or message(text(SELECTED))
        result = g.generate(notes, fields, config)
        return client.call_args.kwargs, client.return_value.messages.create.call_args.kwargs, result


class PricingFingerprint(SimpleTestCase):
    def fingerprint(self, **overrides):
        with override_settings(**{**SONNET_46, **overrides}), patch.dict(os.environ, PRICE_ENV):
            return g.configuration()

    def test_rollback_reproduces_the_recorded_fingerprint_whatever_the_sonnet_5_settings_say(self):
        for thinking in ('disabled', 'adaptive', 'not-a-mode'):
            for effort in ('low', 'medium', 'high', 'max'):
                with self.subTest(thinking=thinking, effort=effort):
                    config = self.fingerprint(AI_THINKING=thinking, AI_EFFORT=effort)
                    self.assertEqual(config['request_profile'], g.LEGACY_PROFILE)
                    self.assertEqual(config['pricing_version'], ROLLBACK_FINGERPRINT)

    def test_sonnet_5_fingerprints_are_pinned_and_carry_the_profile(self):
        disabled = self.fingerprint(**SONNET_5)
        adaptive = self.fingerprint(**dict(SONNET_5, AI_THINKING='adaptive'))
        us = self.fingerprint(**dict(SONNET_5, AI_INFERENCE_GEO='us'))
        self.assertEqual(disabled['pricing_version'], SONNET_5_DISABLED_MEDIUM)
        self.assertEqual(adaptive['pricing_version'], SONNET_5_ADAPTIVE_MEDIUM)
        self.assertEqual(us['pricing_version'], SONNET_5_DISABLED_MEDIUM_US)
        self.assertNotEqual(disabled['pricing_version'], UNPROFILED_SONNET_5)
        # Every choice that changes the request changes the price fingerprint.
        seen = {self.fingerprint(**dict(SONNET_5, AI_THINKING=t, AI_EFFORT=e))['pricing_version']
                for t in g.THINKING_MODES for e in g.EFFORT_LEVELS}
        self.assertEqual(len(seen), len(g.THINKING_MODES) * len(g.EFFORT_LEVELS))
        self.assertEqual(disabled['request_profile'], {
            'profile': 'claude-sonnet-5-v1', 'max_output_tokens': 8000, 'timeout_seconds': 120,
            'thinking': {'type': 'disabled'}, 'effort': 'medium'})
        self.assertEqual(adaptive['request_profile']['thinking'], {'type': 'adaptive', 'display': 'omitted'})
        self.assertEqual(adaptive['request_profile']['max_output_tokens'], 16000)

    def test_the_defaults_are_disabled_thinking_at_medium_effort_and_no_geography(self):
        import quillmd.settings as module
        for name in ('QUILLMD_AI_THINKING', 'QUILLMD_AI_EFFORT', 'QUILLMD_AI_INFERENCE_GEO'):
            self.assertNotIn(name, os.environ, 'the test environment must not preset the profile it is testing')
        self.assertEqual((module.AI_THINKING, module.AI_EFFORT, module.AI_INFERENCE_GEO), ('disabled', 'medium', ''))

    def test_an_invalid_choice_is_recorded_never_raised_and_refuses_generation(self):
        cases = [dict(SONNET_5, AI_THINKING='enabled'), dict(SONNET_5, AI_THINKING='Adaptive'),
                 dict(SONNET_5, AI_EFFORT='xhigh'), dict(SONNET_5, AI_EFFORT='max'),
                 dict(SONNET_5, AI_INFERENCE_GEO='eu'), dict(SONNET_46, AI_MODEL='claude-haiku-4-5', AI_INFERENCE_GEO='us'),
                 dict(SONNET_46, AI_PROVIDER='openai', AI_MODEL='gpt-4.1-mini', AI_INFERENCE_GEO='us'),
                 dict(SONNET_5, AI_MODEL='Claude-Sonnet-5'), dict(SONNET_5, AI_MODEL='claude-sonnet-5 ')]
        for overrides in cases:
            with self.subTest(overrides=overrides), override_settings(**overrides), \
                    patch.dict(os.environ, PRICE_ENV), patch('anthropic.Anthropic') as client, \
                    patch('openai.OpenAI') as openai_client:
                config = g.configuration()          # transcription quotes and pages keep working
                self.assertIn('invalid', config['request_profile'])
                with self.assertRaises(NoProviderRequest):
                    g.maximum_cost(NOTES, FIELDS)
                with self.assertRaises(NoProviderRequest):
                    g.generate(NOTES, FIELDS)
                client.assert_not_called()
                openai_client.assert_not_called()

    def test_a_newer_claude_model_without_its_own_profile_is_refused_whatever_it_carries(self):
        """The class, not the instance: Claude 4.7+ tokenizes larger and Sonnet 5 / Opus 5 think by default, so the legacy
        request is unsafe on ANY newer model — not only on a misspelt claude-sonnet-5."""
        for model in ('claude-opus-5', 'claude-opus-5-5', 'claude-sonnet-5-1', 'claude-opus-4-7', 'claude-opus-4-8',
                      'claude-fable-5-1', 'CLAUDE-OPUS-5', ' claude-sonnet-5', 'Claude-Sonnet-5'):
            with self.subTest(model=model):
                self.assertIn('invalid', g.request_profile('anthropic', model, 'disabled', 'medium', ''))
                with override_settings(**dict(SONNET_46, AI_MODEL=model)), patch.dict(os.environ, PRICE_ENV), \
                        patch('anthropic.Anthropic') as client:
                    quoted = g.configuration()
                    old = {k: v for k, v in quoted.items() if k != 'request_profile'}
                    for config in (quoted, old, {**old, 'request_profile': g.LEGACY_PROFILE}):
                        with self.assertRaises(NoProviderRequest):
                            g.generate(NOTES, FIELDS, config)
                        with self.assertRaises(NoProviderRequest):
                            g.maximum_cost(NOTES, FIELDS, config)
                    client.assert_not_called()
        # The LISTED Claude models up to 4.6 under anthropic, and non-Claude ids under openai, keep the pre-profile request.
        # ⚠️ This list used to pin ('anthropic', 'synthetic-model') and ('openai', 'claude-opus-5') as LEGACY too — the
        # wrong behaviour F2 (round 3) measured: each was held, sent to the wrong API, and 404'd into reconciliation.
        # Both are now refused; see test_the_provider_and_model_must_be_a_pair_quillmd_sends.
        for provider, model in (('anthropic', 'claude-sonnet-4-6'), ('anthropic', 'claude-haiku-4-5'),
                                ('anthropic', 'claude-sonnet-4-5-20250929'), ('openai', 'gpt-4.1-mini')):
            with self.subTest(provider=provider, model=model):
                self.assertEqual(g.request_profile(provider, model, 'x', 'y', ''), g.LEGACY_PROFILE)

    def test_the_provider_and_model_must_be_a_pair_quillmd_sends(self):
        """F2 (round 3). anthropic accepts only claude-sonnet-5 and LEGACY_CLAUDE_MODELS; openai refuses any Claude id.
        Measured before the repair: openai + claude-sonnet-4-6 was rated legacy, held $0.19, was sent to api.openai.com and
        404'd into reconciliation with the hold kept; anthropic + gpt-4.1-mini — the settings default — was rated legacy.
        Every mismatched pair is INVALID and refused before any hold or request, from configuration, a stored pre-profile
        config and a forged legacy snapshot alike."""
        pairs = [('openai', model) for model in ('claude-sonnet-4-6', 'claude-sonnet-5', 'claude-opus-4-1', 'Claude-Haiku-4-5',
                                                 'us.anthropic.claude-sonnet-4-6')]
        pairs += [('anthropic', model) for model in ('gpt-4.1-mini', 'synthetic-model', 'o3', '')]
        for provider, model in pairs:
            with self.subTest(provider=provider, model=model):
                self.assertIn('invalid', g.request_profile(provider, model, 'disabled', 'medium', ''))
                with override_settings(**dict(SONNET_46, AI_PROVIDER=provider, AI_MODEL=model)), \
                        patch.dict(os.environ, PRICE_ENV), patch('anthropic.Anthropic') as client, \
                        patch('openai.OpenAI') as openai_client:
                    quoted = g.configuration()
                    old = {k: v for k, v in quoted.items() if k != 'request_profile'}
                    for config in (None, quoted, old, {**old, 'request_profile': g.LEGACY_PROFILE}):
                        with self.assertRaises(NoProviderRequest):
                            g.maximum_cost(NOTES, FIELDS, config)
                        with self.assertRaises(NoProviderRequest):
                            g.generate(NOTES, FIELDS, config)
                    client.assert_not_called()
                    openai_client.assert_not_called()
        self.assertEqual(g.request_profile('openai', 'claude-sonnet-4-6', 'disabled', 'medium', ''),
                         {'invalid': 'QUILLMD_AI_MODEL names a Claude model but QUILLMD_AI_PROVIDER is openai: Claude models '
                                     'are sent only with QUILLMD_AI_PROVIDER=anthropic.'})

    def test_only_the_listed_claude_models_get_the_legacy_request_deny_by_default(self):
        """S5-R1. The version parser read `claude-<family>-<major>[-<minor>]`, so `claude-mythos-preview` — a real id outside
        that shape — parsed as nothing, counted as "not newer than 4.6", and was SENT the legacy request (6000 tokens,
        60 s, no thinking field). Deny by default: only an exact listed id gets the legacy request; every other Claude id is
        refused before any request — from the live configuration, a stored pre-profile config, and a forged legacy snapshot.
        """
        refused = ('claude-mythos-preview', 'claude-mythos', 'claude-sonet-4-6', 'claude-sonnet-4-6 ', 'Claude-Sonnet-4-6',
                   'claude-sonnet-4-6-20260101', 'claude-opus-4-5-20251101', 'claude-3-7-sonnet-20250219',
                   'us.anthropic.claude-sonnet-4-6', 'claude_sonnet_4_6', 'claude-haiku-4-5-preview', 'claude',
                   # Deprecated by Anthropic (retiring 2026-08-05) and never used here: fails closed like any unlisted id.
                   'claude-opus-4-1', 'claude-opus-4-1-20250805')
        for model in refused:
            with self.subTest(model=model):
                self.assertIn('invalid', g.request_profile('anthropic', model, 'disabled', 'medium', ''))
                with override_settings(**dict(SONNET_46, AI_MODEL=model)), patch.dict(os.environ, PRICE_ENV), \
                        patch('anthropic.Anthropic') as client:
                    client.return_value.messages.create.return_value = message(text(SELECTED))
                    quoted = g.configuration()
                    old = {k: v for k, v in quoted.items() if k != 'request_profile'}
                    for config in (None, quoted, old, {**old, 'request_profile': g.LEGACY_PROFILE}):
                        with self.assertRaises(NoProviderRequest):
                            g.generate(NOTES, FIELDS, config)
                        with self.assertRaises(NoProviderRequest):
                            g.maximum_cost(NOTES, FIELDS, config)
                    client.assert_not_called()
        # Positive control: every listed id IS sent, and what it is sent is exactly the pre-profile request.
        for model in sorted(g.LEGACY_CLAUDE_MODELS):
            with self.subTest(model=model):
                client_kwargs, sent, _ = captured(dict(SONNET_46, AI_MODEL=model))
                self.assertEqual(client_kwargs, {'timeout': 60, 'max_retries': 0})
                self.assertEqual((sent['model'], sent['max_tokens']), (model, 6000))
                self.assertEqual(set(sent), {'model', 'max_tokens', 'system', 'messages', 'output_config'})
        # The list itself is pinned: widening it is a deliberate code change that has to edit this line.
        self.assertEqual(g.LEGACY_CLAUDE_MODELS, frozenset(('claude-sonnet-4-6', 'claude-haiku-4-5',
                                                            'claude-sonnet-4-5-20250929')))

    def test_a_provider_spelled_any_other_way_is_invalid_and_refused_before_any_request(self):
        """R2-3. generate() sends to Anthropic for 'anthropic' and to OpenAI OTHERWISE, and every model check keys on
        'anthropic' — so 'Anthropic' passed them all, showed a green legacy row, and sent a Claude id to OpenAI. The provider
        must be exactly one of the supported names; any other spelling is INVALID and nothing is priced or sent."""
        for provider in ('Anthropic', 'ANTHROPIC', ' anthropic', 'anthropic ', 'OpenAI', 'claude', 'bedrock', ''):
            with self.subTest(provider=provider):
                self.assertEqual(g.request_profile(provider, 'claude-sonnet-4-6', 'disabled', 'medium', ''),
                                 {'invalid': 'QUILLMD_AI_PROVIDER must be exactly one of: anthropic, openai.'})
                with override_settings(**dict(SONNET_46, AI_PROVIDER=provider)), patch.dict(os.environ, PRICE_ENV), \
                        patch('anthropic.Anthropic') as client, patch('openai.OpenAI') as openai_client:
                    quoted = g.configuration()
                    old = {k: v for k, v in quoted.items() if k != 'request_profile'}
                    for config in (None, quoted, old, {**old, 'request_profile': g.LEGACY_PROFILE}):
                        with self.assertRaises(NoProviderRequest):
                            g.maximum_cost(NOTES, FIELDS, config)
                        with self.assertRaises(NoProviderRequest):
                            g.generate(NOTES, FIELDS, config)
                    client.assert_not_called()
                    openai_client.assert_not_called()
        # Positive control: the two exact names keep the legacy request.
        for provider, model in (('anthropic', 'claude-sonnet-4-6'), ('openai', 'gpt-4.1-mini')):
            with self.subTest(provider=provider):
                self.assertEqual(g.request_profile(provider, model, 'disabled', 'medium', ''), g.LEGACY_PROFILE)

    def test_a_stored_profile_that_does_not_match_its_shapes_is_refused_before_any_request(self):
        with override_settings(**SONNET_5), patch.dict(os.environ, PRICE_ENV):
            good = g.configuration()
        tampered = [
            {**good['request_profile'], 'thinking': {'type': 'enabled', 'budget_tokens': 4000}},
            {**good['request_profile'], 'temperature': 0},
            {**good['request_profile'], 'effort': 'max'},
            {**good['request_profile'], 'max_output_tokens': 64000},
            {**good['request_profile'], 'max_output_tokens': True},
            {**good['request_profile'], 'timeout_seconds': 600},
            {**good['request_profile'], 'inference_geo': 'eu'},
            g.LEGACY_PROFILE,                      # a legacy request would run Sonnet 5's own defaults
            'legacy-v1',
        ]
        for profile in tampered:
            with self.subTest(profile=profile), patch('anthropic.Anthropic') as client:
                with self.assertRaises(NoProviderRequest):
                    g.generate(NOTES, FIELDS, {**good, 'request_profile': profile})
                client.assert_not_called()
        # And a Sonnet 5 profile on the rollback model is refused just the same.
        with override_settings(**SONNET_46), patch.dict(os.environ, PRICE_ENV), patch('anthropic.Anthropic') as client:
            legacy = g.configuration()
            with self.assertRaises(NoProviderRequest):
                g.generate(NOTES, FIELDS, {**legacy, 'request_profile': good['request_profile']})
            client.assert_not_called()


class DiscountValidatedAsUsed(SimpleTestCase):
    """Extra B. normalize() rounds to 28 digits, so a discount just under 1 passed the `< 1` check, became '1', was
    stored and held on, and settlement refused it only AFTER the provider call — the job stranded in reconciliation."""

    def test_a_discount_that_rounds_to_one_is_refused_before_any_hold_or_request(self):
        for value in ('0.' + '9' * 29, '0.' + '9' * 40, '0.' + '9' * 28 + '5'):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    g.normalized_discount(value)
                with override_settings(**SONNET_46), \
                        patch.dict(os.environ, {**PRICE_ENV, 'QUILLMD_PROVIDER_DISCOUNT_RATE': value}), \
                        patch('anthropic.Anthropic') as client:
                    for attempt in (g.configuration, lambda: g.maximum_cost(NOTES, FIELDS), lambda: g.generate(NOTES, FIELDS)):
                        with self.assertRaises(ValidationError):
                            attempt()
                    client.assert_not_called()
        # Positive control: the largest value still below 1 once normalized is accepted, and used exactly as written.
        self.assertEqual(g.normalized_discount('0.' + '9' * 28), '0.' + '9' * 28)
        self.assertEqual(g.normalized_discount('0.20'), '0.2')

    def test_a_stored_discount_of_one_is_refused_before_the_request(self):
        """A config stored before the repair can carry the '1' the old code produced: refused as NoProviderRequest by the
        check maximum_cost and generate both run first. The worker's release of the hold is StoredDiscountRefusal's."""
        with override_settings(**SONNET_46), patch.dict(os.environ, PRICE_ENV), patch('anthropic.Anthropic') as client:
            profiled = {**g.configuration(), 'discount_rate': '1'}
            # F3 (round 3): the population the running release actually writes has NO request_profile key — a check that
            # only ran for profiled configs survived every test. Both shapes are refused.
            pre_profile = {k: v for k, v in profiled.items() if k != 'request_profile'}
            for label, stored in (('profiled', profiled), ('pre-profile', pre_profile)):
                with self.subTest(config=label):
                    with self.assertRaises(NoProviderRequest):
                        g.maximum_cost(NOTES, FIELDS, stored)
                    with self.assertRaises(NoProviderRequest):
                        g.generate(NOTES, FIELDS, stored)
            client.assert_not_called()


class RollbackIsByteIdentical(SimpleTestCase):
    def test_the_rollback_kwargs_are_the_pre_profile_call(self):
        client_kwargs, sent, _ = captured(SONNET_46)
        self.assertEqual(client_kwargs, {'timeout': 60, 'max_retries': 0})
        self.assertEqual(set(sent), {'model', 'max_tokens', 'system', 'messages', 'output_config'})
        self.assertEqual(sent['model'], 'claude-sonnet-4-6')
        self.assertEqual(sent['max_tokens'], 6000)
        self.assertEqual(sent['output_config'],
                         {'format': {'type': 'json_schema', 'schema': g.Selections.model_json_schema()}})
        self.assertEqual(len(sent['messages']), 1)
        self.assertEqual(sent['messages'][0]['role'], 'user')

    def test_a_job_quoted_before_profiles_existed_sends_the_same_legacy_request(self):
        with override_settings(**SONNET_46), patch.dict(os.environ, PRICE_ENV):
            old = {k: v for k, v in g.configuration().items() if k != 'request_profile'}
        _, sent, _ = captured(SONNET_46, config=old)
        _, current, _ = captured(SONNET_46)
        self.assertEqual(sent, current)

    def test_the_http_body_is_byte_identical_to_the_pre_profile_call(self):
        """Through the real SDK: the bytes that would leave for api.anthropic.com, compared to the literal old call."""
        Real = anthropic.Anthropic
        bodies, constructed = [], []

        def handler(request):
            self.assertEqual(request.url.host, 'api.anthropic.com')
            bodies.append(request.content)
            return httpx.Response(200, json=message_json(text(SELECTED), model='claude-sonnet-4-6'))

        def real_client(**kwargs):
            constructed.append(kwargs)
            return Real(api_key='synthetic-no-network', http_client=httpx.Client(transport=httpx.MockTransport(handler)),
                        **kwargs)

        with override_settings(**SONNET_46), patch.dict(os.environ, PRICE_ENV), \
                patch('anthropic.Anthropic', side_effect=real_client):
            raw, *_ = g.generate(NOTES, FIELDS)
        sent = json.loads(bodies[0])
        # The pre-profile call, written out literally as it stood before this change.
        reference = real_client(timeout=60, max_retries=0).messages.create(
            model='claude-sonnet-4-6', max_tokens=6000, system=sent['system'],
            messages=[{'role': 'user', 'content': sent['messages'][0]['content']}],
            output_config={'format': {'type': 'json_schema', 'schema': g.Selections.model_json_schema()}})
        self.assertEqual(reference.stop_reason, 'end_turn')
        self.assertEqual(bodies[0], bodies[1])
        self.assertEqual(set(sent), {'model', 'max_tokens', 'system', 'messages', 'output_config'})
        self.assertEqual(constructed[0], {'timeout': 60, 'max_retries': 0})
        self.assertEqual(g.validated(raw)['symptoms']['text'], 'no chest pain')


class Sonnet5RequestProfile(SimpleTestCase):
    def test_every_sonnet_5_request_states_thinking_and_effort_and_nothing_forbidden(self):
        for thinking in g.THINKING_MODES:
            for effort in g.EFFORT_LEVELS:
                with self.subTest(thinking=thinking, effort=effort):
                    client_kwargs, sent, _ = captured(dict(SONNET_5, AI_THINKING=thinking, AI_EFFORT=effort))
                    self.assertEqual(client_kwargs, {'timeout': 120, 'max_retries': 0})
                    self.assertEqual(sent['thinking'], {'type': 'disabled'} if thinking == 'disabled'
                                     else {'type': 'adaptive', 'display': 'omitted'})
                    self.assertEqual(sent['output_config']['effort'], effort)
                    self.assertEqual(sent['output_config']['format']['type'], 'json_schema')
                    self.assertEqual(sent['max_tokens'], g.SONNET_5_MAX_OUTPUT_TOKENS[thinking])
                    self.assertEqual(set(sent), {'model', 'max_tokens', 'system', 'messages', 'output_config',
                                                 'thinking'})
                    self.assertFalse(set(keys_anywhere(sent)) & g.FORBIDDEN_REQUEST_KEYS)
                    # No assistant prefill: exactly one message, the user's.
                    self.assertEqual([m['role'] for m in sent['messages']], ['user'])

    def test_inference_geo_is_sent_only_when_configured(self):
        _, sent, _ = captured(SONNET_5)
        self.assertNotIn('inference_geo', sent)
        _, sent, _ = captured(dict(SONNET_5, AI_INFERENCE_GEO='us'))
        self.assertEqual(sent['inference_geo'], 'us')
        _, sent, _ = captured(dict(SONNET_46, AI_INFERENCE_GEO='us'))
        self.assertEqual(sent['inference_geo'], 'us')
        self.assertEqual(sent['max_tokens'], 6000)

    def test_the_hold_prices_exactly_the_max_tokens_that_is_sent(self):
        for overrides in (SONNET_46, SONNET_5, dict(SONNET_5, AI_THINKING='adaptive')):
            with self.subTest(model=overrides['AI_MODEL'], thinking=overrides['AI_THINKING']):
                _, sent, _ = captured(overrides)
                with override_settings(**overrides), patch.dict(os.environ, PRICE_ENV):
                    priced = g.maximum_cost(NOTES, FIELDS)
                with override_settings(**dict(overrides, AI_OUTPUT_RATE='0')), patch.dict(os.environ, PRICE_ENV):
                    input_only = g.maximum_cost(NOTES, FIELDS)
                self.assertEqual(priced - input_only,
                                 Decimal(sent['max_tokens']) * Decimal(overrides['AI_OUTPUT_RATE']) / 1000000)

    def test_requested_us_inference_raises_the_hold_by_the_multiplier(self):
        with override_settings(**SONNET_5), patch.dict(os.environ, PRICE_ENV):
            standard = g.maximum_cost(NOTES, FIELDS)
        with override_settings(**dict(SONNET_5, AI_INFERENCE_GEO='us')), patch.dict(os.environ, PRICE_ENV):
            us = g.maximum_cost(NOTES, FIELDS)
        self.assertGreaterEqual(us, standard * Decimal('1.1'))
        self.assertLess(us - standard * Decimal('1.1'), g.COST_QUANTUM)
        self.assertEqual(us, us.quantize(g.COST_QUANTUM))

    def test_every_profile_stays_non_streaming_and_inside_the_worker_stop(self):
        sdk = anthropic.Anthropic(api_key='synthetic-no-network')
        # The constant IS the SDK's rule: at it a non-streaming request is allowed, one token more is refused.
        sdk._calculate_nonstreaming_timeout(g.NONSTREAMING_MAX_OUTPUT_TOKENS, None)
        with self.assertRaises(ValueError):
            sdk._calculate_nonstreaming_timeout(g.NONSTREAMING_MAX_OUTPUT_TOKENS + 1, None)
        profiles = [g.LEGACY_PROFILE] + [g.request_profile('anthropic', g.SONNET_5, t, 'high', 'us')
                                         for t in g.THINKING_MODES]
        for profile in profiles:
            with self.subTest(profile=profile['profile'], tokens=profile['max_output_tokens']):
                sdk._calculate_nonstreaming_timeout(profile['max_output_tokens'], None)
                self.assertLess(profile['timeout_seconds'], g.WORKER_STOP_SECONDS)   # TimeoutStopSec=150
                self.assertLess(profile['timeout_seconds'], 5 * 60)                 # mark_stale's 5 minutes
        # 6000 tokens sized on Sonnet 4.6 become ~7800 on Sonnet 5's tokenizer; the disabled profile covers that.
        self.assertGreaterEqual(g.SONNET_5_MAX_OUTPUT_TOKENS['disabled'], 6000 * 1.3)
        self.assertGreater(g.SONNET_5_MAX_OUTPUT_TOKENS['adaptive'], g.SONNET_5_MAX_OUTPUT_TOKENS['disabled'])
        unit = Path(__file__).resolve().parents[3] / 'rebuild' / 'deploy' / 'quillmd-fresh-worker.service'
        self.assertIn(f'TimeoutStopSec={g.WORKER_STOP_SECONDS}\n', unit.read_text())

    def test_the_schema_sent_carries_no_text_from_the_notes(self):
        """The output schema is static: nothing from the notes or the form may reach it. Positive control first — the
        canary DOES reach the payload, so its absence from the schema is not a vacuous pass."""
        from core.tests.test_natural_tab_generation import NOTES as TAB_NOTES, ORIGINAL
        from documents.engine import docx_inspect
        canary = 'CANARY-7f3c-notes-never-in-schema'
        tab_fields = docx_inspect(ORIGINAL)[3]
        cases = [('legacy', f'Symptoms: {canary}', [dict(FIELDS[0], label=f'Symptoms {canary}')]),
                 ('tab', TAB_NOTES + f'\nThe patient said {canary}.', tab_fields)]
        for contract, notes, fields in cases:
            for overrides in (SONNET_5, dict(SONNET_5, AI_THINKING='adaptive'), SONNET_46):
                with self.subTest(contract=contract, model=overrides['AI_MODEL'], thinking=overrides['AI_THINKING']):
                    _, sent, _ = captured(overrides, reply=message(text('{"fields":[]}')), notes=notes, fields=fields)
                    self.assertIn(canary, sent['messages'][0]['content'])
                    schema = json.dumps(sent['output_config'])
                    self.assertNotIn(canary, schema)
                    self.assertNotIn('CANARY', schema)
                    expected = g.UnitSelections if contract == 'tab' else g.Selections
                    self.assertEqual(sent['output_config']['format']['schema'], expected.model_json_schema())

    def test_the_real_sdk_serializes_the_profile_and_parses_a_thinking_first_reply(self):
        Real = anthropic.Anthropic
        bodies = []

        def handler(request):
            bodies.append(json.loads(request.content))
            return httpx.Response(200, json=message_json(THINKING, text(SELECTED),
                                                          usage={'output_tokens_details': {'thinking_tokens': 7},
                                                                 'inference_geo': 'global'}))

        def real_client(**kwargs):
            return Real(api_key='synthetic-no-network', http_client=httpx.Client(transport=httpx.MockTransport(handler)),
                        **kwargs)

        with override_settings(**dict(SONNET_5, AI_THINKING='adaptive', AI_EFFORT='low')), \
                patch.dict(os.environ, PRICE_ENV), patch('anthropic.Anthropic', side_effect=real_client):
            raw, *_ = g.generate(NOTES, FIELDS)
        body = bodies[0]
        self.assertEqual(body['thinking'], {'type': 'adaptive', 'display': 'omitted'})
        self.assertEqual(body['output_config']['effort'], 'low')
        self.assertEqual(body['max_tokens'], 16000)
        self.assertFalse(set(keys_anywhere(body)) & g.FORBIDDEN_REQUEST_KEYS)
        self.assertEqual([block.type for block in raw['anthropic_response'].content], ['thinking', 'text'])
        self.assertEqual(g.validated(raw)['symptoms']['text'], 'no chest pain')


class OperatorValueBlocks(SimpleTestCase):
    """S5-R4. The note's value blocks are what the owner pastes into the private environment, which the doctor, admin and
    worker units read through systemd's EnvironmentFile= — where `#` starts a comment only at the start of a line and an
    inline `# …` stays in the value. `QUILLMD_AI_INFERENCE_GEO=   # unset for the byte-identical request` therefore
    refused every generation, the rollback included. Every value line is literal, and each block, read the way systemd
    reads it, selects exactly what the note says it does."""
    ROOT = Path(__file__).resolve().parents[3]
    NOTE = ROOT / 'docs' / 'rebuild' / 'v1' / 'sonnet5-migration.md'
    EXAMPLE = ROOT / 'rebuild' / '.env.example'

    #: An opening code fence of either kind, at any indent (a block inside a list item), with or without an info string.
    FENCE = re.compile(r'^[ \t]*(?P<fence>`{3,}|~{3,})(?P<info>.*)$')
    #: A line systemd would read as an assignment; a `#` or `;` line is a comment and never matches.
    ASSIGNMENT = re.compile(r'^[ \t]*(?:export[ \t]+)?[A-Za-z_][A-Za-z0-9_]*[ \t]*=')

    @classmethod
    def blocks(cls, text=None):
        """Every fenced block in the note, whatever its fence: ``` or ~~~, bare or with an info string (```ini), at any
        indent. R2-5: the reader used to see only unindented bare ``` fences, so a value block written any other way —
        the shapes a note naturally grows — carried an inline comment past this test. An unclosed fence runs to the end,
        as CommonMark reads it. Lines are returned de-indented, as they would be pasted."""
        blocks, current, fence = [], [], None
        for line in (cls.NOTE.read_text() if text is None else text).splitlines():
            if fence is None:
                match = cls.FENCE.match(line)
                if match and not (match['fence'][0] == '`' and '`' in match['info']):
                    fence, current = match['fence'], []
            elif re.fullmatch(r'[ \t]*' + re.escape(fence[0]) + '{%d,}[ \t]*' % len(fence), line):
                blocks.append(current)
                fence = None
            else:
                current.append(line.strip())
        if fence is not None:
            blocks.append(current)
        return blocks

    @classmethod
    def assignments(cls, lines):
        return [line.strip() for line in lines if cls.ASSIGNMENT.match(line)]

    @classmethod
    def systemd_values(cls, lines):
        """EnvironmentFile= as systemd.exec documents it: a line starting with `#` or `;` is a comment; an unquoted value
        loses its leading and trailing whitespace and keeps everything else, an inline `#` included."""
        return {name.strip(): value.strip() for name, _, value in (line.partition('=') for line in cls.assignments(lines))}

    def test_the_block_reader_sees_every_fence_shape(self):
        """The reader's own positive control: each shape a value block can take is found, with its lines de-indented."""
        text = ('```\nA=1\n```\n\n```ini\nB=2\n```\n\n- item:\n\n    ```\n    C=3\n    ```\n\n~~~\nD=4\n~~~\n\n'
                '````text\nE=5\n```\nstill E\n````\n\n~~~~\nF=6\n')
        self.assertEqual(self.blocks(text), [['A=1'], ['B=2'], ['C=3'], ['D=4'], ['E=5', '```', 'still E'], ['F=6']])

    def test_no_value_line_carries_an_inline_comment(self):
        note = [line for block in self.blocks() for line in self.assignments(block)]
        self.assertGreaterEqual(len(note), 12, 'positive control: the switch (4), profile (3) and rollback (5) value lines')
        # Every assignment-shaped line anywhere in the note too — an indented code block has no fence at all.
        anywhere = self.assignments(self.NOTE.read_text().splitlines())
        self.assertLessEqual(set(note), set(anywhere))
        for line in note + anywhere + self.assignments(self.EXAMPLE.read_text().splitlines()):
            with self.subTest(line=line):
                self.assertNotIn('#', line)

    def test_the_env_example_rollback_names_every_key_the_rollback_block_resets(self):
        """The note's rollback block resets five keys, QUILLMD_AI_INFERENCE_GEO among them; .env.example's rollback
        sentence said 'the four lines above', so following it left US-only inference set — not the rollback request."""
        lines = self.EXAMPLE.read_text().splitlines()
        start = next(i for i, line in enumerate(lines) if line.startswith('# Rollback'))
        sentence = []
        for line in lines[start:]:
            if not line.startswith('#'):
                break
            sentence.append(line)
        rollback = next(values for values in map(self.systemd_values, self.blocks())
                        if values.get('QUILLMD_AI_MODEL') == 'claude-sonnet-4-6')
        self.assertEqual(len(rollback), 5)
        for name in rollback:
            with self.subTest(key=name):
                self.assertIn(name, ' '.join(sentence))

    def block(self, has):
        as_settings = lambda values: {name[len('QUILLMD_'):]: value for name, value in values.items()}
        return next(as_settings(values) for values in map(self.systemd_values, self.blocks()) if has(values))

    def test_the_switch_blocks_read_as_systemd_reads_them_select_the_default_sonnet_5_profile(self):
        switch = self.block(lambda values: values.get('QUILLMD_AI_MODEL') == 'claude-sonnet-5')
        profile = self.block(lambda values: 'QUILLMD_AI_THINKING' in values)
        with override_settings(**{**SONNET_46, **switch, **profile}), patch.dict(os.environ, PRICE_ENV):
            config = g.configuration()
        self.assertNotIn('invalid', config['request_profile'])
        self.assertEqual(config['pricing_version'], SONNET_5_DISABLED_MEDIUM)

    def test_the_rollback_block_read_as_systemd_reads_it_is_the_byte_identical_legacy_request(self):
        rollback = self.block(lambda values: values.get('QUILLMD_AI_MODEL') == 'claude-sonnet-4-6')
        # Rolling back FROM a Sonnet 5 configuration that had US-only inference and adaptive thinking set.
        with override_settings(**{**SONNET_5, 'AI_THINKING': 'adaptive', 'AI_INFERENCE_GEO': 'us', **rollback}), \
                patch.dict(os.environ, PRICE_ENV):
            config = g.configuration()
        self.assertEqual(config['request_profile'], g.LEGACY_PROFILE)
        self.assertEqual(config['pricing_version'], ROLLBACK_FINGERPRINT)


class OutcomeFixture(SyntheticFixture):
    """Private media, the pinned price environment and one synthetic scope; shared with test_sonnet5_settlement.py."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        media = override_settings(MEDIA_ROOT=Path(directory.name))
        media.enable()
        self.addCleanup(media.disable)
        env = patch.dict(os.environ, PRICE_ENV)
        env.start()
        self.addCleanup(env.stop)
        self.user, _, _, _, _, self.encounter, _ = self.make_scope('sonnet5')

    def fresh_encounter(self):
        original = self.encounter
        return Encounter.objects.create(department=original.department, patient=original.patient,
                                        template_version=original.template_version, created_by=original.created_by,
                                        service_date=original.service_date, notes=original.notes,
                                        answers=original.answers)

    def run_job(self, encounter, reply):
        with patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.return_value = reply
            job = enqueue(encounter, self.user)
            self.assertTrue(run_one())
            sent = client.return_value.messages.create.call_args.kwargs
        job.refresh_from_db()
        encounter.refresh_from_db()
        return job, sent


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, **SONNET_5)
class Sonnet5Outcomes(OutcomeFixture, TestCase):
    """Through enqueue + run_one: what the doctor's document and the ledger look like after each provider outcome."""

    def test_a_thinking_block_before_the_text_adopts_identical_answers(self):
        plain_encounter, thinking_encounter = self.fresh_encounter(), self.fresh_encounter()
        plain, _ = self.run_job(plain_encounter, message(text(SELECTED), ident='msg_plain'))
        thought, sent = self.run_job(thinking_encounter, message(
            THINKING, text(SELECTED), ident='msg_thinking', usage={'output_tokens_details': {'thinking_tokens': 9}}))
        self.assertEqual((plain.state, thought.state), ('succeeded', 'succeeded'))
        self.assertEqual(thinking_encounter.answers, plain_encounter.answers)
        self.assertEqual(thinking_encounter.answers['symptoms']['text'], 'no chest pain')
        self.assertEqual(thinking_encounter.status, 'review')
        self.assertEqual(sent['thinking'], {'type': 'disabled'})
        self.assertEqual(sent['output_config']['effort'], 'medium')
        # The stored receipt keeps the block exactly as returned: empty text and an opaque signature, no reasoning.
        stored = json.loads(private_path(thought.result_path).read_text())
        self.assertEqual(stored['provider_output']['content'][0], THINKING)
        self.assertTrue(audit_report()['all_checks_pass'])

    def test_refusal_truncation_and_context_overflow_never_touch_the_document_and_are_absorbed(self):
        outcomes = {
            'refusal': message(stop_reason='refusal', ident='msg_refusal', usage={'output_tokens': 0},
                               stop_details={'type': 'refusal', 'category': 'cyber', 'explanation': None}),
            'max_tokens': message(THINKING, text('{"fields":[{"key":"symptoms","quotes":["no ches'),
                                  stop_reason='max_tokens', ident='msg_truncated', usage={'output_tokens': 8000}),
            'model_context_window_exceeded': message(text('{"fields":['), stop_reason='model_context_window_exceeded',
                                                     ident='msg_overflow'),
            # The stop reason itself is the gate, not the JSON parser: output that happens to parse is still refused.
            'max_tokens (parseable)': message(text(SELECTED), stop_reason='max_tokens', ident='msg_parseable'),
        }
        for label, reply in outcomes.items():
            with self.subTest(stop_reason=label):
                encounter = self.fresh_encounter()
                before = (encounter.answers, encounter.status, encounter.revision, encounter.notes)
                job, sent = self.run_job(encounter, reply)
                self.assertEqual((encounter.answers, encounter.status, encounter.revision, encounter.notes), before)
                self.assertEqual(job.state, 'failed')
                self.assertTrue(job.error.startswith(PLATFORM_FAILURE), job.error)
                usage = Usage.objects.get(job=job)
                self.assertTrue(ProviderReceipt.objects.filter(job=job, provider='anthropic:claude-sonnet-5').exists())
                self.assertEqual(usage.charged_cost, usage.actual_cost * Decimal('1.5'))
                # Absorbed: the customer's debit is reversed to the cent and QuillMD carries the provider cost.
                self.assertEqual(sum(LedgerEntry.objects.filter(job=job, kind__in=['usage', 'absorbed'])
                                     .values_list('amount', flat=True), Decimal(0)), 0)
                self.assertEqual(PlatformCost.objects.get(job=job, kind='absorbed_failure').amount, usage.actual_cost)
                self.assertFalse(Reservation.objects.filter(job=job, state='held').exists())
                self.assertEqual(sent['max_tokens'], 8000)
        self.assertTrue(audit_report()['all_checks_pass'])

    def test_a_queued_job_keeps_the_profile_it_was_priced_with(self):
        encounter = self.fresh_encounter()
        with override_settings(AI_THINKING='adaptive', AI_EFFORT='high'), patch('anthropic.Anthropic'):
            job = enqueue(encounter, self.user)
            expected_version = g.configuration()['pricing_version']
        self.assertEqual(job.config['pricing_version'], expected_version)
        self.assertEqual(job.config['request_profile']['thinking'], {'type': 'adaptive', 'display': 'omitted'})
        hold = sum(Reservation.objects.filter(job=job).values_list('amount', flat=True), Decimal(0))
        with patch('anthropic.Anthropic') as client:                   # settings now say disabled / medium
            client.return_value.messages.create.return_value = message(text(SELECTED), ident='msg_queued')
            self.assertTrue(run_one())
            sent = client.return_value.messages.create.call_args.kwargs
        self.assertEqual(sent['thinking'], {'type': 'adaptive', 'display': 'omitted'})
        self.assertEqual((sent['output_config']['effort'], sent['max_tokens']), ('high', 16000))
        # The hold priced the 16000 tokens that were sent, not the 8000 the settings now select.
        self.assertGreaterEqual(hold, Decimal(16000) * 10 / 1000000 * Decimal('1.5'))

    def test_a_sonnet_5_job_quoted_before_profiles_existed_is_refused_and_released(self):
        encounter = self.fresh_encounter()
        old = {k: v for k, v in g.configuration().items() if k != 'request_profile'}
        with self.assertRaises(NoProviderRequest):          # a stale signed quote cannot enqueue it
            enqueue(encounter, self.user, config=old)
        self.assertFalse(Job.objects.filter(encounter=encounter).exists())
        # A row that already exists (queued by the previous release) is refused by the worker, before any request.
        job = Job.objects.create(encounter=encounter, user=self.user, request_key=f'generation:{encounter.pk}:legacy',
                                 revision=encounter.revision, config=old)
        reserve(job, Decimal('0.2'))
        with patch('anthropic.Anthropic') as client:
            self.assertTrue(run_one())
            client.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        self.assertTrue(job.error.startswith('Not processed: '), job.error)
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.assertFalse(Reservation.objects.filter(job=job, state='held').exists())


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class QuoteAcrossAModelSwitch(OutcomeFixture, TestCase):
    """R2-1. The encounter page signs the whole configuration() into its quote, and the quote used to be enqueued as it
    stood for its 600 s. Measured: a page loaded under claude-sonnet-5 and clicked after a rollback, restart and drain queued
    and SENT a claude-sonnet-5 request while configuration_status said legacy. A generation quote whose pricing_version is
    not the current one is refused at enqueue — no job, no hold, nothing sent — and the page it returns to re-quotes."""

    def page(self, encounter, **kwargs):
        self.client.force_login(self.user)
        return self.client.get(f'/encounters/{encounter.pk}/', **kwargs)

    def test_a_page_loaded_under_sonnet_5_cannot_queue_it_after_the_rollback(self):
        encounter = self.fresh_encounter()
        with override_settings(**SONNET_5):
            quote = self.page(encounter).context['usage_quote']
        with override_settings(**SONNET_46), patch('anthropic.Anthropic') as client:
            response = self.client.post(f'/encounters/{encounter.pk}/generate/', {'usage_quote': quote}, follow=True)
            client.assert_not_called()
        self.assertFalse(Job.objects.filter(encounter=encounter).exists())
        self.assertFalse(Reservation.objects.filter(job__encounter=encounter).exists())
        self.assertContains(response, 'The prices or the language model changed after this page loaded')
        # Positive control: the page it lands on signed a fresh quote under the rolled-back configuration, and that one
        # queues and sends exactly the legacy request.
        with override_settings(**SONNET_46), patch('anthropic.Anthropic') as client:
            self.client.post(f'/encounters/{encounter.pk}/generate/', {'usage_quote': response.context['usage_quote']})
            job = Job.objects.get(encounter=encounter)
            self.assertEqual((job.config['pricing_version'], job.config['request_profile']),
                             (ROLLBACK_FINGERPRINT, g.LEGACY_PROFILE))
            client.return_value.messages.create.return_value = message(text(SELECTED), model='claude-sonnet-4-6')
            self.assertTrue(run_one())
            sent = client.return_value.messages.create.call_args.kwargs
        self.assertEqual((sent['model'], sent['max_tokens']), ('claude-sonnet-4-6', 6000))
        self.assertNotIn('thinking', sent)

    def test_any_price_change_refuses_a_directly_enqueued_quote_before_any_hold(self):
        encounter = self.fresh_encounter()
        with override_settings(**SONNET_46):
            quoted = g.configuration()
        for label, overrides, env in (('rates', dict(SONNET_46, AI_OUTPUT_RATE='16'), {}),
                                      ('model', SONNET_5, {}),
                                      ('geography', dict(SONNET_46, AI_INFERENCE_GEO='us'), {}),
                                      ('discount', SONNET_46, {'QUILLMD_PROVIDER_DISCOUNT_RATE': '0.1'})):
            with self.subTest(changed=label), override_settings(**overrides), patch.dict(os.environ, env), \
                    patch('anthropic.Anthropic') as client:
                with self.assertRaisesMessage(ValidationError, 'The prices or the language model changed'):
                    enqueue(encounter, self.user, config=quoted)
                client.assert_not_called()
                self.assertFalse(Job.objects.filter(encounter=encounter).exists())
                self.assertFalse(Reservation.objects.filter(job__encounter=encounter).exists())
        with override_settings(**SONNET_46):                       # unchanged: the same quote queues
            self.assertEqual(enqueue(encounter, self.user, config=quoted).config['pricing_version'], ROLLBACK_FINGERPRINT)


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class ProviderSpelling(OutcomeFixture, TestCase):
    def test_a_misspelt_provider_is_refused_at_enqueue_with_no_job_and_no_hold(self):
        """R2-3, through enqueue: measured before the repair, provider 'Anthropic' held $0.19, fell to the OpenAI branch and
        stranded the job in reconciliation with its hold. Now it is refused before Job.objects.create commits and before
        any hold."""
        encounter = self.fresh_encounter()
        with override_settings(**dict(SONNET_46, AI_PROVIDER='Anthropic')), patch('anthropic.Anthropic') as client, \
                patch('openai.OpenAI') as openai_client:
            with self.assertRaises(NoProviderRequest):
                enqueue(encounter, self.user)
            client.assert_not_called()
            openai_client.assert_not_called()
        self.assertFalse(Job.objects.filter(encounter=encounter).exists())
        self.assertFalse(Reservation.objects.filter(job__encounter=encounter).exists())


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, **SONNET_46)
class StoredDiscountRefusal(OutcomeFixture, TestCase):
    def test_a_queued_job_whose_discount_normalized_to_one_is_not_sent_and_its_hold_is_released(self):
        """Extra B through the worker: a job queued by the previous release with discount_rate '1' is refused before any
        request, marked not processed, charged nothing, and its hold released — instead of reaching the provider and
        stranding in reconciliation. F3 (round 3): the previous release writes configs WITHOUT a request_profile key, so
        that is the shape tested here."""
        encounter = self.fresh_encounter()
        config = {**{k: v for k, v in g.configuration().items() if k != 'request_profile'}, 'discount_rate': '1'}
        self.assertNotIn('request_profile', config)
        job = Job.objects.create(encounter=encounter, user=self.user, request_key=f'generation:{encounter.pk}:discount',
                                 revision=encounter.revision, config=config)
        reserve(job, Decimal('0.2'))
        with patch('anthropic.Anthropic') as client:
            self.assertTrue(run_one())
            client.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        self.assertTrue(job.error.startswith('Not processed: '), job.error)
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.assertFalse(Reservation.objects.filter(job=job, state='held').exists())


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class ModeSwitch(OutcomeFixture, TestCase):
    """F1 (round 3). pricing_version does not hash the mode, so a switch between live and fixture was invisible to the
    stale-quote check and to the worker. Measured: a page quoted live and clicked after the switch to fixture queued a
    LIVE job that held $0.19, was sent and charged, while the console said no provider request is sent; the reverse put
    a fixture job's synthetic answers into a live deployment. Now: the quote is refused at enqueue in both directions,
    a job already queued is refused by the worker before sending (not processed, nothing charged, hold released), and
    the console counts the live jobs still queued."""
    FIXTURE = dict(SONNET_46, AI_MODE='fixture')

    def page(self, encounter):
        self.client.force_login(self.user)
        return self.client.get(f'/encounters/{encounter.pk}/')

    def held(self, encounter):
        return Reservation.objects.filter(job__encounter=encounter, state='held').exists()

    def test_a_quote_from_either_mode_is_refused_after_the_switch_and_the_page_re_quotes(self):
        for label, quoted_under, clicked_under in (('live -> fixture', SONNET_46, self.FIXTURE),
                                                   ('fixture -> live', self.FIXTURE, SONNET_46)):
            with self.subTest(switch=label):
                encounter = self.fresh_encounter()
                answers = encounter.answers
                with override_settings(**quoted_under):
                    quote = self.page(encounter).context['usage_quote']
                with override_settings(**clicked_under), patch('anthropic.Anthropic') as client:
                    response = self.client.post(f'/encounters/{encounter.pk}/generate/', {'usage_quote': quote}, follow=True)
                    client.assert_not_called()
                    self.assertContains(response, 'QuillMD was switched between live and synthetic processing')
                    self.assertFalse(Job.objects.filter(encounter=encounter).exists())
                    self.assertFalse(self.held(encounter))
                    encounter.refresh_from_db()
                    self.assertEqual(encounter.answers, answers)
                    # Positive control: the re-quoted page queues a job in the mode that is configured NOW.
                    self.client.post(f'/encounters/{encounter.pk}/generate/', {'usage_quote': response.context['usage_quote']})
                    self.assertEqual(Job.objects.get(encounter=encounter).config['mode'], clicked_under['AI_MODE'])

    def test_a_queued_live_job_is_not_sent_after_the_switch_to_fixture(self):
        encounter = self.fresh_encounter()
        with override_settings(**SONNET_46):
            job = enqueue(encounter, self.user)
        self.assertTrue(self.held(encounter))
        with override_settings(**self.FIXTURE), patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.return_value = message(text(SELECTED), model='claude-sonnet-4-6')
            self.assertTrue(run_one())
            client.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        self.assertTrue(job.error.startswith('Not processed: QuillMD was switched out of live mode'), job.error)
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.assertFalse(ProviderReceipt.objects.filter(job=job).exists())
        self.assertFalse(self.held(encounter))
        self.assertTrue(audit_report()['all_checks_pass'])

    def test_a_queued_fixture_job_is_not_used_after_the_switch_to_live(self):
        encounter = self.fresh_encounter()
        encounter.answers = {}
        encounter.save(update_fields=['answers'])
        with override_settings(**self.FIXTURE):
            job = enqueue(encounter, self.user)
        with override_settings(**SONNET_46), patch('anthropic.Anthropic') as client:
            self.assertTrue(run_one())
            client.assert_not_called()
        job.refresh_from_db()
        encounter.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        self.assertTrue(job.error.startswith('Not processed: QuillMD was switched to live mode'), job.error)
        self.assertEqual((encounter.answers, encounter.status), ({}, 'draft'))
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.assertFalse(self.held(encounter))

    def test_the_console_counts_the_live_jobs_still_queued(self):
        from core import admin_console
        encounter = self.fresh_encounter()
        with override_settings(**SONNET_46):
            job = enqueue(encounter, self.user)
            row = admin_console.language_model_rows()[-1]
        self.assertEqual(row, {'name': 'live generation jobs', 'value': '1 queued, 0 running (drained when both are 0)',
                               'severity': ''})
        with override_settings(**self.FIXTURE):
            row = admin_console.language_model_rows()[-1]
        self.assertEqual(row['name'], 'live generation jobs')
        self.assertTrue(row['value'].startswith('1 queued, 0 running — QUILLMD_AI_MODE is not live, so the worker refuses'))
        self.assertEqual(row['severity'], 'warning')
        self.assertNotIn(str(job.pk), repr(row))
        self.assertNotIn(str(encounter.pk), repr(row))
        # A fixture job is not a live one, and a finished live job is not queued.
        with override_settings(**self.FIXTURE):
            enqueue(self.fresh_encounter(), self.user)
            Job.objects.filter(pk=job.pk).update(state='succeeded')
            self.assertTrue(admin_console.language_model_rows()[-1]['value'].startswith('0 queued, 0 running'))


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class ProviderModelPairing(OutcomeFixture, TestCase):
    def test_a_mismatched_pair_is_refused_at_enqueue_and_a_stored_one_is_not_sent(self):
        """F2 (round 3), through enqueue and the worker: refused before any job or hold; a job stored with a mismatched
        pair (queued by the previous release) is refused before sending, not processed, hold released."""
        for provider, model in (('openai', 'claude-sonnet-4-6'), ('anthropic', 'gpt-4.1-mini')):
            with self.subTest(provider=provider, model=model), \
                    override_settings(**dict(SONNET_46, AI_PROVIDER=provider, AI_MODEL=model)), \
                    patch('anthropic.Anthropic') as client, patch('openai.OpenAI') as openai_client:
                encounter = self.fresh_encounter()
                with self.assertRaises(NoProviderRequest):
                    enqueue(encounter, self.user)
                self.assertFalse(Job.objects.filter(encounter=encounter).exists())
                stored = {k: v for k, v in g.configuration().items() if k != 'request_profile'}
                job = Job.objects.create(encounter=encounter, user=self.user, revision=encounter.revision,
                                         request_key=f'generation:{encounter.pk}:paired', config=stored)
                reserve(job, Decimal('0.2'))
                self.assertTrue(run_one())
                client.assert_not_called()
                openai_client.assert_not_called()
                job.refresh_from_db()
                self.assertEqual(job.state, 'failed')
                self.assertTrue(job.error.startswith('Not processed: '), job.error)
                self.assertFalse(Usage.objects.filter(job=job).exists())
                self.assertFalse(Reservation.objects.filter(job=job, state='held').exists())
