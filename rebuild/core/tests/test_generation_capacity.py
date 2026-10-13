"""Prospective capacity, old quotes, retained failures; no external provider calls."""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
import hashlib
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from core import ai_stages, generation
from core.jobs import enqueue, generation_maximum, mark_stale, run_one
from core.models import Encounter, Job, LedgerEntry, PlatformCost, ProviderReceipt, Reservation, Usage, Wallet
from core.security import private_path
from core.tests.test_ai_stages import IndependentStageTests


LIVE = {'mode': 'live', 'provider': 'anthropic', 'model': 'synthetic-model',
        'input_rate': '2', 'cached_rate': '0.20', 'output_rate': '10'}


def legacy(config):
    config = deepcopy(config)
    config.pop('semantic_capacity_profile', None)
    config.pop('semantic_timeout_seconds', None)
    config['semantic_output_token_limit'] = 4000
    config['semantic_maximum_cost'] = str(ai_stages.maximum_cost(config))
    return config


class GenerationCapacityPureTests(SimpleTestCase):
    def test_prospective_quote_and_historical_quote_are_distinct_and_input_is_unchanged(self):
        before = deepcopy(LIVE)
        current = ai_stages.pipeline_config(LIVE)
        self.assertEqual(ai_stages.generation_limits(current), (16000, 120))
        self.assertEqual(ai_stages.generation_limits(LIVE), (4000, 60))
        self.assertEqual(ai_stages.maximum_cost(LIVE), Decimal('6.75'))
        self.assertEqual(ai_stages.maximum_cost(current), Decimal('7.35'))
        self.assertEqual(Decimal(current['semantic_maximum_cost']), Decimal('7.35'))
        self.assertEqual(LIVE, before)
        self.assertEqual(Decimal(ai_stages.definition_pipeline_config(LIVE)['definition_maximum_cost']), Decimal('2.94'))
        self.assertEqual(ai_stages.definition_pipeline_config(LIVE)['definition_max_calls'], 2)
        with patch('core.jobs.generation.configuration', return_value=LIVE), \
                patch('core.word_contract.require_generation', return_value={'field': {}}):
            encounter = SimpleNamespace(template_version=object())
            self.assertEqual(generation_maximum(encounter), Decimal('7.35'))
            self.assertEqual(generation_maximum(encounter, LIVE), Decimal('6.75'))

    def test_bad_markers_and_typed_limits_refuse_instead_of_selecting_legacy(self):
        config = ai_stages.pipeline_config(LIVE)
        for key, values in (
            ('semantic_capacity_profile', (None, False, 0, '', 'unknown')),
            ('semantic_output_token_limit', (None, True, 4000, 16000.0, '16000', 16001)),
            ('semantic_timeout_seconds', (None, True, 60, 120.0, '120', 121))):
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ai_stages.StageNotSent):
                    ai_stages.maximum_cost({**config, key: value})
        with self.assertRaises(ai_stages.StageNotSent):
            ai_stages.maximum_cost({**LIVE, 'semantic_timeout_seconds': 120})

    def test_real_sdk_sends_finite_limit_timeout_and_never_retries(self):
        import httpx
        from anthropic import Anthropic
        sent = []
        retained = []
        def handle(request):
            self.assertEqual(request.url.host, 'synthetic-provider.invalid')
            sent.append(json.loads(request.content))
            self.assertEqual(request.extensions['timeout']['read'], 120)
            return httpx.Response(200, headers={'request-id': 'req_synthetic'}, json={
                'id': 'msg_synthetic', 'type': 'message', 'role': 'assistant', 'model': 'synthetic-model',
                'content': [{'type': 'text', 'text': '{"answer":"ok"}'}],
                'stop_reason': 'end_turn', 'stop_sequence': None,
                'usage': {'input_tokens': 1000, 'output_tokens': 16000}})
        with httpx.Client(transport=httpx.MockTransport(handle)) as http:
            def client(**kwargs):
                self.assertEqual(kwargs, {'timeout': 120, 'max_retries': 0})
                return Anthropic(api_key='synthetic-offline-only', base_url='https://synthetic-provider.invalid',
                                 http_client=http, **kwargs)
            with patch('anthropic.Anthropic', side_effect=client):
                result = ai_stages._response({}, {'type': 'object', 'properties': {'answer': {'type': 'string'}},
                    'required': ['answer'], 'additionalProperties': False}, 'Return an answer.',
                    LIVE, 16000, 120, retained.append)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]['max_tokens'], 16000)
        self.assertEqual(len(retained), 1)
        self.assertTrue(result[-1])
        self.assertEqual(result[1], Decimal('0.162'))


