"""1a: preservation holds and releases are signed into the independent journal before their rows commit.

Synthetic organizations, patients, documents and keys generated inside each test only. No retention period, schedule
or duration exists here: holds preserve, nothing is aged, and nothing clinical is deleted.
"""
import uuid
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings

from core import models as m, retention, disposition_execution as x, disposition_journal as j, disposition_policy as p
from core.security import private_path
from core.tests.test_disposition_execution import ExecutionFixture
from core.tests.test_retention_preservation import ISOLATED
from ops import integrity_contract, production_restore_check as restore_check

HOLD_REFUSAL = 'Work, review, financial or preservation history makes this adapter unavailable.'


def query(sql):
    with connection.cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchall()


class HoldJournalFixture(ExecutionFixture):
    def setup_journal(self):
        self.setup_execution()
        self.instance = str(uuid.uuid4())
        # The files this synthetic database references, so the restore check's file section can pass.
        for scope in (self.scope, self.other):
            path = private_path(scope[4].original_path); path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(scope[6])

    def older_backup(self, action):
        """Run `action` as committed work (its after-commit steps included), then roll back its database effects: an
        exact backup taken before it. The journal survives."""
        with transaction.atomic():
            with TestCase.captureOnCommitCallbacks(execute=True):
                result = action()
            transaction.set_rollback(True)
        return result

    def quarantine(self, instance=None):
        return override_settings(RESTORE_QUARANTINE=True, RESTORE_INSTANCE_ID=instance or self.instance)

    def fresh(self):
        return self.checkpoint(j.verified())

    def patient_hold(self, key=None, authority='a'*64, actor=None):
        return retention.create_hold(actor or self.admin, 'patient', self.scope[3].pk, authority, key or uuid.uuid4())

    def restore_check(self):
        return restore_check.check(query, None, len(integrity_contract.GUARDS), journal_holds=list(j.journaled_holds()),
                                   files_root=settings.MEDIA_ROOT)

    def entry(self, number, previous, contract, field, record):
        return self.sign(self.writer, 'writer', {'contract': contract, 'namespace': self.namespace, 'sequence': number,
                                                 'previous_sha256': previous, 'written_at': self.base.isoformat(), field: record})

    def write(self, *envelopes):
        self.path.write_bytes(b''.join(p.canonical(e) + b'\n' for e in envelopes))


