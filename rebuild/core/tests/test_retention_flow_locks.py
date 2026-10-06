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
from core.tests.surfaces import SurfaceClient
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
        client = SurfaceClient(raise_request_exception=False)
        client.force_login(self.user)
        return client

    def custodian_client(self):
        device = TOTPDevice.objects.create(user=self.admin, name='Synthetic authenticator', confirmed=True)
        client = SurfaceClient(raise_request_exception=False)
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
        doctor = SurfaceClient(raise_request_exception=False)
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
        second = SurfaceClient(raise_request_exception=False)
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
        client = SurfaceClient(raise_request_exception=False)
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
            # Admission now holds the encounter before storing bytes. Disposition must finish in the remaining
            # pre-lock window; waiting synchronously inside store_upload would deadlock the test's own schedule.
            racing, executed = self.disposed_during('VoiceForm', instruction)
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

    def test_disposition_waits_for_a_recording_admitted_first_and_preserves_its_job(self):
        """Opposite lock order: an approved empty draft becomes nonempty while disposition waits, so it refuses."""
        from django.core.exceptions import ValidationError
        row, instruction = self.approved()
        doctor = self.clinician()
        paused, resume = threading.Event(), threading.Event()
        real_store = views.store_upload
        def pause_stored(*args, **kwargs):
            result = real_store(*args, **kwargs)
            paused.set()
            if not resume.wait(15):raise RuntimeError('Synthetic upload deadline expired')
            return result
        with patch.dict(os.environ, STANDARD_ENV), patch('core.views.store_upload', side_effect=pause_stored):
            quote = doctor.get(f'/encounters/{row.pk}/').context['usage_quote']
            uploading, uploaded = in_thread(lambda: doctor.post(f'/encounters/{row.pk}/voice/', {
                'audio': SimpleUploadedFile('rf3-first.wav', wav_bytes(seconds=2, tag='rf3-first'), content_type='audio/wav'),
                'consent': 'on', 'usage_quote': quote}))
            try:
                self.assertTrue(paused.wait(10), 'upload never reached private storage')
                disposing, disposed = in_thread(lambda: x.execute(self.admin, instruction.pk, self.genesis))
                blocked = wait_for_blocked_backend(timeout=2)
            finally:
                resume.set()
            for thread in (uploading, disposing):
                thread.join(20)
                self.assertFalse(thread.is_alive(), 'bounded synthetic admission race did not finish')
        self.assertTrue(blocked, 'disposition did not wait for recording admission')
        self.assertNotIn('error', uploaded, uploaded.get('error'))
        self.assertEqual(uploaded['value'].status_code, 302)
        self.assertIsInstance(disposed.get('error'), ValidationError)
        self.assertTrue(m.Encounter.objects.filter(pk=row.pk).exists())
        job = m.Job.objects.get(encounter_id=row.pk, kind='transcription')
        self.assertTrue(private_path(job.input_path).exists())
        self.assertEqual(self.orphaned_recordings(), [])
        self.assertFalse(m.DispositionTombstone.objects.filter(target_id=str(row.pk)).exists())

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


from datetime import timedelta  # noqa: E402

from core.models import Invitation, Membership, Usage  # noqa: E402
from core.security import digest, token  # noqa: E402
from core.tests.test_recording_limit import EXPENSIVE_ENV  # noqa: E402


def paused_after_account_lock(action, paused, resume):
    """Run `action` on its thread's connection, stopping right after the first row lock it takes on an account
    (core_user, FOR UPDATE or FOR NO KEY UPDATE) until `resume` is set."""
    def wrapper(execute, sql, params, many, context):
        result = execute(sql, params, many, context)
        if not paused.is_set() and 'FROM "core_user"' in sql and sql.rstrip().endswith(' UPDATE'):
            paused.set()
            resume.wait(30)
        return result

    def run():
        with connection.execute_wrapper(wrapper):
            return action()
    return run


