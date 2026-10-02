"""NEW-1: a release journaled after its target was put back into a restored database is applied by replay.

A replay recorded the hold 'target_absent' (its target was created after the restored backup). The target is then
inserted again with its id (a data-damage reconcile), and quillmd_restore_absent_hold applies the hold. The source
releases that hold afterwards. Before this repair the release replay decided from the hold marker's stale outcome: it
recorded the release 'target_absent' and never applied it, so the hold stayed active although the source had released
it, and the database still counted the release as accounted for. A local custodian's release then made every later
replay refuse, leaving the target quarantined with no in-product recovery.

Synthetic organizations, patients, documents and keys generated inside each test only. No retention period, schedule or
duration exists here.
"""
import uuid

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core import disposition as d, models as m, restore_admission, retention
from core import disposition_execution as x, disposition_journal as j, disposition_policy as p
from core.tests.test_retention_journal_repair import RELEASE, RepairFixture
from core.tests.test_retention_preservation import ISOLATED


@override_settings(**ISOLATED)
class ReleaseJournaledAfterReinsertion(RepairFixture, TestCase):
    def setUp(self): self.setup_journal()

    def reinserted(self):
        """An encounter hold replayed 'target_absent', admitted, then its target put back with its id."""
        saved = {}
        def act():
            row = self.empty()
            saved.update({name: getattr(row, name) for name in
                          ('id', 'department_id', 'patient_id', 'template_version_id', 'created_by_id', 'service_date')})
            retention.create_hold(self.admin, 'encounter', row.pk, 'a'*64, uuid.uuid4())
        self.older_backup(act)
        with self.quarantine():
            self.assertEqual(x.replay(self.admin, self.fresh())['holds_target_absent'], 1)
        self.admit()
        with self.lifted():
            m.Encounter.objects.create(notes='', **saved)
        hold = m.RetentionHold.objects.get(encounter_id=saved['id'])  # applied by quillmd_restore_absent_hold
        self.assertTrue(self.held(hold.pk, saved['id']))
        return saved['id'], hold

    def journal_release(self, hold):
        release = {'id': str(uuid.uuid4()), 'hold_id': str(hold.pk), 'authority_sha256': 'b'*64,
                   'created_by': str(self.second.pk)}
        entry = j.append_release(release, retention.hold_record(hold))  # the old host, after admission
        return release, entry

    def test_a_release_journaled_after_the_target_was_put_back_is_applied_by_replay(self):
        target, hold = self.reinserted()
        release, _ = self.journal_release(hold)
        with self.lifted():
            self.assertTrue(d.quarantined())  # journal growth: the target waits for replay
            report = x.replay(self.admin, self.fresh())
            # ac43e379: (1, 0, 1): only a 'target_absent' marker was recorded and the release was never applied.
            self.assertEqual((report['releases'], report['releases_imported'], report['releases_target_absent']), (1, 1, 0))
            self.assertFalse(self.held(hold.pk, target))  # ac43e379: True, although the source released it
            row = m.RetentionHoldRelease.objects.get(hold=hold)
            self.assertEqual((str(row.pk), row.authority_sha256, row.created_by_id), (release['id'], 'b'*64, self.second.pk))
            marker = m.RetentionHoldReplay.objects.get(record_id=release['id'])
            self.assertEqual((marker.event, marker.outcome), ('release', 'imported'))
            self.assertFalse(d.quarantined())
            # The source's release stands here; a local custodian cannot end the hold a second time with other evidence.
            third = self.custodian('custodian3')
            with self.assertRaisesMessage(ValidationError, 'already released with other evidence'):
                retention.release_hold(third, hold.pk, 'c'*64)
        # Unrelated growth afterwards replays without conflict, and a restore of this database admits.
        j.append_hold({'id': str(uuid.uuid4()), 'scope': 'patient', 'target_id': str(self.other[3].pk),
                       'authority_sha256': 'a'*64, 'request_key': str(uuid.uuid4()), 'created_by': str(self.admin.pk)})
        with self.lifted():
            self.assertTrue(d.quarantined())
            again = x.replay(self.admin, self.fresh())
            self.assertEqual((again['holds_imported'], again['releases_imported']), (1, 1))
            self.assertFalse(d.quarantined())
        with self.quarantine():
            assessed = restore_admission.assess(self.instance, self.fresh(), RELEASE)
        self.assertEqual((assessed['missing_holds'], assessed['unreplayed'], assessed['blockers']), (0, 0, []))

    def test_a_stale_absent_release_marker_is_not_counted_and_the_next_replay_applies_it(self):
        """A database where the earlier code already recorded the release 'target_absent' after the target came back."""
        target, hold = self.reinserted()
        release, entry = self.journal_release(hold)
        # Exactly the row ac43e379's _replay_release wrote here: the marker path, no release row.
        m.RetentionHoldReplay.objects.create(record_id=release['id'], hold_id=hold.pk, event='release',
                                             outcome='target_absent', journal_entry=entry, entry_sha256=p.digest(entry),
                                             created_by=self.admin)
        self.assertTrue(self.held(hold.pk, target))
        # Not accounted for: the marker states an absence the database no longer has (ac43e379: accounted, served).
        self.assertEqual(retention.unaccounted_journal_records(), {release['id']})
        with self.lifted():
            self.assertTrue(d.quarantined())
        with self.quarantine():
            stale = restore_admission.assess(self.instance, self.fresh(), RELEASE)
            self.assertEqual(stale['missing_holds'], 1)  # ac43e379: 0
            self.assertIn('hold_replay_incomplete', stale['blockers'])
            report = x.replay(self.admin, self.fresh())
            self.assertEqual(report['releases_target_absent'], 1)  # counts state the append-only marker's outcome
            self.assertFalse(self.held(hold.pk, target))  # ac43e379: True
            row = m.RetentionHoldRelease.objects.get(hold=hold)
            self.assertEqual((str(row.pk), row.created_by_id), (release['id'], self.second.pk))
            self.assertEqual(x.replay(self.admin, self.fresh())['releases_target_absent'], 1)  # idempotent
            healed = restore_admission.assess(self.instance, self.fresh(), RELEASE)
        self.assertEqual((healed['missing_holds'], healed['blockers']), (0, []))
        self.assertEqual(retention.unaccounted_journal_records(), set())
        with self.lifted():
            self.assertFalse(d.quarantined())

    def test_a_release_journaled_while_the_target_is_still_absent_keeps_the_marker_path(self):
        """Control: with the target still absent the release is recorded 'target_absent', and a later reinsertion
        applies the hold and its release together (quillmd_restore_absent_hold)."""
        saved = {}
        def act():
            row = self.empty()
            saved.update({name: getattr(row, name) for name in
                          ('id', 'department_id', 'patient_id', 'template_version_id', 'created_by_id', 'service_date')})
            hold = retention.create_hold(self.admin, 'encounter', row.pk, 'a'*64, uuid.uuid4())
            self.committed(lambda: retention.release_hold(self.second, hold.pk, 'b'*64))
        self.older_backup(act)
        with self.quarantine():
            report = x.replay(self.admin, self.fresh())
        self.assertEqual((report['holds_target_absent'], report['releases_target_absent']), (1, 1))
        self.assertFalse(m.RetentionHoldRelease.objects.exists())
        self.assertEqual(retention.unaccounted_journal_records(), set())
        self.admit()
        with self.lifted():
            m.Encounter.objects.create(notes='', **saved)
            hold = m.RetentionHold.objects.get(encounter_id=saved['id'])
            self.assertTrue(m.RetentionHoldRelease.objects.filter(hold=hold).exists())
            self.assertFalse(self.held(hold.pk, saved['id']))
            self.assertFalse(d.quarantined())

    def test_F8_a_stale_marker_and_a_local_release_with_other_evidence_replay_without_conflict(self):
        """Refutation F8 (dc33e094, the refuter's P13): ac43e379 left the stale 'target_absent' release marker, served the
        target with the hold active, and a local custodian then released the hold with other evidence (its journal copy
        refused: the journal already held the source's release). The next replay refused (conflict) and the target stayed
        quarantined. Both the journal and this database have ended the hold, so preservation agrees; only the release
        evidence differs, and that is recorded rather than refused."""
        target, hold = self.reinserted()
        release, entry = self.journal_release(hold)
        m.RetentionHoldReplay.objects.create(record_id=release['id'], hold_id=hold.pk, event='release',
                                             outcome='target_absent', journal_entry=entry, entry_sha256=p.digest(entry),
                                             created_by=self.admin)
        third = self.custodian('custodian3')
        with self.assertLogs('core.retention', 'ERROR'):
            self.committed(lambda: retention.release_hold(third, hold.pk, 'c'*64))
        local = m.RetentionHoldRelease.objects.get(hold=hold)
        self.assertNotEqual(str(local.pk), release['id'])
        self.assertEqual(retention.unaccounted_journal_records(), set())  # dc33e094: {the source's release}
        with self.quarantine():
            report = x.replay(self.admin, self.fresh())  # dc33e094: ValidationError (conflicts with the journal)
            self.assertEqual(report['releases_target_absent'], 1)
            assessed = restore_admission.assess(self.instance, self.fresh(), RELEASE)
        self.assertEqual((assessed['missing_holds'], assessed['blockers']), (0, []))
        self.assertFalse(self.held(hold.pk, target))
        self.assertEqual(list(m.RetentionHoldRelease.objects.filter(hold=hold).values_list('pk', flat=True)), [local.pk])
        differs = m.AuditEvent.objects.get(action='retention.release_evidence_differs', target=str(hold.pk))
        self.assertEqual((differs.details['journaled_release'], differs.details['local_release']), (release['id'], str(local.pk)))
        with self.lifted():
            self.assertFalse(d.quarantined())

    def test_F8_control_a_mismatched_release_without_the_stale_marker_still_conflicts(self):
        """The acceptance is narrow: a hold the replay found present (no stale absence marker) whose release here differs
        from the journal's is still a conflict, as before."""
        hold = self.patient_hold()
        local = self.committed(lambda: retention.release_hold(self.second, hold.pk, 'b'*64))
        entries = j.verified()
        forged = dict(entries[1]['body']['release'], id=str(uuid.uuid4()))
        self.write(entries[0], self.entry(2, p.digest(entries[0]), j.RELEASE, 'release', forged))
        with self.quarantine(), self.assertRaisesMessage(ValidationError, 'conflicts with the independent journal'):
            x.replay(self.admin, self.fresh())
        self.assertEqual(m.RetentionHoldRelease.objects.get(hold=hold).pk, local.pk)
