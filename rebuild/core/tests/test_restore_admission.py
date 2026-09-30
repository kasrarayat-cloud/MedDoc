"""1d: a quarantined restore is admitted only after replay, against a fresh checkpoint, by one append-only record.

Synthetic data and keys generated inside each test; the restored database is the test database rolled back to before
the journaled acts. No retention period, schedule or duration exists here.
"""
import copy
import importlib
import io
import json
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection, transaction
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from core import disposition as d, models as m, restore_admission, retention, disposition_execution as x
from core import disposition_journal as j, disposition_policy as p
from core.security import scoped
from core.tests.test_retention_hold_journal import HoldJournalFixture
from core.tests.test_retention_preservation import ISOLATED
from ops import integrity_contract

RELEASE = len(integrity_contract.GUARDS)


@override_settings(**ISOLATED)
class RestoreAdmission(HoldJournalFixture, TestCase):
    def setUp(self): self.setup_journal()

    def admit(self, checkpoint=None, actor=None, instance=None, triggers=RELEASE):
        return restore_admission.admit(actor or self.admin, instance or self.instance, checkpoint or self.fresh(), triggers)

    def disposed_and_held_after_backup(self):
        """A restore older than one executed disposition and one hold; returns the disposed draft."""
        row, instruction = self.approved()
        def act():
            x.execute(self.admin, instruction.pk, self.genesis); self.patient_hold()
        self.older_backup(act)
        self.assertTrue(m.Encounter.objects.filter(pk=row.pk).exists()); self.assertFalse(m.RetentionHold.objects.exists())
        return row

    def test_a_restore_older_than_a_tombstone_and_a_hold_is_admitted_only_after_replay(self):
        row = self.disposed_and_held_after_backup()
        with self.quarantine():
            with self.assertRaises(ValidationError) as refused: self.admit()
            for label in ('hold_replay_incomplete', 'journal_target_visible', 'restore_check_failed', 'tombstone_replay_incomplete'):
                self.assertIn(label, str(refused.exception))
            self.assertFalse(m.RestoreAdmission.objects.exists())
            x.replay(self.admin, self.fresh())
            record = self.admit()
            self.assertEqual(self.admit().pk, record.pk)  # one record per instance; a repeat changes nothing
        self.assertEqual((record.report['blockers'], record.report['admissible'], record.journal_sequence), ([], True, 2))
        self.assertEqual(record.report_sha256, p.digest(record.report))
        self.assertEqual(record.journal_head_sha256, p.digest(j.verified()[-1]))
        self.assertEqual(record.report['restore_check']['holds'], {'journaled': 1, 'missing': 0, 'passed': True})
        self.assertFalse(scoped(m.Encounter, self.scope[0]).filter(pk=row.pk).exists())  # the disposed draft stays hidden
        self.assertTrue(m.DispositionTombstone.objects.filter(target_id=row.pk).exists())
        self.assertNotIn(self.scope[3].display_name, json.dumps(record.report))

    def test_quarantine_lifts_only_against_the_admission_record_of_the_selected_instance(self):
        inner = lambda request: HttpResponse('synthetic')
        def status(): return d.RestoreQuarantineMiddleware(inner)(RequestFactory().get('/encounters/')).status_code
        lifted = override_settings(RESTORE_QUARANTINE=False, RESTORE_INSTANCE_ID=self.instance)
        with lifted:
            self.assertTrue(d.quarantined()); self.assertEqual(status(), 503)  # the flag alone is not a release
        self.older_backup(self.patient_hold)
        with self.quarantine():
            x.replay(self.admin, self.fresh()); self.admit()
            self.assertTrue(d.quarantined())  # still quarantined while the operator's flag is on
        with lifted:
            self.assertFalse(d.quarantined()); self.assertEqual(status(), 200)
        for other in (str(uuid.uuid4()), 'not-a-uuid'):
            with self.subTest(other=other), override_settings(RESTORE_QUARANTINE=False, RESTORE_INSTANCE_ID=other):
                self.assertTrue(d.quarantined())
        with override_settings(RESTORE_QUARANTINE=False, RESTORE_INSTANCE_ID=''):
            self.assertFalse(d.quarantined())  # an ordinary, never-restored installation

    def test_an_expired_mismatched_or_untrusted_checkpoint_refuses(self):
        self.older_backup(self.patient_hold)
        with self.quarantine():
            x.replay(self.admin, self.fresh())
            good = self.fresh()
            stale = self.checkpoint([])  # names the empty genesis head, not the complete journal
            untrusted = dict(good, signature='0'*128)
            elsewhere = self.sign(self.checkpoint_key, 'checkpoint', dict(good['body'], namespace=str(uuid.uuid4())))
            for label, checkpoint in (('mismatched', stale), ('untrusted', untrusted), ('other namespace', elsewhere)):
                with self.subTest(label), self.assertRaises(ValidationError): self.admit(checkpoint)
            self.clock.return_value = self.base + timedelta(days=3)  # after the checkpoint's own signed expiry
            with self.assertRaisesMessage(ValidationError, 'expired'): self.admit(good)
            self.clock.return_value = self.base + timedelta(seconds=100)
            self.assertFalse(m.RestoreAdmission.objects.exists())
            self.assertEqual(self.admit(good).journal_sequence, 1)  # positive control: the same checkpoint, unexpired

    def test_a_missing_replayed_hold_refuses(self):
        self.older_backup(self.patient_hold)
        with self.quarantine():
            x.replay(self.admin, self.fresh())
            # A hold journaled on the target after its replay, whose database commit failed: the journal holds it and
            # this database does not.
            with patch('core.retention.audit', side_effect=RuntimeError('SYNTHETIC crash before commit')):
                with self.assertRaises(RuntimeError): self.patient_hold()
            report = restore_admission.assess(self.instance, self.fresh(), RELEASE)
            self.assertEqual((report['missing_holds'], report['unreplayed_holds']), (1, 1))
            self.assertEqual(report['restore_check']['holds'], {'journaled': 2, 'missing': 1, 'passed': False})
            with self.assertRaisesMessage(ValidationError, 'hold_replay_incomplete'): self.admit()
            self.assertFalse(m.RestoreAdmission.objects.exists())
            x.replay(self.admin, self.fresh())
            self.assertEqual(self.admit().report['journal']['holds'], 2)

    def test_the_database_refuses_an_admission_whose_replay_claim_it_can_disprove(self):
        self.older_backup(self.patient_hold)
        with self.quarantine():
            x.replay(self.admin, self.fresh())
            checkpoint = self.fresh(); report = restore_admission.assess(self.instance, checkpoint, RELEASE)
        self.assertTrue(report['admissible'])
        def insert(value, **overrides):
            fields = dict(instance_id=self.instance, checkpoint=checkpoint, journal_sequence=value['journal']['sequence'],
                          journal_head_sha256=value['journal']['head_sha256'], report=value,
                          report_sha256=p.digest(value), created_by=self.admin)
            fields.update(overrides)
            return m.RestoreAdmission.objects.create(**fields)
        forged = {'restore_check_failed': lambda r: r['restore_check'].update(passed=False),
                  'holds_missing': lambda r: r['restore_check']['holds'].update(missing=1),
                  'visible_target': lambda r: r.update(visible_targets=1), 'unreplayed': lambda r: r.update(unreplayed=1),
                  'missing_hold': lambda r: r.update(missing_holds=1), 'not_admissible': lambda r: r.update(admissible=False),
                  'other_instance': lambda r: r.update(instance_id=str(uuid.uuid4())),
                  'other_head': lambda r: r['journal'].update(head_sha256='f'*64)}
        for label, change in forged.items():
            value = copy.deepcopy(report); change(value)
            with self.subTest(label), self.assertRaises(DatabaseError), transaction.atomic(): insert(value)
        with self.assertRaises(DatabaseError), transaction.atomic():
            insert(report, checkpoint=self.checkpoint([]))  # a checkpoint naming another head
        # An 'imported' marker whose hold row never arrived: the report claims nothing about it, the database sees it.
        hold_id = str(uuid.uuid4()); entry = {'key_id': 'writer', 'signature': '0'*128, 'body': {
            'contract': j.HOLD, 'hold': {'id': hold_id, 'scope': 'global', 'target_id': None}}}
        m.RetentionHoldReplay.objects.create(record_id=hold_id, hold_id=hold_id, event='hold', outcome='imported',
                                             journal_entry=entry, entry_sha256='d'*64, created_by=self.admin)
        with self.assertRaisesMessage(DatabaseError, 'complete replay'), transaction.atomic(): insert(report)
        self.assertFalse(m.RestoreAdmission.objects.exists())

    def test_the_admission_record_cannot_be_updated_deleted_or_truncated(self):
        self.older_backup(self.patient_hold)
        with self.quarantine():
            x.replay(self.admin, self.fresh()); record = self.admit()
        for verb in ('UPDATE core_restoreadmission SET report_sha256=report_sha256', 'DELETE FROM core_restoreadmission',
                     'TRUNCATE core_restoreadmission', 'TRUNCATE core_restoreadmission CASCADE'):
            with self.subTest(verb=verb), self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor: cursor.execute(verb)
        with self.assertRaises(DatabaseError), transaction.atomic(): m.RestoreAdmission.objects.filter(pk=record.pk).update(journal_sequence=0)
        with self.assertRaises(DatabaseError), transaction.atomic(): m.RestoreAdmission.objects.filter(pk=record.pk).delete()
        self.assertEqual(list(m.RestoreAdmission.objects.values_list('pk', 'report_sha256')), [(record.pk, record.report_sha256)])

    def test_admission_runs_only_for_a_custodian_on_the_selected_quarantined_target(self):
        self.older_backup(self.patient_hold)
        with self.assertRaises(ValidationError): self.admit()  # not quarantined
        with self.quarantine():
            x.replay(self.admin, self.fresh())
            with self.assertRaises(ValidationError): self.admit(instance=str(uuid.uuid4()))
            with self.assertRaises(PermissionDenied): self.admit(actor=self.scope[0])
            with self.assertRaisesMessage(ValidationError, 'restore_check_failed'): self.admit(triggers=82)  # a stale count
        with override_settings(RESTORE_QUARANTINE=True, RESTORE_INSTANCE_ID=''), self.assertRaises(ValidationError): self.admit()
        self.assertFalse(m.RestoreAdmission.objects.exists())

    def test_the_management_command_checks_then_records_with_counts_only(self):
        self.disposed_and_held_after_backup()
        path = Path(self.journal_temp.name) / 'checkpoint.json'
        def run(*extra):
            output = io.StringIO()
            path.write_text(json.dumps(self.fresh()))
            call_command('restore_admission', '--instance-id', self.instance, '--custodian', self.admin.email,
                         '--checkpoint', str(path), '--expected-triggers', str(RELEASE), *extra, stdout=output)
            return output.getvalue()
        with self.quarantine():
            with self.assertRaisesMessage(CommandError, 'hold_replay_incomplete'): run('--check-only')
            x.replay(self.admin, self.fresh())
            checked = json.loads(run('--check-only'))
            self.assertTrue(checked['admissible']); self.assertFalse(m.RestoreAdmission.objects.exists())
            recorded = json.loads(run())
        record = m.RestoreAdmission.objects.get()
        self.assertEqual(recorded, {'admitted': True, 'instance_id': self.instance, 'record': str(record.pk),
                                    'journal_sequence': 2, 'report_sha256': record.report_sha256})
        for private in (self.scope[3].display_name, self.encounter.notes, str(self.scope[3].pk)):
            self.assertNotIn(private, json.dumps(checked))

    def test_reversing_0032_refuses_while_replay_or_admission_evidence_exists(self):
        reverse = importlib.import_module('core.migrations.0032_restore_hold_replay_admission').REVERSE
        self.older_backup(self.patient_hold)
        with self.quarantine():
            x.replay(self.admin, self.fresh())
        with self.assertRaisesMessage(DatabaseError, 'requires a forward migration'), transaction.atomic():
            with connection.cursor() as cursor: cursor.execute(reverse)
        self.assertEqual(m.RetentionHoldReplay.objects.count(), 1)
