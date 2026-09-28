"""MONEY-1 and MONEY-2 (verified 2026-09-28), each reproduced with the finding's own input.

MONEY-1. Behind QUILLMD_V3_GENERATION_BATCHES: every part of a batch was sent, settled and staged, and finish() then met a
CHANGED QuillMD configuration (the batch flag, a rate, an unrelated voice setting; a worker restarted for a config deploy
while the last part was in flight is the natural trigger). finish() classified that as the user's own decision: the batch
went 'not_adopted', every part stayed charged, nothing was absorbed, and the output was never delivered. QuillMD's own
change is never billed. The batch stops as a platform failure and every settled part is absorbed, exactly as the same
change one step earlier (between parts) already is.

MONEY-2. With no provider credential, anthropic 0.125.0 refuses while BUILDING the request, inside messages.create, before
any connection. That TypeError escaped every pre-provider guard, so the job read 'Provider outcome is uncertain' and kept
its hold. A request that provably never left ends 'not processed' with its hold released, like every other pre-send
refusal. The proof is structural (the TypeError's innermost frame is the SDK's own header validation); any other
TypeError stays an unknown outcome with its hold kept, which the controls below pin.

Synthetic inputs only. Every provider is simulated: the real SDK with no credential (it never reaches a socket), the real
SDK over an httpx MockTransport, or a patched client. Every socket connect is refused and recorded.
"""
import json
import os
import tempfile
from contextlib import contextmanager, nullcontext
from decimal import Decimal
from unittest.mock import patch

import anthropic
import httpx
from django.test import SimpleTestCase, TestCase, override_settings

from core import batch_jobs as jobs, generation as g
from core.jobs import public_error, run_one as run_job
from core.models import (AuditEvent, Encounter, GenerationBatch, Job, LedgerEntry, Membership, PlatformCost,
                         ProviderReceipt, Reservation, Usage, Wallet)
from .test_generation_batch import SETTINGS as BATCH, BatchFixture, response as batch_response
from .test_v3_ordinary_notes import LIVE
from .test_word_v3_workflow import V3EncounterFixture

#: The SDK class itself, captured before any test patches `anthropic.Anthropic`.
REAL_ANTHROPIC = anthropic.Anthropic
SYNTHETIC_KEY = 'synthetic-credential-never-sent'


@contextmanager
def no_provider_credential():
    """A live worker with no provider credential: every ANTHROPIC_* variable unset and a HOME holding no profile, so the
    SDK's explicit, environment and profile lookups all find nothing. Nothing else in the environment changes, so the
    configuration a job or a batch was quoted under still matches."""
    with tempfile.TemporaryDirectory(prefix='quillmd-no-credential-') as home, patch.dict(os.environ, {'HOME': home}):
        for name in [name for name in os.environ if name.startswith('ANTHROPIC_')]:
            del os.environ[name]
        yield


@contextmanager
def synthetic_credential():
    """The same process WITH the credential the deployment contract names (ANTHROPIC_API_KEY): the positive control."""
    with tempfile.TemporaryDirectory(prefix='quillmd-credential-') as home, \
            patch.dict(os.environ, {'HOME': home, 'ANTHROPIC_API_KEY': SYNTHETIC_KEY}):
        yield


