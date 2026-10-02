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


def Q_source(pk):
    from django.db.models import Q
    return Q(source_id=pk) | Q(prior_record__encounter_id=str(pk))


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
        # Round 2 (R2D-X2): the removal of the bytes is audited too, a count and no path, so the exposure ledger knows when
        # they left this volume (core.exposure.commit_evidence).
        self.assertEqual(sorted(m.AuditEvent.objects.filter(action__startswith='redaction.').values_list('action', flat=True)),
                         ['redaction.executed', 'redaction.files_removed', 'redaction.requested'])
        self.assertEqual(m.AuditEvent.objects.get(action='redaction.files_removed').details, {'files': len(files)})
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

    def test_file_bytes_are_removed_unless_another_record_references_them(self):
        """Round 2 (R2D-R1 of 4cfa4301): bytes whose digest differs from the journaled one were kept and logged on every
        sweep, so a recording missing at the redaction (journaled as empty) and restored later was never removed and the
        restore never admitted. A redacted document's storage keys are its own (never reused), so its bytes are removed
        whatever they hold now; only a key another record references is kept, and that record's bytes are not the
        redaction's."""
        row, job, (audio, result) = self.worked_draft()
        self.redact(row)
        changed = self.write(result, b'SYNTHETIC CHANGED AFTER THE JOURNAL')
        restored = self.write(audio, b'SYNTHETIC RECORDING BYTES')
        records = [{'storage_key': key, 'sha256': hashlib.sha256(b'SYNTHETIC AS JOURNALED').hexdigest(), 'byte_count': 21}
                   for key in (audio, result)]
        self.assertEqual(redaction.remove_files(records, row.pk), 2)  # 4cfa4301: 0, both logged 'digest changed'
        self.assertFalse(changed.exists()); self.assertFalse(restored.exists())
        self.assertEqual(redaction.remove_files(records, row.pk), 0)  # already gone: nothing to do, nothing logged

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




MARKERS = ('SYNTHETIC REDACTABLE', 'chest pain since Monday', 'SYNTHETIC RECORDING BYTES')


def stores_holding(markers, roots=()):
    """Every database column (of EVERY table, enumerated from the catalogue, so a new table or column is covered without
    editing this) and every file under `roots` whose content holds one of `markers`. Names only, never content."""
    found = []
    with connection.cursor() as cursor:
        for table in connection.introspection.table_names(cursor):
            for column in connection.introspection.get_table_description(cursor, table):
                cursor.execute('SELECT count(*) FROM "%s" WHERE "%s"::text ILIKE ANY(%%s)' % (table, column.name),
                               [['%' + marker + '%' for marker in markers]])
                if cursor.fetchone()[0]:
                    found.append(f'{table}.{column.name}')
    for root in roots:
        for path in sorted(Path(root).rglob('*')):
            if path.is_file() and any(marker.encode() in path.read_bytes() for marker in markers):
                found.append(str(path))
    return found