@override_settings(WORD_PREPARATION_ENABLED=True, AI_MODE='fixture', TESTING_AUTHORITY_MODE='',
    TESTING_AUTHORITY_ID='', TESTING_AUTHORITY_SHA256='', ADMIN_SITE=False, STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class GenerationCapacityDatabaseTests(TestCase):
    assert_audit = IndependentStageTests.assert_audit

    def setUp(self):
        IndependentStageTests.setUp(self)
        from core.tests.test_billing_policy import fund
        fund(Wallet.objects.get(user=self.user, kind='paid'), Decimal('100'), 'payment:capacity-fixture')
        self.provider_number = 0

    def provider(self):
        self.provider_number += 1
        prefix = str(self.provider_number)+'_'
        respond = IndependentStageTests.provider(self)
        def unique(*args):
            callback = args[-1]
            def retain(response):
                response.id = prefix+response.id
                response._request_id = prefix+response._request_id
                original_dump = response.model_dump
                response.model_dump = lambda **kwargs: {**original_dump(**kwargs), 'id': response.id}
                callback(response)
            result = list(respond(*args[:-1], retain))
            config = args[3]
            list_cost = Decimal('10')*generation.rates(config)['input_per_million']/1000000
            discount = generation.discount_rate(config)
            result[1] = generation.discounted_cost(list_cost, discount)
            result[3] = generation.cost_rates(generation.rates(config), list_cost, discount)
            return tuple(result)
        return unique

    def another_encounter(self):
        return Encounter.objects.create(department=self.department, patient=self.encounter.patient,
            template_version=self.version, created_by=self.user,
            service_date=self.encounter.service_date, notes=self.encounter.notes)

    def historical_job(self, encounter=None, transform=legacy, config=None):
        create = Job.objects.create
        def insert(**values):
            values['config'] = transform(values['config'])
            return create(**values)
        with patch('core.jobs.Job.objects.create', side_effect=insert):
            return enqueue(encounter or self.encounter, self.user, config=config)

    def test_new_job_and_old_job_use_their_own_transport_quote_and_immutable_receipts(self):
        for historical in (True, False):
            e = self.another_encounter()
            job = self.historical_job(e, config=LIVE) if historical else enqueue(e, self.user, config=LIVE)
            before = deepcopy(job.config)
            expected_limit, expected_timeout = (4000, 60) if historical else (16000, 120)
            self.assertEqual(Decimal(job.config['semantic_maximum_cost']), Decimal('6.75' if historical else '7.35'))
            with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'synthetic-offline-only'}), \
                    patch.object(ai_stages, '_response', side_effect=self.provider()) as send:
                self.assertTrue(run_one())
            job.refresh_from_db()
            self.assertEqual(job.state, 'succeeded', job.error)
            self.assertEqual(len(send.call_args_list), 3)
            for call, receipt in zip(send.call_args_list, job.ai_stage_receipts.order_by('created_at')):
                self.assertEqual(call.args[4:6], (expected_limit, expected_timeout))
                request = json.loads(private_path(receipt.request_path).read_bytes())
                self.assertEqual(request['max_output_tokens'], expected_limit)
                if historical:
                    self.assertNotIn('timeout_seconds', request)
                else:
                    self.assertEqual(request['timeout_seconds'], expected_timeout)
                self.assertEqual(receipt.config, before)
                raw = private_path(receipt.request_path).read_bytes()
                self.assertEqual(receipt.quote_maximum, ai_stages.quote(job.config, len(raw), expected_limit))
            self.assertEqual(job.config, before)
            self.assertTrue(self.backup_accepts(job, before))
            invalid = [('semantic_capacity_profile', value) for value in (None, False, '', 'unknown')]
            if historical:
                invalid += [('semantic_timeout_seconds', 120), ('semantic_output_token_limit', 16000)]
            else:
                invalid += [('semantic_output_token_limit', value) for value in (4000, '16000', 16000.0)]
                invalid += [('semantic_timeout_seconds', value) for value in (60, '120', 120.0)]
            for key, value in invalid:
                with self.subTest(historical=historical, key=key, value=value):
                    self.assertFalse(self.backup_accepts(job, {**before, key: value}))
            self.assertEqual(enqueue(e, self.user, config=LIVE, require_current_generation_quote=True).pk, job.pk)
            self.assertFalse(run_one())
            with self.assertRaises(DatabaseError), transaction.atomic():
                Job.objects.filter(pk=job.pk).update(config={**before, 'semantic_output_token_limit': 32000})

    def backup_accepts(self, job, config):
        """Feed a changed snapshot to the actual reader; retained rows stay immutable."""
        from ops.backup_restore import _SEMANTIC_STAGE_TOTAL_VALID
        sql = '''WITH core_job AS (
            SELECT (jsonb_populate_record(NULL::public.core_job,to_jsonb(original)||%s::jsonb)).*
            FROM public.core_job original), core_aistagereceipt AS (
            SELECT (jsonb_populate_record(NULL::public.core_aistagereceipt,to_jsonb(original)||%s::jsonb)).*
            FROM public.core_aistagereceipt original)
            SELECT (''' + _SEMANTIC_STAGE_TOTAL_VALID + ''') IS TRUE
            FROM core_usage u JOIN core_job j ON j.id=u.job_id
            JOIN core_encounter e ON e.id=j.encounter_id WHERE j.id=%s'''
        override = json.dumps({'config': config})
        with connection.cursor() as cursor:
            cursor.execute(sql, [override, override, job.pk])
            rows = cursor.fetchall()
        self.assertEqual(len(rows), 1)
        return rows[0][0]

    def test_signed_page_displays_exact_current_quote_and_old_page_cannot_buy_larger_request(self):
        self.client.force_login(self.user)
        with override_settings(AI_MODE='live', AI_PROVIDER='anthropic', AI_MODEL='synthetic-model',
                               AI_INPUT_RATE='2', AI_CACHED_RATE='0.20', AI_OUTPUT_RATE='10'):
            response = self.client.get(f'/encounters/{self.encounter.pk}/')
        self.assertEqual(response.status_code, 200)
        token = response.context['usage_quote']
        quoted = signing.loads(token, salt='usage-quote')
        self.assertEqual(quoted['generation_config']['semantic_output_token_limit'], 16000)
        self.assertEqual(response.context['generation_max_charge'], Decimal('11.025'))
        # The same page authorizes voice separately: its configuration must not
        # acquire a generation stage contract and fail transcription accounting.
        from core.views import usage_quote
        request = RequestFactory().post('/', {'usage_quote': token})
        request.user = self.user
        voice_config = usage_quote(request, self.encounter)
        self.assertEqual(voice_config, quoted['config'])
        self.assertFalse(any(key.startswith('semantic_') for key in voice_config))
        self.assertEqual(usage_quote(request, self.encounter, generation_request=True), quoted['generation_config'])
        old = {key: value for key, value in quoted.items() if key != 'generation_config'}
        old_token = signing.dumps(old, salt='usage-quote')
        refused = self.client.post(f'/encounters/{self.encounter.pk}/generate/',
            {'usage_quote': old_token}, HTTP_ACCEPT='application/json')
        self.assertEqual(refused.status_code, 409)
        self.assertIn('Reload', refused.json()['error'])
        self.assertFalse(Job.objects.filter(encounter=self.encounter).exists())
        accepted = self.client.post(f'/encounters/{self.encounter.pk}/generate/',
            {'usage_quote': token}, HTTP_ACCEPT='application/json')
        self.assertEqual(accepted.status_code, 200, accepted.content)
        job = Job.objects.get(encounter=self.encounter)
        self.assertEqual(Decimal(job.config['semantic_maximum_cost']), Decimal('7.35'))
        self.assertEqual(sum(Reservation.objects.filter(job=job).values_list('amount', flat=True)), Decimal('11.025'))
        # An old page replay observes this exact attempt rather than upgrading or refusing it.
        replay = self.client.post(f'/encounters/{self.encounter.pk}/generate/',
            {'usage_quote': old_token}, HTTP_ACCEPT='application/json')
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.json()['reused'])
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(), 1)

    def test_bad_frozen_profile_limit_and_cost_fail_before_receipt_or_send(self):
        cases = [('semantic_capacity_profile', x) for x in (None, False, '', 'unknown')]
        cases += [('semantic_output_token_limit', 4000), ('semantic_timeout_seconds', 60),
                  ('semantic_maximum_cost', '1')]
        for key, value in cases:
            e = self.another_encounter()
            # Model the historic immutable row at insertion; never edit a retained config.
            with patch('core.jobs.generation_maximum', return_value=Decimal('0')):
                job = self.historical_job(e, transform=lambda cfg: {**cfg, key: value})
            with self.subTest(key=key, value=value), patch.object(ai_stages, '_response') as send:
                self.assertTrue(run_one())
                send.assert_not_called()
                job.refresh_from_db(); e.refresh_from_db()
                self.assertEqual(job.state, 'failed', job.error)
                self.assertFalse(job.ai_stage_receipts.exists())
                self.assertFalse(Usage.objects.filter(job=job).exists())
                self.assertFalse(ProviderReceipt.objects.filter(job=job).exists())
                self.assertEqual(e.answers, {})

    def test_output_exhaustion_even_with_valid_json_remains_failed_retained_and_unbilled(self):
        for valid_json in (False, True):
            e = self.another_encounter()
            job = enqueue(e, self.user, config=LIVE)
            respond = self.provider()
            def incomplete(*args):
                result = list(respond(*args))
                result[-1] = False
                if not valid_json:result[-2] = '{"unfinished":"'
                return tuple(result)
            with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'synthetic-offline-only'}), \
                    patch.object(ai_stages, '_response', side_effect=incomplete) as send:
                self.assertTrue(run_one()); self.assertFalse(run_one())
            job.refresh_from_db(); e.refresh_from_db()
            self.assertEqual(job.state, 'failed', job.error)
            self.assertEqual(send.call_count, 1)
            receipt = job.ai_stage_receipts.get()
            self.assertEqual(receipt.error_code, 'invalid_response')
            self.assertEqual(hashlib.sha256(private_path(receipt.result_path).read_bytes()).hexdigest(), receipt.result_sha256)
            # Ordinary billing preserves the original usage and offsets its
            # debit with an absorption credit; the net account charge is zero.
            self.assertEqual(sum(LedgerEntry.objects.filter(job=job).values_list('amount', flat=True)), 0)
            self.assertEqual(PlatformCost.objects.get(job=job).amount, receipt.actual_cost)
            self.assertEqual(e.answers, {})
            self.assertEqual(enqueue(e, self.user).pk, job.pk)
            self.assertFalse(run_one())

    def test_stale_stage_grace_changes_only_for_new_profile_and_never_retries(self):
        for historical in (True, False):
            e = self.another_encounter()
            job = self.historical_job(e, config=LIVE) if historical else enqueue(e, self.user, config=LIVE)
            with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'synthetic-offline-only'}), \
                    patch.object(ai_stages, '_response', side_effect=SystemExit('offline interrupted worker')):
                with self.assertRaises(SystemExit):run_one()
            activity = job.ai_stage_receipts.get().started_at
            Job.objects.filter(pk=job.pk).update(started_at=activity-timedelta(minutes=10))
            with patch('core.jobs.timezone.now', return_value=activity+timedelta(seconds=121)):
                mark_stale()
            job.refresh_from_db()
            self.assertEqual(job.state, 'reconciliation' if historical else 'running')
            with patch('core.jobs.timezone.now', return_value=activity+timedelta(seconds=181)):
                mark_stale()
            job.refresh_from_db()
            self.assertEqual(job.state, 'reconciliation')
            self.assertTrue(Reservation.objects.filter(job=job, state='held').exists())
            self.assertFalse(run_one())