def message_json(text, *, ident='msg_synthetic_money', usage=None):
    return {'id': ident, 'type': 'message', 'role': 'assistant', 'model': g.SONNET_5,
            'content': [{'type': 'text', 'text': text}], 'stop_reason': 'end_turn', 'stop_details': None,
            'stop_sequence': None, 'usage': usage or {'input_tokens': 100, 'output_tokens': 10,
                                                     'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0}}


def over_mock_transport(handler):
    """`anthropic.Anthropic` as the REAL SDK class, constructed exactly as QuillMD constructs it, over a MockTransport.
    No credential is passed: the SDK resolves it from the environment, as in production."""
    def build(**kwargs):
        return REAL_ANTHROPIC(http_client=httpx.Client(transport=httpx.MockTransport(handler)), **kwargs)
    return patch('anthropic.Anthropic', side_effect=build)


class DeniedNetwork:
    """Every socket connect is refused and recorded: 'nothing left' is measured, not assumed."""

    def deny_network(self):
        self.connects = []

        def refuse(*args, **kwargs):
            self.connects.append(args)
            raise OSError('synthetic test: the network is denied')
        denied = patch('socket.socket.connect', side_effect=refuse)
        denied.start()
        self.addCleanup(denied.stop)


# --------------------------------------------------------------------------------------------------------------------
# MONEY-1
# --------------------------------------------------------------------------------------------------------------------

@contextmanager
def revoked(user, department):
    """The user's own state: their access to the department is revoked before finish()."""
    Membership.objects.filter(user=user, department=department).delete()
    yield


@override_settings(**BATCH)
class QuillMDConfigurationChangeAtFinish(BatchFixture, TestCase):
    """MONEY-1. Reproduce: V3_GENERATION_BATCHES=1 with the batch test settings (live, claude-sonnet-5, rates 2/10). A
    synthetic 101-field v3 form is admitted through /generate/ as a 2-part batch; both parts are sent (provider patched)
    and staged; the worker then comes back with a changed setting and run_one() reaches finish().

    RED on bf8f7b78 for every QuillMD-side change: batch 'not_adopted', both parts 'failed' with 'not_adopted: The source,
    authorization or clinical decisions changed ...', each part's charge kept (ledger net -0.0018), no absorbed_failure."""

    def wallets(self):
        return {w.pk: (w.balance, w.reserved) for w in Wallet.objects.filter(user=self.user).order_by('pk')}

    def staged_then_finish(self, change, *, configuration_changes):
        before = self.wallets()
        batch = self.admit()
        calls, call = self.fake(batch)
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect = call
            self.assertTrue(jobs.run_one())
            self.assertTrue(jobs.run_one())
            self.assertEqual(sorted(batch.parts.values_list('job__state', flat=True)), ['staged', 'staged'])
            self.assertEqual(Usage.objects.filter(job__generation_part__batch=batch).count(), 2)
            self.assertEqual(batch.plan['config'], g.configuration())
            with change:
                # The change under test is real, and is (or is not) a configuration change: never a vacuous control.
                self.assertEqual(batch.plan['config'] != g.configuration(), configuration_changes)
                self.assertTrue(jobs.run_one())
            self.assertEqual(len(calls), 2)
        batch.refresh_from_db()
        return batch, before

    def assert_absorbed_as_platform_failure(self, batch, before):
        from core.management.commands.audit_billing import audit_report
        self.assertEqual(batch.state, 'failed', batch.error)
        self.assertIn('configuration', batch.error)
        for part in batch.parts.select_related('job').order_by('ordinal'):
            job = part.job
            with self.subTest(part=part.ordinal):
                self.assertEqual(job.state, 'failed')
                self.assertTrue(job.error.startswith('platform_failure: '), job.error)
                self.assertNotIn('source, authorization or clinical decisions', job.error)
                self.assertIn('it is not charged to you', public_error(job))
                # The provider cost stays recorded; the customer's charge is reversed and QuillMD carries it.
                usage = Usage.objects.get(job=job)
                self.assertGreater(usage.charged_cost, 0)
                cost = PlatformCost.objects.get(job=job, kind='absorbed_failure')
                self.assertEqual(cost.amount, usage.actual_cost)
                entries = LedgerEntry.objects.filter(job=job)
                self.assertEqual(sorted(entries.values_list('kind', flat=True)), ['absorbed', 'usage'])
                self.assertEqual(sum(entries.values_list('amount', flat=True), Decimal(0)), Decimal(0))
                # Settled once at send, never released again: no hold is left and none is double-counted.
                self.assertEqual(set(Reservation.objects.filter(job=job).values_list('state', flat=True)), {'settled'})
        self.assertEqual(self.wallets(), before)
        self.encounter.refresh_from_db()
        self.assertEqual((self.encounter.answers, self.encounter.status), ({}, 'draft'))
        self.assertFalse(jobs.pending(self.encounter))
        report = audit_report()
        self.assertTrue(report['all_checks_pass'], report)

    def test_the_batch_flag_turned_off_at_finish_is_absorbed_not_billed(self):
        batch, before = self.staged_then_finish(override_settings(V3_GENERATION_BATCHES=False), configuration_changes=True)
        self.assert_absorbed_as_platform_failure(batch, before)

    def test_a_rate_change_at_finish_is_absorbed_not_billed(self):
        batch, before = self.staged_then_finish(override_settings(AI_OUTPUT_RATE='11'), configuration_changes=True)
        self.assert_absorbed_as_platform_failure(batch, before)

    def test_an_unrelated_voice_setting_at_finish_is_absorbed_not_billed(self):
        batch, before = self.staged_then_finish(patch.dict(os.environ, {'QUILLMD_VOICE_MAX_COST': '0.25'}),
                                                configuration_changes=True)
        self.assert_absorbed_as_platform_failure(batch, before)

    def test_our_change_is_never_billed_even_when_the_users_access_also_changed(self):
        """Both at once: QuillMD's change alone makes the output unusable, so the user is not charged for it."""
        change = override_settings(AI_OUTPUT_RATE='11')

        @contextmanager
        def both():
            with change, revoked(self.user, self.department):
                yield
        batch, before = self.staged_then_finish(both(), configuration_changes=True)
        self.assert_absorbed_as_platform_failure(batch, before)

    # Controls: the repair must not turn every finish into a refund.

    def test_control_an_unchanged_configuration_is_adopted_and_charged(self):
        batch, before = self.staged_then_finish(nullcontext(), configuration_changes=False)
        self.assertEqual(batch.state, 'succeeded', batch.error)
        self.encounter.refresh_from_db()
        self.assertEqual(len(self.encounter.answers), 101)
        self.assertFalse(PlatformCost.objects.filter(kind='absorbed_failure').exists())
        for part in batch.parts.select_related('job'):
            usage = Usage.objects.get(job=part.job)
            self.assertEqual(sum(LedgerEntry.objects.filter(job=part.job).values_list('amount', flat=True), Decimal(0)),
                             -usage.charged_cost)

    def test_control_the_users_own_revoked_access_at_finish_stays_not_adopted_and_charged(self):
        """The design keeps not-adopted billing for the user's own source, permission or decision changes."""
        batch, before = self.staged_then_finish(revoked(self.user, self.department), configuration_changes=False)
        self.assertEqual(batch.state, 'not_adopted', batch.error)
        for part in batch.parts.select_related('job'):
            self.assertTrue(part.job.error.startswith('not_adopted: '), part.job.error)
            usage = Usage.objects.get(job=part.job)
            self.assertEqual(sum(LedgerEntry.objects.filter(job=part.job).values_list('amount', flat=True), Decimal(0)),
                             -usage.charged_cost)
        self.assertFalse(PlatformCost.objects.filter(kind='absorbed_failure').exists())


# --------------------------------------------------------------------------------------------------------------------
# MONEY-2
# --------------------------------------------------------------------------------------------------------------------

NOTES = 'Referring physician: Dr Example\nPatient seen today.'


def reply_with_empty_selections(sent):
    def handler(request):
        sent.append(request)
        return httpx.Response(200, json=message_json(json.dumps({'fields': []})),
                              headers={'request-id': 'req_synthetic_money'})
    return handler


@override_settings(**LIVE)
class NoCredentialSingleJob(DeniedNetwork, V3EncounterFixture, TestCase):
    """MONEY-2, the default and the ordinary paths. Reproduce: live mode with the LIVE test settings (claude-sonnet-5,
    rates 2/10), ANTHROPIC_API_KEY and every other ANTHROPIC_* variable unset, the REAL anthropic 0.125.0 SDK, every
    connect refused. Notes 'Referring physician: Dr Example\\nPatient seen today.'; jobs.enqueue then jobs.run_one.

    RED on bf8f7b78: 'reconciliation', 'Provider outcome is uncertain; reconcile before retrying.', audit billing
    'uncertain' error_class TypeError, the hold still 'held', and the encounter locked."""

    def setUp(self):
        super().setUp()
        self.deny_network()

    def enqueued(self):
        from core.jobs import enqueue
        encounter = Encounter.objects.get(pk=self.encounter.pk)
        saved = self.client.post(f'/encounters/{encounter.pk}/notes/', {'revision': encounter.revision, 'notes': NOTES})
        self.assertEqual(saved.status_code, 302)
        job = enqueue(Encounter.objects.get(pk=self.encounter.pk), self.user)
        self.assertEqual(list(Reservation.objects.filter(job=job).values_list('state', flat=True)), ['held'])
        return job

    def assert_not_processed(self, job):
        job.refresh_from_db()
        self.assertEqual(job.state, 'failed', job.error)
        self.assertTrue(job.error.startswith('Not processed: '), job.error)
        self.assertIn('not connected', job.error)
        self.assertIn('held funds were released', job.error)
        self.assertEqual(list(Reservation.objects.filter(job=job).values_list('state', flat=True)), ['released'])
        self.assertFalse(ProviderReceipt.objects.filter(job=job).exists())
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.assertFalse(LedgerEntry.objects.filter(job=job).exists())
        self.assertEqual(self.connects, [])
        row = AuditEvent.objects.filter(action='job.failed', target=str(job.pk)).get()
        self.assertEqual((row.details['billing'], row.details['error_class']), ('not_processed', 'NoProviderRequest'))
        self.assertTrue(all(w.reserved == 0 for w in Wallet.objects.filter(user=self.user)))
        # The encounter is not locked behind an administrator: the notes save again.
        encounter = Encounter.objects.get(pk=self.encounter.pk)
        saved = self.client.post(f'/encounters/{encounter.pk}/notes/',
                                 {'revision': encounter.revision, 'notes': NOTES + '\nFollow-up in two weeks.'})
        self.assertEqual(saved.status_code, 302)

    def test_default_path_without_a_credential_is_not_processed_and_releases_the_hold(self):
        job = self.enqueued()
        self.assertNotIn('ordinary_field_contract', job.config)
        with no_provider_credential():
            self.assertTrue(run_job())
        self.assert_not_processed(job)

    @override_settings(V3_FIELD_RELATIONS=True)
    def test_ordinary_path_without_a_credential_is_not_processed_and_releases_the_hold(self):
        job = self.enqueued()
        self.assertIn('ordinary_field_contract', job.config)
        with no_provider_credential():
            self.assertTrue(run_job())
        self.assert_not_processed(job)

    def assert_left_once(self, job):
        """The same real SDK, the same job, one difference: ANTHROPIC_API_KEY is set. The request leaves exactly once,
        carrying that credential, and its outcome is settled rather than refused."""
        sent = []
        with synthetic_credential(), over_mock_transport(reply_with_empty_selections(sent)):
            self.assertTrue(run_job())
        job.refresh_from_db()
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].headers.get('x-api-key'), SYNTHETIC_KEY)
        self.assertFalse(job.error.startswith('Not processed'), job.error)
        self.assertTrue(ProviderReceipt.objects.filter(job=job).exists())
        self.assertEqual(set(Reservation.objects.filter(job=job).values_list('state', flat=True)), {'settled'})
        self.assertEqual(self.connects, [])

    def test_control_default_path_with_the_credential_leaves_once_and_is_settled(self):
        self.assert_left_once(self.enqueued())

    def test_control_a_type_error_from_anywhere_else_stays_an_unknown_outcome_with_its_hold(self):
        """Only the SDK's own request-build refusal proves nothing left. The same class and message raised by the send
        itself is indistinguishable from a failure after transmission, so it keeps the conservative outcome."""
        job = self.enqueued()
        refusal = TypeError('"Could not resolve authentication method. Expected one of api_key, auth_token, or '
                            'credentials to be set."')
        with no_provider_credential(), patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.side_effect = refusal
            self.assertTrue(run_job())
        job.refresh_from_db()
        self.assertEqual(job.state, 'reconciliation', job.error)
        self.assertEqual(job.error, 'Provider outcome is uncertain; reconcile before retrying.')
        self.assertEqual(list(Reservation.objects.filter(job=job).values_list('state', flat=True)), ['held'])

    @override_settings(V3_FIELD_RELATIONS=True)
    def test_control_ordinary_path_with_the_credential_leaves_once_and_is_settled(self):
        job = self.enqueued()
        self.assertIn('ordinary_field_contract', job.config)
        self.assert_left_once(job)


