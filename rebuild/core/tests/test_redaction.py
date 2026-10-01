"""Redaction tombstones (0033, core.redaction): a draft with work loses its clinical content and keeps its skeleton.

Every row, file and key here is synthetic and generated inside the test. No retention period, schedule or duration
exists: redaction is an explicit two-custodian act, refused while any hold applies, and re-applied by restore replay.
"""
import hashlib
import importlib
import json
import uuid
from datetime import date, timedelta
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.http import Http404
from django.test import Client, RequestFactory, TestCase, override_settings
from django_otp.plugins.otp_totp.models import TOTPDevice

from core import disposition as d, models as m, redaction, restore_admission, retention, views
from core import disposition_execution as x, disposition_journal as j, disposition_policy as p
from core.security import private_path, scoped
from core.tests.test_retention_journal_repair import RELEASE, RepairFixture
from core.tests.test_retention_preservation import ISOLATED

REASON = 'c' * 64
SKELETON = ('Job', 'ProviderReceipt', 'Usage', 'LedgerEntry', 'Reservation', 'Wallet', 'AuditEvent', 'Patient', 'Template',
            'TemplateVersion')


class RedactionFixture(RepairFixture):
    def write(self, relative, data):
        path = private_path(relative); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        return path

    def worked_draft(self, scope=None):
        """An unfinalized document with a completed transcription: recording, provider result, receipt, usage, ledger
        entry, and a code suggestion quoting the notes."""
        scope = scope or self.scope
        row = m.Encounter.objects.create(department=scope[2], patient=scope[3], template_version=scope[5].template_version,
            created_by=scope[0], notes='SYNTHETIC REDACTABLE NOTE: chest pain since Monday', service_date=scope[5].service_date,
            answers={'symptoms': {'text': 'SYNTHETIC REDACTABLE ANSWER', 'status': 'supported'}}, status='review',
            template_review={'symptoms': {'reviewed': True}})
        audio = f'audio/{uuid.uuid4().hex}{"0"*16}.wav'; result = f'receipts/{uuid.uuid4().hex}{"1"*16}.json'
        self.write(audio, b'SYNTHETIC RECORDING BYTES')
        payload = json.dumps({'raw_transcript': 'SYNTHETIC REDACTABLE TRANSCRIPT', 'transcript': 'SYNTHETIC'}).encode()
        self.write(result, payload); sha = hashlib.sha256(payload).hexdigest()
        job = m.Job.objects.create(encounter=row, user=scope[0], kind='transcription', state='succeeded',
                                   request_key=str(uuid.uuid4()), input_path=audio, result_path=result, result_sha256=sha,
                                   provider='synthetic:fixture', payer='personal')
        m.ProviderReceipt.objects.create(job=job, provider='synthetic:fixture', actual_cost=Decimal('0.02'), simulated=True,
                                         result_path=result, result_sha256=sha)
        m.Usage.objects.create(job=job, user=scope[0], department=scope[2], organization=scope[1], payer='personal',
                               provider='synthetic:fixture', actual_cost=Decimal('0.02'), charged_cost=Decimal('0.03'),
                               simulated=True)
        wallet = m.Wallet.objects.get(user=scope[0], kind='promo')
        m.LedgerEntry.objects.create(wallet=wallet, amount=Decimal('-0.03'), kind='usage', key=f'usage:{job.pk}',
                                     description='Synthetic transcription', job=job, balance_after=wallet.balance)
        release = m.CodeSet.objects.create(system='ICD-10-CM', version=f'synthetic-{uuid.uuid4().hex[:8]}',
            effective_from=date(2025, 10, 1), effective_until=date(2026, 9, 30), source_url='https://synthetic.invalid/',
            sha256='d'*64)
        code = m.Code.objects.create(release=release, code='R07.9', description='Synthetic chest pain code')
        m.CodeSuggestion.objects.create(encounter=row, terminology=code, explanation='SYNTHETIC REDACTABLE EXPLANATION',
                                        evidence='chest pain since Monday')
        return row, job, (audio, result)

    def skeleton(self):
        return {name: list(getattr(m, name).objects.order_by('pk').values()) for name in SKELETON}

    def redact(self, row, actor=None, approver=None):
        requested = redaction.request(actor or self.admin, row.pk, REASON, uuid.uuid4())
        with self.captureOnCommitCallbacks(execute=True):
            return requested, redaction.execute(approver or self.second, requested.pk, self.fresh())


