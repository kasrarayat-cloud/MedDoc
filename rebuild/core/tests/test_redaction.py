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
        # Round 2 (R2D-X2): the removal of the bytes is audited too, counts and no path, so the exposure ledger knows when
        # they left this volume (core.exposure.commit_evidence); round 4 (R4S-4) names it 'redaction.swept' and records the
        # whole outcome, which also tells the worker whether to come back (redaction.sweep_left).
        self.assertEqual(sorted(m.AuditEvent.objects.filter(action__startswith='redaction.').values_list('action', flat=True)),
                         ['redaction.executed', 'redaction.requested', 'redaction.swept'])
        self.assertEqual(m.AuditEvent.objects.get(action='redaction.swept').details,
                         {'removed': len(files), 'retryable': 0, 'refused': 0, 'sequence': 1, 'quotes': 0})
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


@override_settings(**ISOLATED)
class RoundFourRepairs(RedactionFixture, TestCase):
    """Refutation round 4 of b3d8111d: the sweep lens (R4S-1..R4S-4, R4S-6) and the restore half of its false greens
    (R4F-A, R4F-1..R4F-6, R4F-14)."""
    def setUp(self): self.setup_journal()

    refusing = RoundTwoRepairs.refusing
    link = RoundThreeRepairs.link

    def overlimit(self, row):
        """What core.views.voice leaves after an over-limit quote: the stored upload and its audit row, no job yet."""
        from core.security import audit
        upload = f'audio/{uuid.uuid4().hex}{"a" * 16}.wav'
        self.write(upload, b'SYNTHETIC OVER-LIMIT DICTATION BYTES')
        audit(self.scope[0], 'voice.over_limit_quoted', row.pk, department=row.department, seconds='900',
              charge_limit='1.00', standard_limit='0.40', path=upload)
        return upload

    def at(self, minutes):
        return patch('django.utils.timezone.now', return_value=self.base + timedelta(minutes=minutes))

    def test_R4S1_the_reaper_removing_a_pending_dictation_never_strands_a_redaction(self):
        """b3d8111d: the dictation was part of the content fingerprint, and the reaper deletes it on its own 40-minute timer:
        a pending redaction's execute, or a journaled one's exact retry, then refused for good ('content changed'). The
        fingerprint covers what the document's own rows hold; a pending dictation is swept with them, never fingerprinted."""
        from core import jobs
        for journaled_first in (False, True):
            with self.subTest(journaled_first=journaled_first):
                row, _job, (audio, result) = self.worked_draft()
                upload = self.overlimit(row)
                requested = redaction.request(self.admin, row.pk, REASON, uuid.uuid4())
                if journaled_first:                                    # journaled, then its commit failed (F3's state)
                    with patch('core.redaction.apply', side_effect=DatabaseError('SYNTHETIC lost connection')):
                        with self.assertRaises(DatabaseError):
                            redaction.execute(self.second, requested.pk, self.fresh())
                with self.at(41):
                    self.assertEqual(jobs.reap_abandoned_voice_uploads(), 1)   # the worker's reaper, on its own timer
                self.assertFalse(private_path(upload).exists())
                with self.captureOnCommitCallbacks(execute=True):
                    redaction.execute(self.second, requested.pk, self.fresh())  # b3d8111d: CONTENT_CHANGED for good
                self.assertEqual(m.Encounter.objects.get(pk=row.pk).status, 'redacted')
                self.assertFalse(private_path(audio).exists() or private_path(result).exists())
        # The dictation is still removed with the document when the reaper has not run yet.
        row, _job, _files = self.worked_draft()
        upload = self.overlimit(row)
        self.redact(row)
        self.assertFalse(private_path(upload).exists())

    def test_R4S2_the_reapers_removal_of_a_redacted_dictation_dates_the_exposure(self):
        """The reaper and the sweep both remove a redacted document's dictation, and the ledger dated byte removal by the
        sweep's audit only: a dictation the reaper removed two hours on was counted as gone at the commit."""
        from core import exposure, jobs
        row, _job, _files = self.worked_draft()
        upload = self.overlimit(row)
        with self.at(1), self.refusing(upload), self.assertLogs('core.redaction', 'ERROR'):
            _requested, tomb = self.redact(row)
        self.assertIsNone(exposure.commit_evidence().get(str(tomb.pk)))      # bytes left: no evidence yet
        with self.at(120):
            self.assertEqual(jobs.reap_abandoned_voice_uploads(), 1)         # the reaper removes it first
        evidence = exposure.commit_evidence()[str(tomb.pk)]
        self.assertEqual(evidence, self.base + timedelta(minutes=120))      # b3d8111d: the commit time, T+1m

    def pending_release(self, scope_patient=None):
        """A hold the journal never took, released here while the release's journal copy fails."""
        with patch('core.disposition_journal.append_hold', side_effect=ValidationError('SYNTHETIC journal outage')), \
                self.assertLogs('core.retention', 'ERROR'):
            hold = self.committed(lambda: retention.create_hold(self.admin, 'patient', scope_patient or self.scope[3].pk,
                                                                'a' * 64, uuid.uuid4()))
        with patch('core.disposition_journal.append_release', side_effect=ValidationError('SYNTHETIC journal outage')), \
                self.assertLogs('core.retention', 'ERROR'):
            self.committed(lambda: retention.release_hold(self.second, hold.pk, 'b' * 64))
        return hold

    def test_R4FA_R4S3_any_active_custodian_journals_a_committed_release_from_its_own_evidence(self):
        """b3d8111d: only the releasing custodian's exact retry could journal a pending release; once that custodian left,
        every redaction in the hold's scope was refused for good. Any active verified custodian journals the committed
        release as it was recorded (its id, authority and releasing custodian), audited under the one who does it."""
        row, _job, _files = self.worked_draft()
        hold = self.pending_release()
        m.User.objects.filter(pk=self.second.pk).update(is_active=False)    # the releasing custodian has left
        self.assertEqual(redaction.refusals(row), ['hold_release_not_journaled'])
        third = self.custodian('custodian3')
        with self.assertRaises(PermissionDenied):
            retention.release_hold(self.second, hold.pk, 'b' * 64)           # (the control: the old path is closed)
        entry = retention.journal_committed_release(third, hold.pk)
        release = m.RetentionHoldRelease.objects.get(hold=hold)
        self.assertEqual(entry['body']['release'], {'id': str(release.pk), 'hold_id': str(hold.pk),
                                                    'authority_sha256': 'b' * 64, 'created_by': str(self.second.pk)})
        self.assertEqual(m.AuditEvent.objects.get(action='retention.release_journaled').actor_id, third.pk)
        self.assertEqual(retention.journal_committed_release(third, hold.pk), entry)   # idempotent: nothing appended
        self.assertEqual([j.kind(e) for e in j.verified()].count('release'), 1)
        self.assertEqual(redaction.refusals(row), [])
        self.redact(row, approver=third)                                     # (the releasing custodian has left)
        with self.assertRaises(PermissionDenied):
            retention.journal_committed_release(m.User.objects.get(pk=self.second.pk), hold.pk)   # not by a departed one

    def test_R4FA_the_command_journals_every_pending_release_in_a_documents_scope(self):
        import io
        from django.core.management import call_command
        row, _job, _files = self.worked_draft()
        self.pending_release()
        third = self.custodian('custodian3')
        out = io.StringIO()
        call_command('redaction', 'journal-releases', '--custodian', third.email, '--document', str(row.pk), stdout=out)
        self.assertEqual(json.loads(out.getvalue()), {'journaled_releases': 1})
        self.assertEqual(redaction.refusals(row), [])

    def test_R4F5_a_pending_release_outside_the_documents_scope_refuses_nothing(self):
        row, _job, _files = self.worked_draft()
        self.pending_release(scope_patient=self.other[3].pk)                 # another organization's patient
        self.assertEqual(redaction.refusals(row), [])
        redaction.request(self.admin, row.pk, REASON, uuid.uuid4())

    def test_R4S4_the_steady_state_sweep_costs_the_same_however_many_redactions_exist(self):
        """b3d8111d ran files_left (about 14 queries, an unindexed audit scan among them) for every tombstone every minute.
        A document whose last sweep left nothing retryable is not visited again."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        def pass_cost():
            with CaptureQueriesContext(connection) as queries:
                self.assertEqual(redaction.sweep_left(), 0)
            return len(queries.captured_queries)
        self.redact(self.worked_draft()[0])
        one = pass_cost()
        gone, _job, files = self.worked_draft()
        for key in files: private_path(key).unlink()                         # a redaction whose sweep finds nothing to remove
        self.redact(gone)
        for _ in range(3):
            self.redact(self.worked_draft()[0])
        self.assertEqual(pass_cost(), one)                                   # b3d8111d: grows by ~14 per redaction
        self.assertLessEqual(one, 3)

    def test_R4S4_the_dictation_read_is_narrowed_by_the_documents_department(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        row, _job, _files = self.worked_draft()
        upload = self.overlimit(row)
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(redaction.pending_uploads(row.pk), [upload])
        audit_reads = [q['sql'] for q in queries.captured_queries if 'core_auditevent' in q['sql']]
        self.assertTrue(audit_reads and all('"department_id" =' in sql for sql in audit_reads), audit_reads)

    def test_R4F2_R4F3_R4F4_one_unreadable_record_stops_neither_the_sweep_nor_the_worker(self):
        from django.core.management import call_command
        first, _j1, (audio1, _r1) = self.worked_draft()
        second, _j2, (audio2, _r2) = self.worked_draft()
        third, _j3, (audio3, _r3) = self.worked_draft()
        with self.refusing(audio1, audio2, audio3), self.assertLogs('core.redaction', 'ERROR'):
            self.redact(first); self.redact(second); self.redact(third)
        real = redaction.sweep
        def unreadable(target_id, *args, **kwargs):
            if str(target_id) == str(first.pk): raise ValidationError('SYNTHETIC unreadable record')
            return real(target_id, *args, **kwargs)
        with patch('core.redaction.sweep', side_effect=unreadable), self.assertLogs('core.redaction', 'ERROR'):
            self.assertEqual(redaction.sweep_left(), 2)                      # every other document is swept (R4F-3, R4F-4)
        self.assertTrue(private_path(audio1).exists())
        self.assertFalse(private_path(audio2).exists() or private_path(audio3).exists())
        with patch('core.redaction.sweep', side_effect=unreadable), \
                patch('core.management.commands.worker.run_one', return_value=False) as ran, \
                patch('core.management.commands.worker.mark_stale'), \
                patch('core.management.commands.worker.reap_abandoned_voice_uploads'), \
                self.assertLogs('core.redaction', 'ERROR'):
            call_command('worker', once=True)                                # R4F-2: the queue is still served
        ran.assert_called_once_with()

    def test_R4F1_a_key_reached_through_a_linked_directory_is_refused(self):
        from django.conf import settings
        row, job, (audio, _result) = self.worked_draft()
        name = f'{uuid.uuid4().hex}{"b" * 16}.docx'                         # a production-shaped key (the journal's pattern)
        original = self.write(f'originals/{name}', b'SYNTHETIC ANOTHER DEPARTMENT ORIGINAL')
        m.Template.objects.filter(pk=self.other[4].pk).update(original_path=f'originals/{name}')
        root = settings.MEDIA_ROOT.resolve()
        (root / 'lnk').symlink_to(original.parent, target_is_directory=True)
        m.Job.objects.filter(pk=job.pk).update(input_path=f'lnk/{name}')     # the key resolves into another record's file
        with self.assertLogs('core.redaction', 'ERROR'):
            self.redact(row)
        self.assertTrue(original.exists())                                   # b3d8111d without its second half: unlinked

    def test_R4F6_a_state_directory_behind_a_symbolic_link_is_still_swept(self):
        import tempfile
        from django.conf import settings
        row, _job, (audio, _result) = self.worked_draft()
        import os
        holder = tempfile.mkdtemp()
        linked = Path(holder) / 'media'; linked.symlink_to(settings.MEDIA_ROOT.resolve(), target_is_directory=True)
        self.addCleanup(os.rmdir, holder); self.addCleanup(linked.unlink)
        with override_settings(MEDIA_ROOT=linked):
            self.assertEqual(redaction.remove_files([{'storage_key': audio, 'sha256': ''}], row.pk), 1)
        self.assertFalse(private_path(audio).exists())

    def test_R4S6_R4F14_a_link_at_a_redacted_key_is_reported_once_and_never_promised_away(self):
        row, _job, (audio, result) = self.worked_draft()
        self.redact(row)
        original = private_path(self.scope[4].original_path)
        self.link(result, original)
        with self.assertLogs('core.redaction', 'ERROR') as logged:
            self.assertEqual(redaction.sweep(row.pk), 0)
        self.assertNotIn('removes it', ' '.join(logged.output))             # b3d8111d: a promise nothing keeps
        self.assertIn('operator', ' '.join(logged.output))
        with self.assertNoLogs('core.redaction', 'ERROR'):
            for _ in range(3):
                self.assertEqual(redaction.sweep_left(), 0)                  # b3d8111d: one error per minute, forever
        self.assertTrue(original.exists())

    def test_R4S6_the_newest_sweep_decides_a_retry_whatever_the_clock_says(self):
        """The round-4 repair read a document's latest 'redaction.swept' by time; a sweep on the same timestamp as the one
        before it, or after a clock stepped back, was read as the OLDER one, so a document whose newest sweep left bytes
        retryable was taken as clean and its bytes were never retried. Found by the repair's own mutant (links counted as
        retryable survived: the frozen fixture clock tied the two rows)."""
        for minutes in (5, 10):                                          # stepped back; the same timestamp
            with self.subTest(newest_sweep_at=minutes):
                row, _job, (audio, result) = self.worked_draft()
                with self.at(10):
                    self.redact(row)                                     # clean: {'removed': 2}
                restored = self.write(result, b'SYNTHETIC BYTES A RESTORE PUT BACK')
                with self.at(minutes), self.refusing(result), self.assertLogs('core.redaction', 'ERROR'):
                    self.assertEqual(redaction.sweep(row.pk), 0)         # newest: one retryable
                with self.at(11):
                    self.assertEqual(redaction.sweep_left(), 1)          # before: read as clean, never retried
                self.assertFalse(restored.exists())

    def test_R4S6_between_two_sweeps_of_one_number_the_later_decides(self):
        """Two sweeps running at once both number their outcome one past the last; then the later in time is the newer
        state of the document. Both insertion orders, so the reading never rests on the order rows come back in."""
        from core.security import audit
        clean, retry = {'removed': 1, 'retryable': 0, 'refused': 0, 'sequence': 2}, {'removed': 0, 'retryable': 1, 'refused': 0, 'sequence': 2}
        for later in ('clean', 'retryable'):
            with self.subTest(later=later):
                row, _job, _files = self.worked_draft()
                self.redact(row)                                         # sequence 1, at the fixture time
                rows = [(5, retry), (10, clean)] if later == 'clean' else [(5, clean), (10, retry)]
                for minutes, details in rows:
                    with self.at(minutes):
                        audit(None, 'redaction.swept', row.pk, **details)
                latest = redaction.latest_outcomes(m.AuditEvent.objects.filter(action='redaction.swept', target=str(row.pk)))
                self.assertEqual(latest[str(row.pk)], rows[-1][1])

    def test_R4S4_a_retry_that_changes_nothing_records_nothing(self):
        """A failure the worker retries every minute (a permission the operator has not fixed yet) is recorded when it
        appears and when it changes, never once a minute: the audit table is append-only."""
        row, _job, (audio, result) = self.worked_draft()
        with self.at(1), self.refusing(result), self.assertLogs('core.redaction', 'ERROR'):
            self.redact(row)
        swept = lambda: m.AuditEvent.objects.filter(action='redaction.swept', target=str(row.pk)).count()
        recorded = swept()
        for minute in (2, 3, 4):
            with self.at(minute), self.refusing(result), self.assertLogs('core.redaction', 'ERROR'):
                self.assertEqual(redaction.sweep_left(), 0)              # retried: still refused
        self.assertEqual(swept(), recorded)
        with self.at(5):
            self.assertEqual(redaction.sweep_left(), 1)                  # the permission fixed: removed, and recorded
        self.assertEqual(swept(), recorded + 1)
        self.assertFalse(private_path(result).exists())


@override_settings(**ISOLATED)
class RoundFiveRepairs(RedactionFixture, TestCase):
    """Refutation round 5 of a0bc4fd8: the restore lens (R5R-1, R5R-2) and the redaction half of its false greens
    (R5F-1..R5F-3, R5F-5..R5F-9, R5F-11..R5F-13)."""
    def setUp(self): self.setup_journal()

    refusing = RoundTwoRepairs.refusing
    link = RoundThreeRepairs.link
    overlimit = RoundFourRepairs.overlimit
    at = RoundFourRepairs.at
    pending_release = RoundFourRepairs.pending_release

    def latest(self, row):
        return redaction.latest_outcomes(m.AuditEvent.objects.filter(action='redaction.swept', target=str(row.pk))).get(
            str(row.pk))

    def quote(self, row, upload):
        from core.security import audit
        audit(self.scope[0], 'voice.over_limit_quoted', row.pk, department=row.department, seconds='900',
              charge_limit='1.00', standard_limit='0.40', path=upload)

    def test_R5R1_a_restored_volume_newer_than_its_database_never_keeps_a_redacted_dictation(self):
        """a0bc4fd8 journaled only the files the fingerprint covers, so the journal (the one record of a redaction's keys
        outside the clinical backup) no longer named the over-limit dictation. A database restored from before the quote,
        paired with a volume snapshot from after it (ops/production_restore_check.py), replayed with the dictation left on
        the volume, admitted, and dated the exposure as ended; nothing referenced the key again. Both orders: the quote
        pending at the redaction, and the reaper having removed it live first (the restored volume still holds it)."""
        from core import exposure, jobs
        for reaper_first in (False, True):
            with self.subTest(reaper_first=reaper_first):
                row, _job, files = self.worked_draft()
                originals = {key: private_path(key).read_bytes() for key in files}
                snapshot = {}
                def quote_then_redact():
                    upload = self.overlimit(row)                               # after the database's recovery point
                    snapshot[upload] = private_path(upload).read_bytes()       # the volume snapshot is taken now
                    if reaper_first:
                        with self.at(41):
                            self.assertEqual(jobs.reap_abandoned_voice_uploads(), 1)
                    _requested, tomb = self.redact(row)
                    return upload, tomb.journal_entry
                upload, entry = self.older_backup(quote_then_redact)
                self.assertIn(upload, [record['storage_key'] for record in entry['body']['redaction']['files']])
                for key, data in {**originals, **snapshot}.items(): self.write(key, data)
                self.assertFalse(m.AuditEvent.objects.filter(action='voice.over_limit_quoted', target=str(row.pk)).exists())
                with self.quarantine():
                    with self.refusing(upload), self.assertLogs('core.redaction', 'ERROR'):
                        with self.captureOnCommitCallbacks(execute=True):
                            x.replay(self.admin, self.fresh())
                    self.assertTrue(private_path(upload).exists())
                    self.assertIn('redaction_replay_incomplete',                # a0bc4fd8: admissible
                                  restore_admission.assess(self.instance, self.fresh(), RELEASE)['blockers'])
                    with self.captureOnCommitCallbacks(execute=True):
                        x.replay(self.admin, self.fresh())
                    self.assertFalse(private_path(upload).exists())             # a0bc4fd8: left on the volume
                    self.assertEqual(restore_admission.assess(self.instance, self.fresh(), RELEASE)['blockers'], [])
                tomb = m.RedactionTombstone.objects.get(target_id=row.pk)
                self.assertIn(str(tomb.pk), exposure.commit_evidence())

    def test_R5R2_a_quote_written_after_the_clean_sweep_is_swept_by_the_next_worker_pass(self):
        """views.voice stores the upload, enqueue refuses over the limit and releases the lock, and only then is the quote
        audited: a redaction committing in between swept clean, and a0bc4fd8's worker never came back (the reaper removed
        the dictation 40 minutes later). The frozen clock gives the quote and the sweep one timestamp, as two processes'
        clocks may."""
        row, _job, _files = self.worked_draft()
        upload = f'audio/{uuid.uuid4().hex}{"c" * 16}.wav'
        self.write(upload, b'SYNTHETIC OVER-LIMIT DICTATION BYTES')            # store_upload, before enqueue
        self.redact(row)                                                        # commits and sweeps before the quote
        self.quote(row, upload)
        self.assertEqual(redaction.sweep_left(), 1)                             # a0bc4fd8: 0
        self.assertFalse(private_path(upload).exists())
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(redaction.sweep_left(), 0)
        self.assertLessEqual(len(queries.captured_queries), 3)                  # seen once: not revisited

    def test_R5R2_a_quote_whose_dictation_is_already_gone_is_seen_once(self):
        """A revisit that removes nothing (the reaper got there first, or the upload never reached the volume) still records
        the quote as seen; otherwise the document would be swept every minute for good."""
        from django.test.utils import CaptureQueriesContext
        row, _job, _files = self.worked_draft()
        self.redact(row)
        self.quote(row, f'audio/{uuid.uuid4().hex}{"e" * 16}.wav')               # its bytes are not on this volume
        self.assertEqual(redaction.sweep_left(), 0)
        self.assertEqual(self.latest(row)['quotes'], 1)
        for _ in range(2):
            with CaptureQueriesContext(connection) as queries:
                self.assertEqual(redaction.sweep_left(), 0)
            self.assertLessEqual(len(queries.captured_queries), 3)

    def test_R5R2_a_quote_landing_while_a_sweep_reads_the_files_is_revisited(self):
        """The sweep counts the quotes BEFORE it reads the files: a quote landing in between is revisited, never recorded as
        seen with its dictation still on the volume."""
        row, _job, _files = self.worked_draft()
        upload = f'audio/{uuid.uuid4().hex}{"d" * 16}.wav'
        self.write(upload, b'SYNTHETIC OVER-LIMIT DICTATION BYTES')
        real = redaction.redacted_files
        def then_quoted(target_id):
            files = real(target_id)
            if str(target_id) == str(row.pk) and not m.AuditEvent.objects.filter(action='voice.over_limit_quoted').exists():
                self.quote(row, upload)                                          # lands after the files were read
            return files
        with patch('core.redaction.redacted_files', then_quoted):
            self.redact(row)
        self.assertTrue(private_path(upload).exists())
        self.assertEqual(redaction.sweep_left(), 1)
        self.assertFalse(private_path(upload).exists())

    def test_R5F1_a_redaction_whose_commit_sweep_never_ran_is_swept_by_the_worker(self):
        """The process ends between the commit and its on-commit sweep: no 'redaction.swept' row, every byte left."""
        row, _job, files = self.worked_draft()
        requested = redaction.request(self.admin, row.pk, REASON, uuid.uuid4())
        with self.captureOnCommitCallbacks(execute=False):
            redaction.execute(self.second, requested.pk, self.fresh())
        self.assertIsNone(self.latest(row))
        self.assertEqual(redaction.sweep_left(), len(files))
        self.assertEqual(redaction.files_left(row.pk), 0)

    def test_R5F2_an_unreadable_sharing_check_is_retryable_and_the_worker_comes_back(self):
        row, _job, files = self.worked_draft()
        requested = redaction.request(self.admin, row.pk, REASON, uuid.uuid4())
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            redaction.execute(self.second, requested.pk, self.fresh())
        with patch('core.redaction.shared_keys', side_effect=DatabaseError('SYNTHETIC lost connection')), \
                self.assertLogs('core.redaction', 'ERROR'):
            for callback in callbacks: callback()
        self.assertEqual(self.latest(row)['retryable'], len(files))
        self.assertEqual(redaction.sweep_left(), len(files))
        self.assertEqual(redaction.files_left(row.pk), 0)

    def test_R5F3_a_removal_alone_is_recorded_and_dates_the_exposure(self):
        """Nothing retryable or refused before or after: only the removal records the sweep that ended the exposure."""
        from core import exposure
        row, _job, (audio, result) = self.worked_draft()
        with self.at(1):
            _requested, tomb = self.redact(row)
        self.write(result, b'SYNTHETIC BYTES A RESTORED VOLUME PUT BACK')
        with self.at(60):
            self.assertIsNone(exposure.commit_evidence().get(str(tomb.pk)))
            self.assertEqual(redaction.sweep(row.pk), 1)
        self.assertEqual(exposure.commit_evidence()[str(tomb.pk)], self.base + timedelta(minutes=60))

    def test_R5F5_another_records_key_is_said_once_and_never_retried(self):
        row, _job, (audio, result) = self.worked_draft()
        with self.at(1), self.refusing(audio), self.assertLogs('core.redaction', 'ERROR'):
            self.redact(row)                                                    # the recording's unlink failed
        other = self.worked_draft(self.other)[1]
        m.Job.objects.filter(pk=other.pk).update(input_path=audio)             # its key is now another record's
        with self.at(2), self.assertLogs('core.redaction', 'ERROR'):
            redaction.sweep_left()
        self.assertEqual({key: self.latest(row)[key] for key in ('retryable', 'refused')}, {'retryable': 0, 'refused': 1})
        with self.assertNoLogs('core.redaction', 'ERROR'):
            for minute in (3, 4, 5):
                with self.at(minute):
                    redaction.sweep_left()
        self.assertTrue(private_path(audio).exists())

    def test_R5F6_a_newly_refused_link_is_recorded(self):
        row, _job, (audio, result) = self.worked_draft()
        with self.at(1):
            self.redact(row)
        self.link(result, private_path(self.scope[4].original_path))
        with self.at(30), self.assertLogs('core.redaction', 'ERROR'):
            redaction.sweep(row.pk)
        self.assertEqual({key: self.latest(row)[key] for key in ('removed', 'retryable', 'refused')},
                         {'removed': 0, 'retryable': 0, 'refused': 1})

    def journal_releases(self, *arguments):
        import io
        from django.core.management import call_command
        out = io.StringIO()
        call_command('redaction', 'journal-releases', *arguments, stdout=out)
        return json.loads(out.getvalue())

    def test_R5F7_journal_releases_refuses_anyone_but_an_active_custodian(self):
        from django.core.management.base import CommandError
        row, _job, _files = self.worked_draft()
        m.User.objects.filter(pk=self.second.pk).update(is_active=False)
        for email in ('nobody@synthetic.invalid', self.second.email, self.scope[0].email):
            with self.subTest(email=email.split('@')[0]):
                with self.assertRaisesMessage(CommandError, 'An active verified administrator is required.'):
                    self.journal_releases('--custodian', email, '--document', str(row.pk))

    def test_R5F8_journal_releases_needs_a_document(self):
        from django.core.management.base import CommandError
        self.pending_release(scope_patient=self.other[3].pk)
        third = self.custodian('custodian3')
        with self.assertRaisesMessage(CommandError, 'journal-releases needs --document.'):
            self.journal_releases('--custodian', third.email)
        self.assertFalse(m.AuditEvent.objects.filter(action='retention.release_journaled').exists())

    def test_R5F9_a_second_run_journals_nothing_and_audits_nothing(self):
        row, _job, _files = self.worked_draft()
        self.pending_release()
        third = self.custodian('custodian3')
        runs = [self.journal_releases('--custodian', third.email, '--document', str(row.pk)) for _ in range(2)]
        self.assertEqual(runs, [{'journaled_releases': 1}, {'journaled_releases': 0}])
        self.assertEqual(m.AuditEvent.objects.filter(action='retention.release_journaled').count(), 1)

    def test_R5F11_journaling_an_unreleased_hold_is_refused_as_such(self):
        hold = self.committed(lambda: retention.create_hold(self.admin, 'patient', self.scope[3].pk, 'a' * 64, uuid.uuid4()))
        with self.assertRaisesMessage(ValidationError, 'This preservation instruction has no committed release.'):
            retention.journal_committed_release(self.custodian('custodian3'), hold.pk)

    def test_R5F12_journal_releases_for_an_unknown_document_is_refused(self):
        """a0bc4fd8: scoped_holds answers an unknown id with every hold, so a mistyped document id journaled every pending
        release in the database, across organizations, under the caller."""
        from django.core.management.base import CommandError
        self.pending_release(scope_patient=self.other[3].pk)                  # another organization's patient
        third = self.custodian('custodian3')
        for document in (str(uuid.uuid4()), 'not-a-document-id'):
            with self.subTest(document=document):
                with self.assertRaisesMessage(CommandError, 'Unknown document.'):
                    self.journal_releases('--custodian', third.email, '--document', document)
        self.assertFalse(m.AuditEvent.objects.filter(action='retention.release_journaled').exists())

    def test_R5F13_a_release_is_audited_as_journaled_only_by_whoever_journaled_it(self):
        """a0bc4fd8 audited every call: a second call, or one after the releasing custodian's exact retry had journaled it,
        appended nothing and still recorded a journaling under the caller."""
        hold = self.pending_release()
        third = self.custodian('custodian3')
        first = retention.journal_committed_release(third, hold.pk)
        self.assertEqual(retention.journal_committed_release(third, hold.pk), first)
        self.assertEqual(m.AuditEvent.objects.filter(action='retention.release_journaled').count(), 1)
        other = self.pending_release()                                          # a second hold, its release copy pending
        self.committed(lambda: retention.release_hold(self.second, other.pk, 'b' * 64))   # the releaser's exact retry
        retention.journal_committed_release(third, other.pk)
        self.assertEqual(m.AuditEvent.objects.filter(action='retention.release_journaled').count(), 1)
