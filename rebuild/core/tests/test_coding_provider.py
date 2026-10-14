"""Offline provider boundaries; no actual credentials, transport or database."""
from contextlib import contextmanager, nullcontext
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase, override_settings
from pydantic import BaseModel, ConfigDict

from core import coding_provider as provider


class Answer(BaseModel):
    model_config = ConfigDict(extra='forbid')
    value: str


BASE = {'mode': 'live', 'provider': 'anthropic', 'model': 'synthetic-model',
        'input_rate': '1', 'cached_rate': '0.1', 'output_rate': '2',
        'discount_rate': '0', 'pricing_version': 'synthetic-configured-rates'}


class MemoryRun(SimpleNamespace):
    objects = None

    def save(self, update_fields):
        self.saves.append({key: deepcopy(getattr(self, key)) for key in update_fields})


@override_settings(AI_MODE='live', AI_PROVIDER='anthropic', AI_MODEL='synthetic-model', SYNTHETIC_ONLY=True)
class CodingProviderTests(SimpleTestCase):
    def setUp(self):
        self.patches = [patch.object(provider.generation, 'configuration', return_value=deepcopy(BASE)),
                        patch('core.security.membership'),
                        patch.object(provider.transaction, 'atomic', side_effect=lambda: nullcontext()),
                        patch.object(provider, '_provider_slot', side_effect=lambda cfg: nullcontext()),
                        patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'offline-test-placeholder'})]
        self.mocks = [item.start() for item in self.patches]
        for item in self.patches:
            self.addCleanup(item.stop)
        actor_id, department_id = next(iter(provider.testing_authority.ACTORS.items()))
        actor = SimpleNamespace(pk=actor_id, is_active=True)
        encounter = SimpleNamespace(pk='synthetic-encounter', department_id=department_id, created_by_id=actor_id)
        inputs, context, releases = {'notes': 'Synthetic source.'}, {}, []
        self.run = MemoryRun(pk='synthetic-run', user=actor, user_id=actor_id, encounter=encounter,
            encounter_id=encounter.pk, inputs=inputs, context=context, releases=releases,
            input_digest=provider.digest({'inputs': inputs, 'context': context, 'releases': releases}),
            config=provider.configuration(actor, encounter), requests=[], actual_cost=None, state='running', saves=[])
        manager = Mock()
        manager.select_for_update.return_value.select_related.return_value.get.return_value = self.run
        manager.exclude.return_value.filter.return_value.exists.return_value = False
        MemoryRun.objects = manager
        self.sequence = 0

    def transport(self, change=None, text='{"value":"documented"}', complete=True):
        def response(payload, schema, instructions, config, maximum, timeout, on_response):
            self.sequence += 1
            entry = self.run.requests[-1]
            self.assertEqual(entry['state'], 'sending')
            self.assertTrue(entry['sent'])
            self.assertEqual(entry['request_sha256'], provider.digest(entry['envelope']))
            raw = {'id': 'synthetic-resource-' + str(self.sequence), 'model': BASE['model'],
                   'usage': {'input_tokens': 100, 'cache_read_input_tokens': 0,
                             'cache_creation_input_tokens': 0, 'output_tokens': 10}}
            if change:
                change(raw)
            obj = SimpleNamespace(id=raw['id'], _request_id='synthetic-request-' + str(self.sequence),
                                  model=raw['model'], model_dump=lambda **kwargs: deepcopy(raw))
            on_response(obj)
            # Accounting uses the retained raw response, not these untrusted aliases.
            return obj, Decimal('999'), {}, {}, text, complete
        return response

    def call(self, stage='concepts', **kwargs):
        return provider.execute(self.run, stage, kwargs.get('payload', {'source': 'Synthetic source.'}),
                                kwargs.get('schema', Answer), kwargs.get('instructions', 'Extract only documented concepts.'))

    def test_two_distinct_stages_preserve_raw_cost_and_never_create_clinical_jobs(self):
        with patch.object(provider.ai_stages, '_response', side_effect=self.transport()) as send:
            self.assertEqual(self.call(), {'value': 'documented'})
            self.assertEqual(self.call('resolution'), {'value': 'documented'})
            self.assertEqual(send.call_count, 2)
            with self.assertRaises(provider.CodingNotSent):
                self.call('resolution')
        self.assertEqual(self.run.actual_cost, Decimal('0.000240'))
        self.assertEqual(self.run.state, 'running')
        self.assertEqual([row['state'] for row in self.run.requests], ['succeeded', 'succeeded'])
        for row in self.run.requests:
            self.assertEqual(row['response_sha256'], provider.digest(row['raw_response']))
            self.assertEqual(row['actual_cost'], '0.00012')
        received = [save['requests'][-1] for save in self.run.saves if 'requests' in save]
        self.assertTrue(any(row['raw_response'] is not None and row['actual_cost'] is None for row in received))

    def test_uncertain_second_send_preserves_first_cost_and_null_aggregate(self):
        with patch.object(provider.ai_stages, '_response', side_effect=self.transport()):
            self.call()
        with patch.object(provider.ai_stages, '_response', side_effect=TimeoutError('offline')) as send:
            with self.assertRaises(provider.CodingUnknown):
                self.call('resolution')
            with self.assertRaises(provider.CodingNotSent):
                self.call('resolution')
            self.assertEqual(send.call_count, 1)
        self.assertEqual(self.run.requests[0]['actual_cost'], '0.00012')
        self.assertEqual(self.run.requests[1]['state'], 'unknown')
        self.assertIsNone(self.run.actual_cost)

    def test_raw_boolean_float_negative_and_nested_cache_are_not_integer_usage(self):
        changes = [lambda raw: raw['usage'].update(cache_read_input_tokens=False),
                   lambda raw: raw['usage'].update(input_tokens=100.0),
                   lambda raw: raw['usage'].update(output_tokens=-1),
                   lambda raw: raw['usage'].update(cache_creation={'ephemeral_5m_input_tokens': False, 'ephemeral_1h_input_tokens': 0})]
        for change in changes:
            with self.subTest(change=change):
                self.run.requests = []
                self.run.actual_cost = None
                with patch.object(provider.ai_stages, '_response', side_effect=self.transport(change)):
                    with self.assertRaises(provider.CodingUnknown):
                        self.call()
                self.assertIsNotNone(self.run.requests[0]['raw_response'])
                self.assertIsNone(self.run.actual_cost)
                self.assertEqual(self.run.requests[0]['state'], 'unknown')

    def test_invalid_schema_result_keeps_known_cost_without_resend(self):
        for text, complete in [('{"value":8}', True), ('{"value":"a","extra":1}', True),
                               ('{"value":"a","value":"b"}', True), ('{}', False)]:
            with self.subTest(text=text):
                self.run.requests = []
                with patch.object(provider.ai_stages, '_response', side_effect=self.transport(text=text, complete=complete)):
                    with self.assertRaises(provider.CodingFailure):
                        self.call()
                self.assertEqual(self.run.actual_cost, Decimal('0.00012'))
                self.assertEqual(self.run.requests[0]['state'], 'failed')

    def test_wrong_stage_changed_snapshot_configuration_and_oversize_refuse_before_send(self):
        with patch.object(provider.ai_stages, '_response') as send:
            with self.assertRaises(provider.CodingNotSent):
                self.call('resolution')
            with self.assertRaises(provider.CodingNotSent):
                self.call('invented')
            with self.assertRaises(provider.CodingNotSent):
                self.call(payload={'text': 'x' * provider.MAX_REQUEST_BYTES})
            with self.assertRaises(provider.CodingNotSent):
                self.call(schema={'type': 'object'})
            self.run.inputs['notes'] = 'Changed source.'
            with self.assertRaises(provider.CodingNotSent):
                self.call()
            self.run.inputs['notes'] = 'Synthetic source.'
            self.run.config['model'] = 'other'
            with self.assertRaises(provider.CodingNotSent):
                self.call()
            send.assert_not_called()
        self.assertEqual(self.run.requests, [])

    def test_unsent_credential_refusal_is_retained_and_not_retried(self):
        with patch.dict('os.environ', {}, clear=True), patch.object(provider.ai_stages, '_response') as send:
            with self.assertRaises(provider.CodingNotSent):
                self.call()
            with self.assertRaises(provider.CodingNotSent):
                self.call()
            send.assert_not_called()
        self.assertEqual(self.run.requests[0]['state'], 'not_sent')
        self.assertFalse(self.run.requests[0]['sent'])
        self.assertEqual(self.run.actual_cost, 0)

    def test_identity_replay_from_another_run_is_retained_as_unknown(self):
        MemoryRun.objects.exclude.return_value.filter.return_value.exists.return_value = True
        with patch.object(provider.ai_stages, '_response', side_effect=self.transport()):
            with self.assertRaises(provider.CodingUnknown):
                self.call()
        self.assertIsNotNone(self.run.requests[0]['raw_response'])
        self.assertIsNone(self.run.actual_cost)

    def test_transport_uses_frozen_envelope_even_if_callers_payload_changes(self):
        payload = {'source': 'Synthetic source.'}
        @contextmanager
        def slot(config):
            payload['source'] = 'Mutated caller object'
            yield
        response = self.transport()
        def inspect(sent_payload, *args):
            self.assertEqual(sent_payload, {'source': 'Synthetic source.'})
            return response(sent_payload, *args)
        with patch.object(provider, '_provider_slot', side_effect=slot), patch.object(provider.ai_stages, '_response', side_effect=inspect):
            self.call(payload=payload)

    def test_actor_provider_and_finite_prices_rechecked_without_new_authority_purpose(self):
        for changes in ({'provider': 'invented'}, {'model': 'other'}, {'input_rate': 'Infinity'},
                        {'output_rate': '-1'}, {'cached_rate': True}, {'discount_rate': 'NaN'}):
            with self.subTest(changes=changes), patch.object(provider.generation, 'configuration', return_value={**BASE, **changes}):
                with self.assertRaises(ValidationError):
                    provider.configuration(self.run.user, self.run.encounter)
        with override_settings(SYNTHETIC_ONLY=False), self.assertRaises(ValidationError):
            provider.configuration(self.run.user, self.run.encounter)
        self.assertFalse(provider.testing_authority.KEYS.intersection(self.run.config))
        self.assertEqual(self.run.config['coding_authority_id'], provider.AUTHORITY_ID)

    def test_explicit_fixture_isolated_from_provider_and_zero_cost(self):
        base = {**BASE, 'mode': 'fixture'}
        db = SimpleNamespace(vendor='sqlite', settings_dict={'NAME': ':memory:'})
        with patch.object(provider.generation, 'configuration', return_value=base), patch.object(provider, 'connection', db):
            with self.assertRaises(provider.CodingNotSent):
                provider.configuration(self.run.user, self.run.encounter)
            with override_settings(CODING_ALLOW_TEST_FIXTURES=True,
                                   CODING_FIXTURE_RESPONSES={'concepts': {'value': 'fixture'}, 'resolution': {'value': 'fixture'}}):
                self.run.config = provider.configuration(self.run.user, self.run.encounter)
                with patch.object(provider.ai_stages, '_response') as send:
                    self.assertEqual(self.call(), {'value': 'fixture'})
                    send.assert_not_called()
                self.assertEqual(self.run.actual_cost, 0)
                self.assertTrue(self.run.requests[0]['simulated'])
                self.assertFalse(self.run.requests[0]['sent'])


