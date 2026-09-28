"""Retention/preservation locks against ordinary clinician, custodian and administrator flows.

Real PostgreSQL transactions on separate connections (TransactionTestCase and threads): a deadlock only exists
between two sessions. Every input is synthetic; no provider, payment or network request is made.
"""
import os
import threading
import time
import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, connections
from django.test import Client, TransactionTestCase, override_settings
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from core import billing, retention, views
from core.billing import reserve
from core.models import Encounter, Job, Reservation, RetentionHold, Wallet
from core.security import private_path
from core.tests.audio_fixtures import wav_bytes
from core.tests.test_billing_boundary import LIVE
from core.tests.test_recording_limit import STANDARD_ENV
from core.tests.test_retention_preservation import ISOLATED, Fixture

LOCKED = dict(ISOLATED, **LIVE)


def in_thread(target):
    """Run one request or transaction on its own database connection; keep its outcome or exception."""
    outcome = {}

    def run():
        try:
            outcome['value'] = target()
        except BaseException as error:  # the test asserts on it; nothing may be lost in the thread
            outcome['error'] = error
        finally:
            connections.close_all()
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, outcome


def wait_for_blocked_backend(timeout=15):
    """True once another backend waits for a lock (row, transaction or advisory) held elsewhere."""
    deadline = time.monotonic() + timeout
    with connection.cursor() as cursor:
        while time.monotonic() < deadline:
            cursor.execute('SELECT count(*) FROM pg_locks WHERE NOT granted AND pid<>pg_backend_pid()')
            if cursor.fetchone()[0]:
                return True
            time.sleep(.02)
    return False


def pause_after(action, paused, resume):
    """An audit wrapper that stops the calling transaction right after it records `action`."""
    real = views.audit

    def audit(actor, name, *args, **kwargs):
        row = real(actor, name, *args, **kwargs)
        if name == action and not paused.is_set():
            paused.set()
            resume.wait(30)
        return row
    return audit


class LockFlowFixture(Fixture):
    def setUp(self):
        self.setup_records()
        self.user, self.organization, self.department, self.patient = self.scope[:4]

    def doctor(self):
        client = Client(raise_request_exception=False)
        client.force_login(self.user)
        return client

    def custodian_client(self):
        device = TOTPDevice.objects.create(user=self.admin, name='Synthetic authenticator', confirmed=True)
        client = Client(raise_request_exception=False)
        client.force_login(self.admin)
        session = client.session
        session['otp_device_id'] = device.persistent_id
        session.save()
        return client

    def draft(self):
        return Encounter.objects.create(department=self.department, patient=self.patient,
                                        template_version=self.encounter.template_version, created_by=self.user,
                                        notes='', service_date=self.encounter.service_date)

    def orphaned_recordings(self):
        """Recordings in private storage that no job owns."""
        root = Path(settings.MEDIA_ROOT) / 'audio'
        stored = ['audio/' + path.name for path in root.iterdir()] if root.is_dir() else []
        owned = set(Job.objects.values_list('input_path', flat=True))
        return [name for name in stored if name not in owned]

    def recording(self, tag):
        return SimpleUploadedFile(f'{tag}.wav', wav_bytes(seconds=2, tag=tag), content_type='audio/wav')

    def finish(self, *threads):
        for thread in threads:
            thread.join(60)
            self.assertFalse(thread.is_alive(), 'a synthetic request never finished')


