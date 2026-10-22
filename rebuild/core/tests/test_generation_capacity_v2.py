"""Finite prospective output capacity; all provider transports are injected."""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
import hashlib
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.core import signing
from django.test import SimpleTestCase, TestCase, override_settings

from core import ai_stages, anthropic_request_policy
from core.jobs import enqueue, generation_maximum, mark_stale, run_one
from core.models import Job, LedgerEntry, PlatformCost, ProviderReceipt, Reservation, Usage
from core.security import private_path
from core.tests import test_generation_capacity as previous


LIVE = {**previous.LIVE, 'model': 'claude-sonnet-5-5'}


def v1(config):
    return {**config, 'semantic_capacity_profile': 'bounded-output-16k-v1',
            'semantic_output_token_limit': 16000, 'semantic_timeout_seconds': 120,
            'semantic_maximum_cost': '7.35000000000'}


class GenerationCapacityV2PureTests(SimpleTestCase):
    def test_supported_prospective_quote_is_recalculated_without_mutating_input(self):
        original = deepcopy(LIVE)
        config = ai_stages.pipeline_config(LIVE)
        self.assertEqual(ai_stages.generation_limits(config), (32000, 240))
        self.assertEqual(config['semantic_capacity_profile'], 'bounded-output-32k-v2')
        self.assertEqual(config['semantic_max_calls'], 5)
        self.assertEqual(config['semantic_request_byte_limit'], 512000)
        self.assertEqual(Decimal(config['semantic_maximum_cost']), Decimal('8.15'))
        self.assertEqual((config['provider'], config['model']), ('anthropic', 'claude-sonnet-5-5'))
        self.assertEqual(LIVE, original)
        with patch('core.jobs.generation.configuration', return_value=LIVE), \
                patch('core.word_contract.require_generation', return_value={'field': {}}):
            encounter = SimpleNamespace(template_version=object())
            self.assertEqual(generation_maximum(encounter), Decimal('8.15'))
            self.assertEqual(generation_maximum(encounter, v1(config)), Decimal('7.35'))
            self.assertEqual(generation_maximum(encounter, previous.legacy(config)), Decimal('6.75'))
        discounted = ai_stages.pipeline_config({**LIVE, 'discount_rate': '0.25'})
        self.assertEqual(Decimal(discounted['semantic_maximum_cost']), Decimal('6.1125'))

    def test_historical_and_unsupported_configurations_keep_their_exact_contracts(self):
        current = ai_stages.pipeline_config(LIVE)
        for frozen, limits, quote in ((v1(current), (16000, 120), '7.35'),
                                     (previous.legacy(current), (4000, 60), '6.75')):
            before = ai_stages.encode(frozen)
            self.assertEqual(ai_stages.generation_limits(frozen), limits)
            self.assertEqual(ai_stages.maximum_cost(frozen), Decimal(quote))
            self.assertEqual(ai_stages.encode(frozen), before)
        for provider, model in (('anthropic', 'synthetic-model'), ('openai', 'claude-sonnet-5-5'),
                                ('anthropic', 'claude-sonnet-5-5-unreviewed'), ('anthropic', 'CLAUDE-SONNET-5-5')):
            config = {**LIVE, 'provider': provider, 'model': model}
            expected = {**config, 'semantic_contract': 'semantic-facts-v1',
                'semantic_stage_protocol': 'quillmd-ai-stages-v1', 'semantic_max_calls': 5,
                'semantic_request_byte_limit': 512000, 'semantic_capacity_profile': 'bounded-output-16k-v1',
                'semantic_timeout_seconds': 120, 'semantic_output_token_limit': 16000,
                'semantic_maximum_cost': '7.35000000000'}
            self.assertEqual(ai_stages.encode(ai_stages.pipeline_config(config)), ai_stages.encode(expected))

    def test_v2_profile_refuses_typed_limit_model_and_provider_tampering(self):
        config = ai_stages.pipeline_config(LIVE)
        cases = [('semantic_capacity_profile', x) for x in (None, False, '', 'unknown')]
        cases += [('semantic_output_token_limit', x) for x in (None, True, 16000, 32000.0, '32000', 32001)]
        cases += [('semantic_timeout_seconds', x) for x in (None, True, 120, 240.0, '240', 241)]
        cases += [('provider', x) for x in ('openai', None, [], True)]
        cases += [('model', x) for x in ('synthetic-model', 'claude-sonnet-5-5-extra', None, [], True)]
        for key, value in cases:
            with self.subTest(key=key, value=value), self.assertRaises(ai_stages.StageNotSent):
                ai_stages.maximum_cost({**config, key: value})

    def test_definition_and_all_retained_checker_contracts_stay_v1(self):
        from core.semantic_revalidation import CONTRACTS
        config = ai_stages.definition_pipeline_config(LIVE)
        self.assertEqual(config, {**LIVE, anthropic_request_policy.CONFIG_KEY: anthropic_request_policy.PROFILE,
            'definition_stage_protocol': 'quillmd-ai-stages-v1',
            'definition_max_calls': 2, 'definition_request_byte_limit': 512000,
            'definition_output_token_limit': 16000, 'definition_maximum_cost': '2.94000000000'})
        for contract in CONTRACTS:
            frozen = ai_stages.revalidation_config(LIVE, contract=contract)
            self.assertEqual(ai_stages.generation_limits(frozen), (16000, 120))
            self.assertEqual(frozen['semantic_max_calls'], 1)
            self.assertEqual(frozen['semantic_capacity_profile'], 'bounded-output-16k-v1')
            self.assertEqual(Decimal(frozen['semantic_maximum_cost']), Decimal('1.47'))

    def test_stage_admission_caps_each_profile_before_parent_or_send(self):
        class ReachedParent(Exception): pass
        config = ai_stages.pipeline_config(LIVE)
        cases = [(config, 'extractor', 32000, 240), (v1(config), 'extractor', 16000, 120),
                 (previous.legacy(config), 'extractor', 4000, 120),
                 (ai_stages.definition_pipeline_config(LIVE), 'definition_proposer', 16000, 120)]
        for frozen, stage, tokens, timeout in cases:
            args = dict(job=None if stage.startswith('definition_') else object(),
                stage=stage, payload={}, schema={}, instructions='', config=frozen)
            with patch.object(ai_stages, 'parent_context', side_effect=ReachedParent) as parent:
                with self.assertRaises(ReachedParent):
                    ai_stages.execute_stage(**args, max_output_tokens=tokens, timeout_seconds=timeout)
                parent.assert_called_once()
                for changed in ({'max_output_tokens': tokens+1, 'timeout_seconds': timeout},
                                {'max_output_tokens': tokens, 'timeout_seconds': timeout+1},
                                {'max_output_tokens': tokens, 'timeout_seconds': True},
                                {'max_output_tokens': tokens, 'timeout_seconds': float('nan')},
                                {'max_output_tokens': tokens, 'timeout_seconds': float('inf')}):
                    parent.reset_mock()
                    with self.assertRaises(ai_stages.StageNotSent): ai_stages.execute_stage(**args, **changed)
                    parent.assert_not_called()

    def test_larger_output_does_not_truncate_or_expand_the_input_bound(self):
        payload = {'source': 'x' * 512001}
        before = deepcopy(payload)
        with patch.object(ai_stages, 'parent_context', return_value=(object(), object(), object())), \
                patch.object(ai_stages, '_response') as send, \
                patch.object(ai_stages, 'assert_installed_guards') as database_guard:
            with self.assertRaisesMessage(ai_stages.StageNotSent, 'nothing was truncated or sent'):
                ai_stages.execute_stage(job=object(), stage='extractor', payload=payload,
                    schema={}, instructions='', config=ai_stages.pipeline_config(LIVE))
            send.assert_not_called()
            database_guard.assert_not_called()
        self.assertEqual(payload, before)

    def sdk(self, *, stop='end_turn', timeout=False):
        import httpx
        from anthropic import Anthropic
        sent, retained = [], []
        text = json.dumps({'answer': 'complete synthetic response ' * 1200})
        payload = {'source': 'unchanged synthetic source ' * 1000}
        def handle(request):
            self.assertEqual(request.url.host, 'synthetic-provider.invalid')
            sent.append(json.loads(request.content))
            self.assertEqual(request.extensions['timeout']['read'], 240)
            if timeout: raise httpx.ReadTimeout('offline injected timeout', request=request)
            return httpx.Response(200, headers={'request-id': 'req_synthetic_v2'}, json={
                'id': 'msg_synthetic_v2', 'type': 'message', 'role': 'assistant', 'model': LIVE['model'],
                'content': [{'type': 'text', 'text': text}], 'stop_reason': stop, 'stop_sequence': None,
                'usage': {'input_tokens': 1000, 'output_tokens': 32000}})
        with httpx.Client(transport=httpx.MockTransport(handle)) as http:
            def client(**kwargs):
                self.assertEqual(kwargs, {'timeout': 240, 'max_retries': 0})
                return Anthropic(api_key='synthetic-offline-only', base_url='https://synthetic-provider.invalid',
                                 http_client=http, **kwargs)
            with patch('anthropic.Anthropic', side_effect=client):
                try:
                    result = ai_stages._response(payload, {'type': 'object',
                        'properties': {'answer': {'type': 'string'}}, 'required': ['answer'],
                        'additionalProperties': False}, 'Return the complete answer.',
                        LIVE, 32000, 240, retained.append)
                finally:
                    self.assertEqual(len(sent), 1)
                    self.assertEqual(sent[0]['max_tokens'], 32000)
                    self.assertEqual(sent[0]['model'], LIVE['model'])
                    self.assertEqual(json.loads(sent[0]['messages'][0]['content']), payload)
                    self.assertNotIn('thinking', sent[0])
                    self.assertNotIn('effort', sent[0]['output_config'])
                    self.assertNotIn('temperature', sent[0])
        self.assertEqual(len(retained), 1)
        self.assertEqual(result[-2], text)
        self.assertEqual(result[1], Decimal('0.322'))
        return result

    def test_actual_sdk_preserves_complete_payload_and_adaptive_defaults(self):
        self.assertTrue(self.sdk()[-1])

    def test_actual_sdk_output_limit_is_incomplete_even_for_valid_json(self):
        self.assertFalse(self.sdk(stop='max_tokens')[-1])

    def test_actual_sdk_timeout_is_one_attempt(self):
        from anthropic import APITimeoutError
        with self.assertRaises(APITimeoutError): self.sdk(timeout=True)