@override_settings(AI_MODE='live', AI_PROVIDER='anthropic', AI_MODEL='synthetic-model', SYNTHETIC_ONLY=True)
class CodingAdmissionScopeTests(SimpleTestCase):
    """Only the new coding purpose admits existing records in the enrolled scope."""
    def setUp(self):
        from core.models import Membership
        self.actor_id = next(actor for actor, enrollment in provider.testing_authority.ACTOR_ENROLLMENTS.items()
                             if enrollment == 'quillmd-cedar-clinician-20261013-v1')
        self.department_id = provider.testing_authority.ACTORS[self.actor_id]
        owner_id = next(actor for actor, department in provider.testing_authority.ACTORS.items()
                        if department == self.department_id and actor not in provider.testing_authority.ACTOR_ENROLLMENTS)
        self.actor = SimpleNamespace(pk=self.actor_id, is_active=True, verified_at=True)
        self.encounter = SimpleNamespace(pk='existing-synthetic-owner-encounter', department_id=self.department_id,
            created_by_id=owner_id, status='finalized', notes='SYNTHETIC existing owner document.')
        self.memberships = Mock()
        self.memberships.filter.return_value.first.return_value = SimpleNamespace(role='clinician')
        for target in [patch.object(Membership, 'objects', self.memberships),
                       patch.object(provider.generation, 'configuration', return_value=deepcopy(BASE))]:
            target.start(); self.addCleanup(target.stop)

    def test_enrolled_clinician_can_code_existing_owner_record_without_changing_clinical_authority(self):
        before = deepcopy(vars(self.encounter))
        actors = deepcopy(provider.testing_authority.ACTORS)
        enrollments = deepcopy(provider.testing_authority.ACTOR_ENROLLMENTS)
        with self.assertRaises(ValidationError):
            provider.testing_authority.admit_encounter(self.actor, self.encounter)
        config = provider.configuration(self.actor, self.encounter)
        self.assertEqual(config['coding_encounter_scope'], 'authorized_department_existing_synthetic')
        self.assertEqual(config['coding_authority_id'], provider.AUTHORITY_ID)
        self.assertEqual(config['actor_enrollment'], enrollments[self.actor_id])
        self.assertEqual(config['department_id'], self.department_id)
        self.assertEqual(config['account_charged_usd'], '0')
        self.assertEqual(vars(self.encounter), before)
        self.assertEqual(provider.testing_authority.ACTORS, actors)
        self.assertEqual(provider.testing_authority.ACTOR_ENROLLMENTS, enrollments)
        with self.assertRaises(ValidationError):
            provider.testing_authority.admit_encounter(self.actor, self.encounter)
        self.assertEqual(self.memberships.filter.call_args.kwargs, {
            'user': self.actor, 'department': self.department_id, 'active': True,
            'user__is_active': True, 'user__verified_at__isnull': False})

    def test_new_coding_scope_does_not_admit_foreign_departments_or_unenrolled_actors(self):
        self.encounter.department_id = 'foreign-synthetic-department'
        with self.assertRaises(ValidationError):
            provider.configuration(self.actor, self.encounter)
        self.encounter.department_id = self.department_id
        self.actor.pk = 'unenrolled-synthetic-actor'
        with self.assertRaises(ValidationError):
            provider.configuration(self.actor, self.encounter)

    def test_manager_assistant_inactive_unverified_and_revoked_membership_refuse(self):
        for role in ('manager', 'assistant'):
            with self.subTest(role=role):
                self.memberships.filter.return_value.first.return_value = SimpleNamespace(role=role)
                with self.assertRaises(PermissionDenied):
                    provider.configuration(self.actor, self.encounter)
        self.memberships.filter.return_value.first.return_value = SimpleNamespace(role='clinician')
        self.actor.is_active = False
        with self.assertRaises(ValidationError):
            provider.configuration(self.actor, self.encounter)
        self.actor.is_active = True
        self.actor.verified_at = None
        with self.assertRaises(PermissionDenied):
            provider.configuration(self.actor, self.encounter)
        self.actor.verified_at = True
        self.memberships.filter.return_value.first.return_value = None
        with self.assertRaises(PermissionDenied):
            provider.configuration(self.actor, self.encounter)

    def test_new_scope_still_requires_the_global_synthetic_boundary(self):
        with override_settings(SYNTHETIC_ONLY=False), self.assertRaises(ValidationError):
            provider.configuration(self.actor, self.encounter)


