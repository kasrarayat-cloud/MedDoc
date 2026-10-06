"""R6R-1: private dictation admission and durable redaction serialize on the encounter row.

Real PostgreSQL connections and actual upload/over-limit route; synthetic one-second recording, no provider sends.
"""
import os
import threading
import uuid
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection
from django.test import TransactionTestCase, override_settings

from core import disposition_journal as journal, models as m, redaction, views
from core.security import private_path
from core.tests.audio_fixtures import wav_bytes
from core.tests.test_billing_boundary import LIVE
from core.tests.test_recording_limit import EXPENSIVE_ENV
from core.tests.test_redaction import RedactionFixture, REASON
from core.tests.test_retention_flow_locks import in_thread, wait_for_blocked_backend
from core.tests.test_retention_preservation import ISOLATED


@override_settings(**dict(ISOLATED, **LIVE))
class VoiceRedactionSerialization(RedactionFixture, TransactionTestCase):
    def setUp(self):
        self.setup_journal()
        self.client.force_login(self.scope[0])
        self.row = self.scope[5]

    def upload(self, quote):
        return self.client.post(f'/encounters/{self.row.pk}/voice/', {
            'audio': SimpleUploadedFile('synthetic-race.wav', wav_bytes(seconds=1, tag='synthetic-race'), content_type='audio/wav'),
            'consent': 'on', 'usage_quote': quote})

    def finish(self, *threads):
        for thread in threads:
            thread.join(20)
            self.assertFalse(thread.is_alive(), 'bounded synthetic race did not finish')

    def test_pending_quote_is_committed_before_redaction_journals_its_file_manifest(self):
        requested = redaction.request(self.admin, self.row.pk, REASON, uuid.uuid4())
        paused, resume, redacted = threading.Event(), threading.Event(), threading.Event()
        real_audit = views.audit
        def pause_quote(actor, action, *args, **kwargs):
            if action=='voice.over_limit_quoted':
                paused.set()
                if not resume.wait(15):raise RuntimeError('Synthetic quote deadline expired')
            return real_audit(actor, action, *args, **kwargs)
        def execute():
            result = redaction.execute(self.second, requested.pk, self.fresh())
            redacted.set(); return result
        with patch.dict(os.environ, EXPENSIVE_ENV), patch('core.views.audit', side_effect=pause_quote), \
                patch('core.jobs.httpx.post') as provider:
            quote = self.client.get(f'/encounters/{self.row.pk}/').context['usage_quote']
            uploading, uploaded = in_thread(lambda: self.upload(quote))
            try:
                self.assertTrue(paused.wait(10), 'actual upload never reached over-limit quote')
                deleting, deleted = in_thread(execute)
                blocked = wait_for_blocked_backend(timeout=2)
                premature = redacted.is_set()
            finally:
                resume.set()
            self.finish(uploading, deleting)
            provider.assert_not_called()
        self.assertNotIn('error', uploaded, uploaded.get('error'))
        self.assertNotIn('error', deleted, deleted.get('error'))
        self.assertTrue(blocked, 'redaction journaled before the pending quote was committed')
        self.assertFalse(premature, 'redaction completed while the only recording reference was still pending')
        self.assertEqual(uploaded['value'].status_code, 409)
        event = m.AuditEvent.objects.get(action='voice.over_limit_quoted', target=str(self.row.pk))
        key = event.details['path']
        tomb = deleted['value']
        self.assertIn(key, [record['storage_key'] for record in tomb.journal_entry['body']['redaction']['files']])
        self.assertFalse(private_path(key).exists())
        self.assertFalse(m.Job.objects.filter(encounter=self.row).exists())
        self.assertFalse(m.Reservation.objects.exists())

    def test_redaction_journaled_before_upload_admission_creates_no_recording_or_quote(self):
        requested = redaction.request(self.admin, self.row.pk, REASON, uuid.uuid4())
        paused, resume = threading.Event(), threading.Event()
        real_append = journal.append_redaction
        def pause_after_journal(*args, **kwargs):
            result = real_append(*args, **kwargs)
            paused.set()
            if not resume.wait(15):raise RuntimeError('Synthetic redaction deadline expired')
            return result
        with patch.dict(os.environ, EXPENSIVE_ENV), patch('core.disposition_journal.append_redaction', side_effect=pause_after_journal), \
                patch('core.jobs.httpx.post') as provider:
            quote = self.client.get(f'/encounters/{self.row.pk}/').context['usage_quote']
            deleting, deleted = in_thread(lambda: redaction.execute(self.second, requested.pk, self.fresh()))
            try:
                self.assertTrue(paused.wait(10), 'redaction never reached its journal boundary')
                uploading, uploaded = in_thread(lambda: self.upload(quote))
            finally:
                resume.set()
            self.finish(deleting, uploading)
            provider.assert_not_called()
        self.assertNotIn('error', deleted, deleted.get('error'))
        self.assertNotIn('error', uploaded, uploaded.get('error'))
        self.assertIn(uploaded['value'].status_code, [302,404])
        self.assertFalse(m.AuditEvent.objects.filter(action='voice.over_limit_quoted', target=str(self.row.pk)).exists())
        self.assertFalse(list(private_path('audio/synthetic-unused.wav').parent.glob('*.wav')))
        self.assertFalse(m.Job.objects.filter(encounter=self.row).exists())

    def test_quote_commit_failure_removes_unowned_recording_without_job_or_hold(self):
        real_commit = connection.commit
        calls = []
        def fail_first_commit():
            calls.append(True)
            if len(calls)==1:raise DatabaseError('SYNTHETIC commit failure')
            return real_commit()
        with patch.dict(os.environ, EXPENSIVE_ENV), patch('core.jobs.httpx.post') as provider:
            quote = self.client.get(f'/encounters/{self.row.pk}/').context['usage_quote']
            with patch.object(connection, 'commit', side_effect=fail_first_commit):
                response = self.upload(quote)
            provider.assert_not_called()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(m.AuditEvent.objects.filter(action='voice.over_limit_quoted', target=str(self.row.pk)).exists())
        self.assertFalse(list(private_path('audio/synthetic-unused.wav').parent.glob('*.wav')))
        self.assertFalse(m.Job.objects.filter(encounter=self.row).exists())
        self.assertFalse(m.Reservation.objects.exists())