def finished_or_blocked(thread, timeout=15):
    """'finished' once the thread ends, 'blocked' once any other backend waits for a lock, else 'timeout'."""
    deadline = time.monotonic() + timeout
    with connection.cursor() as cursor:
        while time.monotonic() < deadline:
            if not thread.is_alive():
                return 'finished'
            cursor.execute('SELECT count(*) FROM pg_locks WHERE NOT granted AND pid<>pg_backend_pid()')
            if cursor.fetchone()[0]:
                return 'blocked'
            time.sleep(.02)
    return 'timeout'


@override_settings(**LOCKED)
class InvitationAcceptanceAgainstTheSamePayersRequests(LockFlowFixture, TransactionTestCase):
    """RF-R1. Reproduce (the finding's input): an existing verified clinician U (funded promotional wallet, department
    D) holds a department invitation to D2 from D2's owner, and accepts it in a second tab while one of U's own
    requests runs: (a) a 2 s voice upload paused inside reserve() after its 'usage.reserve' audit (wallets locked,
    preservation lock held); (b) the acceptance paused in welcome_credit right after its account row lock, while U
    requests a generation; (c) the same, against the worker's settlement of U's running job.
    RED on 6035d2fa (and bf8f7b78): welcome_credit locked the account FOR UPDATE and then the promotional wallet, the
    reverse of U's requests, which lock the wallets and take FOR KEY SHARE on the account at commit (the deferred
    foreign-key checks of their job, reservation, usage and audit rows). (a) the acceptance is the deadlock victim
    (500, no membership); (b) the generation is (500: generate_view let the DatabaseError through, nothing queued);
    (c) settle() raises it, which run_one turns into a provider-completed job sent to reconciliation."""

    def setUp(self):
        super().setUp()
        owner, _, self.department2 = self.other[:3]
        Membership.objects.filter(user=owner, department=self.department2).update(role='owner')
        self.raw = token()
        self.invitation = Invitation.objects.create(
            email=self.user.email, department=self.department2, role='clinician', invited_by=owner,
            token_hash=digest(self.raw), expires_at=timezone.now() + timedelta(days=1))

    def accept(self, client):
        return lambda: client.post(f'/invite/{self.raw}/', {})

    def assert_accepted(self, outcome):
        self.assertNotIn('error', outcome, outcome.get('error'))
        self.assertEqual(outcome['value'].status_code, 302, getattr(outcome['value'], 'exc_info', None))
        self.assertEqual(outcome['value']['Location'], '/login/')
        self.assertTrue(Membership.objects.filter(user=self.user, department=self.department2, active=True).exists())
        self.invitation.refresh_from_db()
        self.assertIsNotNone(self.invitation.accepted_at)

    def test_positive_control_the_acceptance_alone_is_recorded(self):
        self.assert_accepted({'value': self.accept(self.doctor())()})

    def test_a_voice_upload_holding_the_wallets_and_the_acceptance_serialize(self):
        self.upload_raced_with(self.accept(self.doctor()))
        self.assert_accepted(self.raced)

    def test_a_voice_upload_holding_the_wallets_and_a_clinic_invitation_acceptance_serialize(self):
        """The clinic-owner invitation (core/clinic_invitations.py) locks the account itself before welcome_credit."""
        from core import clinic_invitations
        _, raw = clinic_invitations.issue(self.admin, self.user.email, 'Synthetic second clinic', 'Synthetic front desk')
        second_tab = self.doctor()
        self.upload_raced_with(lambda: second_tab.post(f'/invite/clinic/{raw}/', {}))
        self.assertNotIn('error', self.raced, self.raced.get('error'))
        self.assertEqual(self.raced['value'].status_code, 302, getattr(self.raced['value'], 'exc_info', None))
        self.assertTrue(Membership.objects.filter(user=self.user, role='owner', active=True,
                                                  department__organization__name='Synthetic second clinic').exists())

    def upload_raced_with(self, accept):
        """U's 2 s upload is paused in reserve() (wallets locked); `accept` runs in U's second tab; the upload resumes."""
        draft = self.draft()
        doctor = self.doctor()
        real = billing.audit
        paused, resume = threading.Event(), threading.Event()

        def audit(actor, action, *args, **kwargs):
            row = real(actor, action, *args, **kwargs)
            if action == 'usage.reserve' and not paused.is_set():
                paused.set()
                resume.wait(30)
            return row
        with patch.dict(os.environ, STANDARD_ENV), patch('core.billing.audit', side_effect=audit):
            quote = doctor.get(f'/encounters/{draft.pk}/').context['usage_quote']
            uploading, uploaded = in_thread(lambda: doctor.post(f'/encounters/{draft.pk}/voice/', {
                'audio': self.recording('rfr1-a'), 'consent': 'on', 'usage_quote': quote}))
            try:
                self.assertTrue(paused.wait(15), 'the upload never reached reserve()')
                accepting, self.raced = in_thread(accept)
                blocked = wait_for_blocked_backend()
            finally:
                resume.set()
            self.finish(uploading, accepting)
        self.assertTrue(blocked, 'the acceptance never waited for the upload')
        self.assertNotIn('error', uploaded, uploaded.get('error'))
        self.assertEqual(uploaded['value'].status_code, 302)
        queued = Job.objects.get(encounter=draft, kind='transcription')
        self.assertEqual(queued.state, 'queued')
        self.assertTrue(Reservation.objects.filter(job=queued, state='held').exists())
        self.assertEqual(self.orphaned_recordings(), [])

    def race_with_paused_acceptance(self, request):
        """The acceptance holds the account row lock (paused); `request` runs meanwhile; then the acceptance resumes."""
        paused, resume = threading.Event(), threading.Event()
        accepting, accepted = in_thread(paused_after_account_lock(self.accept(self.doctor()), paused, resume))
        try:
            self.assertTrue(paused.wait(15), 'the acceptance never locked the account')
            running, ran = in_thread(request)
            state = finished_or_blocked(running)
        finally:
            resume.set()
        self.finish(accepting, running)
        self.assertIn(state, ('finished', 'blocked'), 'the request neither finished nor waited')
        self.assert_accepted(accepted)
        self.assertNotIn('error', ran, ran.get('error'))
        return ran['value']

    def test_a_generation_and_the_acceptance_holding_the_account_serialize(self):
        draft = self.draft()
        Encounter.objects.filter(pk=draft.pk).update(notes='Symptoms: no chest pain')
        doctor = self.doctor()
        quote = doctor.get(f'/encounters/{draft.pk}/').context['usage_quote']
        response = self.race_with_paused_acceptance(lambda: doctor.post(f'/encounters/{draft.pk}/generate/', {
            'usage_quote': quote, 'revision': '0'}))
        self.assertEqual(response.status_code, 302, getattr(response, 'exc_info', None))
        self.assertEqual(response['Location'], f'/encounters/{draft.pk}/')
        self.assertTrue(Job.objects.filter(encounter=draft, kind='generation').exists(), 'the generation was not queued')
        job = Job.objects.get(encounter=draft, kind='generation')
        self.assertEqual(job.state, 'queued')
        self.assertTrue(Reservation.objects.filter(job=job, state='held').exists())
        self.assertContains(doctor.get(response['Location']), 'Generation queued')

    def test_the_workers_settlement_and_the_acceptance_holding_the_account_serialize(self):
        job = Job.objects.create(encounter=self.encounter, user=self.user, request_key='rfr1-settle')
        reserve(job, Decimal('0.2'))
        Job.objects.filter(pk=job.pk).update(state='running')
        units = {'input_tokens': 100, 'output_tokens': 0, 'cached_input_tokens': 0, 'cache_creation_tokens': 0}
        usage = self.race_with_paused_acceptance(lambda: billing.settle(
            Job.objects.get(pk=job.pk), Decimal('0.1'), units, {'input_per_million': '1000'}, 'anthropic:synthetic',
            'req_rfr1', provider_resource_id='msg_rfr1'))
        self.assertEqual(Usage.objects.get(job=job).pk, usage.pk)
        self.assertEqual(usage.charged_cost, Decimal('0.15'))
        self.assertFalse(Reservation.objects.filter(job=job, state='held').exists())


