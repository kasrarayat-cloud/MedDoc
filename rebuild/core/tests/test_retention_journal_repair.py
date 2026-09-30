"""Repairs of the refuted 1a/1d defects: L1:P1, L1:P3, L1:P4, L1:P5, L2:R2-1, L2:R2-2 and L2:R2-4.

Each test was run first against 178063f8 and failed there. Synthetic organizations, patients, documents and keys are
generated inside each test only. No retention period, schedule or duration exists here.
"""
import json
import os
import threading
import uuid
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings

from core import disposition as d, models as m, restore_admission, retention, retention_views
from core import disposition_execution as x, disposition_journal as j, disposition_policy as p
from core.tests.test_retention_flow_locks import in_thread, wait_for_blocked_backend
from core.tests.test_retention_hold_journal import HoldJournalFixture
from core.tests.test_retention_preservation import ISOLATED
from ops import integrity_contract

RELEASE = len(integrity_contract.GUARDS)


class RepairFixture(HoldJournalFixture):
    def lifted(self):
        """Quarantine flag off, the restore instance id kept (cutover plan, restore step 7)."""
        return override_settings(RESTORE_QUARANTINE=False, RESTORE_INSTANCE_ID=self.instance)

    def custodian(self, name):
        return m.User.objects.create_user(username=name, email=name + '@synthetic.invalid', verified_at=self.base, is_staff=True)

    def committed(self, action):
        """Run `action` and then its after-commit work, as a committed request would."""
        with TestCase.captureOnCommitCallbacks(execute=True):
            return action()

    def admit(self, actor=None):
        with self.quarantine():
            return restore_admission.admit(actor or self.admin, self.instance, self.fresh(), RELEASE)

    def preserved(self, encounter_id):
        return m.PreservedRecord.objects.filter(source_id=encounter_id).count()

    def edited_and_preserved(self, encounter_id, text):
        before = self.preserved(encounter_id)
        m.Encounter.objects.filter(pk=encounter_id).update(notes=text, revision=7)
        return self.preserved(encounter_id) - before

    def held(self, hold_id, encounter_id):
        return retention.active_holds(encounter_id=encounter_id).filter(pk=hold_id).exists()

    def status(self):
        inner = lambda request: HttpResponse('synthetic')
        return d.RestoreQuarantineMiddleware(inner)(RequestFactory().get('/encounters/')).status_code


@override_settings(**ISOLATED)
class ReleasesAfterCommit(RepairFixture, TestCase):
    """L2:R2-1 / L1:P5: a release the application reported as not recorded must never end preservation."""

    def setUp(self): self.setup_journal()

    def failed_release_through_the_api(self, hold):
        request = RequestFactory().post('/api/retention/holds/%s/release' % hold.pk,
                                        data=json.dumps({'authority_sha256': 'b'*64}), content_type='application/json')
        request.user = self.second
        with patch('core.retention_views.gate'), \
                patch('core.retention.audit', side_effect=DatabaseError('SYNTHETIC lost connection')):
            return self.committed(lambda: retention_views.release(request, hold.pk))

    def test_a_release_whose_commit_failed_is_not_journaled_and_another_custodian_may_release(self):
        hold = self.patient_hold()
        response = self.failed_release_through_the_api(hold)
        self.assertEqual((response.status_code, json.loads(response.content)),
                         (503, {'error': 'Preservation instruction not recorded. Nothing changed; retry.'}))
        self.assertEqual([j.kind(e) for e in j.verified()], ['hold'])  # 178063f8: ['hold', 'release']
        self.assertTrue(self.held(hold.pk, self.encounter.pk))
        third = self.custodian('custodian3')
        row = self.committed(lambda: retention.release_hold(third, hold.pk, 'c'*64))  # 178063f8: refused
        entries = j.verified(self.fresh())
        self.assertEqual([j.kind(e) for e in entries], ['hold', 'release'])
        self.assertEqual(entries[1]['body']['release'], {'id': str(row.pk), 'hold_id': str(hold.pk),
                                                         'authority_sha256': 'c'*64, 'created_by': str(third.pk)})

    def test_a_release_whose_commit_failed_is_not_imported_by_a_restore(self):
        hold = self.patient_hold()
        self.assertEqual(self.failed_release_through_the_api(hold).status_code, 503)
        # This database is the backup: restore it into service.
        with self.quarantine():
            report = x.replay(self.admin, self.fresh())
        self.assertEqual((report['holds_present'], report['releases'], report['releases_imported']), (1, 0, 0))
        self.admit()
        with self.lifted():
            self.assertFalse(d.quarantined())
            self.assertTrue(self.held(hold.pk, self.encounter.pk))  # 178063f8: ended by the imported release
            self.assertFalse(m.RetentionHoldRelease.objects.exists())
            self.assertEqual(self.edited_and_preserved(self.encounter.pk, 'SYNTHETIC EDIT AFTER ADMISSION'), 1)

    def test_a_committed_release_is_journaled_after_its_row_and_a_same_custodian_retry_appends_nothing(self):
        hold = self.patient_hold()
        with patch('core.disposition_journal.append_release', side_effect=ValidationError('SYNTHETIC journal outage')), \
                self.assertLogs('core.retention', 'ERROR'):
            row = self.committed(lambda: retention.release_hold(self.second, hold.pk, 'b'*64))
        self.assertEqual([j.kind(e) for e in j.verified()], ['hold'])  # the row is recorded; its copy is pending
        self.assertEqual(self.committed(lambda: retention.release_hold(self.second, hold.pk, 'b'*64)).pk, row.pk)
        self.assertEqual(j.verified()[-1]['body']['release']['id'], str(row.pk))  # the retry journaled it
        self.assertEqual(self.committed(lambda: retention.release_hold(self.second, hold.pk, 'b'*64)).pk, row.pk)
        self.assertEqual([j.kind(e) for e in j.verified()], ['hold', 'release'])


