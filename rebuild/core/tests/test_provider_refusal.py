"""A provider's DEFINITE refusal is a definite outcome, not an unknown one (2026-10-02).

Campaign 3's attempt 3 (case soap-ankle-speech, request req_011CfcS91wTJvP4v9WqzJt1d) was answered HTTP 400
invalid_request_error "Schema is too complex for compilation". The worker treated every exception from
client.messages.create as an unknown outcome: the generation job went to 'reconciliation' ('Provider outcome is
uncertain; reconcile before retrying.') with its hold kept, waiting for an administrator, for a request the provider
never processed and never bills.

Now an HTTP 400 whose error type is invalid_request_error, or an HTTP 413, raised by the SDK itself for the request's ONLY
attempt (`core.jobs.provider_refused`, a structural proof like `never_transmitted`), ends the generation or mapping job
'failed', not processed: the hold released, nothing charged (no receipt, no usage, no ledger movement), a message the
clinician reads, and an audit record carrying the provider's request id. Every other provider error - 401, 403, 404,
408, 409, 422, 429, 5xx, 529, a timeout, a dropped connection, a 400 the SDK did not raise for a first attempt, a 400 of
another error type - keeps the conservative unknown outcome with its hold.

Synthetic inputs only. The provider is the REAL anthropic SDK over an httpx MockTransport (or a patched client for the
controls); every socket connect is refused and recorded.
"""
import json
from unittest.mock import patch

import anthropic
import httpx
from django.test import TestCase, override_settings

from core import generation as g
from core.jobs import enqueue, public_error, run_one as run_job
from core.models import AuditEvent, Encounter, Job, LedgerEntry, ProviderReceipt, Reservation, Usage, Wallet
from .test_money_closeout import (NOTES, REAL_ANTHROPIC, DeniedNetwork, over_mock_transport,
                                  reply_with_empty_selections, synthetic_credential)
from .test_v3_ordinary_notes import LIVE
from .test_word_v3_workflow import V3EncounterFixture

#: The live refusal's body, verbatim (evidence/003/provider-response.body of the standing campaign 20261002).
TOO_COMPLEX = {'type': 'error', 'error': {
    'type': 'invalid_request_error',
    'message': 'Schema is too complex for compilation. Try reducing the number of tools or simplifying tool schemas.'},
    'request_id': 'req_synthetic_refused_400'}
TOO_LARGE = {'type': 'error', 'error': {'type': 'request_too_large', 'message': 'Request exceeds the maximum allowed '
                                                                                'number of bytes.'},
             'request_id': 'req_synthetic_refused_413'}


def answering(status, body, request_id, sent):
    """The provider: every request recorded, answered `status` with `body` (a dict as JSON, or raw text)."""
    def handler(request):
        sent.append(request)
        content = {'json': body} if isinstance(body, dict) else {'content': body.encode()}
        return httpx.Response(status, headers={'request-id': request_id}, **content)
    return handler