@override_settings(**LOCKED)
class QueueRequestsRefuseADatabaseFailureCleanly(LockFlowFixture, TransactionTestCase):
    """RF-R1, the victim half. Reproduce: a generation request, or the approval of an over-limit recording, whose
    enqueue transaction is aborted by the database (a deadlock victim's OperationalError). RED on 6035d2fa:
    generate_view and voice_approve caught only ValidationError, so the clinician got a 500. enqueue is one transaction,
    so nothing was queued, held, sent or charged: say so. An approved recording stays with its approval (the reaper
    removes it once the approval window ends), so the doctor can approve it again."""

    def test_a_generation_aborted_by_the_database_is_a_handled_refusal(self):
        from django.db import OperationalError
        draft = self.draft()
        Encounter.objects.filter(pk=draft.pk).update(notes='Symptoms: no chest pain')
        doctor = self.doctor()
        quote = doctor.get(f'/encounters/{draft.pk}/').context['usage_quote']
        with patch('core.views.enqueue', side_effect=OperationalError('synthetic deadlock detected')):
            response = doctor.post(f'/encounters/{draft.pk}/generate/', {'usage_quote': quote, 'revision': '0'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], f'/encounters/{draft.pk}/')
        self.assertFalse(Job.objects.filter(encounter=draft).exists())
        self.assertContains(doctor.get(response['Location']), 'Nothing was sent or charged')
        # Positive control: the same request is queued when the database accepts it.
        queued = doctor.post(f'/encounters/{draft.pk}/generate/', {'usage_quote': quote, 'revision': '0'})
        self.assertEqual(queued.status_code, 302)
        self.assertEqual(Job.objects.get(encounter=draft).state, 'queued')

    def test_an_approval_aborted_by_the_database_is_a_handled_refusal_and_can_be_approved_again(self):
        from django.db import OperationalError
        draft = self.draft()
        doctor = self.doctor()
        with patch.dict(os.environ, EXPENSIVE_ENV):
            quote = doctor.get(f'/encounters/{draft.pk}/').context['usage_quote']
            over = doctor.post(f'/encounters/{draft.pk}/voice/', {
                'audio': self.recording('rfr1-approve'), 'consent': 'on', 'usage_quote': quote})
            self.assertEqual(over.status_code, 409)
            approval = {'approval': over.context['approval'], 'decision': 'approve'}
            with patch('core.views.enqueue', side_effect=OperationalError('synthetic deadlock detected')):
                response = doctor.post(f'/encounters/{draft.pk}/voice/approve/', approval)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response['Location'], f'/encounters/{draft.pk}/')
            self.assertFalse(Job.objects.filter(encounter=draft).exists())
            self.assertContains(doctor.get(response['Location']), 'Nothing was sent or charged')
            # The quoted recording is still the approval's (not a stray): approving again queues it.
            again = doctor.post(f'/encounters/{draft.pk}/voice/approve/', approval)
        self.assertEqual(again.status_code, 302)
        job = Job.objects.get(encounter=draft, kind='transcription')
        self.assertTrue(private_path(job.input_path).is_file())
        self.assertEqual(self.orphaned_recordings(), [])