@override_settings(**LOCKED)
class HeldJobResolutionAgainstVoiceUpload(LockFlowFixture, TransactionTestCase):
    """RF-1. Reproduce: a held job (reconciliation, $1 reserved on the promo wallet) is resolved by an administrator,
    paused inside release() after the 'usage.release' audit (the wallet row is locked); the same clinician uploads a
    2 s recording to an empty draft and blocks on that wallet; the administrator resumes.
    RED on bf8f7b78: the upload is the deadlock victim (HTTP 500) and its recording is left in private storage with no
    job; release() locked the wallets before job.save() took the preservation lock, reserve() takes them the other way.
    """

    def test_resolving_a_held_job_and_the_same_payers_voice_upload_serialize(self):
        held = Job.objects.create(encounter=self.encounter, user=self.user, request_key='rf1-held', config={'mode': 'live'})
        reserve(held, charge_limit=Decimal('1'))
        Job.objects.filter(pk=held.pk).update(state='reconciliation')
        draft = self.draft()
        admin, doctor = self.custodian_client(), self.doctor()
        real = billing.audit
        paused, resume = threading.Event(), threading.Event()

        def audit(actor, action, *args, **kwargs):
            row = real(actor, action, *args, **kwargs)
            if action == 'usage.release' and not paused.is_set():
                paused.set()
                resume.wait(30)
            return row
        with patch.dict(os.environ, STANDARD_ENV), patch('core.billing.audit', side_effect=audit):
            quote = doctor.get(f'/encounters/{draft.pk}/').context['usage_quote']
            resolving, resolved = in_thread(lambda: admin.post(f'/console/jobs/{held.pk}/resolve/', {
                'outcome': 'release_no_cost', 'evidence_note': 'Synthetic console shows no provider request'}))
            try:
                self.assertTrue(paused.wait(15), 'the resolution never reached release()')
                uploading, uploaded = in_thread(lambda: doctor.post(f'/encounters/{draft.pk}/voice/', {
                    'audio': self.recording('rf1'), 'consent': 'on', 'usage_quote': quote}))
                blocked = wait_for_blocked_backend()
            finally:
                resume.set()
            self.finish(resolving, uploading)
        self.assertTrue(blocked, 'the upload never waited for the resolution')
        self.assertNotIn('error', resolved, resolved.get('error'))
        self.assertNotIn('error', uploaded, uploaded.get('error'))
        self.assertEqual(resolved['value'].status_code, 302)
        self.assertEqual(uploaded['value'].status_code, 302)
        queued = Job.objects.get(encounter=draft, kind='transcription')
        self.assertEqual(queued.state, 'queued')
        self.assertTrue(private_path(queued.input_path).is_file())
        self.assertEqual(self.orphaned_recordings(), [])
        held.refresh_from_db()
        self.assertEqual(held.state, 'failed')
        self.assertEqual(set(Reservation.objects.filter(job=held).values_list('state', flat=True)), {'released'})
        promo = Wallet.objects.get(user=self.user, kind='promo')
        self.assertEqual(promo.reserved, sum(Reservation.objects.filter(job=queued, wallet=promo, state='held')
                                              .values_list('amount', flat=True), Decimal(0)))


@override_settings(**LOCKED)
class FailedUploadNeverStrandsItsRecording(LockFlowFixture, TransactionTestCase):
    """RF-1, second half. Reproduce: the upload's enqueue fails with a database error (the deadlock victim's
    OperationalError) after the recording was stored. RED on bf8f7b78: the view caught only ValidationError, so the
    clinician got a 500 and the recording stayed in private storage with no job (the reaper only covers over-limit
    quotes). enqueue is one transaction, so nothing was queued, held, sent or charged: say so, and remove the upload."""

    def test_a_database_error_while_queuing_is_a_handled_refusal_and_removes_the_upload(self):
        from django.db import OperationalError
        draft = self.draft()
        doctor = self.doctor()
        with patch.dict(os.environ, STANDARD_ENV):
            quote = doctor.get(f'/encounters/{draft.pk}/').context['usage_quote']
            with patch('core.views.enqueue', side_effect=OperationalError('synthetic deadlock detected')):
                response = doctor.post(f'/encounters/{draft.pk}/voice/', {
                    'audio': self.recording('rf1-db'), 'consent': 'on', 'usage_quote': quote})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(self.orphaned_recordings(), [])
            self.assertFalse(Job.objects.filter(encounter=draft).exists())
            page = doctor.get(response['Location'])
            self.assertContains(page, 'Nothing was sent or charged')
            # Positive control: the same upload without the failure is queued and keeps its recording.
            quote = page.context['usage_quote']
            queued = doctor.post(f'/encounters/{draft.pk}/voice/', {
                'audio': self.recording('rf1-db-ok'), 'consent': 'on', 'usage_quote': quote})
        self.assertEqual(queued.status_code, 302)
        job = Job.objects.get(encounter=draft, kind='transcription')
        self.assertTrue(private_path(job.input_path).is_file())
        self.assertEqual(self.orphaned_recordings(), [])

    def test_an_unexpected_error_is_still_reported_but_never_strands_the_upload(self):
        draft = self.draft()
        doctor = self.doctor()
        with patch.dict(os.environ, STANDARD_ENV):
            quote = doctor.get(f'/encounters/{draft.pk}/').context['usage_quote']
            with patch('core.views.enqueue', side_effect=RuntimeError('synthetic defect')):
                response = doctor.post(f'/encounters/{draft.pk}/voice/', {
                    'audio': self.recording('rf1-defect'), 'consent': 'on', 'usage_quote': quote})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.orphaned_recordings(), [])
        self.assertFalse(Job.objects.filter(encounter=draft).exists())