class RefusalAssertions:
    def assert_refused(self, job, *, status, request_id, error_type, sent, action='job.failed', prefix='Not processed: '):
        job.refresh_from_db()
        self.assertEqual(len(sent), 1)                                   # (sent once, never retried)
        self.assertEqual(job.state, 'failed', job.error)
        self.assertTrue(job.error.startswith(prefix), job.error)
        self.assertIn(request_id, job.error)
        self.assertIn('nothing was charged', job.error.lower())
        self.assertIn('held funds were released', job.error)
        self.assertNotIn('Schema is too complex', job.error)             # (the provider's own words are never shown)
        self.assertEqual(list(Reservation.objects.filter(job=job).values_list('state', flat=True)), ['released'])
        self.assertFalse(ProviderReceipt.objects.filter(job=job).exists())
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.assertFalse(LedgerEntry.objects.filter(job=job).exists())
        self.assertEqual(job.provider_request_id, request_id)
        self.assertTrue(job.request_key.endswith(':' + job.pk.hex), job.request_key)     # (the key is freed)
        row = AuditEvent.objects.filter(action=action, target=str(job.pk)).get()
        self.assertEqual(row.details['error_class'], 'ProviderRefusedRequest')
        refused = AuditEvent.objects.filter(action='provider.refused', target=str(job.pk)).get()
        self.assertEqual((refused.details['request_id'], refused.details['status'], refused.details['error_type']),
                         (request_id, status, error_type))
        # Exactly these members and never the provider's own words (refutation of 9c2ffa92, T1).
        self.assertEqual(set(refused.details), {'kind', 'status', 'error_type', 'request_id', 'job_action'})
        self.assertNotIn('Schema is too complex', json.dumps([row.details, refused.details]))
        self.assertTrue(all(w.reserved == 0 for w in Wallet.objects.filter(user=job.user)))
        from core.management.commands.audit_billing import audit_report
        report = audit_report()
        self.assertTrue(report['all_checks_pass'], report)
        self.assertNotIn(str(job.pk), [str(row['id']) for row in report['unresolved_jobs']])
        return job

    def retire(self, job):
        """End a job left by one subtest (its hold released, its key freed) so the next subtest can enqueue afresh."""
        from core.billing import release
        from core.jobs import ended_key
        job.refresh_from_db()
        release(job)
        Job.objects.filter(pk=job.pk).update(state='failed', request_key=ended_key(job, 'failed'))

    def assert_uncertain_with_its_hold(self, job, sent=None):
        job.refresh_from_db()
        if sent is not None:
            self.assertEqual(len(sent), 1)
        self.assertEqual(job.state, 'reconciliation', job.error)
        self.assertEqual(list(Reservation.objects.filter(job=job).values_list('state', flat=True)), ['held'])
        self.assertFalse(AuditEvent.objects.filter(action='provider.refused', target=str(job.pk)).exists())