@override_settings(**BATCH)
class NoCredentialBatch(BatchFixture, TestCase):
    """MONEY-2, the batch path. Reproduce: BatchFixture, V3_GENERATION_BATCHES=True, a 2-part batch, no credential, the
    REAL SDK. RED on bf8f7b78: a send intent was committed, part 1 went to 'reconciliation' with 0.31287 still held, the
    batch 'reconciliation' and the encounter pending until an administrator resolved it."""

    def test_batch_without_a_credential_is_proved_untransmitted_and_releases_every_hold(self):
        from core.management.commands.audit_billing import audit_report
        batch = self.admit()
        with no_provider_credential():
            self.assertEqual(batch.plan['config'], g.configuration())
            self.assertTrue(jobs.run_one())
        batch.refresh_from_db()
        self.assertEqual(batch.state, 'failed', batch.error)
        # The first child's single attempt stays consumed forever; its durable proof says it never left.
        first = batch.parts.get(ordinal=1)
        self.assertEqual(batch.events.filter(kind='send_intent').count(), 1)
        self.assertTrue(first.events.filter(kind='send_intent').exists())
        self.assertTrue(first.events.filter(kind='not_transmitted').exists())
        self.assertEqual(batch.events.get(kind='part_failed').details['error_class'], 'TypeError')
        for part in batch.parts.select_related('job').order_by('ordinal'):
            with self.subTest(part=part.ordinal):
                self.assertEqual(part.job.state, 'cancelled', part.job.error)
                self.assertEqual(list(Reservation.objects.filter(job=part.job).values_list('state', flat=True)),
                                 ['released'])
        self.assertFalse(Usage.objects.exists())
        self.assertFalse(ProviderReceipt.objects.exists())
        self.assertTrue(all(w.reserved == 0 for w in Wallet.objects.filter(user=self.user)))
        self.assertFalse(jobs.pending(self.encounter))
        self.assertFalse(jobs.run_one())
        report = audit_report()
        self.assertTrue(report['all_checks_pass'], report)

    def test_control_a_type_error_from_the_send_itself_keeps_the_part_in_reconciliation(self):
        """Without the SDK's own proof, a send-intent child that raised is an unknown outcome, exactly as before."""
        batch = self.admit()
        with no_provider_credential(), patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect = TypeError('synthetic failure inside the send')
            self.assertTrue(jobs.run_one())
        batch.refresh_from_db()
        self.assertEqual(batch.state, 'reconciliation')
        first = batch.parts.get(ordinal=1)
        self.assertFalse(first.events.filter(kind='not_transmitted').exists())
        self.assertEqual(first.job.state, 'reconciliation')
        self.assertEqual(list(Reservation.objects.filter(job=first.job).values_list('state', flat=True)), ['held'])

    def test_control_with_the_credential_every_part_leaves_once_and_the_form_is_adopted(self):
        batch = self.admit()
        sent = []

        def handler(request):
            sent.append(request)
            raw = batch_response(batch.plan, len(sent))
            raw.update(type='message', role='assistant', stop_sequence=None, stop_details=None)
            return httpx.Response(200, json=raw, headers={'request-id': f'req_synthetic_{len(sent)}'})
        with synthetic_credential(), patch('socket.socket.connect', side_effect=AssertionError('Network denied')), \
                over_mock_transport(handler):
            for _ in range(3):
                self.assertTrue(jobs.run_one())
            self.assertFalse(jobs.run_one())
        batch.refresh_from_db()
        self.assertEqual(batch.state, 'succeeded', batch.error)
        self.assertEqual(len(sent), 2)
        self.assertTrue(all(request.headers.get('x-api-key') == SYNTHETIC_KEY for request in sent))
        self.assertEqual(Usage.objects.filter(job__generation_part__batch=batch).count(), 2)
        self.assertFalse(Reservation.objects.filter(job__generation_part__batch=batch, state='held').exists())