@override_settings(QUILLMD_PAYER_ROLE_GRANTED=True, **LOCKED)
class PayerChangeAgainstClinicalWritesAndSettlement(LockFlowFixture, TransactionTestCase):
    """RF-R2. Reproduce (the finding's input): with the payer role granted, a staff superuser custodian with an OTP
    session POSTs /console/departments/<D>/payer/ (organization_pays on, a reason, confirm) while (a) the clinician's
    POST /encounters/<E>/notes/ is paused after its 'encounter.notes_saved' audit, or (b) billing.settle(a job in D, 0.1)
    is paused after its 'usage.settle' audit; the paused side then resumes. Both hold the preservation lock and, at
    commit, take FOR KEY SHARE on D for their new rows' foreign keys (audit rows, the usage row).
    RED on 4192fc77: the payer change locked D FOR UPDATE and then waited for the preservation lock in D's trigger, so
    each side waited for the other and the payer change was the deadlock victim (500). (b) is new since RF-1's
    preservation_before_money() in settle; (a) is older."""

    def setUp(self):
        super().setUp()
        type(self.admin).objects.filter(pk=self.admin.pk).update(is_superuser=True)
        self.admin.refresh_from_db()

    def change_payer(self, client):
        return lambda: client.post(f'/console/departments/{self.department.pk}/payer/', {
            'organization_pays': 'on', 'reason': 'Synthetic payer change for a refutation probe', 'confirm': 'on'})

    def race(self, paused_side, paused, resume):
        custodian = self.custodian_client()
        running, ran = in_thread(paused_side)
        try:
            self.assertTrue(paused.wait(15), 'the clinical transaction never reached its pause')
            changing, changed = in_thread(self.change_payer(custodian))
            blocked = wait_for_blocked_backend()
        finally:
            resume.set()
        self.finish(running, changing)
        self.assertTrue(blocked, 'the payer change never waited for the paused transaction')
        self.assertNotIn('error', changed, changed.get('error'))
        self.assertEqual(changed['value'].status_code, 302, getattr(changed['value'], 'exc_info', None))
        self.department.refresh_from_db()
        self.assertTrue(self.department.organization_pays)
        self.assertTrue(Wallet.objects.filter(organization=self.organization, kind='paid').exists())
        self.assertNotIn('error', ran, ran.get('error'))
        return ran['value']

    def test_positive_control_the_payer_change_alone_is_recorded(self):
        response = self.change_payer(self.custodian_client())()
        self.assertEqual(response.status_code, 302)
        self.department.refresh_from_db()
        self.assertTrue(self.department.organization_pays)

    def test_the_payer_change_waits_for_an_in_flight_notes_save(self):
        paused, resume = threading.Event(), threading.Event()
        doctor = self.doctor()
        with patch('core.views.audit', side_effect=pause_after('encounter.notes_saved', paused, resume)):
            response = self.race(lambda: doctor.post(f'/encounters/{self.encounter.pk}/notes/', {
                'notes': 'Symptoms: SYNTHETIC CORRECTION, no chest pain', 'revision': str(self.encounter.revision)}),
                paused, resume)
        self.assertEqual(response.status_code, 302)
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.notes, 'Symptoms: SYNTHETIC CORRECTION, no chest pain')

    def test_the_payer_change_waits_for_the_workers_settlement(self):
        job = Job.objects.create(encounter=self.encounter, user=self.user, request_key='rfr2-settle')
        reserve(job, Decimal('0.2'))
        Job.objects.filter(pk=job.pk).update(state='running')
        units = {'input_tokens': 100, 'output_tokens': 0, 'cached_input_tokens': 0, 'cache_creation_tokens': 0}
        paused, resume = threading.Event(), threading.Event()
        real = billing.audit

        def audit(actor, action, *args, **kwargs):
            row = real(actor, action, *args, **kwargs)
            if action == 'usage.settle' and not paused.is_set():
                paused.set()
                resume.wait(30)
            return row
        with patch('core.billing.audit', side_effect=audit):
            usage = self.race(lambda: billing.settle(
                Job.objects.get(pk=job.pk), Decimal('0.1'), units, {'input_per_million': '1000'}, 'anthropic:synthetic',
                'req_rfr2', provider_resource_id='msg_rfr2'), paused, resume)
        self.assertEqual(Usage.objects.get(job=job).pk, usage.pk)
        # Settled before the change committed: the job keeps the payer reserve() recorded (the user).
        self.assertEqual(Job.objects.get(pk=job.pk).payer, f'user:{self.user.pk}')