@override_settings(**ISOLATED)
class Redaction(RedactionFixture, TestCase):
    def setUp(self): self.setup_journal()

    def test_a_draft_with_work_loses_its_content_and_keeps_its_skeleton(self):
        row, job, files = self.worked_draft()
        before = self.skeleton()
        requested, tombstone = self.redact(row)
        row.refresh_from_db()
        self.assertEqual((row.notes, row.answers, row.template_review, row.status), ('', {}, {}, 'redacted'))
        self.assertFalse(m.CodeSuggestion.objects.filter(encounter=row).exists())
        for relative in files: self.assertFalse(private_path(relative).exists(), relative)
        after = self.skeleton()
        for name in SKELETON:
            if name == 'AuditEvent':  # appended to, never changed
                ids = {r['id'] for r in before[name]}
                self.assertEqual([r for r in after[name] if r['id'] in ids], before[name])
            else:
                self.assertEqual(after[name], before[name], name)  # ids, amounts and storage keys unchanged
        # Who, when and why: two custodians, the reason hash, the removed files' digests, in the signed journal entry.
        body = tombstone.journal_entry['body']['redaction']
        self.assertEqual((body['requested_by'], body['approved_by'], body['reason_sha256'], body['target_id']),
                         (str(self.admin.pk), str(self.second.pk), REASON, str(row.pk)))
        self.assertEqual(sorted(f['storage_key'] for f in body['files']), sorted(files))
        self.assertEqual([e['body']['redaction'] for e in j.redaction_entries(j.verified(self.fresh()))], [body])
        self.assertEqual(tombstone.entry_sha256, p.digest(tombstone.journal_entry))
        self.assertEqual(sorted(m.AuditEvent.objects.filter(action__startswith='redaction.').values_list('action', flat=True)),
                         ['redaction.executed', 'redaction.requested'])
        for text in (self.path.read_text(), json.dumps(list(m.AuditEvent.objects.values('details'))), json.dumps(tombstone.files)):
            for private in ('SYNTHETIC REDACTABLE', 'chest pain', self.scope[3].display_name):
                self.assertNotIn(private, text)
        # The document is unavailable to its clinician, and its provider output is not served; the receipt stays.
        self.assertFalse(scoped(m.Encounter, self.scope[0]).filter(pk=row.pk).exists())
        with self.assertRaisesMessage(ValidationError, 'redacted'): x.require_access(row.pk)
        request = RequestFactory().get('/'); request.user = self.scope[0]
        with self.assertRaises(Http404): views.job_result(request, job.pk)
        # The exact retry by the same custodian returns the tombstone; another custodian cannot re-execute it.
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(redaction.execute(self.second, requested.pk, self.fresh()).pk, tombstone.pk)
        third = self.custodian('custodian3')
        with self.assertRaisesMessage(ValidationError, 'another custodian'): redaction.execute(third, requested.pk, self.fresh())
        self.assertEqual(len(j.redaction_entries(j.verified())), 1)

    def test_a_hold_refuses_redaction_until_it_is_released(self):
        row, _, files = self.worked_draft()
        hold = self.patient_hold()
        with self.assertRaisesMessage(ValidationError, 'active_hold'): redaction.request(self.admin, row.pk, REASON, uuid.uuid4())
        self.committed(lambda: retention.release_hold(self.second, hold.pk, 'b'*64))  # journaled after its commit
        # A request made while no hold applied cannot be executed under a later one either.
        requested = redaction.request(self.admin, row.pk, REASON, uuid.uuid4())
        second = self.patient_hold()
        with self.assertRaisesMessage(ValidationError, 'active_hold'): redaction.execute(self.second, requested.pk, self.fresh())
        self.assertEqual(m.Encounter.objects.get(pk=row.pk).notes[:9], 'SYNTHETIC')
        # The database refuses the tombstone under an unreleased hold whatever the application does.
        entry = {'key_id': 'writer', 'signature': '0'*128, 'body': {'contract': j.REDACTION, 'redaction': {
            'id': str(uuid.uuid4()), 'target_id': str(row.pk), 'department_id': str(row.department_id),
            'request_id': str(requested.pk), 'content_sha256': 'e'*64, 'files': [], 'requested_by': str(self.admin.pk),
            'approved_by': str(self.second.pk)}}}
        with self.assertRaisesMessage(DatabaseError, 'A retention hold applies'), transaction.atomic():
            m.RedactionTombstone.objects.create(id=entry['body']['redaction']['id'], target_id=row.pk,
                department_id=row.department_id, request_id=requested.pk, content_sha256='e'*64, files=[],
                journal_entry=entry, entry_sha256='f'*64)
        self.committed(lambda: retention.release_hold(self.second, second.pk, 'b'*64))
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(redaction.execute(self.second, requested.pk, self.fresh()).target_id, row.pk)

    def test_a_committed_hold_the_journal_never_took_refuses_redaction(self):
        """A hold recorded while the journal could not take it (preservation first): only the database knows it."""
        row, _, _ = self.worked_draft()
        missing = str(self.path) + '.unavailable'
        with override_settings(DISPOSITION_JOURNAL_PATH=missing), self.assertLogs('core.retention', 'ERROR'):
            self.patient_hold()
        self.assertEqual(j.journaled_holds(), {})
        with self.assertRaisesMessage(ValidationError, 'active_hold'): redaction.request(self.admin, row.pk, REASON, uuid.uuid4())

    def test_a_journal_only_hold_refuses_redaction(self):
        row, _, _ = self.worked_draft()
        with patch('core.retention.audit', side_effect=RuntimeError('SYNTHETIC crash before commit')):
            with self.assertRaises(RuntimeError): self.patient_hold()
        self.assertFalse(m.RetentionHold.objects.exists())  # only the journal holds it, and it binds
        with self.assertRaisesMessage(ValidationError, 'active_hold'): redaction.request(self.admin, row.pk, REASON, uuid.uuid4())
        other, _, _ = self.worked_draft(self.other)  # positive control: a document outside the hold's scope
        self.assertEqual(self.redact(other)[1].target_id, other.pk)

    def test_unresolved_work_finalized_changed_content_or_one_custodian_refuse(self):
        row, job, _ = self.worked_draft()
        m.Job.objects.filter(pk=job.pk).update(state='running')
        with self.assertRaisesMessage(ValidationError, 'work_unresolved'): redaction.request(self.admin, row.pk, REASON, uuid.uuid4())
        m.Job.objects.filter(pk=job.pk).update(state='succeeded')
        requested = redaction.request(self.admin, row.pk, REASON, uuid.uuid4())
        with self.assertRaises(PermissionDenied): redaction.execute(self.admin, requested.pk, self.fresh())
        m.Encounter.objects.filter(pk=row.pk).update(notes='SYNTHETIC REDACTABLE NOTE: edited after the request', revision=1)
        with self.assertRaisesMessage(ValidationError, redaction.CONTENT_CHANGED): redaction.execute(self.second, requested.pk, self.fresh())
        with override_settings(DISPOSITION_ENABLED=False), self.assertRaises(ValidationError):
            redaction.request(self.admin, row.pk, REASON, uuid.uuid4())
        with override_settings(DISPOSITION_JOURNAL_PATH=''), self.assertRaisesMessage(ValidationError, 'independent journal'):
            redaction.request(self.admin, row.pk, REASON, uuid.uuid4())
        m.Encounter.objects.filter(pk=self.scope[5].pk).update(status='finalized')
        with self.assertRaisesMessage(ValidationError, 'not_an_unfinalized_document'):
            redaction.request(self.admin, self.scope[5].pk, REASON, uuid.uuid4())
        self.assertFalse(m.RedactionTombstone.objects.exists()); self.assertEqual(j.redaction_entries(j.verified()), [])

    def test_the_database_keeps_a_redacted_document_empty_and_its_records_append_only(self):
        row, job, _ = self.worked_draft()
        requested, tombstone = self.redact(row)
        refused = {
            'content edit': lambda: m.Encounter.objects.filter(pk=row.pk).update(notes='SYNTHETIC RESURRECTED'),
            'status back to draft': lambda: m.Encounter.objects.filter(pk=row.pk).update(status='draft'),
            'new job': lambda: m.Job.objects.create(encounter=row, user=self.scope[0], request_key=str(uuid.uuid4())),
            'new code': lambda: m.CodeSuggestion.objects.create(encounter=row, terminology=m.Code.objects.first(),
                                                                explanation='x', evidence='x'),
            'tombstone update': lambda: m.RedactionTombstone.objects.filter(pk=tombstone.pk).update(files=[]),
            'tombstone delete': lambda: m.RedactionTombstone.objects.filter(pk=tombstone.pk).delete(),
            'request delete': lambda: m.RedactionRequest.objects.filter(pk=requested.pk).delete(),
        }
        for label, action in refused.items():
            with self.subTest(label), self.assertRaises(DatabaseError), transaction.atomic(): action()
        for table in ('redactionrequest', 'redactiontombstone'):
            with self.subTest(table), self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor: cursor.execute(f'TRUNCATE core_{table} CASCADE')
        # A reconcile that inserts the row again cannot bring its content back either.
        with self.assertRaisesMessage(DatabaseError, 'cannot regain clinical content'), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("UPDATE core_encounter SET status='redacted', notes='SYNTHETIC BACK' WHERE id=%s", [row.pk])
        # Positive control: an unredacted document in the same department still takes edits and new work.
        m.Encounter.objects.filter(pk=self.scope[5].pk).update(notes='SYNTHETIC CORRECTION', revision=3)
        m.Job.objects.create(encounter=self.scope[5], user=self.scope[0], request_key=str(uuid.uuid4()), state='failed')

    def test_a_restore_older_than_the_redaction_re_applies_it_before_admission(self):
        row, job, files = self.worked_draft()
        originals = {relative: private_path(relative).read_bytes() for relative in files}
        self.older_backup(lambda: self.redact(row))
        for relative, data in originals.items(): self.write(relative, data)  # the restored volume still has the bytes
        self.assertEqual(m.Encounter.objects.get(pk=row.pk).status, 'review'); self.assertFalse(m.RedactionTombstone.objects.exists())
        with self.quarantine():
            report = restore_admission.assess(self.instance, self.fresh(), RELEASE)
            self.assertIn('redaction_replay_incomplete', report['blockers']); self.assertEqual(report['redactions_unapplied'], 1)
            with self.captureOnCommitCallbacks(execute=True):
                replayed = x.replay(self.admin, self.fresh())
            self.assertEqual((replayed['redactions'], replayed['clinical_rows_deleted']), (1, 1))
            restored = m.Encounter.objects.get(pk=row.pk)
            self.assertEqual((restored.notes, restored.answers, restored.status), ('', {}, 'redacted'))
            for relative in files: self.assertFalse(private_path(relative).exists())
            report = restore_admission.assess(self.instance, self.fresh(), RELEASE)
            self.assertEqual((report['blockers'], report['redactions_unapplied']), ([], 0), report)
            self.assertTrue(report['restore_check']['files']['passed'])  # removed bytes are not expected references
            self.assertEqual(restore_admission.admit(self.admin, self.instance, self.fresh(), RELEASE).report['admissible'], True)
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(x.replay(self.admin, self.fresh())['redactions'], 1)  # idempotent
        self.assertEqual(m.RedactionTombstone.objects.count(), 1)

    def test_a_hold_journaled_after_the_redaction_does_not_capture_the_removed_content_on_replay(self):
        row, _, files = self.worked_draft()
        originals = {relative: private_path(relative).read_bytes() for relative in files}
        def redact_then_hold():
            self.redact(row); self.patient_hold()
        self.older_backup(redact_then_hold)
        for relative, data in originals.items(): self.write(relative, data)
        self.assertFalse(m.PreservedRecord.objects.exists())
        with self.quarantine(), self.captureOnCommitCallbacks(execute=True):
            replayed = x.replay(self.admin, self.fresh())
        self.assertEqual((replayed['redactions'], replayed['holds_imported']), (1, 1))
        # Journal order: the redaction removed the content before the later hold applied, as at the source.
        self.assertFalse(m.PreservedRecord.objects.filter(Q_source(row.pk)).exists())
        self.assertEqual(m.Encounter.objects.get(pk=row.pk).notes, '')

    def test_a_restore_holding_a_hold_released_before_the_redaction_replays_in_journal_order(self):
        """The backup was taken while a hold applied; the source then released it and redacted. Replay must import the
        release before re-applying the redaction (journal order), and the blanking captures nothing."""
        row, _, files = self.worked_draft()
        originals = {relative: private_path(relative).read_bytes() for relative in files}
        hold = self.committed(self.patient_hold)
        def release_then_redact():
            self.committed(lambda: retention.release_hold(self.second, hold.pk, 'b'*64)); self.redact(row)
        self.older_backup(release_then_redact)
        for relative, data in originals.items(): self.write(relative, data)
        self.assertTrue(retention.active_holds(encounter_id=row.pk).filter(pk=hold.pk).exists())  # as in the backup
        with self.quarantine(), self.captureOnCommitCallbacks(execute=True):
            replayed = x.replay(self.admin, self.fresh())
        self.assertEqual((replayed['releases_imported'], replayed['redactions']), (1, 1))
        self.assertEqual(m.Encounter.objects.get(pk=row.pk).status, 'redacted')
        self.assertFalse(m.PreservedRecord.objects.filter(Q_source(row.pk)).exists())

    def test_a_redaction_journaled_after_admission_quarantines_the_target_until_replay(self):
        self.older_backup(self.patient_hold)
        with self.quarantine(): x.replay(self.admin, self.fresh())
        self.admit()
        row, _, _ = self.worked_draft(self.other)
        with self.lifted():
            self.assertFalse(d.quarantined())
            content, files = redaction.content(row)
            # The old host's redaction of this document, journaled after this target was admitted.
            j.append_redaction({'id': str(uuid.uuid4()), 'request_id': str(uuid.uuid4()), 'target_id': str(row.pk),
                'department_id': str(row.department_id), 'content_sha256': content, 'reason_sha256': REASON,
                'files': files, 'requested_by': str(self.admin.pk), 'requested_at': self.base.isoformat(),
                'approved_by': str(self.second.pk)}, self.fresh())
            self.assertTrue(d.quarantined())
            self.assertFalse(scoped(m.Encounter, self.other[0]).filter(pk=row.pk).exists())  # hidden at once
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(x.replay(self.admin, self.fresh())['redactions'], 1)
            self.assertFalse(d.quarantined())
        self.assertEqual(m.Encounter.objects.get(pk=row.pk).status, 'redacted')

    def test_file_bytes_are_removed_only_while_they_have_the_journaled_digest(self):
        kept = self.write(f'receipts/{uuid.uuid4().hex}{"2"*16}.json', b'SYNTHETIC CHANGED AFTER THE JOURNAL')
        gone = self.write(f'receipts/{uuid.uuid4().hex}{"3"*16}.json', b'SYNTHETIC AS JOURNALED')
        records = [{'storage_key': str(path.relative_to(private_path('receipts').parent)), 'sha256':
                    hashlib.sha256(b'SYNTHETIC AS JOURNALED').hexdigest(), 'byte_count': 21} for path in (kept, gone)]
        with self.assertLogs('core.redaction', 'ERROR'):
            self.assertEqual(redaction.remove_files(records), 1)
        self.assertTrue(kept.exists()); self.assertFalse(gone.exists())
        self.assertEqual(redaction.remove_files(records[1:]), 0)  # already gone: nothing to do, nothing logged

    def test_the_command_requests_then_a_second_custodian_executes_with_ids_and_counts_only(self):
        import io
        from django.core.management import call_command
        from django.core.management.base import CommandError
        row, _, files = self.worked_draft()
        def run(*arguments):
            out = io.StringIO(); call_command('redaction', *arguments, stdout=out); return json.loads(out.getvalue())
        requested = run('request', '--custodian', self.admin.email, '--document', str(row.pk), '--reason-sha256', REASON,
                        '--request-key', str(uuid.uuid4()))
        checkpoint = self.out_file('checkpoint.json', json.dumps(self.fresh()))
        with self.assertRaisesMessage(CommandError, 'second custodian'):
            run('execute', '--custodian', self.admin.email, '--request', requested['request'], '--checkpoint', checkpoint)
        with self.captureOnCommitCallbacks(execute=True):
            done = run('execute', '--custodian', self.second.email, '--request', requested['request'], '--checkpoint', checkpoint)
        self.assertEqual((done['redacted'], done['files']), (True, 2))
        self.assertEqual(m.Encounter.objects.get(pk=row.pk).status, 'redacted')
        for text in (json.dumps(requested), json.dumps(done)):
            for private in ('SYNTHETIC', 'audio/', 'receipts/', REASON):
                self.assertNotIn(private, text)

    def out_file(self, name, content):
        path = Path(self.journal_temp.name) / name; path.write_text(content); return str(path)

    def test_reversing_0033_refuses_while_redaction_evidence_exists(self):
        reverse = importlib.import_module('core.migrations.0033_redaction_tombstone').REVERSE
        row, _, _ = self.worked_draft()
        self.redact(row)
        with self.assertRaisesMessage(DatabaseError, 'requires a forward migration'), transaction.atomic():
            with connection.cursor() as cursor: cursor.execute(reverse)
        self.assertEqual(m.RedactionTombstone.objects.count(), 1)


def Q_source(pk):
    from django.db.models import Q
    return Q(source_id=pk) | Q(prior_record__encounter_id=str(pk))