@override_settings(**LIVE)
class RefusedGeneration(RefusalAssertions, DeniedNetwork, V3EncounterFixture, TestCase):
    """Reproduce: live mode with the LIVE test settings (claude-sonnet-5, rates 2/10), ANTHROPIC_API_KEY set, the REAL
    anthropic 0.125.0 SDK over a MockTransport answering HTTP 400 invalid_request_error; jobs.enqueue then jobs.run_one.

    RED on 5ad1e82e: 'reconciliation', 'Provider outcome is uncertain; reconcile before retrying.', the hold 'held',
    audit billing 'uncertain' error_class BadRequestError, the job listed among audit_billing's unresolved jobs."""

    def setUp(self):
        super().setUp()
        self.deny_network()

    def enqueued(self):
        encounter = Encounter.objects.get(pk=self.encounter.pk)
        saved = self.client.post(f'/encounters/{encounter.pk}/notes/', {'revision': encounter.revision, 'notes': NOTES})
        self.assertEqual(saved.status_code, 302)
        job = enqueue(Encounter.objects.get(pk=self.encounter.pk), self.user)
        self.assertEqual(list(Reservation.objects.filter(job=job).values_list('state', flat=True)), ['held'])
        return job

    def refused(self, status, body, request_id):
        job, sent = self.enqueued(), []
        with synthetic_credential(), over_mock_transport(answering(status, body, request_id, sent)):
            self.assertTrue(run_job())
        return job, sent

    def assert_free_to_generate_again(self):
        self.assertFalse(Job.objects.filter(encounter=self.encounter, state__in=['queued', 'running', 'reconciliation'])
                         .exists())
        again = enqueue(Encounter.objects.get(pk=self.encounter.pk), self.user)
        self.assertEqual(list(Reservation.objects.filter(job=again).values_list('state', flat=True)), ['held'])
        return again

    def test_a_400_invalid_request_on_the_default_path_is_failed_released_and_uncharged(self):
        job, sent = self.refused(400, TOO_COMPLEX, 'req_synthetic_refused_400')
        self.assertNotIn('ordinary_field_contract', job.config)
        job = self.assert_refused(job, status=400, request_id='req_synthetic_refused_400',
                                  error_type='invalid_request_error', sent=sent)
        row = AuditEvent.objects.filter(action='job.failed', target=str(job.pk)).get()
        self.assertEqual(row.details['billing'], 'provider_refused')
        self.assertIn('refused', public_error(job))
        self.assert_free_to_generate_again()

    @override_settings(V3_FIELD_RELATIONS=True)
    def test_the_live_too_complex_refusal_on_the_relations_path_is_failed_released_and_uncharged(self):
        job, sent = self.refused(400, TOO_COMPLEX, 'req_synthetic_refused_400')
        self.assertIn('ordinary_field_contract', job.config)
        self.assertIn('output_config', json.loads(sent[0].content))      # (the relations request itself was refused)
        self.assert_refused(job, status=400, request_id='req_synthetic_refused_400',
                            error_type='invalid_request_error', sent=sent)
        self.assert_free_to_generate_again()

    def test_a_413_is_failed_released_and_uncharged(self):
        for body in (TOO_LARGE, '<html><body>413 Request Entity Too Large</body></html>'):
            with self.subTest(body=type(body).__name__):
                job, sent = self.refused(413, body, 'req_synthetic_refused_413')
                self.assert_refused(job, status=413, request_id='req_synthetic_refused_413',
                                    error_type='request_too_large' if isinstance(body, dict) else '', sent=sent)
                self.retire(self.assert_free_to_generate_again())

    # Controls: every other provider error keeps the unknown outcome and its hold.

    def test_control_every_other_status_stays_an_unknown_outcome_with_its_hold(self):
        bodies = {401: 'authentication_error', 403: 'permission_error', 404: 'not_found_error', 408: 'timeout_error',
                  409: 'conflict_error', 422: 'invalid_request_error', 429: 'rate_limit_error', 500: 'api_error',
                  503: 'api_error', 504: 'timeout_error', 529: 'overloaded_error'}
        for status, kind in bodies.items():
            with self.subTest(status=status):
                job, sent = self.refused(status, {'type': 'error', 'error': {'type': kind, 'message': 'synthetic'}},
                                         f'req_synthetic_{status}')
                self.assert_uncertain_with_its_hold(job, sent)
                self.retire(job)

    def test_control_a_400_of_another_kind_stays_an_unknown_outcome_with_its_hold(self):
        for name, body in (('another error type', {'type': 'error', 'error': {'type': 'api_error', 'message': 'x'}}),
                           ('no error type', {'type': 'error'}),
                           ('not JSON', '<html>400 Bad Request</html>')):
            with self.subTest(body=name):
                job, sent = self.refused(400, body, 'req_synthetic_400_other')
                self.assert_uncertain_with_its_hold(job, sent)
                self.retire(job)

    def test_control_a_dropped_connection_and_a_timeout_stay_unknown_outcomes_with_their_holds(self):
        for error in (httpx.ConnectError('synthetic: dropped after the request was written'),
                      httpx.ReadTimeout('synthetic: no answer')):
            with self.subTest(error=type(error).__name__):
                job, sent = self.enqueued(), []

                def handler(request, error=error):
                    sent.append(request)
                    raise error
                with synthetic_credential(), over_mock_transport(handler):
                    self.assertTrue(run_job())
                self.assert_uncertain_with_its_hold(job, sent)
                self.retire(job)

    def test_control_a_400_the_sdk_did_not_raise_for_its_request_stays_an_unknown_outcome(self):
        """The class alone proves nothing: a BadRequestError raised by anything but the SDK's own request loop (here a
        patched client) keeps the conservative outcome."""
        job = self.enqueued()
        request = httpx.Request('POST', 'https://api.anthropic.com/v1/messages',
                                headers={'x-stainless-retry-count': '0'})
        error = anthropic.BadRequestError('synthetic', response=httpx.Response(
            400, request=request, json=TOO_COMPLEX, headers={'request-id': 'req_synthetic_forged'}), body=TOO_COMPLEX)
        with synthetic_credential(), patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.side_effect = error
            self.assertTrue(run_job())
        self.assert_uncertain_with_its_hold(job)

    def test_control_a_refused_call_to_another_endpoint_is_never_a_refusal_of_the_job(self):
        """Refutation of 9c2ffa92, T4: only the job's own Messages call proves a refusal. The same SDK error raised by the
        SDK's own request loop for count_tokens, models.retrieve or batches.create - real calls over a mock transport -
        is not classified, so a refused second call could never release the hold of a processed first one."""
        from core.jobs import provider_refused
        sent = []
        client = REAL_ANTHROPIC(api_key='synthetic-not-a-key', max_retries=0, http_client=httpx.Client(
            transport=httpx.MockTransport(answering(400, TOO_COMPLEX, 'req_synthetic_other_endpoint', sent))))
        calls = {'count_tokens': lambda: client.messages.count_tokens(
                     model='claude-sonnet-5-5', messages=[{'role': 'user', 'content': 'x'}]),
                 'models.retrieve': lambda: client.models.retrieve('claude-sonnet-5-5'),
                 'batches.create': lambda: client.messages.batches.create(requests=[]),
                 'messages.create': lambda: client.messages.create(
                     model='claude-sonnet-5-5', max_tokens=16, messages=[{'role': 'user', 'content': 'x'}])}
        verdicts = {}
        for name, call in calls.items():
            # (try/except, not assertRaises: assertRaises strips the traceback the classifier reads)
            try:
                call()
            except anthropic.BadRequestError as error:
                verdicts[name] = provider_refused(error) is not None
            else:
                self.fail(f'{name} was not refused')
        self.assertEqual(verdicts, {'count_tokens': False, 'models.retrieve': False, 'batches.create': False,
                                    'messages.create': True})          # (positive control: the job's own call)
        self.assertEqual(len(sent), 4)

    def test_control_a_400_after_a_retried_attempt_stays_an_unknown_outcome(self):
        """A 400 answering a RETRY proves nothing about the attempt before it, which may have been processed: only a
        first and only attempt (the SDK's own x-stainless-retry-count 0) is a definite refusal. QuillMD's clients never
        retry; this builds the SDK with one retry to prove the rule does not rest on that alone."""
        job, sent = self.enqueued(), []

        def handler(request):
            sent.append(request)
            if len(sent) == 1:
                return httpx.Response(500, json={'type': 'error', 'error': {'type': 'api_error', 'message': 'x'}},
                                      headers={'request-id': 'req_synthetic_first'})
            return httpx.Response(400, json=TOO_COMPLEX, headers={'request-id': 'req_synthetic_retry'})

        def build(**kwargs):
            return REAL_ANTHROPIC(http_client=httpx.Client(transport=httpx.MockTransport(handler)),
                                  **{**kwargs, 'max_retries': 1})
        with synthetic_credential(), patch('anthropic.Anthropic', side_effect=build), \
                patch('anthropic._base_client.SyncAPIClient._sleep_for_retry', return_value=None):
            self.assertTrue(run_job())
        self.assertEqual([r.headers.get('x-stainless-retry-count') for r in sent], ['0', '1'])
        self.assert_uncertain_with_its_hold(job)

    def test_control_a_successful_answer_is_settled_as_before(self):
        job, sent = self.enqueued(), []
        with synthetic_credential(), over_mock_transport(reply_with_empty_selections(sent)):
            self.assertTrue(run_job())
        job.refresh_from_db()
        self.assertEqual(len(sent), 1)
        self.assertNotEqual(job.state, 'reconciliation', job.error)
        self.assertFalse(job.error.startswith('Not processed'), job.error)
        self.assertTrue(ProviderReceipt.objects.filter(job=job).exists())
        self.assertEqual(set(Reservation.objects.filter(job=job).values_list('state', flat=True)), {'settled'})
        self.assertFalse(AuditEvent.objects.filter(action='provider.refused').exists())