# The global lock order (core.retention): the preservation lock before any Reservation or Wallet row lock.
LOCK_HELD = ("SELECT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory' AND pid=pg_backend_pid() AND granted "
             "AND classid::bigint=%s AND objid::bigint=%s AND objsubid=1)")


class MoneyAfterPreservation:
    """A connection execute wrapper: every Reservation/Wallet row lock must find LOCK_KEY already held by its own
    transaction. It counts what it checked, so a flow that never locks money cannot pass vacuously."""

    def __init__(self):
        self.checked, self.violations, self.inside = 0, [], False

    def __call__(self, execute, sql, params, many, context):
        if not self.inside and 'FOR UPDATE' in sql and ('FROM "core_wallet"' in sql or 'FROM "core_reservation"' in sql):
            self.inside = True
            try:
                with context['connection'].cursor() as cursor:
                    cursor.execute(LOCK_HELD, [retention.LOCK_KEY >> 32, retention.LOCK_KEY & 0xffffffff])
                    held = cursor.fetchone()[0]
            finally:
                self.inside = False
            self.checked += 1
            if not held:
                self.violations.append(sql[sql.index(' FROM '):][:40])
        return execute(sql, params, many, context)


from core import batch_jobs  # noqa: E402
from core.tests.test_generation_batch import BatchFixture, SETTINGS as BATCH_SETTINGS  # noqa: E402