@override_settings(**ISOLATED)
class RefutationRepairs(RedactionFixture, TestCase):
    """Refutation of dc33e094: F1 (batch plans keep the notes), F6 (admission with redacted bytes still on the volume),
    and F12 (each refusal arm alone, the requester re-check and the file digest in the content)."""

    def setUp(self): self.setup_journal()

    def batch(self, row, state='succeeded'):
        # As core.generation_batch writes it: the plan carries the full notes and unit quotes, and the row is immutable.
        return m.GenerationBatch.objects.create(encounter=row, user=self.scope[0], admission_key=uuid.uuid4(),
            revision=row.revision, plan={'notes': row.notes, 'units': [{'id': 'u1', 'quote': 'chest pain since Monday'}],
                                         'parts': []}, plan_sha256='a' * 64, maximum_charge=Decimal('0'), state=state)

    def test_F1_a_draft_with_a_generation_batch_is_refused(self):
        row, _, _ = self.worked_draft()
        batch = self.batch(row)
        self.assertEqual(redaction.refusals(row), ['generation_batch_content'])  # dc33e094: [] and the plan kept the notes
        with self.assertRaisesMessage(ValidationError, 'generation_batch_content'):
            redaction.request(self.admin, row.pk, REASON, uuid.uuid4())
        m.GenerationBatch.objects.filter(pk=batch.pk).update(state='running')
        self.assertEqual(redaction.refusals(row), ['generation_batch_content', 'work_unresolved'])
        # The database refuses the tombstone whatever the application does (0033).
        tomb = str(uuid.uuid4())
        entry = {'key_id': 'writer', 'signature': '0' * 128, 'body': {'contract': j.REDACTION, 'redaction': {
            'id': tomb, 'target_id': str(row.pk), 'department_id': str(row.department_id), 'request_id': tomb,
            'content_sha256': 'e' * 64, 'files': [], 'requested_by': str(self.admin.pk), 'approved_by': str(self.second.pk)}}}
        with self.assertRaisesMessage(DatabaseError, 'generation batch'), transaction.atomic():
            m.RedactionTombstone.objects.create(id=tomb, target_id=row.pk, department_id=row.department_id, request_id=tomb,
                                                content_sha256='e' * 64, files=[], journal_entry=entry, entry_sha256='f' * 64)
        self.assertFalse(m.RedactionTombstone.objects.exists())

    def test_F1_no_store_holds_the_redacted_content_afterwards(self):
        row, _, _ = self.worked_draft()
        from django.conf import settings
        self.assertTrue(stores_holding(MARKERS, (settings.MEDIA_ROOT,)))  # the control: the content is somewhere first
        self.redact(row)
        self.assertEqual(stores_holding(MARKERS, (settings.MEDIA_ROOT, Path(self.journal_temp.name))), [])

    def test_F6_admission_refuses_while_redacted_bytes_remain_on_the_restored_volume(self):
        row, _, files = self.worked_draft()
        originals = {relative: private_path(relative).read_bytes() for relative in files}
        self.older_backup(lambda: self.redact(row))
        for relative, data in originals.items(): self.write(relative, data)
        real_unlink = Path.unlink
        def refuse(path, *args, **kwargs):
            if any(str(path).endswith(relative) for relative in files): raise PermissionError(13, 'SYNTHETIC EACCES')
            return real_unlink(path, *args, **kwargs)
        with self.quarantine():
            with patch.object(Path, 'unlink', refuse), self.assertLogs('core.redaction', 'ERROR'):
                with self.captureOnCommitCallbacks(execute=True):
                    x.replay(self.admin, self.fresh())
            self.assertTrue(all(private_path(relative).exists() for relative in files))
            report = restore_admission.assess(self.instance, self.fresh(), RELEASE)
            self.assertIn('redaction_replay_incomplete', report['blockers'])  # dc33e094: admissible
            self.assertEqual(report['redactions_unapplied'], 1)
            with self.captureOnCommitCallbacks(execute=True):
                x.replay(self.admin, self.fresh())  # the next replay removes them
            self.assertFalse(any(private_path(relative).exists() for relative in files))
            self.assertEqual(restore_admission.assess(self.instance, self.fresh(), RELEASE)['blockers'], [])

    def test_F2_a_file_a_redacted_documents_rows_reference_later_is_swept_and_counted(self):
        row, job, _ = self.worked_draft()
        self.redact(row)
        late = f'receipts/{uuid.uuid4().hex}{"4"*16}.json'
        self.write(late, b'{"provider_output": "SYNTHETIC REDACTABLE LATE OUTPUT"}')
        m.Job.objects.filter(pk=job.pk).update(result_path=late, result_sha256=hashlib.sha256(
            b'{"provider_output": "SYNTHETIC REDACTABLE LATE OUTPUT"}').hexdigest())
        self.assertEqual(redaction.unapplied(j.verified()), 1)  # its bytes are on the volume
        from ops.backup_restore import FILE_QUERIES
        with connection.cursor() as cursor:
            keys = set()
            for _kind, statement in FILE_QUERIES:
                cursor.execute(statement); keys |= {r[0] for r in cursor.fetchall()}
        self.assertNotIn(late, keys)  # a redacted document's files are never a backup's file reference
        self.assertEqual(redaction.sweep(row.pk), 1)
        self.assertFalse(private_path(late).exists())
        self.assertEqual(redaction.unapplied(j.verified()), 0)

    # F12: each refusal arm alone, with the exact set of labels.
    def assert_refused_only(self, row, label):
        self.assertEqual(redaction.refusals(row), [label])
        with self.assertRaisesMessage(ValidationError, label):
            redaction.request(self.admin, row.pk, REASON, uuid.uuid4())

    def test_F12_a_file_shared_with_another_record_alone_refuses(self):
        row, job, files = self.worked_draft()
        other = self.worked_draft(self.other)[0]
        m.Job.objects.create(encounter=other, user=self.other[0], kind='transcription', state='failed',
                             request_key=str(uuid.uuid4()), input_path=files[0])
        self.assert_refused_only(row, 'shared_or_preserved_file')

    def test_F12_preserved_evidence_alone_refuses(self):
        row, _, _ = self.worked_draft()
        m.PreservedRecord.objects.create(source_table='core_encounter', source_id=row.pk, operation='UPDATE', hold_ids=[],
                                         prior_record={'id': str(row.pk)})
        self.assert_refused_only(row, 'preserved_evidence')

    def test_F12_held_funds_alone_refuse(self):
        row, job, _ = self.worked_draft()
        m.Reservation.objects.create(job=job, wallet=m.Wallet.objects.get(user=self.scope[0], kind='promo'),
                                     amount=Decimal('0.10'), state='held')
        self.assert_refused_only(row, 'funds_held')

    def test_F12_a_receipt_without_its_accounting_alone_refuses(self):
        row, _, _ = self.worked_draft()
        orphan = m.Job.objects.create(encounter=row, user=self.scope[0], kind='transcription', state='failed',
                                      request_key=str(uuid.uuid4()))
        m.ProviderReceipt.objects.create(job=orphan, provider='synthetic:fixture', actual_cost=Decimal('0.02'), simulated=True)
        self.assert_refused_only(row, 'receipt_accounting_unresolved')

    def test_F12_unresolved_financial_history_alone_refuses(self):
        row, job, _ = self.worked_draft()
        m.CostReconciliation.objects.create(usage=m.Usage.objects.get(job=job), reconciled_cost=Decimal('0.03'),
            evidence_reference='synthetic', recorded_by=self.admin, charge_delta=Decimal('0.01'), ledger_status='pending_funds')
        self.assert_refused_only(row, 'financial_history_unresolved')

    def test_F12_a_disposition_tombstone_alone_refuses(self):
        row, _, _ = self.worked_draft()
        instruction = str(uuid.uuid4())
        entry = {'key_id': 'writer', 'signature': '0' * 128, 'body': {'contract': 'disposition-journal-entry-v1', 'instruction': {
            'id': instruction, 'target_id': str(row.pk), 'department_id': str(row.department_id),
            'created_by': str(self.admin.pk), 'approved_by': str(self.second.pk)}}}
        m.DispositionTombstone.objects.create(target_id=row.pk, department_id=row.department_id, instruction_id=instruction,
                                              journal_entry=entry, entry_sha256='f' * 64)
        self.assert_refused_only(row, 'disposed_target')

    def test_F12_an_already_redacted_document_says_so(self):
        row, _, _ = self.worked_draft()
        self.redact(row); row.refresh_from_db()
        self.assertEqual(redaction.refusals(row), ['already_redacted', 'not_an_unfinalized_document'])

    def test_F12_a_requester_no_longer_a_custodian_blocks_execution(self):
        row, _, _ = self.worked_draft()
        requested = redaction.request(self.admin, row.pk, REASON, uuid.uuid4())
        m.User.objects.filter(pk=self.admin.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied): redaction.execute(self.second, requested.pk, self.fresh())
        self.assertFalse(m.RedactionTombstone.objects.exists())

    def test_F12_changed_file_bytes_change_the_content(self):
        row, _, files = self.worked_draft()
        requested = redaction.request(self.admin, row.pk, REASON, uuid.uuid4())
        self.write(files[1], b'{"raw_transcript": "SYNTHETIC CHANGED", "transcript": "SYNTHETIC"}')
        with self.assertRaisesMessage(ValidationError, redaction.CONTENT_CHANGED):
            redaction.execute(self.second, requested.pk, self.fresh())