from . import test_mapping_assistance as mapping_tests  # noqa: E402  (the module, so its TestCase is not collected here)
from core import generation, mapping_assistance as mapping  # noqa: E402
MAPPING = mapping_tests.SETTINGS


@override_settings(**dict(MAPPING, AI_MODE='live', QUILLMD_MAPPING_ASSISTANCE_LIVE=True))
class RefusedMapping(RefusalAssertions, TestCase):
    """The mapping worker, the same rule. RED on 5ad1e82e: 'reconciliation' ('Provider outcome or settlement is
    uncertain; reconcile before retrying.') with the hold held."""

    setUp = mapping_tests.MappingAssistance.setUp
    enqueue = mapping_tests.MappingAssistance.enqueue

    def refused(self, status, body, request_id):
        self.config = generation.configuration(); self.compiled = mapping.compile_request(self.version, self.config)
        job, sent, connects = self.enqueue(), [], []

        def refuse(*args, **kwargs):
            connects.append(args); raise OSError('synthetic test: the network is denied')
        with synthetic_credential(), patch('socket.socket.connect', side_effect=refuse), \
                over_mock_transport(answering(status, body, request_id, sent)):
            self.assertTrue(run_job())
        self.assertEqual(connects, [])
        return job, sent

    def test_a_400_invalid_request_is_failed_released_and_uncharged(self):
        job, sent = self.refused(400, TOO_COMPLEX, 'req_synthetic_mapping_400')
        self.assert_refused(job, status=400, request_id='req_synthetic_mapping_400', error_type='invalid_request_error',
                            sent=sent, action='mapping.failed', prefix='not_processed: ')
        self.assertEqual(self.template.versions.count(), 1)
        # nothing pending: a fresh mapping request is accepted for the same template
        self.assertNotEqual(self.enqueue().pk, job.pk)

    def test_a_413_is_failed_released_and_uncharged(self):
        job, sent = self.refused(413, TOO_LARGE, 'req_synthetic_mapping_413')
        self.assert_refused(job, status=413, request_id='req_synthetic_mapping_413', error_type='request_too_large',
                            sent=sent, action='mapping.failed', prefix='not_processed: ')

    def test_control_a_429_and_a_529_stay_unknown_outcomes_with_their_holds(self):
        for status, kind in ((429, 'rate_limit_error'), (529, 'overloaded_error')):
            with self.subTest(status=status):
                job, sent = self.refused(status, {'type': 'error', 'error': {'type': kind, 'message': 'x'}},
                                         f'req_synthetic_mapping_{status}')
                self.assert_uncertain_with_its_hold(job, sent)
                self.retire(job)