@override_settings(**ISOLATED)
class ReleasesReplayed(RepairFixture, TestCase):
    """L1:P1: a journaled (committed) release is imported by replay; nothing is left unreleasable."""

    def setUp(self): self.setup_journal()

    def test_a_release_whose_custodian_is_absent_from_the_restore_is_imported(self):
        def act():
            hold = self.patient_hold()  # custodian: admin, present in the backup
            late = self.custodian('c2late')  # created after the backup
            self.committed(lambda: retention.release_hold(late, hold.pk, 'b'*64))
            return hold.pk, late.pk
        hold_id, late = self.older_backup(act)
        self.assertFalse(m.User.objects.filter(pk=late).exists())
        with self.quarantine():
            report = x.replay(self.second, self.fresh())
        self.assertEqual((report['holds_imported'], report['releases_imported']), (1, 1))  # 178063f8: deferred
        release = m.RetentionHoldRelease.objects.get(hold_id=hold_id)
        self.assertEqual(release.created_by_id, self.second.pk)  # recorded by the replaying custodian here
        marker = m.RetentionHoldReplay.objects.get(event='release')
        self.assertEqual((marker.outcome, marker.journal_entry['body']['release']['created_by']), ('imported', str(late)))
        record = self.admit()
        self.assertEqual(record.report['blockers'], [])
        with self.lifted():
            self.assertFalse(d.quarantined())
            self.assertFalse(self.held(hold_id, self.encounter.pk))
        with self.quarantine():  # idempotent: a second replay adds and conflicts with nothing
            self.assertEqual(x.replay(self.admin, self.fresh())['releases_imported'], 1)
        self.assertEqual(m.RetentionHoldReplay.objects.count(), 2)

    def test_a_release_by_the_custodian_who_replays_a_substituted_hold_is_imported(self):
        def act():
            first = self.custodian('c0late')  # the hold's custodian, created after the backup
            hold = retention.create_hold(first, 'patient', self.scope[3].pk, 'a'*64, uuid.uuid4())
            self.committed(lambda: retention.release_hold(self.second, hold.pk, 'b'*64))
            return hold.pk
        hold_id = self.older_backup(act)
        with self.quarantine():
            report = x.replay(self.second, self.fresh())
        self.assertEqual((report['holds_imported'], report['releases_imported']), (1, 1))  # 178063f8: deferred
        # The hold is recorded here by the replaying custodian (its journaled custodian's account is absent), and the
        # journaled release is signed by that same account; the journal proves two custodians, the markers keep it.
        self.assertEqual(m.RetentionHold.objects.get(pk=hold_id).created_by_id, self.second.pk)
        self.assertEqual(m.RetentionHoldRelease.objects.get(hold_id=hold_id).created_by_id, self.second.pk)
        self.admit()
        with self.lifted():
            self.assertFalse(self.held(hold_id, self.encounter.pk))

    def test_an_inactive_journaled_releaser_is_recorded_through_its_marker(self):
        def act():
            hold = self.patient_hold(); self.committed(lambda: retention.release_hold(self.second, hold.pk, 'b'*64))
            return hold
        hold = self.older_backup(act)
        m.User.objects.filter(pk__in=[self.admin.pk, self.second.pk]).update(is_active=False)  # as in the older backup
        replayer = self.custodian('custodian3')
        with self.quarantine():
            report = x.replay(replayer, self.fresh())
        self.assertEqual((report['holds_imported'], report['releases_imported']), (1, 1))
        self.assertEqual(m.RetentionHold.objects.get().created_by_id, self.admin.pk)
        self.assertEqual(m.RetentionHoldRelease.objects.get().created_by_id, self.second.pk)
        self.assertFalse(self.held(hold.pk, self.encounter.pk))

    def test_the_marker_path_never_admits_a_self_release_or_a_release_without_its_marker(self):
        hold = self.patient_hold()
        # Direct inserts keep 0025's rules: no release by the hold's custodian, and none by an inactive account.
        with self.assertRaisesMessage(DatabaseError, 'A second custodian must release preservation'), transaction.atomic():
            m.RetentionHoldRelease.objects.create(hold=hold, authority_sha256='b'*64, created_by=self.admin)
        # Markers whose journal entries name ONE custodian for the hold and its release do not open the marker path.
        forged_hold = {'key_id': 'writer', 'signature': '0'*128, 'body': {'contract': j.HOLD, 'hold': retention.hold_record(hold)}}
        m.RetentionHoldReplay.objects.create(record_id=hold.pk, hold_id=hold.pk, event='hold', outcome='present',
                                             journal_entry=forged_hold, entry_sha256='d'*64, created_by=self.second)
        release_id = uuid.uuid4()
        forged = {'key_id': 'writer', 'signature': '0'*128, 'body': {'contract': j.RELEASE, 'release': {
            'id': str(release_id), 'hold_id': str(hold.pk), 'authority_sha256': 'b'*64, 'created_by': str(self.admin.pk)}}}
        m.RetentionHoldReplay.objects.create(record_id=release_id, hold_id=hold.pk, event='release', outcome='imported',
                                             journal_entry=forged, entry_sha256='e'*64, created_by=self.second)
        with self.assertRaisesMessage(DatabaseError, 'A second custodian must release preservation'), transaction.atomic():
            m.RetentionHoldRelease.objects.create(id=release_id, hold=hold, authority_sha256='b'*64, created_by=self.admin)
        self.assertTrue(self.held(hold.pk, self.encounter.pk))

    def test_a_restored_hold_is_released_through_the_ordinary_two_person_path_after_admission(self):
        restored = self.older_backup(self.patient_hold)
        with self.quarantine():
            x.replay(self.admin, self.fresh())
        self.admit()
        with self.lifted():
            with self.assertRaises(PermissionDenied): retention.release_hold(self.admin, restored.pk, 'b'*64)
            third = self.custodian('custodian3')
            row = self.committed(lambda: retention.release_hold(third, restored.pk, 'c'*64))
            self.assertFalse(self.held(restored.pk, self.encounter.pk))
            self.assertFalse(d.quarantined())
        self.assertEqual(j.verified()[-1]['body']['release']['id'], str(row.pk))