@override_settings(**ISOLATED)
class RoundTwoRepairs(RedactionFixture, TestCase):
    """Refutation round 2 of 4cfa4301: the data-loss lens (R2D-Q1, R2D-R1) and the false-green lens (FG-2, FG-4, FG-13)."""
    def setUp(self): self.setup_journal()

    def refusing(self, *keys):
        real = Path.unlink
        def refuse(path, *args, **kwargs):
            if any(str(path).endswith(key) for key in keys): raise PermissionError(13, 'SYNTHETIC EACCES')
            return real(path, *args, **kwargs)
        return patch.object(Path, 'unlink', refuse)

    def late(self, job):
        data = b'{"provider_output": "SYNTHETIC REDACTABLE LATE OUTPUT"}'
        key = f'receipts/{uuid.uuid4().hex}{"5"*16}.json'
        self.write(key, data)
        m.Job.objects.filter(pk=job.pk).update(result_path=key, result_sha256=hashlib.sha256(data).hexdigest())
        return key

    def test_Q1_bytes_a_failed_unlink_left_never_quarantine_an_admitted_instance(self):
        """unapplied() counted leftover bytes (F6) and is also the check behind quarantined() on an admitted instance, so one
        failed unlink stopped all provider processing. Admission still refuses while bytes remain; serving does not."""
        self.older_backup(self.patient_hold)
        with self.quarantine():
            x.replay(self.admin, self.fresh())
        self.admit()
        row, _job, (audio, _result) = self.worked_draft(self.other)  # outside the hold's scope
        with self.lifted():
            self.assertFalse(d.quarantined())
            with self.refusing(audio), self.assertLogs('core.redaction', 'ERROR'):
                requested, _tomb = self.redact(row)
            self.assertTrue(private_path(audio).exists())
            self.assertFalse(d.quarantined())                         # 4cfa4301: True, every request refused
            d.require_processing()
            self.assertEqual(redaction.unapplied(j.verified()), 1)    # a restore of this volume would still be refused
            with self.captureOnCommitCallbacks(execute=True):
                redaction.execute(self.second, requested.pk, self.fresh())  # the exact retry removes them
            self.assertFalse(private_path(audio).exists())
            self.assertEqual(redaction.unapplied(j.verified()), 0)
            self.assertFalse(d.quarantined())

    def test_R1_a_file_missing_at_the_redaction_and_restored_later_is_removed_by_replay(self):
        row, _job, (audio, result) = self.worked_draft()
        originals = {key: private_path(key).read_bytes() for key in (audio, result)}
        private_path(audio).unlink()                                  # the stored upload was missing at the redaction
        self.older_backup(lambda: self.redact(row))
        record = [f for f in j.redaction_entries(j.verified())[0]['body']['redaction']['files'] if f['storage_key'] == audio]
        self.assertEqual([(f['sha256'], f['byte_count']) for f in record], [(hashlib.sha256(b'').hexdigest(), 0)])
        for key, data in originals.items(): self.write(key, data)     # the older recovery point's volume holds both
        with self.quarantine():
            with self.captureOnCommitCallbacks(execute=True):
                x.replay(self.admin, self.fresh())
            self.assertFalse(private_path(audio).exists())            # 4cfa4301: kept on every replay, admission refused
            self.assertFalse(private_path(result).exists())
            self.assertEqual(restore_admission.assess(self.instance, self.fresh(), RELEASE)['blockers'], [])

    def test_R1_a_redacted_key_another_record_references_is_never_removed(self):
        row, _job, (audio, _result) = self.worked_draft()
        self.redact(row)
        _other_row, other_job, _ = self.worked_draft(self.other)
        self.write(audio, b'SYNTHETIC BYTES ANOTHER RECORD OWNS')
        m.Job.objects.filter(pk=other_job.pk).update(input_path=audio)  # (a record that references the same key)
        with self.assertLogs('core.redaction', 'ERROR'):
            self.assertEqual(redaction.sweep(row.pk), 0)
        self.assertEqual(private_path(audio).read_bytes(), b'SYNTHETIC BYTES ANOTHER RECORD OWNS')
        self.assertEqual(redaction.files_left(row.pk), 0)               # another record's bytes are not the redaction's
        self.assertEqual(redaction.unapplied(j.verified()), 0)

    def test_FG2_replay_removes_a_late_result_the_documents_rows_reference(self):
        row, job, _ = self.worked_draft()
        self.redact(row)
        key = self.late(job)  # written and referenced, its own after-check never ran (the worker died)
        with self.quarantine():
            with self.captureOnCommitCallbacks(execute=True):
                x.replay(self.admin, self.fresh())
            self.assertFalse(private_path(key).exists())
            self.assertEqual(restore_admission.assess(self.instance, self.fresh(), RELEASE)['blockers'], [])

    def test_FG4_the_exact_retry_removes_a_late_result_the_documents_rows_reference(self):
        row, job, _ = self.worked_draft()
        requested, _tomb = self.redact(row)
        key = self.late(job)
        with self.captureOnCommitCallbacks(execute=True):
            redaction.execute(self.second, requested.pk, self.fresh())
        self.assertFalse(private_path(key).exists())
        self.assertEqual(redaction.unapplied(j.verified()), 0)

    def tombstone_for(self, row):
        ident = str(uuid.uuid4())
        entry = {'key_id': 'writer', 'signature': '0' * 128, 'body': {'contract': j.REDACTION, 'redaction': {
            'id': ident, 'target_id': str(row.pk), 'department_id': str(row.department_id), 'request_id': ident,
            'content_sha256': 'e' * 64, 'files': [], 'requested_by': str(self.admin.pk), 'approved_by': str(self.second.pk)}}}
        return m.RedactionTombstone(id=ident, target_id=row.pk, department_id=row.department_id, request_id=ident,
                                    content_sha256='e' * 64, files=[], journal_entry=entry, entry_sha256='f' * 64)

    def test_FG13_the_database_refuses_a_tombstone_for_a_finalized_document(self):
        """The database's own refusal, by behaviour: a reviewed change that re-pins the guard's hash cannot drop it
        unnoticed (the round-1 'killed' for this arm came from the hash pin alone)."""
        row, _, _ = self.worked_draft()
        with transaction.atomic():                                   # the control: unfinalized, the same row is taken
            self.tombstone_for(row).save(force_insert=True)
            transaction.set_rollback(True)
        m.Encounter.objects.filter(pk=row.pk).update(status='finalized')
        with self.assertRaisesMessage(DatabaseError, 'Only an unfinalized document of its own department can be redacted'):
            with transaction.atomic():
                self.tombstone_for(row).save(force_insert=True)


