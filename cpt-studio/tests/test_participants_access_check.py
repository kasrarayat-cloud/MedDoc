"""The participant access check (HARNESS.md 8; checklist item 1.3): it refuses unless the participant is live, the
installation synthetic-only and authorized, and the single-flight lock free; it sends exactly one request through the
real adapter and its real session factory, prints one JSON receipt with no secret in it, writes nothing to the
database and releases the lock. Offline: requests.Session is patched to return a fake session; data is synthetic."""
from __future__ import annotations

import json
from io import StringIO
from unittest import mock

from django.apps import apps
from django.core.management import CommandError, call_command
from django.db import connection, connections
from django.test import override_settings

from studio.jobs import PROVIDER_LOCK_KEY

from tests.test_participants_support import (ANTHROPIC_KEY, OPENAI_KEY, SECRETS, FakeResponse, FakeSession,
                                             OfflineDatabaseTestCase, anthropic_env, astra_with, empty_reading,
                                             fixture_bytes, openai_env, write_file)
from tests.test_providers import (CLIENT_ID, CLIENT_SECRET, FIXTURES as CORTI_FIXTURES, TOKEN, dotenv as corti_env,
                                  token_response)

AUTHORIZATION = 'docs/foundation/rulings/2026-10-23-cpt-studio-gi.md'
ALL_SECRETS = SECRETS + (CLIENT_ID, CLIENT_SECRET, TOKEN)