@override_settings(**ISOLATED)
class HoldJournal(HoldJournalFixture, TestCase):
    def setUp(self): self.setup_journal()

    def test_a_hold_is_fsynced_before_its_row_and_a_release_only_after_its_row_committed(self):
        events = []
        real_fsync = j.os.fsync
        def fsync(descriptor):
            events.append('fsync'); return real_fsync(descriptor)
        def row(model):
            real = model.objects.create
            def create(**values):
                # At the moment the row is written, the entry naming its id is already in the journal file.
                events.append(('row', model.__name__, str(values['id']) in self.path.read_text()))
                return real(**values)
            return create
        with patch.object(j.os, 'fsync', side_effect=fsync), \
                patch.object(m.RetentionHold.objects, 'create', side_effect=row(m.RetentionHold)), \
                patch.object(m.RetentionHoldRelease.objects, 'create', side_effect=row(m.RetentionHoldRelease)):
            hold = self.patient_hold()
            with self.captureOnCommitCallbacks() as after_commit:
                release = retention.release_hold(self.second, hold.pk, 'b'*64)
            # The release row is written while the journal still holds only the hold; its entry waits for the commit.
            self.assertEqual(events, ['fsync', 'fsync', ('row', 'RetentionHold', True), ('row', 'RetentionHoldRelease', False)])
            self.assertEqual([j.kind(e) for e in j.verified()], ['hold'])
            for callback in after_commit: callback()
        self.assertEqual(events, ['fsync', 'fsync', ('row', 'RetentionHold', True), ('row', 'RetentionHoldRelease', False),
                                  'fsync', 'fsync'])
        entries = j.verified(self.fresh())  # every signature and the chain verify against an independent checkpoint
        self.assertEqual([j.kind(e) for e in entries], ['hold', 'release'])
        self.assertEqual(entries[0]['body']['hold'], retention.hold_record(hold))
        self.assertEqual(entries[1]['body']['release'], {'id': str(release.pk), 'hold_id': str(hold.pk),
                                                         'authority_sha256': 'b'*64, 'created_by': str(self.second.pk)})
        self.assertNotIn(self.scope[3].display_name, self.path.read_text())

    def test_a_journal_append_followed_by_a_database_rollback_keeps_files_and_the_hold_active(self):
        key = uuid.uuid4(); held = self.file(); other = self.file(); unknown = self.file('submissions')
        with patch('core.retention.audit', side_effect=RuntimeError('SYNTHETIC crash after the row, before commit')):
            with self.assertRaises(RuntimeError): self.patient_hold(key)
        self.assertFalse(m.RetentionHold.objects.exists())
        hold_id = j.verified()[0]['body']['hold']['id']
        # Treated as active: the held patient's file is kept and recorded, an unattributed file is kept, and a file of
        # an unrelated patient is still cleaned (the hold is not a blanket refusal).
        self.assertFalse(retention.cleanup_file(held, encounter_id=self.encounter.pk)); self.assertTrue(held.exists())
        self.assertEqual(m.PreservedFile.objects.get().hold_ids, [hold_id])
        self.assertFalse(retention.cleanup_file(unknown)); self.assertTrue(unknown.exists())
        self.assertTrue(retention.cleanup_file(other, encounter_id=self.other[5].pk)); self.assertFalse(other.exists())
        # The same key with other evidence refuses at the journal; the exact retry records the journaled id.
        with self.assertRaisesMessage(ValidationError, 'already used for another instruction'): self.patient_hold(key, 'c'*64)
        hold = self.patient_hold(key)
        self.assertEqual(str(hold.pk), hold_id); self.assertEqual(len(j.verified()), 1)

    def test_a_draft_covered_only_by_a_journaled_hold_is_not_disposed(self):
        row, instruction = self.approved()
        with patch('core.retention.audit', side_effect=RuntimeError('SYNTHETIC crash before commit')):
            with self.assertRaises(RuntimeError): retention.create_hold(self.admin, 'encounter', row.pk, 'a'*64, uuid.uuid4())
        self.assertFalse(m.RetentionHold.objects.exists())
        with self.assertRaisesMessage(ValidationError, HOLD_REFUSAL): x.execute(self.admin, instruction.pk, self.fresh())
        self.assertTrue(m.Encounter.objects.filter(pk=row.pk).exists()); self.assertEqual(j.instruction_entries(j.verified()), [])
        # Positive control: an approved draft outside the hold's scope is disposed with the same fresh checkpoint.
        other, approved = self.approved()
        self.assertEqual(x.execute(self.admin, approved.pk, self.fresh()).outcome, 'empty_draft_deleted')

    def test_a_configured_journal_that_is_missing_or_unverifiable_never_refuses_the_hold_nor_is_rewritten(self):
        # Preservation first (L2:R2-2, L1:P4): the hold is recorded here, the failure logged; the journal is untouched.
        missing = Path(self.journal_temp.name) / 'missing.jsonl'
        with override_settings(DISPOSITION_JOURNAL_PATH=str(missing)), self.assertLogs('core.retention', 'ERROR'):
            first = self.patient_hold()
        self.assertFalse(missing.exists())  # a hold never creates or re-initializes a journal
        record = {'id': str(uuid.uuid4()), 'scope': 'global', 'target_id': None, 'authority_sha256': 'a'*64,
                  'request_key': str(uuid.uuid4()), 'created_by': str(self.admin.pk)}
        self.write(dict(self.entry(1, p.ZERO, j.HOLD, 'hold', record), signature='0'*128))  # an entry nobody signed
        before = self.path.read_bytes()
        with self.assertLogs('core.retention', 'ERROR'):
            second = retention.create_hold(self.admin, 'patient', self.other[3].pk, 'a'*64, uuid.uuid4())
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(set(m.RetentionHold.objects.values_list('pk', flat=True)), {first.pk, second.pk})
        self.assertEqual([m.AuditEvent.objects.get(action='retention.hold_created', target=str(row.pk)).details['journaled']
                          for row in (first, second)], [False, False])

    def test_a_release_is_journaled_after_its_hold_even_for_a_hold_recorded_before_the_journal(self):
        with override_settings(DISPOSITION_JOURNAL_PATH=''):
            hold = self.patient_hold()
        self.assertEqual(j.verified(), [])
        with self.captureOnCommitCallbacks(execute=True):
            release = retention.release_hold(self.second, hold.pk, 'b'*64)
        entries = j.verified()
        self.assertEqual([j.kind(e) for e in entries], ['hold', 'release'])
        self.assertEqual(entries[0]['body']['hold'], retention.hold_record(hold))
        self.assertEqual(entries[1]['body']['release']['id'], str(release.pk))

    def test_the_chain_refuses_a_release_before_its_hold_a_second_release_or_a_self_release(self):
        hold = {'id': str(uuid.uuid4()), 'scope': 'global', 'target_id': None, 'authority_sha256': 'a'*64,
                'request_key': str(uuid.uuid4()), 'created_by': str(self.admin.pk)}
        release = {'id': str(uuid.uuid4()), 'hold_id': hold['id'], 'authority_sha256': 'b'*64, 'created_by': str(self.second.pk)}
        first = self.entry(1, p.ZERO, j.HOLD, 'hold', hold); ended = self.entry(2, p.digest(first), j.RELEASE, 'release', release)
        self.write(first, ended); self.assertEqual(len(j.verified()), 2)  # positive control
        early = self.entry(1, p.ZERO, j.RELEASE, 'release', release)
        refused = {
            'release before its hold': (early, self.entry(2, p.digest(early), j.HOLD, 'hold', hold)),
            'second release': (first, ended, self.entry(3, p.digest(ended), j.RELEASE, 'release', dict(release, id=str(uuid.uuid4())))),
            'release by the hold custodian': (first, self.entry(2, p.digest(first), j.RELEASE, 'release', dict(release, created_by=hold['created_by']))),
            'global hold naming a target': (self.entry(1, p.ZERO, j.HOLD, 'hold', dict(hold, target_id=str(uuid.uuid4()))),),
            'scoped hold without a target': (self.entry(1, p.ZERO, j.HOLD, 'hold', dict(hold, scope='patient')),),
            'duplicate request key': (first, self.entry(2, p.digest(first), j.HOLD, 'hold', dict(hold, id=str(uuid.uuid4())))),
            'unsigned hold': (dict(first, signature='0'*128),),
            'unknown kind': (self.entry(1, p.ZERO, 'retention-hold-entry-v2', 'hold', hold),),
        }
        for label, envelopes in refused.items():
            self.write(*envelopes)
            with self.subTest(label), self.assertRaises(ValidationError): j.verified()