@override_settings(**ISOLATED)
class JournalThatCannotTakeAnEntry(RepairFixture, TestCase):
    """L2:R2-2 and L1:P4 / L2:R2-4: a journal that cannot take an entry never refuses preservation."""

    def setUp(self): self.setup_journal()

    def read_only(self):
        os.chmod(self.path, 0o400); self.addCleanup(os.chmod, self.path, 0o600)

    def test_a_read_only_journal_never_refuses_a_hold_or_a_release_after_admission(self):
        restored = self.older_backup(self.patient_hold)
        self.read_only()  # cutover plan restore step 2 permits it
        with self.quarantine():
            x.replay(self.admin, self.fresh())
        self.admit()
        with self.lifted():
            self.assertFalse(d.quarantined())
            with self.assertLogs('core.retention', 'ERROR'):
                hold = retention.create_hold(self.admin, 'patient', self.other[3].pk, 'a'*64, uuid.uuid4())  # 178063f8: refused
            self.assertTrue(self.held(hold.pk, self.other[5].pk))
            self.assertEqual(self.edited_and_preserved(self.other[5].pk, 'SYNTHETIC EDIT UNDER A NEW HOLD'), 1)
            with self.assertLogs('core.retention', 'ERROR'):
                self.committed(lambda: retention.release_hold(self.second, restored.pk, 'b'*64))  # 178063f8: refused
            self.assertFalse(self.held(restored.pk, self.encounter.pk))
            self.assertFalse(d.quarantined())  # the journal still names nothing this database lacks
        self.assertEqual([j.kind(e) for e in j.verified()], ['hold'])
        self.assertEqual(m.AuditEvent.objects.get(action='retention.hold_created', target=str(hold.pk)).details['journaled'], False)

    def test_a_full_journal_never_refuses_a_hold_and_names_its_bound(self):
        previous = p.ZERO; envelopes = []
        for number in range(1, j.MAX_ENTRIES):
            entry = self.entry(number, previous, j.HOLD, 'hold', {
                'id': str(uuid.uuid4()), 'scope': 'encounter', 'target_id': str(uuid.uuid4()), 'authority_sha256': 'a'*64,
                'request_key': str(uuid.uuid4()), 'created_by': str(self.admin.pk)})
            envelopes.append(entry); previous = p.digest(entry)
        self.write(*envelopes)
        last = self.patient_hold()  # entry 1000, the bound
        self.assertEqual(len(j.verified()), j.MAX_ENTRIES)
        more = {'id': str(uuid.uuid4()), 'scope': 'global', 'target_id': None, 'authority_sha256': 'a'*64,
                'request_key': str(uuid.uuid4()), 'created_by': str(self.admin.pk)}
        with self.assertRaisesMessage(ValidationError, 'exceeds its bound'):  # 178063f8: 'authority could not be verified'
            j.append_hold(more)
        with self.assertLogs('core.retention', 'ERROR'):
            hold = retention.create_hold(self.admin, 'patient', self.other[3].pk, 'a'*64, uuid.uuid4())  # 178063f8: refused
        self.assertEqual(len(j.verified()), j.MAX_ENTRIES)
        kept = self.file()
        self.assertFalse(retention.cleanup_file(kept, encounter_id=self.other[5].pk)); self.assertTrue(kept.exists())
        self.assertEqual(m.PreservedFile.objects.get().hold_ids, [str(hold.pk)])
        with self.assertLogs('core.retention', 'ERROR'):
            self.committed(lambda: retention.release_hold(self.second, last.pk, 'b'*64))  # 178063f8: refused
        self.assertTrue(m.RetentionHoldRelease.objects.filter(hold=last).exists())

    def test_a_same_key_retry_journals_a_hold_the_journal_could_not_take(self):
        key = uuid.uuid4()
        self.read_only()
        with self.assertLogs('core.retention', 'ERROR'):
            hold = self.patient_hold(key)
        self.assertEqual(j.verified(), [])
        os.chmod(self.path, 0o600)
        self.assertEqual(self.patient_hold(key).pk, hold.pk)
        self.assertEqual([e['body']['hold'] for e in j.verified()], [retention.hold_record(hold)])
        with self.assertRaisesMessage(ValidationError, 'already used for another instruction'):
            self.patient_hold(key, 'c'*64)

    def test_a_same_key_reused_with_other_evidence_still_refuses_at_the_journal(self):
        key = uuid.uuid4()
        with patch('core.retention.audit', side_effect=RuntimeError('SYNTHETIC crash before commit')):
            with self.assertRaises(RuntimeError): self.patient_hold(key)
        with self.assertRaisesMessage(ValidationError, 'already used for another instruction'):
            self.patient_hold(key, 'c'*64)
        self.assertFalse(m.RetentionHold.objects.exists())