class AccessCheckTests(OfflineDatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.openai = write_file(self.tmp / 'openai.env', openai_env())
        self.anthropic = write_file(self.tmp / 'anthropic.env', anthropic_env())
        self.corti = write_file(self.tmp / 'corti.env', corti_env())
        self.live = {'ASTRA_MODE': 'live', 'FABLE_MODE': 'live', 'PROVIDER_MODE': 'live',
                     'OPENAI_CREDENTIALS_FILE': str(self.openai), 'ANTHROPIC_CREDENTIALS_FILE': str(self.anthropic),
                     'CORTI_CREDENTIALS_FILE': str(self.corti), 'AUTHORIZATION_REF': AUTHORIZATION}

    def rows(self):
        return {model.__name__: model.objects.count() for model in apps.get_app_config('studio').get_models()}

    def check(self, participant, *steps, **settings):
        """Run the command with a fake session behind requests.Session; return (receipt or None, error, session)."""
        session = FakeSession(*steps)
        out, err = StringIO(), StringIO()
        before = self.rows()
        error = None
        with override_settings(**{**self.live, **settings}), mock.patch('requests.Session', return_value=session):
            try:
                call_command('participant_access_check', participant=participant, stdout=out, stderr=err)
            except CommandError as exc:
                error = str(exc)
        self.assertEqual(self.rows(), before, 'the access check wrote to the database')
        printed = out.getvalue() + err.getvalue() + (error or '')
        for secret in ALL_SECRETS:
            self.assertNotIn(secret, printed)
        self.assertNotIn(str(self.tmp), printed)
        receipt = json.loads(out.getvalue()) if out.getvalue() else None
        if receipt is not None:
            self.assertEqual(out.getvalue().count('\n'), 1)  # exactly one JSON line
        return receipt, error, session

    def assertLockFree(self):
        other = connections.create_connection('default')
        try:
            self.assertEqual(other.settings_dict['NAME'], connection.settings_dict['NAME'])
            with other.cursor() as cursor:
                cursor.execute('SELECT pg_try_advisory_lock(%s)', [PROVIDER_LOCK_KEY])
                self.assertTrue(cursor.fetchone()[0], 'the access check left the provider lock held')
                cursor.execute('SELECT pg_advisory_unlock(%s)', [PROVIDER_LOCK_KEY])
        finally:
            other.close()

    def test_astra_one_request_and_a_receipt_with_no_secret(self):
        raw = fixture_bytes('astra-colonoscopy.response.json')
        receipt, error, session = self.check('astra', FakeResponse(200, raw, headers={'x-request-id': 'req_synth_1'}))
        self.assertIsNone(error)
        (call,) = session.calls
        self.assertEqual(call['url'], 'https://api.openai.com/v1/responses')
        self.assertEqual(call['headers']['Authorization'], f'Bearer {OPENAI_KEY}')
        self.assertEqual(call['headers']['X-Client-Request-Id'], receipt['client_request_id'])
        self.assertTrue(receipt['client_request_id'].startswith('cptstudio-access-check-'))
        sent = json.loads(call['data'])
        self.assertEqual(sent['input'][0]['content'][0]['type'], 'input_text')  # pasted text: no original file
        self.assertIn('SYNTHETIC TEST DOCUMENT - not a real patient.', sent['input'][0]['content'][0]['text'])
        self.assertTrue(session.closed)
        self.assertEqual({key: receipt[key] for key in (
            'participant', 'adapter_version', 'endpoint', 'requested_model', 'returned_model', 'outcome', 'sent',
            'http_status', 'request_id', 'response_id', 'usage_basis', 'error', 'authorization_ref')}, {
            'participant': 'astra', 'adapter_version': 'openai-responses@cptstudio-harness-1',
            'endpoint': 'https://api.openai.com/v1/responses', 'requested_model': 'gpt-6-astra',
            'returned_model': 'gpt-6-astra', 'outcome': 'succeeded', 'sent': True, 'http_status': 200,
            'request_id': 'req_synth_1', 'response_id': 'resp_synthetic_fixture_0001',
            'usage_basis': 'provider_reported_tokens', 'error': '', 'authorization_ref': AUTHORIZATION})
        self.assertEqual(receipt['usage'], json.loads(raw)['usage'])
        self.assertEqual(receipt['estimated_cost']['estimated_usd'], '0.069670')
        self.assertEqual(receipt['reading']['refused'], False)
        self.assertEqual(receipt['reading']['codes'], ['45385', '45380'])
        # The fixture answer quotes another note than the check's: of its five quotes only 'was removed with a cold
        # snare' is also in the check's note, so four are unverified.
        self.assertEqual(receipt['reading']['unverified_quotes'], 4)
        self.assertRegex(receipt['checked_at'], r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$')
        self.assertIsInstance(receipt['latency_ms'], float)
        self.assertLockFree()

    def test_fable_one_request_and_a_receipt_with_no_secret(self):
        raw = fixture_bytes('fable-colonoscopy.response.json')
        receipt, error, session = self.check('fable', FakeResponse(200, raw, headers={'request-id': 'req_synth_2'}))
        self.assertIsNone(error)
        (call,) = session.calls
        self.assertEqual((call['url'], call['headers']['x-api-key']),
                         ('https://api.anthropic.com/v1/messages', ANTHROPIC_KEY))
        self.assertEqual((receipt['participant'], receipt['endpoint'], receipt['requested_model'],
                          receipt['returned_model'], receipt['outcome'], receipt['request_id'], receipt['response_id'],
                          receipt['client_request_id']),
                         ('fable', 'https://api.anthropic.com/v1/messages', 'claude-fable-5-1', 'claude-fable-5-1',
                          'succeeded', 'req_synth_2', 'msg_synthetic_fixture_0001', ''))
        self.assertEqual(receipt['estimated_cost']['estimated_usd'], '0.078200')
        self.assertEqual(receipt['reading']['codes'], ['45385', '45380'])
        self.assertLockFree()

    def test_corti_one_coding_request_and_a_receipt_with_no_secret(self):
        raw = (CORTI_FIXTURES / 'taylor-reed.response.raw.json').read_bytes()
        receipt, error, session = self.check('corti', token_response(),
                                             FakeResponse(200, raw, headers={'X-Request-Id': 'req-synthetic-0003'}))
        self.assertIsNone(error)
        self.assertEqual([call['url'] for call in session.calls],
                         ['https://auth.us.corti.app/realms/synthetic-tenant/protocol/openid-connect/token',
                          'https://api.us.corti.app/v2/tools/coding/'])
        self.assertEqual((receipt['participant'], receipt['endpoint'], receipt['requested_model'],
                          receipt['returned_model'], receipt['outcome'], receipt['request_id'], receipt['usage'],
                          receipt['usage_basis'], receipt['estimated_cost']),
                         ('corti', 'https://api.us.corti.app/v2/tools/coding/', '', '', 'succeeded',
                          'req-synthetic-0003', {'creditsConsumed': 0.019524}, 'provider_reported_credits_not_usd',
                          None))
        self.assertEqual((receipt['reading']['refused'], receipt['reading']['codes']), (False, ['99213']))
        self.assertLockFree()

    def test_it_refuses_unless_the_participant_is_live(self):
        for participant, mode_setting in (('astra', 'ASTRA_MODE'), ('fable', 'FABLE_MODE'), ('corti', 'PROVIDER_MODE')):
            for mode in ('disabled', 'replay'):
                with self.subTest(participant=participant, mode=mode):
                    receipt, error, session = self.check(participant, **{mode_setting: mode})
                    self.assertIsNone(receipt)
                    self.assertIn(f'is not live on this installation (its mode is {mode}); nothing was sent', error)
                    self.assertEqual(session.calls, [])

    def test_it_refuses_without_an_authorization_or_on_an_installation_that_is_not_synthetic_only(self):
        for settings, expect in (({'AUTHORIZATION_REF': ''}, 'No owner authorization is configured'),
                                 ({'SYNTHETIC_ONLY': False}, 'is not synthetic-only')):
            with self.subTest(expect=expect):
                receipt, error, session = self.check('astra', **settings)
                self.assertIsNone(receipt)
                self.assertIn(expect, error)
                self.assertEqual(session.calls, [])

    def test_it_refuses_without_the_credentials_setting(self):
        for participant, settings, expect in (
                ('astra', {'OPENAI_CREDENTIALS_FILE': ''}, 'CPT_STUDIO_OPENAI_CREDENTIALS_FILE'),
                ('fable', {'ANTHROPIC_CREDENTIALS_FILE': ''}, 'CPT_STUDIO_ANTHROPIC_CREDENTIALS_FILE'),
                ('corti', {'CORTI_CREDENTIALS_FILE': ''}, 'CPT_STUDIO_CORTI_CREDENTIALS_FILE')):
            with self.subTest(participant=participant):
                receipt, error, session = self.check(participant, **settings)
                self.assertIsNone(receipt)
                self.assertIn(expect, error)
                self.assertEqual(session.calls, [])
        self.assertLockFree()

    def test_it_refuses_while_another_provider_request_holds_the_lock(self):
        other = connections.create_connection('default')
        try:
            with other.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_lock(%s)', [PROVIDER_LOCK_KEY])
            receipt, error, session = self.check('astra')
            self.assertIsNone(receipt)
            self.assertIn('Another provider request is in flight; nothing was sent', error)
            self.assertEqual(session.calls, [])
            with other.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_unlock(%s)', [PROVIDER_LOCK_KEY])
        finally:
            other.close()
        self.assertLockFree()

    def test_a_failed_request_or_a_refused_reading_prints_its_receipt_and_fails_the_check(self):
        receipt, error, session = self.check('astra', FakeResponse(503, b'{"error":{"message":"synthetic"}}'))
        self.assertEqual((receipt['outcome'], receipt['http_status'], receipt['reading']), ('failed', 503, None))
        self.assertEqual(error, 'The Astra access check did not pass: see the receipt.')
        self.assertEqual(len(session.calls), 1)  # never retried
        truncated = astra_with(empty_reading(), status='incomplete', incomplete_details={'reason': 'max_output_tokens'})
        receipt, error, _ = self.check('astra', FakeResponse(200, truncated))
        self.assertEqual((receipt['outcome'], receipt['reading']['refused'], receipt['reading']['problems']),
                         ('succeeded', True, ['The reading was not used: the response was cut off at the output '
                                              'limit.']))
        self.assertEqual(error, 'The Astra access check did not pass: see the receipt.')
        self.assertLockFree()

    def test_an_unreadable_credentials_file_is_reported_without_its_path_or_content(self):
        self.openai.chmod(0o644)
        receipt, error, session = self.check('astra')
        self.assertEqual((receipt['outcome'], receipt['sent'], receipt['endpoint']), ('not_sent', False, ''))
        self.assertIn('accessible to group or other users', receipt['error'])
        self.assertEqual(session.calls, [])
        self.assertIn('did not pass', error)