@override_settings(STRIPE_SECRET_KEY='sk_test_synthetic_adapter', **LOCKED)
class OrganizationTopUpAgainstRequestsInItsDepartment(LockFlowFixture, TransactionTestCase):
    """RF-R1's class, found while repairing it (the same rule: a row held FOR UPDATE while waiting for a money row).
    Reproduce: D bills its organization. A clinician's 2 s upload in D is paused inside reserve() after its
    'usage.reserve' audit (the organization's paid wallet W locked); the organization's owner, a member of D, starts a
    one-time organization top-up (/billing/checkout/, payer organization:<O>); the upload resumes.
    RED on 8cc0b8fd: checkout's owner-membership check, a bare select_for_update() over a join, locked the owner's
    account and D FOR UPDATE; its Payment row's commit-time foreign-key check waited for W; the upload's commit waited
    for FOR KEY SHARE on D: the top-up is the deadlock victim (500, no payment). No Stripe request is made (patched)."""

    def setUp(self):
        super().setUp()
        from core.models import User
        self.owner = User.objects.create_user(username='rfr1-owner', email='rfr1-owner@synthetic.invalid',
                                              verified_at=timezone.now())
        Membership.objects.create(user=self.owner, department=self.department, role='owner')
        billing.welcome_credit(self.owner)
        type(self.department).objects.filter(pk=self.department.pk).update(organization_pays=True)
        self.wallet, _ = Wallet.objects.get_or_create(organization=self.organization, kind='paid')

    def top_up(self):
        from types import SimpleNamespace
        from django.core import signing
        client = SurfaceClient(raise_request_exception=False)
        client.force_login(self.owner)
        data = {'amount': '10.00', 'consent': 'on', 'payer': f'organization:{self.organization.pk}',
                'checkout_token': signing.dumps({'user': str(self.owner.pk), 'nonce': 'rfr1-topup'}, salt='checkout-authorization')}
        session = SimpleNamespace(id='cs_test_rfr1_topup', url='https://checkout.stripe.com/test/synthetic-rfr1')
        return client, data, session

    def assert_topped_up(self, response):
        self.assertEqual(response.status_code, 302, getattr(response, 'exc_info', None))
        self.assertEqual(response['Location'], 'https://checkout.stripe.com/test/synthetic-rfr1')
        from core.models import Payment
        payment = Payment.objects.get(user=self.owner)
        self.assertEqual((payment.wallet_id, payment.status, payment.amount_cents), (self.wallet.pk, 'pending', 1000))

    def test_positive_control_the_top_up_alone_starts_checkout(self):
        client, data, session = self.top_up()
        with patch('stripe.checkout.Session.create', return_value=session):
            self.assert_topped_up(client.post('/billing/checkout/', data))

    def test_a_top_up_and_an_upload_holding_the_organization_wallet_serialize(self):
        draft = self.draft()
        doctor = self.doctor()
        client, data, session = self.top_up()
        real = billing.audit
        paused, resume = threading.Event(), threading.Event()

        def audit(actor, action, *args, **kwargs):
            row = real(actor, action, *args, **kwargs)
            if action == 'usage.reserve' and not paused.is_set():
                paused.set()
                resume.wait(30)
            return row
        with patch.dict(os.environ, STANDARD_ENV), patch('core.billing.audit', side_effect=audit), \
                patch('stripe.checkout.Session.create', return_value=session):
            quote = doctor.get(f'/encounters/{draft.pk}/').context['usage_quote']
            uploading, uploaded = in_thread(lambda: doctor.post(f'/encounters/{draft.pk}/voice/', {
                'audio': self.recording('rfr1-topup'), 'consent': 'on', 'usage_quote': quote}))
            try:
                self.assertTrue(paused.wait(15), 'the upload never reached reserve()')
                paying, paid = in_thread(lambda: client.post('/billing/checkout/', data))
                blocked = wait_for_blocked_backend()
            finally:
                resume.set()
            self.finish(uploading, paying)
        self.assertTrue(blocked, 'the top-up never waited for the upload')
        self.assertNotIn('error', paid, paid.get('error'))
        self.assert_topped_up(paid['value'])
        self.assertNotIn('error', uploaded, uploaded.get('error'))
        self.assertEqual(uploaded['value'].status_code, 302)
        queued = Job.objects.get(encounter=draft, kind='transcription')
        self.assertEqual((queued.state, queued.payer), ('queued', f'organization:{self.organization.pk}'))
        self.assertTrue(Reservation.objects.filter(job=queued, state='held').exists())
        self.assertEqual(self.orphaned_recordings(), [])