@override_settings(WORD_PREPARATION_ENABLED=True, AI_MODE='fixture', TESTING_AUTHORITY_MODE='',
    TESTING_AUTHORITY_ID='', TESTING_AUTHORITY_SHA256='', ADMIN_SITE=False, STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class GenerationCapacityV2DatabaseTests(TestCase):
    setUp = previous.GenerationCapacityDatabaseTests.setUp
    def provider(self):
        """The provider double emits the explicitly selected wire contract."""
        from core import clinical_schema_transport as transport, clinical_evidence_transport as evidence, clinical_node_transport as nodes, clinical_json_transport as document
        original = previous.GenerationCapacityDatabaseTests.provider(self)
        def respond(*args):
            schema, config, callback = args[1], args[3], args[-1]
            if not transport.selected(config):return original(*args)
            emitted = []
            def retain(response):
                dump = response.model_dump
                parsed = dump()['output']
                codec = {transport.TRANSPORT:transport,
                    transport.EVIDENCE_TRANSPORT:evidence,
                    transport.CURRENT_TRANSPORT:nodes,
                    transport.JSON_TRANSPORT:document}[transport.marker(config)]
                text = json.dumps(codec.encode(schema, parsed)); emitted.append(text)
                response.model_dump = lambda **kw: {
                    **{k:v for k,v in dump(**kw).items() if k!='output'},
                    'content':[{'type':'text','text':text}]}
                callback(response)
            result = list(original(*args[:-1], retain))
            self.assertEqual(len(emitted), 1)
            result[-2] = emitted[0]
            return tuple(result)
        return respond
    another_encounter = previous.GenerationCapacityDatabaseTests.another_encounter
    historical_job = previous.GenerationCapacityDatabaseTests.historical_job
    backup_accepts = previous.GenerationCapacityDatabaseTests.backup_accepts
    assert_audit = previous.GenerationCapacityDatabaseTests.assert_audit

    def test_new_v2_and_existing_v1_jobs_keep_their_own_quotes_and_receipts(self):
        for historical in (True, False):
            e = self.another_encounter()
            job = self.historical_job(e, transform=v1, config=LIVE) if historical else enqueue(e, self.user, config=LIVE)
            before = deepcopy(job.config)
            limit, timeout = (16000, 120) if historical else (32000, 240)
            self.assertEqual(Decimal(before['semantic_maximum_cost']), Decimal('7.35' if historical else '8.15'))
            with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'synthetic-offline-only'}), \
                    patch.object(ai_stages, '_response', side_effect=self.provider()) as send:
                self.assertTrue(run_one())
            job.refresh_from_db()
            self.assertEqual(job.state, 'succeeded', job.error)
            self.assertEqual(send.call_count, 3)
            for call, receipt in zip(send.call_args_list, job.ai_stage_receipts.order_by('created_at')):
                self.assertEqual(call.args[4:6], (limit, timeout))
                raw = private_path(receipt.request_path).read_bytes()
                request = json.loads(raw)
                self.assertEqual((request['max_output_tokens'], request['timeout_seconds']), (limit, timeout))
                self.assertEqual(receipt.config, before)
                self.assertEqual(receipt.quote_maximum, ai_stages.quote(before, len(raw), limit))
                from core import clinical_schema_transport as transport, semantic_generation
                result = private_path(receipt.result_path).read_bytes()
                self.assertEqual(hashlib.sha256(result).hexdigest(), receipt.result_sha256)
                content = json.loads(result)['provider_output']['content']
                self.assertEqual(len(content), 1)
                text = content[0]['text']
                self.assertEqual(json.loads(text)['transport'], before[transport.CONFIG_KEY])
                self.assertEqual(transport.response_value(text, request, config=before,
                    provider=receipt.provider, simulated=receipt.simulated),
                    semantic_generation.fixture_stage(receipt.stage, request['payload']))
            self.assertEqual(job.config, before)
            self.assertTrue(self.backup_accepts(job, before))
            self.assert_audit()
            self.assertEqual(enqueue(e, self.user, config=LIVE, require_current_generation_quote=True).pk, job.pk)
            self.assertFalse(run_one())
            if not historical:
                for key, value in [('provider', 'openai'), ('model', 'unreviewed'),
                    ('semantic_output_token_limit', True), ('semantic_output_token_limit', '32000'),
                    ('semantic_output_token_limit', 32000.0), ('semantic_output_token_limit', 16000),
                    ('semantic_timeout_seconds', '240'), ('semantic_timeout_seconds', 240.0),
                    ('semantic_timeout_seconds', 120), ('semantic_capacity_profile', 'unknown')]:
                    with self.subTest(key=key, value=value):
                        self.assertFalse(self.backup_accepts(job, {**before, key: value}))

    def test_page_quote_reserves_v2_and_old_v1_quote_cannot_buy_it(self):
        self.client.force_login(self.user)
        with override_settings(AI_MODE='live', AI_PROVIDER='anthropic', AI_MODEL=LIVE['model'],
                               AI_INPUT_RATE='2', AI_CACHED_RATE='0.20', AI_OUTPUT_RATE='10'):
            response = self.client.get(f'/encounters/{self.encounter.pk}/')
        self.assertEqual(response.status_code, 200)
        token = response.context['usage_quote']
        quoted = signing.loads(token, salt='usage-quote')
        self.assertEqual(quoted['generation_config']['semantic_capacity_profile'], 'bounded-output-32k-v2')
        self.assertEqual(response.context['generation_max_charge'], Decimal('12.225'))
        old_token = signing.dumps({**quoted, 'generation_config': v1(quoted['generation_config'])}, salt='usage-quote')
        refused = self.client.post(f'/encounters/{self.encounter.pk}/generate/',
            {'usage_quote': old_token}, HTTP_ACCEPT='application/json')
        self.assertEqual(refused.status_code, 409)
        self.assertFalse(Job.objects.filter(encounter=self.encounter).exists())
        accepted = self.client.post(f'/encounters/{self.encounter.pk}/generate/',
            {'usage_quote': token}, HTTP_ACCEPT='application/json')
        self.assertEqual(accepted.status_code, 200, accepted.content)
        job = Job.objects.get(encounter=self.encounter)
        self.assertEqual(Decimal(job.config['semantic_maximum_cost']), Decimal('8.15'))
        self.assertEqual(sum(Reservation.objects.filter(job=job).values_list('amount', flat=True)), Decimal('12.225'))

    def test_truncation_retains_cost_and_raw_response_without_retry_or_answers(self):
        for valid_json in (False, True):
            e = self.another_encounter()
            job = enqueue(e, self.user, config=LIVE)
            text = '{"facts":[]}' if valid_json else '{"facts":[{"unfinished":"'
            def incomplete(payload, schema, instructions, config, maximum, timeout, on_response):
                from core import generation
                self.assertEqual((maximum, timeout), (32000, 240))
                response = SimpleNamespace(id='msg_capacity_'+str(valid_json), _request_id='req_capacity_'+str(valid_json),
                    model=LIVE['model'], model_dump=lambda **kw: {'id':'msg_capacity_'+str(valid_json),
                        'content':[{'type':'text','text':text}], 'stop_reason':'max_tokens',
                        'usage':{'input_tokens':1000,'output_tokens':32000}})
                on_response(response)
                rates = generation.cost_rates(generation.rates(config), Decimal('0.322'), Decimal('0'))
                return response, Decimal('0.322'), {'input_tokens':1000,'cached_input_tokens':0,
                    'cache_creation_tokens':0,'output_tokens':32000}, rates, text, False
            with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'synthetic-offline-only'}), \
                    patch.object(ai_stages, '_response', side_effect=incomplete) as send:
                self.assertTrue(run_one()); self.assertFalse(run_one())
            job.refresh_from_db(); e.refresh_from_db()
            self.assertEqual(job.state, 'failed', job.error)
            self.assertEqual(send.call_count, 1)
            receipt = job.ai_stage_receipts.get()
            self.assertEqual(receipt.error_code, 'invalid_response')
            raw = private_path(receipt.result_path).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), receipt.result_sha256)
            self.assertEqual(json.loads(raw)['provider_output']['content'][0]['text'], text)
            self.assertEqual(Usage.objects.get(job=job).actual_cost, Decimal('0.322'))
            self.assertTrue(ProviderReceipt.objects.filter(job=job).exists())
            self.assertEqual(sum(LedgerEntry.objects.filter(job=job).values_list('amount', flat=True)), 0)
            self.assertEqual(PlatformCost.objects.get(job=job).amount, Decimal('0.322'))
            self.assertEqual(e.answers, {})
            self.assertTrue(self.backup_accepts(job, job.config))
            self.assert_audit()
            self.assertEqual(enqueue(e, self.user, config=LIVE).pk, job.pk)
            self.assertFalse(run_one())

    def test_bad_frozen_v2_profile_quote_and_call_limit_refuse_before_send(self):
        for key, value in [('semantic_maximum_cost', '7.35000000000'), ('semantic_max_calls', 6),
                           ('semantic_output_token_limit', 32000.0), ('semantic_timeout_seconds', 241),
                           ('provider', 'openai'), ('model', 'unreviewed')]:
            e = self.another_encounter()
            with patch('core.jobs.generation_maximum', return_value=Decimal('0')):
                job = self.historical_job(e, transform=lambda cfg: {**cfg, key: value}, config=LIVE)
            with self.subTest(key=key, value=value), patch.object(ai_stages, '_response') as send:
                self.assertTrue(run_one())
                send.assert_not_called()
            job.refresh_from_db(); e.refresh_from_db()
            self.assertEqual(job.state, 'failed', job.error)
            self.assertFalse(job.ai_stage_receipts.exists())
            self.assertFalse(Usage.objects.filter(job=job).exists())
            self.assertFalse(ProviderReceipt.objects.filter(job=job).exists())
            self.assertEqual(e.answers, {})

    def test_v2_stale_timeout_grace_is_finite_and_never_resends(self):
        job = enqueue(self.encounter, self.user, config=LIVE)
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'synthetic-offline-only'}), \
                patch.object(ai_stages, '_response', side_effect=SystemExit('offline interrupted worker')):
            with self.assertRaises(SystemExit): run_one()
        activity = job.ai_stage_receipts.get().started_at
        Job.objects.filter(pk=job.pk).update(started_at=activity-timedelta(minutes=10))
        with patch('core.jobs.timezone.now', return_value=activity+timedelta(seconds=299)): mark_stale()
        job.refresh_from_db(); self.assertEqual(job.state, 'running')
        with patch('core.jobs.timezone.now', return_value=activity+timedelta(seconds=301)): mark_stale()
        job.refresh_from_db(); self.assertEqual(job.state, 'reconciliation')
        self.assertTrue(Reservation.objects.filter(job=job, state='held').exists())
        self.assertFalse(run_one())