@override_settings(**ISOLATED)
class JournalGrowthAfterAdmission(RepairFixture, TestCase):
    """L1:P3: a restored target serves only while its database accounts for everything the journal preserves."""

    def setUp(self): self.setup_journal()

    def admitted(self):
        self.older_backup(self.patient_hold)
        with self.quarantine():
            x.replay(self.admin, self.fresh())
        self.admit()
        with self.lifted():
            self.assertFalse(d.quarantined())

    def test_a_hold_journaled_after_admission_quarantines_the_target_until_replay_imports_it(self):
        self.admitted()
        # Another writer (the old host) journals a hold this database lacks.
        j.append_hold({'id': str(uuid.uuid4()), 'scope': 'patient', 'target_id': str(self.other[3].pk),
                       'authority_sha256': 'a'*64, 'request_key': str(uuid.uuid4()), 'created_by': str(self.admin.pk)})
        with self.lifted():
            self.assertTrue(d.quarantined())  # 178063f8: False, and the hold is never imported
            self.assertEqual(self.status(), 503)
            with self.assertRaises(ValidationError): d.require_processing()
            self.assertEqual(x.replay(self.admin, self.fresh())['holds_imported'], 2)  # runs while quarantined; the
            self.assertTrue(m.RetentionHold.objects.filter(patient_id=self.other[3].pk).exists())  # new hold is here
            self.assertFalse(d.quarantined()); self.assertEqual(self.status(), 200)
            self.assertEqual(self.edited_and_preserved(self.other[5].pk, 'SYNTHETIC EDIT AFTER REPLAY'), 1)

    def test_a_release_journaled_after_admission_quarantines_the_target_until_replay_imports_it(self):
        self.admitted()
        hold = m.RetentionHold.objects.get()
        j.append_release({'id': str(uuid.uuid4()), 'hold_id': str(hold.pk), 'authority_sha256': 'b'*64,
                          'created_by': str(self.second.pk)}, retention.hold_record(hold))
        with self.lifted():
            self.assertTrue(d.quarantined())
            self.assertEqual(x.replay(self.admin, self.fresh())['releases_imported'], 1)
            self.assertFalse(d.quarantined())
        self.assertFalse(self.held(hold.pk, self.encounter.pk))

    def test_a_marker_that_claims_an_import_without_its_row_does_not_lift_quarantine(self):
        self.admitted()
        entry = j.append_hold({'id': str(uuid.uuid4()), 'scope': 'patient', 'target_id': str(self.other[3].pk),
                               'authority_sha256': 'a'*64, 'request_key': str(uuid.uuid4()), 'created_by': str(self.admin.pk)})
        hold_id = entry['body']['hold']['id']
        m.RetentionHoldReplay.objects.create(record_id=hold_id, hold_id=hold_id, event='hold', outcome='imported',
                                             journal_entry=entry, entry_sha256=p.digest(entry), created_by=self.admin)
        with self.lifted():
            self.assertTrue(d.quarantined())  # the marker is a claim; only the row (or a recorded absence) accounts

    def test_an_unreadable_journal_keeps_a_restored_target_quarantined(self):
        self.admitted()
        with self.lifted():
            with override_settings(DISPOSITION_JOURNAL_PATH=str(self.path) + '.missing'):
                self.assertTrue(d.quarantined())
            with override_settings(DISPOSITION_JOURNAL_PATH=''):
                self.assertTrue(d.quarantined())
            self.assertFalse(d.quarantined())

    def test_a_target_reinserted_after_admission_carries_its_journaled_hold_and_release(self):
        saved = {}
        def act():
            for label in ('held', 'released'):
                row = self.empty()
                saved[label] = {name: getattr(row, name) for name in
                                ('id', 'department_id', 'patient_id', 'template_version_id', 'created_by_id', 'service_date')}
                hold = retention.create_hold(self.admin, 'encounter', row.pk, 'a'*64, uuid.uuid4())
                if label == 'released':
                    self.committed(lambda: retention.release_hold(self.second, hold.pk, 'b'*64))
        self.older_backup(act)
        with self.quarantine():
            report = x.replay(self.admin, self.fresh())
        self.assertEqual((report['holds_target_absent'], report['releases_target_absent']), (2, 1))
        self.admit()
        journaled = {record['hold']['target_id']: record for record in j.journaled_holds().values()}
        with self.lifted():
            for label, fields in saved.items():
                # The data-damage reconcile puts the row back into the admitted database, keeping its id.
                m.Encounter.objects.create(notes='', **fields)
                hold = m.RetentionHold.objects.filter(encounter_id=fields['id']).first()  # 178063f8: None
                self.assertIsNotNone(hold, label)
                self.assertEqual(retention.hold_record(hold), journaled[str(fields['id'])]['hold'])
                self.assertEqual(self.held(hold.pk, fields['id']), label == 'held')
                if label == 'released':
                    release = m.RetentionHoldRelease.objects.get(hold=hold)
                    self.assertEqual((str(release.pk), release.created_by_id),
                                     (journaled[str(fields['id'])]['release']['id'], self.second.pk))
            self.assertEqual(self.edited_and_preserved(saved['held']['id'], 'SYNTHETIC EDIT ON A RECONCILED ROW'), 1)
            self.assertFalse(d.quarantined())
        with self.quarantine():  # a restore of this database replays and admits it without conflict
            x.replay(self.admin, self.fresh())
            report = restore_admission.assess(self.instance, self.fresh(), RELEASE)
        self.assertEqual((report['missing_holds'], report['blockers']), (0, []))

    def test_a_patient_reinserted_after_admission_carries_its_journaled_hold(self):
        saved = {}
        def act():
            patient = m.Patient.objects.create(department=self.scope[2], display_name='SYNTHETIC LATE PATIENT',
                                               reference='late', created_by=self.scope[0])
            saved.update(id=patient.pk, department_id=patient.department_id, display_name=patient.display_name,
                         reference=patient.reference, created_by_id=patient.created_by_id)
            retention.create_hold(self.admin, 'patient', patient.pk, 'a'*64, uuid.uuid4())
        self.older_backup(act)
        with self.quarantine():
            self.assertEqual(x.replay(self.admin, self.fresh())['holds_target_absent'], 1)
        self.admit()
        with self.lifted():
            m.Patient.objects.create(**saved)
            self.assertTrue(retention.active_holds().filter(patient_id=saved['id']).exists())  # 178063f8: False