@override_settings(**LOCKED)
class PendingReconciliationAgainstSettlementInItsDepartment(LockFlowFixture, TransactionTestCase):
    """RF-R1's class, found while repairing it. Reproduce: a settled job J2 in D has a reconciled additional charge held
    for funds (pending_funds) on its payer's paid wallet W; W is funded; the worker's settlement of another job J1 in D,
    held on W, is paused after its 'usage.settle' audit; apply_pending_reconciliations(wallet=W) (what a top-up runs
    after its commit) starts; the settlement resumes.
    RED on 8983eccc: the reconciliation row was locked with a bare select_for_update().select_related('usage__department'),
    which also locked D FOR UPDATE, then waited for W; the settlement's commit waited for FOR KEY SHARE on D. The apply
    is the deadlock victim: caught and audited (usage.reconciliation_apply_failed), the charge stays pending_funds until
    the payer's next payment, and nothing else retries it."""

    def test_the_pending_charge_is_applied_after_the_settlement(self):
        from core.billing import apply_pending_reconciliations, reconcile_usage, settle
        from core.models import AuditEvent, CostReconciliation
        units = {'input_tokens': 100, 'output_tokens': 0, 'cached_input_tokens': 0, 'cache_creation_tokens': 0}
        rates = {'input_per_million': '1000'}
        promo = Wallet.objects.get(user=self.user, kind='promo')
        paid = Wallet.objects.get(user=self.user, kind='paid')
        reconciled = Job.objects.create(encounter=self.encounter, user=self.user, request_key='rfr1-reconciled')
        reserve(reconciled, Decimal('0.2'))
        usage = settle(reconciled, Decimal('0.1'), units, rates, 'anthropic:synthetic', 'req_rfr1_rec', provider_resource_id='msg_rfr1_rec')
        Job.objects.filter(pk=reconciled.pk).update(state='succeeded')
        row = reconcile_usage(usage, Decimal('0.5'), 'synthetic-invoice-rfr1', self.admin)
        self.assertEqual(row.ledger_status, 'pending_funds')
        self.assertGreater(row.charge_delta, 0)
        Wallet.objects.filter(pk=promo.pk).update(balance=Decimal('0'))
        Wallet.objects.filter(pk=paid.pk).update(balance=Decimal('5'))
        running = Job.objects.create(encounter=self.encounter, user=self.user, request_key='rfr1-running')
        reserve(running, Decimal('0.2'))
        self.assertEqual(list(Reservation.objects.filter(job=running).values_list('wallet_id', flat=True)), [paid.pk])
        Job.objects.filter(pk=running.pk).update(state='running')
        paused, resume = threading.Event(), threading.Event()
        real = billing.audit

        def audit(actor, action, *args, **kwargs):
            result = real(actor, action, *args, **kwargs)
            if action == 'usage.settle' and not paused.is_set():
                paused.set()
                resume.wait(30)
            return result
        with patch('core.billing.audit', side_effect=audit):
            settling, settled = in_thread(lambda: settle(Job.objects.get(pk=running.pk), Decimal('0.1'), units, rates,
                                                         'anthropic:synthetic', 'req_rfr1_run', provider_resource_id='msg_rfr1_run'))
            try:
                self.assertTrue(paused.wait(15), 'the settlement never reached its audit')
                applying, applied = in_thread(lambda: apply_pending_reconciliations(actor=self.admin, wallet=paid))
                blocked = wait_for_blocked_backend()
            finally:
                resume.set()
            self.finish(settling, applying)
        self.assertTrue(blocked, 'the apply never waited for the settlement')
        self.assertNotIn('error', settled, settled.get('error'))
        self.assertNotIn('error', applied, applied.get('error'))
        failed = list(AuditEvent.objects.filter(action='usage.reconciliation_apply_failed').values_list('details', flat=True))
        self.assertEqual(failed, [], 'the pending charge was a deadlock victim')
        self.assertEqual([r.pk for r in applied['value']], [row.pk])
        self.assertEqual(CostReconciliation.objects.get(pk=row.pk).ledger_status, 'applied')
        paid.refresh_from_db()
        self.assertEqual(paid.balance, Decimal('5') - settled['value'].charged_cost - row.charge_delta)
        self.assertEqual(Usage.objects.get(job=running).pk, settled['value'].pk)