@override_settings(**ISOLATED)
class HoldReplay(HoldJournalFixture, TestCase):
    def setUp(self): self.setup_journal()

    def test_a_hold_journaled_after_the_backup_is_replayed_into_the_quarantined_restore(self):
        self.older_backup(self.patient_hold)
        self.assertFalse(m.RetentionHold.objects.exists())
        flagged = self.restore_check()
        self.assertEqual(flagged['holds'], {'journaled': 1, 'missing': 1, 'passed': False}); self.assertFalse(flagged['passed'])
        with self.quarantine():
            report = x.replay(self.admin, self.fresh())
            self.assertEqual((report['holds'], report['holds_imported']), (1, 1))
            self.assertEqual(x.replay(self.admin, self.fresh())['holds_imported'], 1)  # idempotent, nothing added
        entry = j.verified()[0]
        row = m.RetentionHold.objects.get()
        self.assertEqual(retention.hold_record(row), entry['body']['hold'])
        marker = m.RetentionHoldReplay.objects.get()
        self.assertEqual((marker.event, marker.outcome, marker.entry_sha256, marker.journal_entry),
                         ('hold', 'imported', p.digest(entry), entry))
        checked = self.restore_check()
        self.assertEqual(checked['holds'], {'journaled': 1, 'missing': 0, 'passed': True}); self.assertTrue(checked['passed'], checked)
        # The database enforces it again: a correction to the held patient's document keeps its prior value.
        old = self.encounter.notes
        m.Encounter.objects.filter(pk=self.encounter.pk).update(notes='SYNTHETIC CORRECTION', revision=1)
        self.assertEqual(m.PreservedRecord.objects.get(source_id=self.encounter.pk).prior_record['notes'], old)

    def test_a_release_is_replayed_only_after_its_hold(self):
        def hold_then_release():
            hold = self.patient_hold(); retention.release_hold(self.second, hold.pk, 'b'*64); return hold
        hold = self.older_backup(hold_then_release)
        with self.quarantine():
            report = x.replay(self.admin, self.fresh())
        self.assertEqual((report['holds_imported'], report['releases_imported']), (1, 1))
        self.assertEqual(m.RetentionHoldRelease.objects.get().hold_id, hold.pk)
        self.assertEqual(sorted(m.RetentionHoldReplay.objects.values_list('event', 'outcome')), [('hold', 'imported'), ('release', 'imported')])
        # The database refuses a release marker whose hold has no marker yet, whatever the application does.
        orphan = {'id': str(uuid.uuid4()), 'hold_id': str(uuid.uuid4()), 'authority_sha256': 'b'*64, 'created_by': str(self.second.pk)}
        forged = {'key_id': 'writer', 'signature': '0'*128, 'body': {'contract': j.RELEASE, 'release': orphan}}
        with self.assertRaisesMessage(DatabaseError, 'A release replays only after its hold'), transaction.atomic():
            m.RetentionHoldReplay.objects.create(record_id=orphan['id'], hold_id=orphan['hold_id'], event='release',
                outcome='target_absent', journal_entry=forged, entry_sha256='c'*64, created_by=self.admin)

    def test_inactive_journaled_custodians_keep_their_names_on_the_replayed_hold_and_release(self):
        def hold_then_release():
            hold = self.patient_hold(); retention.release_hold(self.second, hold.pk, 'b'*64); return hold
        hold = self.older_backup(hold_then_release)
        m.User.objects.filter(pk__in=[self.admin.pk, self.second.pk]).update(is_active=False)  # as in the older backup
        replayer = m.User.objects.create_user(username='custodian3', email='custodian3@synthetic.invalid',
                                              verified_at=self.base, is_staff=True)
        with self.quarantine():
            report = x.replay(replayer, self.fresh())
        # A journaled release is a committed one (L1:P1): it is imported, never deferred into a hold nobody can end.
        self.assertEqual((report['holds_imported'], report['releases_imported']), (1, 1))
        self.assertEqual(m.RetentionHold.objects.get().created_by_id, self.admin.pk)  # the journaled custodian, not the replayer
        self.assertEqual(m.RetentionHoldRelease.objects.get().created_by_id, self.second.pk)
        self.assertFalse(retention.active_holds(encounter_id=self.encounter.pk).filter(pk=hold.pk).exists())
        self.assertTrue(self.restore_check()['holds']['passed'])

    def test_a_hold_whose_custodian_account_is_absent_is_imported_under_the_replaying_custodian(self):
        absent = str(uuid.uuid4())
        entry = j.append_hold({'id': str(uuid.uuid4()), 'scope': 'patient', 'target_id': str(self.scope[3].pk),
                               'authority_sha256': 'a'*64, 'request_key': str(uuid.uuid4()), 'created_by': absent})
        with self.quarantine():
            x.replay(self.second, self.fresh())
        row = m.RetentionHold.objects.get()
        self.assertEqual(row.created_by_id, self.second.pk)
        self.assertEqual(m.RetentionHoldReplay.objects.get().journal_entry['body']['hold']['created_by'], absent)
        self.assertEqual(str(row.pk), entry['body']['hold']['id'])
        # The replaying custodian is now the hold's maker: it cannot also end it.
        with self.assertRaises(PermissionDenied): retention.release_hold(self.second, row.pk, 'b'*64)

    def test_a_hold_on_a_target_created_after_the_backup_is_recorded_absent_not_lost(self):
        def new_document_and_hold():
            row = self.empty(); return retention.create_hold(self.admin, 'encounter', row.pk, 'a'*64, uuid.uuid4())
        self.older_backup(new_document_and_hold)
        self.assertEqual(self.restore_check()['holds']['missing'], 1)
        with self.quarantine():
            report = x.replay(self.admin, self.fresh())
        self.assertEqual(report['holds_target_absent'], 1); self.assertFalse(m.RetentionHold.objects.exists())
        self.assertEqual(self.restore_check()['holds'], {'journaled': 1, 'missing': 0, 'passed': True})
        # The database accepts 'target_absent' only for an absent target.
        present = dict(j.verified()[0], signature='0'*128)
        present['body'] = dict(present['body'], hold=dict(present['body']['hold'], id=str(uuid.uuid4()),
                                                          target_id=str(self.encounter.pk)))
        with self.assertRaisesMessage(DatabaseError, 'target is absent'), transaction.atomic():
            m.RetentionHoldReplay.objects.create(record_id=present['body']['hold']['id'], hold_id=present['body']['hold']['id'],
                event='hold', outcome='target_absent', journal_entry=present, entry_sha256='e'*64, created_by=self.admin)

    def test_a_restored_hold_that_conflicts_with_the_journal_refuses_replay(self):
        hold = self.patient_hold()
        entry = j.verified()[0]
        forged = dict(entry['body']['hold'], authority_sha256='d'*64)
        self.write(self.entry(1, p.ZERO, j.HOLD, 'hold', forged))
        with self.quarantine(), self.assertRaisesMessage(ValidationError, 'conflicts with the independent journal'):
            x.replay(self.admin, self.fresh())
        self.assertFalse(m.RetentionHoldReplay.objects.exists()); self.assertEqual(m.RetentionHold.objects.get().pk, hold.pk)

    def test_replay_markers_are_append_only(self):
        self.older_backup(self.patient_hold)
        with self.quarantine(): x.replay(self.admin, self.fresh())
        for verb in ('UPDATE core_retentionholdreplay SET outcome=outcome', 'DELETE FROM core_retentionholdreplay',
                     'TRUNCATE core_retentionholdreplay'):
            with self.subTest(verb=verb), self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor: cursor.execute(verb)
        self.assertEqual(m.RetentionHoldReplay.objects.count(), 1)