@override_settings(**ISOLATED)
class GrowthRaceOnTheServingTarget(RepairFixture, TransactionTestCase):
    """A hold this host is committing is journaled before its row: another request waits for it, never quarantines."""

    def setUp(self): self.setup_journal()

    def paused_hold(self, paused, resume, fail=False):
        real = retention.audit
        def audit(actor, action, *args, **kwargs):
            row = real(actor, action, *args, **kwargs)
            if action == 'retention.hold_created':
                paused.set(); resume.wait(30)
                if fail: raise DatabaseError('SYNTHETIC lost connection after the journal append')
            return row
        return patch('core.retention.audit', side_effect=audit)

    def race(self, fail):
        self.older_backup(self.patient_hold)
        with self.quarantine():
            x.replay(self.admin, self.fresh())
        self.admit()
        with self.lifted():
            self.assertFalse(d.quarantined())
            paused, resume = threading.Event(), threading.Event()
            with self.paused_hold(paused, resume, fail):
                holding, held = in_thread(lambda: retention.create_hold(
                    self.admin, 'patient', self.other[3].pk, 'a'*64, uuid.uuid4()))
                try:
                    self.assertTrue(paused.wait(15))
                    checking, checked = in_thread(d.quarantined)
                    blocked = wait_for_blocked_backend()
                finally:
                    resume.set()
                holding.join(30); checking.join(30)
        self.assertTrue(blocked, 'the check never waited for the hold being committed')
        self.assertNotIn('error', checked, checked.get('error'))
        return held, checked['value']

    def test_a_request_during_this_hosts_own_hold_waits_for_its_commit(self):
        held, quarantined = self.race(fail=False)
        self.assertIsInstance(held.get('value'), m.RetentionHold)
        self.assertFalse(quarantined)

    def test_a_hold_whose_commit_failed_after_its_journal_append_quarantines_until_replayed(self):
        held, quarantined = self.race(fail=True)
        self.assertIsInstance(held.get('error'), DatabaseError)
        self.assertTrue(quarantined)
        with self.lifted():
            self.assertEqual(x.replay(self.admin, self.fresh())['holds_imported'], 2)  # the restored one, and this one
            self.assertTrue(m.RetentionHold.objects.filter(patient_id=self.other[3].pk).exists())
            self.assertFalse(d.quarantined())
