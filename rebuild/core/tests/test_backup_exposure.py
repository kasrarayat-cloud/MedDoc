"""The offline backup exposure ledger (core.exposure): which recovery points may still contain a disposed or redacted
document, read from the verified journal and the backup system's own inventory. Synthetic data only; no retention
period exists here: a recovery point's expiry comes from its inventory, and an absent expiry means kept.
"""
import io
import uuid
import json
import os
import stat
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core import disposition_execution as x, disposition_journal as j, exposure
from core.tests.test_redaction import RedactionFixture
from core.tests.test_retention_preservation import ISOLATED


@override_settings(**ISOLATED)
class BackupExposureLedger(RedactionFixture, TestCase):
    def setUp(self):
        self.setup_journal()
        self.out = Path(self.journal_temp.name)

    def two_acts(self):
        """An empty-draft disposition at base+100s, then a redaction at base+1h, journaled in that order."""
        row, instruction = self.approved()
        x.execute(self.admin, instruction.pk, self.fresh())
        draft, _, _ = self.worked_draft()
        self.clock.return_value = self.base + timedelta(hours=1)
        _, tombstone = self.redact(draft)
        return instruction, tombstone

    def point(self, ident, offset, expires=None):
        value = {'id': ident, 'created_at': (self.base + offset).isoformat(), 'location': 'offsite'}
        if expires is not None: value['expires_at'] = (self.base + expires).isoformat()
        return value

    def test_each_act_names_the_recovery_points_taken_before_it_and_each_point_what_its_restore_re_applies(self):
        instruction, tombstone = self.two_acts()
        disposed = str(instruction.pk); redacted = tombstone.journal_entry['body']['redaction']['id']
        points = exposure.inventory({'recovery_points': [
            self.point('before-both', timedelta(seconds=10)),
            self.point('between', timedelta(minutes=30)),
            self.point('in-commit-gap', timedelta(hours=1, seconds=30)),
            self.point('after-both', timedelta(hours=2)),
            self.point('expired-before-both', timedelta(seconds=5), expires=timedelta(hours=1, minutes=30)),
            self.point('expiring-later', timedelta(seconds=20), expires=timedelta(days=30))]})
        value = exposure.ledger(j.verified(self.fresh()), points, self.base + timedelta(hours=3), exposure.commit_evidence())
        rows = {row['id']: row for row in value['acts']}
        self.assertEqual([row['kind'] for row in value['acts']], ['instruction', 'redaction'])
        self.assertEqual(rows[disposed]['exposed_recovery_points'], ['before-both', 'expiring-later'])
        self.assertEqual(rows[redacted]['exposed_recovery_points'], ['before-both', 'between', 'expiring-later'])
        self.assertEqual(rows[redacted]['possibly_exposed_recovery_points'], ['in-commit-gap'])
        contains = {row['id']: row['contains'] for row in value['recovery_points']}
        self.assertEqual(contains, {'before-both': [disposed, redacted], 'expiring-later': [disposed, redacted],
                                    'between': [redacted], 'in-commit-gap': [redacted], 'after-both': []})
        self.assertNotIn('expired-before-both', contains)  # the copy itself no longer exists: nothing left exposed
        self.assertEqual(value['counts'], {'acts': 2, 'exposed_acts': 2, 'recovery_points': 5,
                                           'expired_recovery_points_omitted': 1, 'recovery_points_with_exposure': 4})
        text = json.dumps(value)
        for private in ('SYNTHETIC', self.scope[3].display_name, 'audio/', 'receipts/'):
            self.assertNotIn(private, text)

    def test_F3_a_redaction_whose_commit_was_retried_later_counts_every_point_until_that_commit(self):
        """Refutation F3 (dc33e094): the journal entry's time plus a five-minute tolerance missed a recovery point taken
        while a journaled redaction waited for its retried commit: the content was still in the database."""
        from django.db import DatabaseError
        from core import redaction
        from core.tests.test_redaction import REASON
        row, _, _ = self.worked_draft()
        requested = redaction.request(self.admin, row.pk, REASON, uuid.uuid4())
        with patch('core.redaction.apply', side_effect=DatabaseError('SYNTHETIC lost connection')):
            with self.assertRaises(DatabaseError): redaction.execute(self.second, requested.pk, self.fresh())
        acted = exposure.acts(j.verified())[0]['acted_at']
        point = {'id': 'db-backup-T+30min', 'created_at': acted + timedelta(minutes=30), 'expires_at': None, 'location': 'x'}
        later = {'id': 'db-backup-T+3h', 'created_at': acted + timedelta(hours=3), 'expires_at': None, 'location': 'x'}
        # Before the retry commits, the database holds no tombstone: every later point may hold the content.
        value = exposure.ledger(j.verified(), [point, later], self.base + timedelta(hours=4), exposure.commit_evidence())
        self.assertEqual(value['acts'][0]['possibly_exposed_recovery_points'], ['db-backup-T+30min', 'db-backup-T+3h'])
        self.assertIsNone(value['acts'][0]['committed_at'])
        self.clock.return_value = self.base + timedelta(hours=1)
        with self.captureOnCommitCallbacks(execute=True):
            redaction.execute(self.second, requested.pk, self.fresh())
        value = exposure.ledger(j.verified(), [point, later], self.base + timedelta(hours=4), exposure.commit_evidence())
        act = value['acts'][0]
        self.assertEqual(act['possibly_exposed_recovery_points'], ['db-backup-T+30min'])  # dc33e094: []
        self.assertEqual({row['id']: row['contains'] for row in value['recovery_points']},
                         {'db-backup-T+30min': [act['id']], 'db-backup-T+3h': []})
        self.assertIsNotNone(act['committed_at'])

    def test_local_backup_runs_count_only_when_complete(self):
        root = self.out / 'backups'; root.mkdir()
        def run(name, summary=None, incomplete=False):
            path = root / name; path.mkdir()
            if summary is not None: (path / 'summary.json').write_text(json.dumps(summary))
            if incomplete: (path / 'INCOMPLETE').write_text('x')
        run('20261001T010203Z-0a1b2c3d', {'complete': True, 'run_id': '20261001T010203Z-0a1b2c3d'})
        run('20261001T020000Z-1111aaaa', {'complete': True, 'run_id': '20261001T020000Z-1111aaaa'}, incomplete=True)
        run('20261001T030000Z-2222bbbb', {'complete': False, 'run_id': '20261001T030000Z-2222bbbb'})
        run('20261001T040000Z-3333cccc')  # no summary
        run('not-a-run', {'complete': True, 'run_id': 'not-a-run'})
        points = exposure.local_backups(root)
        self.assertEqual([(p['id'], p['created_at'].isoformat(), p['expires_at']) for p in points],
                         [('20261001T010203Z-0a1b2c3d', '2026-10-01T01:02:03+00:00', None)])

    def test_an_invalid_inventory_refuses(self):
        good = self.point('a', timedelta(0))
        for label, data in {'not a list': {'recovery_points': {}}, 'duplicate id': {'recovery_points': [good, good]},
                            'naive time': {'recovery_points': [dict(good, created_at='2026-10-01T00:00:00')]},
                            'unknown field': {'recovery_points': [dict(good, contents='x')]},
                            'odd id': {'recovery_points': [dict(good, id='a b')]}}.items():
            with self.subTest(label), self.assertRaises(ValidationError): exposure.inventory(data)

    def test_the_command_verifies_the_journal_and_writes_once_privately_outside_the_state_root(self):
        self.two_acts()
        checkpoint = self.out / 'checkpoint.json'; checkpoint.write_text(json.dumps(self.fresh()))
        inventory = self.out / 'points.json'
        inventory.write_text(json.dumps({'recovery_points': [self.point('before-both', timedelta(seconds=10))]}))
        output = self.out / 'ledger.json'
        stdout = io.StringIO()
        call_command('backup_exposure_ledger', '--checkpoint', str(checkpoint), '--recovery-points', str(inventory),
                     '--output', str(output), stdout=stdout)
        printed = json.loads(stdout.getvalue())
        self.assertEqual((printed['acts'], printed['exposed_acts'], printed['journal_sequence']), (2, 2, 2))
        self.assertEqual(stat.S_IMODE(os.stat(output).st_mode), 0o600)
        self.assertEqual(json.loads(output.read_text())['contract'], exposure.CONTRACT)
        self.assertNotIn('before-both', stdout.getvalue())  # identifiers stay in the private file
        with self.assertRaisesMessage(CommandError, 'exists'):
            call_command('backup_exposure_ledger', '--checkpoint', str(checkpoint), '--recovery-points', str(inventory),
                         '--output', str(output), stdout=io.StringIO())
        from django.conf import settings
        inside = Path(settings.MEDIA_ROOT) / 'ledger.json'
        with self.assertRaisesMessage(CommandError, 'outside the clinical state root'):
            call_command('backup_exposure_ledger', '--checkpoint', str(checkpoint), '--recovery-points', str(inventory),
                         '--output', str(inside), stdout=io.StringIO())
        stale = self.out / 'stale.json'; stale.write_text(json.dumps(self.checkpoint([])))
        with self.assertRaisesMessage(CommandError, 'checkpoint'):
            call_command('backup_exposure_ledger', '--checkpoint', str(stale), '--recovery-points', str(inventory),
                         '--output', str(self.out / 'other.json'), stdout=io.StringIO())
        self.assertFalse(inside.exists()); self.assertFalse((self.out / 'other.json').exists())
