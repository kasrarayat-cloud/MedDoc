"""The publisher verdict: published-and-unhealthy is not a failure; a missing, stale or foreign write,
a replayed run and an unrelated error still are. Shapes are copied from the 2026-09-22 journal."""
import unittest

try:
    from . import publisher_verification as v
except ImportError:
    import publisher_verification as v

BEFORE_ROW = {'computed_at': '2026-09-22T20:18:07.921620+00:00', 'condition': 'offsite_policy_expired',
              'severity': 'failure', 'healthy': False}
BEFORE_INVOCATION = '6b2f5fda' + '0' * 24
RUN = 'e88a37d5' + '1' * 24


def unit(**overrides):
    base = {'InvocationID': RUN, 'Result': 'exit-code', 'ExecMainStatus': '1',
            'ExecMainStartTimestamp': 'Tue 2026-09-22 20:23:04 UTC', 'ExecMainExitTimestamp': 'Tue 2026-09-22 20:23:05 UTC'}
    base.update(overrides)
    return base


def row(**overrides):
    base = {'computed_at': '2026-09-22T20:23:05.675538+00:00', 'condition': 'offsite_policy_expired',
            'severity': 'failure', 'healthy': False}
    base.update(overrides)
    return base


PUBLISHED = [(RUN, 'Published backup status: offsite_policy_expired (failure).')]


class PublisherVerdict(unittest.TestCase):
    def refused(self, reason, **kwargs):
        args = {'before_row': BEFORE_ROW, 'before_invocation': BEFORE_INVOCATION,
                'unit': unit(), 'row': row(), 'journal': PUBLISHED}
        args.update(kwargs)
        with self.assertRaises(v.VerificationFailure) as caught:
            v.judge(**args)
        self.assertEqual(caught.exception.reason, reason)

    def test_the_2026_09_22_run_is_a_verified_publication_of_an_unhealthy_state(self):
        verdict = v.judge(BEFORE_ROW, BEFORE_INVOCATION, unit(), row(), PUBLISHED)
        self.assertTrue(verdict['publication_verified'])
        self.assertIs(verdict['backup_healthy'], False, 'fixing the verifier must never claim healthy backups')
        self.assertIn('UNHEALTHY', verdict['meaning'])

    def test_a_healthy_run_exits_zero_and_says_so(self):
        verdict = v.judge(BEFORE_ROW, BEFORE_INVOCATION, unit(Result='success', ExecMainStatus='0'),
                          row(condition='healthy', severity='healthy', healthy=True),
                          [(RUN, 'Published backup status: healthy (healthy).')])
        self.assertTrue(verdict['backup_healthy'])

    def test_a_missing_write_fails(self):
        self.refused('no_write', row=None)
        self.refused('no_write', row=dict(BEFORE_ROW))                     # the row never advanced

    def test_a_stale_or_foreign_write_fails(self):
        # advanced, but written before this run started (another writer, or an earlier tick)
        self.refused('stale_or_foreign_write', row=row(computed_at='2026-09-22T20:20:00+00:00'))
        # advanced, but after this run had already exited
        self.refused('stale_or_foreign_write', row=row(computed_at='2026-09-22T20:23:09+00:00'))

    def test_a_replayed_or_missing_invocation_fails(self):
        self.refused('replayed_invocation', before_invocation=RUN)
        self.refused('no_invocation', unit=unit(InvocationID=''))

    def test_unrelated_errors_fail_even_with_exit_1(self):
        self.refused('execution_error', journal=PUBLISHED + [(RUN, 'Traceback (most recent call last):')])
        self.refused('execution_error', journal=[(RUN, 'CommandError: The operations aggregator returned a shape')])
        self.refused('publication_not_logged', journal=[])
        self.refused('publication_not_logged', journal=[(BEFORE_INVOCATION, PUBLISHED[0][1])])   # another run's line
        self.refused('publication_mismatch', journal=[(RUN, 'Published backup status: healthy (healthy).')])

    def test_exit_codes_must_agree_with_the_published_state(self):
        self.refused('inconsistent_exit', row=row(healthy=True, severity='healthy', condition='healthy'),
                     journal=[(RUN, 'Published backup status: healthy (healthy).')])
        self.refused('inconsistent_exit', unit=unit(Result='success', ExecMainStatus='0'))
        for result, status in (('exit-code', '2'), ('signal', '9'), ('timeout', '0'), ('core-dump', '1'), ('exit-code', '')):
            with self.subTest(result=result, status=status):
                self.refused('execution_failure', unit=unit(Result=result, ExecMainStatus=status))

    def test_unverifiable_evidence_fails(self):
        self.refused('unverifiable_timestamps', unit=unit(ExecMainExitTimestamp='n/a'))
        self.refused('unverifiable_row', row=row(computed_at='2026-09-22T20:23:05'))


if __name__ == '__main__':
    unittest.main()