@override_settings(**BATCH_SETTINGS)
class BatchStopAgainstVoiceUpload(BatchFixture, TransactionTestCase):
    """RF-1, the batch shapes the finding named from reading (batch_jobs.py:210-211, resolve_view).
    Reproduce: the clinician cancels a queued complete-form batch (cancel_child -> stop()), paused inside release() after
    its 'usage.release' audit; the same clinician uploads a 2 s recording to an empty draft; the cancellation resumes.
    RED on bf8f7b78: stop() released the part's funds (wallet locked) before job.save() took the preservation lock, the
    upload held that lock and waited for the wallet, and one of the two was aborted as a deadlock victim."""

    def draft(self):
        return Encounter.objects.create(department=self.department, patient=self.patient,
                                        template_version=self.encounter.template_version, created_by=self.user,
                                        notes='', service_date=self.encounter.service_date)

    def orphaned_recordings(self):
        return LockFlowFixture.orphaned_recordings(self)

    def test_cancelling_a_queued_batch_and_the_same_payers_voice_upload_serialize(self):
        batch = self.admit()
        draft = self.draft()
        doctor = Client(raise_request_exception=False)
        doctor.force_login(self.user)
        real = billing.audit
        paused, resume = threading.Event(), threading.Event()

        def audit(actor, action, *args, **kwargs):
            row = real(actor, action, *args, **kwargs)
            if action == 'usage.release' and not paused.is_set():
                paused.set()
                resume.wait(30)
            return row
        with patch.dict(os.environ, STANDARD_ENV), patch('core.billing.audit', side_effect=audit):
            quote = doctor.get(f'/encounters/{draft.pk}/').context['usage_quote']
            cancelling, cancelled = in_thread(lambda: batch_jobs.cancel_child(batch.parts.first().job, self.user))
            try:
                self.assertTrue(paused.wait(15), 'the cancellation never reached release()')
                uploading, uploaded = in_thread(lambda: doctor.post(f'/encounters/{draft.pk}/voice/', {
                    'audio': SimpleUploadedFile('rf1-batch.wav', wav_bytes(seconds=2, tag='rf1-batch'),
                                                content_type='audio/wav'),
                    'consent': 'on', 'usage_quote': quote}))
                blocked = wait_for_blocked_backend()
            finally:
                resume.set()
            for thread in (cancelling, uploading):
                thread.join(60)
                self.assertFalse(thread.is_alive())
        self.assertTrue(blocked, 'the upload never waited for the cancellation')
        self.assertNotIn('error', cancelled, cancelled.get('error'))
        self.assertNotIn('error', uploaded, uploaded.get('error'))
        self.assertEqual(uploaded['value'].status_code, 302)
        batch.refresh_from_db()
        self.assertEqual(batch.state, 'cancelled')
        self.assertFalse(Reservation.objects.filter(job__generation_part__batch=batch, state='held').exists())
        queued = Job.objects.get(encounter=draft, kind='transcription')
        self.assertEqual(queued.state, 'queued')
        self.assertEqual(self.orphaned_recordings(), [])

    def test_every_money_lock_in_a_batch_stop_follows_the_preservation_lock(self):
        """The order itself, without a second actor: a batch stop (cancel_child). RED on bf8f7b78: release() locks
        the part's reservation and wallet rows before the transaction holds the preservation lock."""
        batch = self.admit()
        order = MoneyAfterPreservation()
        with connection.execute_wrapper(order):
            batch_jobs.cancel_child(batch.parts.first().job, self.user)
        self.assertGreater(order.checked, 0)
        self.assertEqual(order.violations, [], 'batch stop locked money before the preservation lock')
        batch.refresh_from_db()
        self.assertEqual(batch.state, 'cancelled')

    def test_every_money_lock_in_a_batch_closeout_follows_the_preservation_lock(self):
        """An administrator's closeout of an uncertain part (resolve_view: release, job.save, absorb, stop).
        RED on bf8f7b78: release() locks money before job.save() takes the preservation lock."""
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory
        batch = self.admit()
        calls, call = self.fake(batch, fail_at=2)
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect = call
            batch_jobs.run_one()
            batch_jobs.run_one()
        uncertain = batch.parts.get(ordinal=2).job
        uncertain.refresh_from_db()
        self.assertEqual(uncertain.state, 'reconciliation')
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        request = RequestFactory().post('/console/jobs/resolve/', {
            'outcome': 'release_no_cost', 'evidence_note': 'Synthetic provider console evidence: request not charged'})
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)
        order = MoneyAfterPreservation()
        with connection.execute_wrapper(order):
            self.assertEqual(batch_jobs.resolve_view(request, uncertain.pk).status_code, 302)
        self.assertGreater(order.checked, 0)
        self.assertEqual(order.violations, [], 'batch closeout locked money before the preservation lock')
        self.assertFalse(Reservation.objects.filter(job__generation_part__batch=batch, state='held').exists())
        self.assertEqual(len(calls), 2)


@override_settings(**LOCKED)
class JobMoneyLockOrder(LockFlowFixture, TransactionTestCase):
    """The global order on the single-job billing paths: queue (reserve), cancel, administrator resolution (release),
    worker settlement (settle) and absorption. Each wallet or reservation lock follows the preservation lock."""

    def checked(self, action):
        order = MoneyAfterPreservation()
        with connection.execute_wrapper(order):
            result = action()
        self.assertGreater(order.checked, 0, 'the flow never locked money; the check would be vacuous')
        self.assertEqual(order.violations, [])
        return result

    def test_queue_cancel_resolve_settle_and_absorb(self):
        from core.billing import absorb_failed_job, settle
        from core.jobs import cancel, enqueue
        draft = self.draft()
        Encounter.objects.filter(pk=draft.pk).update(notes='Symptoms: no chest pain')
        draft.refresh_from_db()
        queued = self.checked(lambda: enqueue(draft, self.user))
        self.checked(lambda: cancel(queued, self.user))
        self.assertEqual(Job.objects.get(pk=queued.pk).state, 'cancelled')
        held = Job.objects.create(encounter=self.encounter, user=self.user, request_key='order-held', config={'mode': 'live'})
        self.checked(lambda: reserve(held, charge_limit=Decimal('1')))
        Job.objects.filter(pk=held.pk).update(state='reconciliation')
        admin = self.custodian_client()
        response = self.checked(lambda: admin.post(f'/console/jobs/{held.pk}/resolve/', {
            'outcome': 'release_no_cost', 'evidence_note': 'Synthetic console shows no provider request'}))
        self.assertEqual(response.status_code, 302)
        settled = Job.objects.create(encounter=self.encounter, user=self.user, request_key='order-settled')
        reserve(settled, Decimal('0.2'))
        units = {'input_tokens': 100, 'output_tokens': 0, 'cached_input_tokens': 0, 'cache_creation_tokens': 0}
        self.checked(lambda: settle(settled, Decimal('0.1'), units, {'input_per_million': '1000'}, 'anthropic:synthetic',
                                    'req_order', provider_resource_id='msg_order'))
        Job.objects.filter(pk=settled.pk).update(state='failed', error='platform_failure: synthetic')
        cost = self.checked(lambda: absorb_failed_job(settled))
        self.assertEqual(cost.amount, Decimal('0.1'))