from django.test import TestCase  # noqa: E402


@override_settings(**LOCKED)
class WelcomeCreditEntryPointsNeverHoldTheAccountForUpdate(LockFlowFixture, TestCase):
    """RF-R1, the rule itself on every entry point that reaches welcome_credit (core.retention: an account row held
    while this transaction goes on to lock a wallet is FOR NO KEY UPDATE, never FOR UPDATE). The deadlocks are pinned
    by the race tests above for the two invitation flows; email verification cannot race (an unverified account has no
    request that holds its wallet), so the lock mode itself is what is pinned there.
    RED on d41847f6: /verify/<raw>/ locked the account FOR UPDATE before welcome_credit."""

    def account_locks(self, action):
        """The account-row lock modes the action's SQL takes, in order; the action's own result."""
        seen = []

        def wrapper(execute, sql, params, many, context):
            text = sql.rstrip()
            if 'FROM "core_user"' in text and text.endswith(' UPDATE'):
                seen.append('FOR NO KEY UPDATE' if text.endswith('FOR NO KEY UPDATE') else 'FOR UPDATE')
            return execute(sql, params, many, context)
        with connection.execute_wrapper(wrapper):
            result = action()
        return result, seen

    def assert_no_key_only(self, response, seen):
        self.assertEqual(response.status_code, 302, getattr(response, 'exc_info', None))
        self.assertTrue(seen, 'the flow never locked the account; the check would be vacuous')
        self.assertEqual(set(seen), {'FOR NO KEY UPDATE'})

    def test_email_verification(self):
        from core.models import LedgerEntry, User, Verification
        user = User.objects.create_user(username='rfr1-verify@synthetic.invalid', email='rfr1-verify@synthetic.invalid')
        raw = token()
        Verification.objects.create(user=user, token_hash=digest(raw), expires_at=timezone.now() + timedelta(hours=1))
        response, seen = self.account_locks(lambda: SurfaceClient().post(f'/verify/{raw}/'))
        self.assert_no_key_only(response, seen)
        self.assertTrue(LedgerEntry.objects.filter(key=f'welcome:{user.pk}').exists())

    def test_department_invitation_for_an_existing_account(self):
        owner, _, department = self.other[:3]
        Membership.objects.filter(user=owner, department=department).update(role='owner')
        raw = token()
        Invitation.objects.create(email=self.user.email, department=department, role='clinician', invited_by=owner,
                                  token_hash=digest(raw), expires_at=timezone.now() + timedelta(days=1))
        response, seen = self.account_locks(lambda: self.doctor().post(f'/invite/{raw}/', {}))
        self.assert_no_key_only(response, seen)
        self.assertTrue(Membership.objects.filter(user=self.user, department=department).exists())

    def test_clinic_invitation_for_an_existing_account(self):
        from core import clinic_invitations
        _, raw = clinic_invitations.issue(self.admin, self.user.email, 'Synthetic lock-mode clinic', 'Synthetic desk')
        response, seen = self.account_locks(lambda: self.doctor().post(f'/invite/clinic/{raw}/', {}))
        self.assert_no_key_only(response, seen)
        self.assertTrue(Membership.objects.filter(user=self.user, role='owner',
                                                  department__organization__name='Synthetic lock-mode clinic').exists())