class NoCredentialNarrative(DeniedNetwork, SimpleTestCase):
    """MONEY-2, the WM narrative path: the same send outside its guard, raising into the same run_one classification as
    the default path. RED on bf8f7b78: nothing recognised the SDK's request-build refusal, so run_one kept the hold."""

    def setUp(self):
        super().setUp()
        self.deny_network()

    def test_narrative_without_a_credential_is_proved_untransmitted(self):
        from core import jobs as single
        from .test_wm_narrative import FIELDS, REQUIREMENTS, SFJ
        from .test_wm_narrative_sonnet5 import SETTINGS as NARRATIVE
        # Caught by hand: assertRaises strips the traceback, and the traceback is the proof being tested.
        def raised():
            try:
                g.generate(SFJ, FIELDS, g.configuration(), requirements=REQUIREMENTS)
            except TypeError as error:
                return error
            self.fail('generate() did not raise')
        with override_settings(**NARRATIVE), no_provider_credential():
            refused = raised()
        self.assertEqual(self.connects, [])
        self.assertIn('Could not resolve authentication method', str(refused))
        self.assertTrue(getattr(single, 'never_transmitted', lambda error: False)(refused))
        # Control: the same class and message from anywhere but the SDK's own validation proves nothing.
        with override_settings(**NARRATIVE), patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.side_effect = TypeError(str(refused))
            foreign = raised()
        self.assertFalse(single.never_transmitted(foreign))

    def test_control_narrative_with_the_credential_sends_once(self):
        from .test_wm_narrative import FIELDS, REQUIREMENTS, SFJ
        from .test_wm_narrative_sonnet5 import SETTINGS as NARRATIVE
        sent = []
        with override_settings(**NARRATIVE), synthetic_credential(), over_mock_transport(reply_with_empty_selections(sent)):
            raw, cost, *_ = g.generate(SFJ, FIELDS, g.configuration(), requirements=REQUIREMENTS)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].headers.get('x-api-key'), SYNTHETIC_KEY)
        self.assertGreater(cost, 0)
        self.assertEqual(self.connects, [])