@override_settings(**LOCKED)
class HoldCreationAgainstClinicalWrites(LockFlowFixture, TransactionTestCase):
    """RF-2. Reproduce (the finding's input): the clinician POSTs changed notes at the current revision, paused right
    after its 'encounter.notes_saved' audit, so e.save() has taken the preservation lock and the transaction is open;
    the custodian calls retention.create_hold(admin, 'department', E.department_id, 'a'*64, uuid4()); the clinician
    resumes and commits. RED on bf8f7b78: create_hold locked the department FOR UPDATE and waited for the preservation
    lock; the clinician's commit-time foreign-key check (FOR KEY SHARE on that department, for its audit rows) waited
    for the hold: deadlock, the hold is not recorded (a 500 on the page/API). The same shape for an organization hold
    (audit organization key) and a patient hold (a new encounter's patient key)."""

    def save_notes(self, client):
        return lambda: client.post(f'/encounters/{self.encounter.pk}/notes/', {
            'notes': 'Symptoms: SYNTHETIC CORRECTION, no chest pain', 'revision': str(self.encounter.revision)})

    def create_encounter(self, client):
        return lambda: client.post('/encounters/new/', {
            'patient': str(self.patient.pk), 'template_version': str(self.encounter.template_version_id), 'notes': '',
            'service_date': self.encounter.service_date.isoformat(), 'synthetic_only': 'on'})

    def race(self, write, action, hold):
        paused, resume = threading.Event(), threading.Event()
        with patch('core.views.audit', side_effect=pause_after(action, paused, resume)):
            writing, written = in_thread(write)
            try:
                self.assertTrue(paused.wait(15), 'the clinical write never reached its audit')
                holding, held = in_thread(hold)
                blocked = wait_for_blocked_backend()
            finally:
                resume.set()
            self.finish(writing, holding)
        self.assertTrue(blocked, 'hold creation never waited for the clinical write')
        self.assertNotIn('error', written, written.get('error'))
        self.assertNotIn('error', held, held.get('error'))
        self.assertEqual(written['value'].status_code, 302)
        return held['value']

    def direct_hold(self, scope, target):
        return lambda: retention.create_hold(self.admin, scope, target, 'a' * 64, uuid.uuid4())

    def assert_saved_then_held(self, hold, scope):
        self.assertIsInstance(hold, RetentionHold)
        self.assertEqual(hold.scope, scope)
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.notes, 'Symptoms: SYNTHETIC CORRECTION, no chest pain')
        # The save committed first, so the hold has nothing of it to preserve; the next correction is preserved.
        from core.models import PreservedRecord
        self.assertFalse(PreservedRecord.objects.exists())
        response = self.doctor().post(f'/encounters/{self.encounter.pk}/notes/', {
            'notes': 'Symptoms: SYNTHETIC SECOND CORRECTION', 'revision': str(self.encounter.revision)})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PreservedRecord.objects.get(source_table='core_encounter').prior_record['notes'],
                         'Symptoms: SYNTHETIC CORRECTION, no chest pain')

    def test_department_hold_waits_for_an_in_flight_notes_save(self):
        hold = self.race(self.save_notes(self.doctor()), 'encounter.notes_saved', self.direct_hold('department', self.department.pk))
        self.assert_saved_then_held(hold, 'department')

    def test_organization_hold_waits_for_an_in_flight_notes_save(self):
        hold = self.race(self.save_notes(self.doctor()), 'encounter.notes_saved', self.direct_hold('organization', self.organization.pk))
        self.assert_saved_then_held(hold, 'organization')

    def test_patient_hold_waits_for_an_in_flight_encounter_creation(self):
        before = set(Encounter.objects.values_list('pk', flat=True))
        hold = self.race(self.create_encounter(self.doctor()), 'encounter.create', self.direct_hold('patient', self.patient.pk))
        self.assertEqual(hold.scope, 'patient')
        created = Encounter.objects.exclude(pk__in=before).get()
        self.assertEqual(created.patient_id, self.patient.pk)

    def test_document_hold_still_waits_for_the_document_lock(self):
        """Positive control: an encounter hold was never part of the cycle (the save holds the encounter row, and the
        hold waits for it before the preservation lock). It must keep serializing the same way."""
        hold = self.race(self.save_notes(self.doctor()), 'encounter.notes_saved', self.direct_hold('encounter', self.encounter.pk))
        self.assert_saved_then_held(hold, 'encounter')

    def test_the_retention_page_records_a_department_hold_raced_with_a_notes_save(self):
        custodian = self.custodian_client()
        response = self.race(self.save_notes(self.doctor()), 'encounter.notes_saved', lambda: custodian.post('/console/retention/', {
            'action': 'create', 'scope': 'department', 'target': str(self.department.pk), 'authority_sha256': 'b' * 64,
            'request_key': str(uuid.uuid4()), 'confirmed': 'on'}))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RetentionHold.objects.get().department_id, self.department.pk)

    def test_a_database_failure_while_recording_a_hold_is_a_handled_refusal(self):
        """Reproduce: hold creation or release aborted by the database (a deadlock victim, a lost connection).
        RED on bf8f7b78: the page and the JSON API caught only ValidationError, so the custodian got a 500. The
        instruction is one transaction, so nothing was recorded: the custodian is told so and can retry."""
        from django.db import OperationalError
        custodian = self.custodian_client()
        form = {'action': 'create', 'scope': 'department', 'target': str(self.department.pk), 'authority_sha256': 'c' * 64,
                'request_key': str(uuid.uuid4()), 'confirmed': 'on'}
        payload = '{"scope":"department","target":"%s","authority_sha256":"%s","request_key":"%s"}' % (
            self.department.pk, 'c' * 64, uuid.uuid4())
        with patch('core.retention.create_hold', side_effect=OperationalError('synthetic deadlock detected')):
            page = custodian.post('/console/retention/', form)
            api = custodian.post('/console/retention/holds/', payload, content_type='application/json')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'was not recorded')
        self.assertEqual(api.status_code, 503)
        self.assertEqual(api.json(), {'error': 'Preservation instruction not recorded. Nothing changed; retry.'})
        self.assertFalse(RetentionHold.objects.exists())
        # Positive control: the same page records the hold when the database accepts it.
        self.assertEqual(custodian.post('/console/retention/', form).status_code, 302)
        hold = RetentionHold.objects.get()
        second = Client(raise_request_exception=False)
        device = TOTPDevice.objects.create(user=self.second, name='Synthetic second authenticator', confirmed=True)
        second.force_login(self.second)
        session = second.session
        session['otp_device_id'] = device.persistent_id
        session.save()
        with patch('core.retention.release_hold', side_effect=OperationalError('synthetic deadlock detected')):
            released = second.post(f'/console/retention/holds/{hold.pk}/release/', '{"authority_sha256":"%s"}' % ('d' * 64),
                                   content_type='application/json')
        self.assertEqual(released.status_code, 503)
        self.assertFalse(hasattr(RetentionHold.objects.get(), 'release'))