@override_settings(**ISOLATED)
class RoundThreeRepairs(RedactionFixture, TestCase):
    """Refutation round 3 of 75d11c09: the restore lens (R3R-T1, T3, T5, T19) and its false greens (R3F-2, R3F-3, R3F-9)."""
    def setUp(self): self.setup_journal()

    refusing = RoundTwoRepairs.refusing

    def link(self, relative, target):
        from django.conf import settings
        path = settings.MEDIA_ROOT.resolve() / relative
        if path.exists() or path.is_symlink(): path.unlink()
        path.parent.mkdir(parents=True, exist_ok=True); path.symlink_to(target)
        return path

    def test_R3RT1_a_symbolic_link_at_a_redacted_key_is_refused_and_its_target_never_removed(self):
        """75d11c09: private_path() resolves, so the sweep's symlink check never fired and it unlinked the link's TARGET, a
        template's original another document still uses, leaving the link."""
        row, _job, (audio, result) = self.worked_draft()
        original = private_path(self.scope[4].original_path)
        link = self.link(audio, original)
        with self.assertLogs('core.redaction', 'ERROR'):
            self.redact(row)
        self.assertTrue(original.exists())                        # 75d11c09: the template's original was unlinked
        self.assertTrue(link.is_symlink())
        self.assertFalse(private_path(result).exists())           # the document's own file is removed as before
        # A link placed at a redacted key afterwards (a restored volume): every later sweep refuses it too.
        late = self.link(result, original)
        with self.assertLogs('core.redaction', 'ERROR'):
            self.assertEqual(redaction.sweep(row.pk), 0)
        self.assertTrue(original.exists()); self.assertTrue(late.is_symlink())

    def test_R3RT3_a_release_whose_journal_copy_is_pending_holds_back_a_redaction(self):
        """75d11c09: a hold the journal never took was released and the release's journal copy failed; the redaction went
        ahead, and the custodian's later retry journaled the hold and its release AFTER the redaction. Every backup taken
        under the hold then replayed the redaction into a held document and stayed quarantined for good."""
        row, _job, _files = self.worked_draft()
        with patch('core.disposition_journal.append_hold', side_effect=ValidationError('SYNTHETIC journal outage')), \
                self.assertLogs('core.retention', 'ERROR'):
            hold = self.committed(lambda: self.patient_hold())        # recorded here, not journaled
        def after_the_backup():
            with patch('core.disposition_journal.append_release', side_effect=ValidationError('SYNTHETIC journal outage')), \
                    self.assertLogs('core.retention', 'ERROR'):
                self.committed(lambda: retention.release_hold(self.second, hold.pk, 'b' * 64))
            row.refresh_from_db()
            self.assertEqual(redaction.refusals(row), ['hold_release_not_journaled'])   # 75d11c09: [] and it went ahead
            with self.assertRaisesMessage(ValidationError, 'hold_release_not_journaled'):
                redaction.request(self.admin, row.pk, REASON, uuid.uuid4())
            self.committed(lambda: retention.release_hold(self.second, hold.pk, 'b' * 64))   # the exact retry journals it
            self.assertEqual(redaction.refusals(row), [])
            self.redact(row)
        self.older_backup(after_the_backup)                           # this database is the backup taken under the hold
        self.assertEqual([j.kind(entry) for entry in j.verified()][-3:], ['hold', 'release', 'redaction'])
        with self.quarantine():
            with self.captureOnCommitCallbacks(execute=True):
                x.replay(self.admin, self.fresh())                    # 75d11c09: 'A retention hold applies' for good
            self.assertEqual(restore_admission.assess(self.instance, self.fresh(), RELEASE)['blockers'], [])
        self.assertEqual(m.Encounter.objects.get(pk=row.pk).status, 'redacted')

    def test_R3RT5_the_worker_sweeps_bytes_a_failed_unlink_left_on_a_serving_instance(self):
        """R2D-Q1 stopped leftover bytes from quarantining a serving instance, and with it the only automatic retry there:
        a redaction applied by replay has no request row for the exact retry, and replay is refused once admitted."""
        row, _job, (audio, _result) = self.worked_draft()
        with self.refusing(audio), self.assertLogs('core.redaction', 'ERROR'):
            self.redact(row)
        self.assertTrue(private_path(audio).exists())
        self.assertEqual(redaction.sweep_left(), 1)                    # 75d11c09: no such pass
        self.assertFalse(private_path(audio).exists())
        self.assertEqual(redaction.files_left(row.pk), 0)
        self.assertEqual(redaction.sweep_left(), 0)
        from django.core.management import call_command
        with patch('core.management.commands.worker.run_one', return_value=False), \
                patch('core.management.commands.worker.mark_stale'), \
                patch('core.management.commands.worker.reap_abandoned_voice_uploads'), \
                patch('core.management.commands.worker.sweep_left') as swept:
            call_command('worker', once=True)
        swept.assert_called_once_with()                               # the worker loop runs it

    def test_R3RT19_an_over_limit_dictation_of_a_redacted_document_is_removed_with_it(self):
        """Until a doctor approves it, an over-limit upload is referenced only by its quote's audit row: a redaction left it
        on the volume, uncounted by admission and the exposure ledger, until the reaper removed it 40 minutes later."""
        from core.security import audit
        row, _job, _files = self.worked_draft()
        upload = f'audio/{uuid.uuid4().hex}{"6" * 16}.wav'
        self.write(upload, b'SYNTHETIC REDACTABLE DICTATION')
        audit(self.scope[0], 'voice.over_limit_quoted', row.pk, department=row.department, seconds='900',
              charge_limit='1.00', standard_limit='0.40', path=upload)
        self.assertIn(upload, redaction.referenced_files(row.pk))
        self.redact(row)
        self.assertFalse(private_path(upload).exists())               # 75d11c09: still on the volume, files_left 0
        self.assertEqual(redaction.unapplied(j.verified()), 0)

    def other_document(self):
        other_row, other_job, _ = self.worked_draft(self.other)
        return other_row, other_job

    def test_R3F2_R3F3_each_sharing_record_holds_back_the_redaction_and_keeps_the_bytes(self):
        """Only a shared Job.input_path and preserved files were tested; each arm of shared_keys is pinned here, through the
        execution refusal and through the sweep."""
        def other_job_result(key, other_row, other_job):
            m.Job.objects.filter(pk=other_job.pk).update(result_path=key)
        def other_receipt(key, other_row, other_job):
            job = m.Job.objects.create(encounter=other_row, user=self.other[0], kind='transcription', state='failed',
                                       request_key=str(uuid.uuid4()), provider='synthetic:fixture', payer='personal')
            m.ProviderReceipt.objects.create(job=job, provider='synthetic:fixture', actual_cost=Decimal('0.02'), simulated=True,
                                             result_path=key, result_sha256='f' * 64)   # receipts are append-only
        def template_original(key, other_row, other_job):
            m.Template.objects.filter(pk=self.other[4].pk).update(original_path=key)
        def other_export(key, other_row, other_job):
            m.Encounter.objects.filter(pk=self.other[5].pk).update(export_path=key, export_sha256='e' * 64)
        for arm in (other_job_result, other_receipt, template_original, other_export):
            with self.subTest(arm=arm.__name__), transaction.atomic():
                row, _job, (_audio, result) = self.worked_draft()
                other_row, other_job = self.other_document()
                arm(result, other_row, other_job)
                self.assertEqual(redaction.refusals(row), ['shared_or_preserved_file'])   # R3F-2/3: refusals []
                self.assertEqual(redaction.shared_keys([result], row.pk), {result})
                with self.assertLogs('core.redaction', 'ERROR'):
                    self.assertEqual(redaction.remove_files([{'storage_key': result, 'sha256': ''}], row.pk), 0)
                self.assertTrue(private_path(result).exists())                         # the other record's bytes stay

    def test_R3F9_when_sharing_cannot_be_read_nothing_is_removed(self):
        row, _job, (audio, result) = self.worked_draft()
        with patch('core.redaction.shared_keys', side_effect=DatabaseError('SYNTHETIC lost connection')), \
                self.assertLogs('core.redaction', 'ERROR'):
            self.assertEqual(redaction.remove_files([{'storage_key': audio, 'sha256': ''}], row.pk), 0)
        self.assertTrue(private_path(audio).exists())

    def test_R3F1_withheld_names_only_the_redacted_document(self):
        """The journal arm of withheld() is keyed on the redacted document. A mutant matching any journaled redaction
        discarded every document's provider output once one redaction existed, with every suite green."""
        row, _job, _files = self.worked_draft()
        requested = redaction.request(self.admin, row.pk, REASON, uuid.uuid4())
        with patch('core.redaction.apply', side_effect=DatabaseError('SYNTHETIC lost connection')):
            with self.assertRaises(DatabaseError): redaction.execute(self.second, requested.pk, self.fresh())
        self.assertFalse(m.RedactionTombstone.objects.exists())
        self.assertTrue(redaction.withheld(row.pk))              # journaled only: withheld
        self.assertFalse(redaction.withheld(self.scope[5].pk))   # another document: never