from core import batch_jobs  # noqa: E402
from core.models import GenerationBatch  # noqa: E402
from .test_generation_batch import SETTINGS as BATCH, BatchFixture, response as batch_response  # noqa: E402


@override_settings(**BATCH)
class RefusedBatchPart(RefusalAssertions, BatchFixture, TestCase):
    """The complete-form batch worker (core.batch_jobs, which the relations field batches use too), the same rule: a part
    whose ONLY attempt the provider definitely refused ends 'failed', not processed, its hold released and nothing
    charged; the batch stops with no partial form, and nothing is left for an administrator.

    RED on 5ad1e82e: the part 'reconciliation' with its 0.3-dollar hold held, the batch 'reconciliation', the encounter
    pending until an administrator resolved it."""

    def run_batch(self, batch, statuses):
        """Every part answered in order: a status from `statuses` (200: the part's normal answer)."""
        sent = []

        def handler(request):
            sent.append(request)
            status = statuses[len(sent) - 1]
            if status == 200:
                raw = batch_response(batch.plan, len(sent))
                raw.update(type='message', role='assistant', stop_sequence=None, stop_details=None)
                return httpx.Response(200, json=raw, headers={'request-id': f'req_synthetic_part_{len(sent)}'})
            body = TOO_COMPLEX if status == 400 else TOO_LARGE if status == 413 else {
                'type': 'error', 'error': {'type': 'overloaded_error', 'message': 'x'}}
            return httpx.Response(status, json=body, headers={'request-id': f'req_synthetic_part_{len(sent)}'})
        with synthetic_credential(), over_mock_transport(handler):
            for _ in range(4):
                if not batch_jobs.run_one():
                    break
        batch.refresh_from_db()
        return sent

    def assert_part_refused(self, batch, ordinal, status, request_id):
        part = batch.parts.select_related('job').get(ordinal=ordinal)
        job = part.job
        self.assertEqual(job.state, 'failed', job.error)
        self.assertTrue(job.error.startswith('Not processed: '), job.error)
        self.assertIn(request_id, job.error)
        self.assertIn('nothing was charged', job.error.lower())
        self.assertEqual(job.provider_request_id, request_id)
        self.assertEqual(list(Reservation.objects.filter(job=job).values_list('state', flat=True)), ['released'])
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.assertFalse(ProviderReceipt.objects.filter(job=job).exists())
        self.assertFalse(LedgerEntry.objects.filter(job=job).exists())
        self.assertEqual(part.events.get(kind='provider_refused').details,
                         {'status': status, 'request_id': request_id,
                          'error_type': 'invalid_request_error' if status == 400 else 'request_too_large'})
        refused = AuditEvent.objects.filter(action='provider.refused', target=str(job.pk)).get()
        self.assertEqual((refused.details['request_id'], refused.details['status']), (request_id, status))
        self.assertEqual(set(refused.details), {'kind', 'status', 'error_type', 'request_id', 'job_action'})
        self.assertNotIn('Schema is too complex', json.dumps(refused.details))

    def assert_closed_out(self, batch):
        from core.management.commands.audit_billing import audit_report
        self.assertEqual(batch.state, 'failed', batch.error)
        self.assertIn('refused', batch.error)
        self.assertFalse(Reservation.objects.filter(job__generation_part__batch=batch, state='held').exists())
        self.assertTrue(all(w.reserved == 0 for w in Wallet.objects.filter(user=self.user)))
        self.assertFalse(batch_jobs.pending(self.encounter))
        report = audit_report()
        self.assertTrue(report['all_checks_pass'], report)
        self.assertEqual(report['unresolved_jobs'], [])

    def test_a_first_part_refused_ends_the_batch_failed_with_every_hold_released(self):
        batch = self.admit()
        sent = self.run_batch(batch, [400])
        self.assertEqual(len(sent), 1)                                  # (the second part is never sent)
        self.assert_part_refused(batch, 1, 400, 'req_synthetic_part_1')
        second = batch.parts.select_related('job').get(ordinal=2).job
        self.assertEqual(second.state, 'cancelled', second.error)
        self.assertEqual(list(Reservation.objects.filter(job=second).values_list('state', flat=True)), ['released'])
        self.assertFalse(Usage.objects.exists())
        self.assert_closed_out(batch)

    def test_a_later_part_refused_after_a_settled_part_absorbs_the_settled_one(self):
        batch = self.admit()
        sent = self.run_batch(batch, [200, 413])
        self.assertEqual(len(sent), 2)
        self.assert_part_refused(batch, 2, 413, 'req_synthetic_part_2')
        first = batch.parts.select_related('job').get(ordinal=1).job
        self.assertEqual(first.state, 'failed', first.error)               # (settled, not adopted: a platform failure)
        self.assertTrue(first.error.startswith('platform_failure: '), first.error)
        self.assertTrue(Usage.objects.filter(job=first).exists())
        self.assertEqual(sum(LedgerEntry.objects.filter(job=first).values_list('amount', flat=True)), 0)   # (absorbed)
        self.assert_closed_out(batch)

    def test_control_an_overloaded_part_stays_in_reconciliation_with_its_hold(self):
        batch = self.admit()
        sent = self.run_batch(batch, [529])
        self.assertEqual(len(sent), 1)
        self.assertEqual(batch.state, 'reconciliation')
        first = batch.parts.select_related('job').get(ordinal=1)
        self.assertEqual(first.job.state, 'reconciliation')
        self.assertEqual(list(Reservation.objects.filter(job=first.job).values_list('state', flat=True)), ['held'])
        self.assertFalse(first.events.filter(kind='provider_refused').exists())
