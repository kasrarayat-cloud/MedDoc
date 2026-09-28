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