from core import disposition_execution as x, models as m  # noqa: E402
from core.tests.test_disposition_execution import ExecutionFixture  # noqa: E402


@override_settings(**ISOLATED)
class DispositionAgainstClinicianRequests(ExecutionFixture, TransactionTestCase):
    """RF-3. Reproduce (the finding's input): a prospective policy is admitted and an exact empty draft (older than
    minimum_age_seconds=60) is prepared and approved by two distinct custodians. The clinician GETs the draft (a view
    is allowed), then POSTs a 2 s WAV to it; right after store_upload returns, x.execute(admin, instruction,
    checkpoint) commits on another connection. RED on bf8f7b78: enqueue's unscoped Encounter select_for_update().get()
    raises Encounter.DoesNotExist, an unhandled 500, and the recording outlives the draft whose disposal was ordered."""

    def setUp(self):
        self.setup_execution()

    def orphaned_recordings(self):
        return LockFlowFixture.orphaned_recordings(self)

    def disposed_during(self, name, instruction):
        """Patch views.<name> so the approved disposition commits, on its own connection, right after it returns."""
        real = getattr(views, name)
        executed = {}

        def racing(*args, **kwargs):
            result = real(*args, **kwargs)
            thread, outcome = in_thread(lambda: x.execute(self.admin, instruction.pk, self.genesis))
            thread.join(30)
            executed.update(outcome)
            return result
        return patch(f'core.views.{name}', side_effect=racing), executed

    def clinician(self):
        client = Client(raise_request_exception=False)
        client.force_login(self.scope[0])
        return client

    def assert_disposed(self, executed, row):
        self.assertNotIn('error', executed, executed.get('error'))
        self.assertEqual(executed['value'].outcome, 'empty_draft_deleted')
        self.assertFalse(m.Encounter.objects.filter(pk=row.pk).exists())
        self.assertFalse(m.Job.objects.filter(encounter_id=row.pk).exists())

    def test_a_recording_uploaded_while_the_draft_is_disposed_is_refused_and_removed(self):
        row, instruction = self.approved()
        doctor = self.clinician()
        with patch.dict(os.environ, STANDARD_ENV):
            page = doctor.get(f'/encounters/{row.pk}/')
            self.assertEqual(page.status_code, 200)
            quote = page.context.get('usage_quote')
            racing, executed = self.disposed_during('store_upload', instruction)
            with racing:
                response = doctor.post(f'/encounters/{row.pk}/voice/', {
                    'audio': SimpleUploadedFile('rf3.wav', wav_bytes(seconds=2, tag='rf3'), content_type='audio/wav'),
                    'consent': 'on', **({'usage_quote': quote} if quote else {})})
        self.assert_disposed(executed, row)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.orphaned_recordings(), [])
        followed = doctor.get(response['Location'])
        self.assertEqual(followed.status_code, 200)
        self.assertContains(followed, 'no longer available')

    def test_a_generation_requested_while_the_draft_is_disposed_is_refused(self):
        """generate_view reaches the same lookup (the finding, from reading)."""
        row, instruction = self.approved()
        doctor = self.clinician()
        racing, executed = self.disposed_during('usage_quote', instruction)
        with racing:
            response = doctor.post(f'/encounters/{row.pk}/generate/', {})
        self.assert_disposed(executed, row)
        self.assertEqual(response.status_code, 302)
        self.assertContains(doctor.get(response['Location']), 'no longer available')

    def test_queueing_on_a_document_disposed_after_it_was_read_is_a_refusal_not_a_crash(self):
        """Both enqueue routes lock the row the caller read earlier; a disposed row is a refusal (ValidationError),
        never Encounter.DoesNotExist. The complete-form route is reached through jobs.enqueue, its only caller."""
        from django.core.exceptions import ValidationError
        from core import batch_jobs
        from core.jobs import enqueue
        row, instruction = self.approved()
        stale = m.Encounter.objects.get(pk=row.pk)
        x.execute(self.admin, instruction.pk, self.genesis)
        with self.subTest(route='single request'), self.assertRaisesMessage(ValidationError, 'no longer available'):
            enqueue(stale, self.scope[0])
        with self.subTest(route='complete-form batch'), patch('core.generation_batch.needed', return_value=True), \
                patch.object(batch_jobs, 'enqueue', wraps=batch_jobs.enqueue) as batch:
            with self.assertRaisesMessage(ValidationError, 'no longer available'):
                enqueue(stale, self.scope[0])
            batch.assert_not_called()
        self.assertFalse(m.Job.objects.exists())

    def test_positive_control_an_undisposed_draft_still_queues_its_recording(self):
        row = self.empty()
        doctor = self.clinician()
        with patch.dict(os.environ, STANDARD_ENV):
            quote = doctor.get(f'/encounters/{row.pk}/').context.get('usage_quote')
            response = doctor.post(f'/encounters/{row.pk}/voice/', {
                'audio': SimpleUploadedFile('rf3-ok.wav', wav_bytes(seconds=2, tag='rf3-ok'), content_type='audio/wav'),
                'consent': 'on', **({'usage_quote': quote} if quote else {})})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], f'/encounters/{row.pk}/')
        job = m.Job.objects.get(encounter=row, kind='transcription')
        self.assertTrue(private_path(job.input_path).is_file())
        self.assertEqual(self.orphaned_recordings(), [])