class RawCodingMeterTests(SimpleTestCase):
    def test_shared_provider_lock_refuses_contention_without_send_and_unlocks_after_error(self):
        cursor = Mock()
        cursor.fetchone.return_value = (False,)
        db = SimpleNamespace(vendor='postgresql', cursor=lambda: nullcontext(cursor))
        with patch.object(provider, 'connection', db), self.assertRaises(provider.CodingNotSent):
            with provider._provider_slot(BASE):
                self.fail('Contention must not enter transport.')
        self.assertEqual(cursor.execute.call_args[0][1], [provider.testing_authority.PROVIDER_LOCK])
        cursor.reset_mock()
        cursor.fetchone.side_effect = [(True,), (True,)]
        with patch.object(provider, 'connection', db), self.assertRaises(TimeoutError):
            with provider._provider_slot(BASE):
                raise TimeoutError('offline')
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertIn('pg_advisory_unlock', cursor.execute.call_args[0][0])

    def test_openai_cache_and_anthropic_cache_duration_are_accounted_from_raw(self):
        raw = {'usage': {'input_tokens': 100, 'output_tokens': 10, 'input_tokens_details': {'cached_tokens': 20}}}
        cost, units, rates = provider.raw_accounting(raw, {**BASE, 'provider': 'openai'})
        self.assertEqual(cost, Decimal('0.000102'))
        self.assertEqual(units['cached_input_tokens'], 20)
        raw = {'usage': {'input_tokens': 100, 'output_tokens': 10, 'cache_creation_input_tokens': 20,
                        'cache_creation': {'ephemeral_5m_input_tokens': 20, 'ephemeral_1h_input_tokens': 0}}}
        self.assertEqual(provider.raw_accounting(raw, BASE)[0], Decimal('0.000145'))
        raw['usage']['cache_creation']['ephemeral_1h_input_tokens'] = 1
        with self.assertRaises(provider.CodingUnknown):
            provider.raw_accounting(raw, BASE)
        raw['usage']['cache_creation']['ephemeral_5m_input_tokens'] = 19
        with self.assertRaises(provider.CodingUnknown):
            provider.raw_accounting(raw, BASE)

    def test_openai_missing_or_excess_cache_usage_is_unknown(self):
        for details in (None, {'cached_tokens': False}, {'cached_tokens': 11}):
            with self.subTest(details=details), self.assertRaises(provider.CodingUnknown):
                provider.raw_accounting({'usage': {'input_tokens': 10, 'output_tokens': 1, 'input_tokens_details': details}},
                                        {**BASE, 'provider': 'openai'})
