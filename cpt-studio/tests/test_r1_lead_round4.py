"""Refutation round 4 of release 1: the lead's repairs of its low findings (a lead commit; DECISIONS D415).

disposal-0: the daily run pruned old rate windows inside its recorded transaction, so the console's clear of a sign-in
delay - which deletes the name's rate windows while holding the account - and then the member's own sign-in waited for
the whole run (about 10 s at its name bound). Rate windows are sign-in counters, not records: they are pruned in a short
transaction of their own before the recorded one, as the session cleanup is.
regression-0: the account page's password change hashed the new password (Argon2) while holding the account's row lock;
the hash is now taken before the lock."""
import threading
from datetime import timedelta
from unittest import mock

from django.db import connections
from django.test import TransactionTestCase
from django.utils import timezone

from studio import maintenance, models, rate


class RateWindowPruneOutsideTheRecordTests(TransactionTestCase):
    def test_old_rate_windows_are_gone_for_another_connection_while_the_recorded_steps_run(self):
        old = timezone.now() - timedelta(days=3)
        with mock.patch('django.utils.timezone.now', return_value=old):
            rate.hit('signin.fail.client', '192.0.2.9', window_seconds=60)
        self.assertEqual(models.RateWindow.objects.filter(window_start__lt=timezone.now() - timedelta(days=1)).count(), 1)
        seen = {}
        real_hash = maintenance.hash_unmatched_signin_names

        def probe(*args, **kwargs):  # a recorded step: look from ANOTHER connection, as a web request would
            def look():
                try:
                    with connections['default'].cursor() as cursor:
                        cursor.execute('SELECT count(*) FROM studio_ratewindow WHERE key = %s', ['192.0.2.9'])
                        seen['old_windows'] = cursor.fetchone()[0]
                finally:
                    connections['default'].close()
            reader = threading.Thread(target=look)
            reader.start()
            reader.join(30)
            return real_hash(*args, **kwargs)

        with mock.patch.object(maintenance, 'hash_unmatched_signin_names', probe):
            counts = maintenance.run_daily()
        self.assertEqual(seen.get('old_windows'), 0, 'the old rate window was still there while the recorded steps ran')
        self.assertEqual(counts['rate_windows_pruned'], 1)
        record = models.SecurityEvent.objects.get(event=maintenance.DAILY_EVENT)
        self.assertEqual(record.data['rate_windows_pruned'], 1)


@__import__('django.test', fromlist=['override_settings']).override_settings(
    STORAGES=__import__('tests.test_frontend', fromlist=['PLAIN_STATIC']).PLAIN_STATIC)
class PasswordHashedBeforeTheLockTests(TransactionTestCase):
    def test_the_new_password_is_hashed_outside_any_transaction_and_saved_under_the_lock(self):
        from django.contrib.auth.base_user import AbstractBaseUser
        from django.db import transaction
        from tests import test_account as account
        from tests.support import coding as f
        ws = f.workspace()
        user = f.member(ws)
        client = account.signed_in(user)
        hashed_in = []
        real = AbstractBaseUser.set_password

        def watched(self, raw):
            hashed_in.append(transaction.get_connection().in_atomic_block)
            return real(self, raw)

        with mock.patch.object(AbstractBaseUser, 'set_password', watched):
            answer = account.change(client)
        self.assertEqual(answer.status_code, 302, 'the change was made')
        self.assertEqual(hashed_in, [False], 'the new password was hashed while a transaction (the account lock) was open')
        user.refresh_from_db()
        self.assertTrue(user.check_password(account.NEW))
