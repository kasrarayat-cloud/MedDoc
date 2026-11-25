"""Repair round 3 of release 1, builder s3's change in a file of no round-3 lane (a lead commit): provision locks the
account it re-provisions FOR NO KEY UPDATE, as studio.session_store.lock_accounts takes an account - a plain FOR UPDATE
blocks a foreign key's KEY SHARE on that account, so an owner's access off (which records the owner as its actor)
deadlocked with a re-provisioning that changes that owner's membership (the shape of refutation round 3's locks-3)."""
import io
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

OWNER_PASSWORD = 'owner-Pass-0rd-for-lead-test-4417'


class ProvisionAccountLockTests(TestCase):
    def test_the_accounts_row_is_locked_for_no_key_update(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        secret = Path(folder.name) / 'o'
        secret.write_text(OWNER_PASSWORD + '\n', encoding='utf-8')
        with CaptureQueriesContext(connection) as queries:
            call_command('provision', '--owner-username', 'lead-owner', '--owner-password-file', str(secret),
                         stdout=io.StringIO())
        locks = [q['sql'] for q in queries.captured_queries if 'FOR ' in q['sql'] and 'studio_user' in q['sql']]
        self.assertTrue(locks, 'provision locked no account row')
        for sql in locks:
            self.assertIn('FOR NO KEY UPDATE', sql)
