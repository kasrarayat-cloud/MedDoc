"""Post-expiry renewal-administration reservation: synthetic ledger, no provider, no credential."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from . import offsite_renewal_administration as door
    from . import offsite_allocation as allocation
except ImportError:
    import offsite_renewal_administration as door
    import offsite_allocation as allocation

engine = door.engine
renewal = door.renewal
END = '2026-09-22T23:00:00+00:00'


class RenewalAdministrationReservation(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.state = Path(temporary.name)
        self.now = datetime(2026, 9, 22, 20, 0, tzinfo=timezone.utc)
        self.limits = {'observed_at': '2026-09-21T19:32:21.377935+00:00',
                       'valid_until': '2026-09-22T19:32:21.377935+00:00',
                       'max_run_seconds': 900, 'daily_request_budget': 500,
                       'daily_download_budget_bytes': 100_000_000}
        self.raw = json.dumps(self.limits).encode()
        self.ledger = {'version': 2, 'day': '2026-09-22', 'requests': 285, 'download_bytes': 81_169_896,
                       'days': {'2026-09-21': {'requests': 188, 'download_bytes': 49_270_808},
                                '2026-09-22': {'requests': 285, 'download_bytes': 81_169_896}},
                       'legacy_import': None,
                       'external_reservations': [{'reference': 'account-audit-98b609fe6b166bef1b256644373ae3df',
                                                  'at': '2026-09-21T18:30:12+00:00', 'requests': 20,
                                                  'download_bytes': 8_388_608, 'charged_days': ['2026-09-21']}]}
        engine.atomic(self.state / 'budget.json', self.ledger)
        self.patch(engine, 'STATE', self.state)
        self.policy = self.patch(engine, 'policy', side_effect=engine.Refusal('policy_expired'))
        self.historical = self.patch(renewal, 'historical_limits', return_value=(self.limits, self.raw))
        self.renewal_state = self.patch(renewal, 'read_state', return_value={'state': 'installed'})
        self.patch(engine, 'now', return_value=self.now)
        self.patch(engine.offsite, 'configuration', side_effect=AssertionError('No credential access allowed.'))
        self.patch_path('requests.Session', side_effect=AssertionError('No provider use allowed.'))

    def patch(self, target, name, *new, **kwargs):
        patcher = patch.object(target, name, *new, **kwargs)
        mocked = patcher.start()
        self.addCleanup(patcher.stop)
        return mocked

    def patch_path(self, name, **kwargs):
        patcher = patch(name, **kwargs)
        patcher.start()
        self.addCleanup(patcher.stop)

    def ledger_bytes(self):
        return (self.state / 'budget.json').read_bytes()

    def refused(self, code, *args, **kwargs):
        before = self.ledger_bytes()
        if len(args) == 3:
            args = (*args, END)
        with self.assertRaises(engine.Refusal) as caught:
            door.reserve(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.ledger_bytes(), before, 'a refusal must leave the ledger byte-identical')

    def test_expired_policy_admits_the_bounded_administration_session_in_advance(self):
        result = door.reserve(34, 4_456_448, 'desktop-key-administration-20260923', END)
        self.assertEqual(result['provider_calls'], 0)
        value = json.loads(self.ledger_bytes())
        self.assertEqual(value['days']['2026-09-22'], {'requests': 319, 'download_bytes': 85_626_344})
        self.assertEqual(value['days']['2026-09-21'], self.ledger['days']['2026-09-21'], 'prior days untouched')
        self.assertEqual(value['external_reservations'][0], self.ledger['external_reservations'][0])
        entry = value['external_reservations'][-1]
        self.assertTrue(entry['reference'].startswith('renewal-administration:'))
        self.assertTrue(entry['reference'].endswith(':desktop-key-administration-20260923'))
        self.assertEqual(entry['charged_days'], ['2026-09-22'])
        self.assertEqual((self.state / 'budget.json').stat().st_mode & 0o777, 0o600)
        # the policy is validated at its ORIGINAL time, not now
        self.historical.assert_called_once_with()

    def test_a_valid_policy_is_refused_so_the_ordinary_door_stays_the_only_one(self):
        self.policy.side_effect = None
        self.policy.return_value = self.limits
        self.refused('state_invalid', 34, 4_456_448, 'desktop-key-administration')

    def test_missing_invalid_or_historically_unverifiable_authorization_is_refused(self):
        for code in ('policy_missing', 'policy_invalid'):
            with self.subTest(current=code):
                self.policy.side_effect = engine.Refusal(code)
                self.refused(code, 34, 4_456_448, 'desktop-key-administration')
        self.policy.side_effect = engine.Refusal('policy_expired')
        self.historical.side_effect = engine.Refusal('policy_invalid')
        self.refused('policy_invalid', 34, 4_456_448, 'desktop-key-administration')

    def test_an_import_in_progress_is_refused(self):
        self.renewal_state.return_value = {'state': 'importing'}
        self.refused('state_invalid', 34, 4_456_448, 'desktop-key-administration')

    def test_envelope_and_values_are_bounded(self):
        for requests, downloaded, label in ((41, 0, 'valid-label'), (0, 0, 'valid-label'), (1, 8 * 1024 * 1024 + 1, 'valid-label'),
                                            (-1, 0, 'valid-label'), (True, 0, 'valid-label'), (1, 0, 'Bad Label'),
                                            (1, 0, 'x'), (1, 0, 'a' * 70), (1, 0, '../escape')):
            with self.subTest(requests=requests, downloaded=downloaded, label=label):
                self.refused('state_invalid', requests, downloaded, label)

    def test_daily_limits_and_prior_consumption_are_respected(self):
        self.ledger['days']['2026-09-22'] = {'requests': 480, 'download_bytes': 81_169_896}
        self.ledger.update(requests=480)
        engine.atomic(self.state / 'budget.json', self.ledger)
        self.refused('budget_exhausted', 34, 4_456_448, 'desktop-key-administration')
        self.ledger['days']['2026-09-22'] = {'requests': 285, 'download_bytes': 97_000_000}
        self.ledger.update(requests=285, download_bytes=97_000_000)
        engine.atomic(self.state / 'budget.json', self.ledger)
        self.refused('budget_exhausted', 34, 4_456_448, 'desktop-key-administration')

    def test_a_session_that_can_cross_midnight_is_charged_to_both_days(self):
        self.now = datetime(2026, 9, 22, 23, 55, tzinfo=timezone.utc)
        engine.now.return_value = self.now
        result = door.reserve(34, 4_456_448, 'late-session', '2026-09-23T06:00:00+00:00')
        self.assertEqual(result['reservation']['charged_days'], ['2026-09-22', '2026-09-23'])
        value = json.loads(self.ledger_bytes())
        self.assertEqual(value['days']['2026-09-23'], {'requests': 34, 'download_bytes': 4_456_448})

    def test_the_full_reservation_is_charged_to_every_day_of_the_declared_session(self):
        result = door.reserve(34, 4_456_448, 'two-day-session', '2026-09-24T19:00:00+00:00')
        self.assertEqual(result['reservation']['charged_days'], ['2026-09-22', '2026-09-23', '2026-09-24'])
        value = json.loads(self.ledger_bytes())
        self.assertEqual(value['days']['2026-09-22'], {'requests': 319, 'download_bytes': 85_626_344})
        for day in ('2026-09-23', '2026-09-24'):
            self.assertEqual(value['days'][day], {'requests': 34, 'download_bytes': 4_456_448})

    def test_the_session_window_is_bounded_like_the_ticket_window(self):
        for end in ('2026-09-22T19:59:59+00:00', '2026-09-22T20:00:00+00:00', '2026-09-24T20:00:01+00:00'):
            with self.subTest(end=end):
                self.refused('state_invalid', 34, 4_456_448, 'window-check', end)
        for malformed in ('not-a-time', '2026-09-23T12:00'):          # a typo and a naive time
            self.refused('state_invalid', 34, 4_456_448, 'window-check', malformed)

    def test_entries_written_before_expiry_by_another_door_do_not_use_up_the_cap(self):
        scope = 'renewal-administration:' + door.installer.digest(self.raw)[:16] + ':'
        for name in ('squat-a', 'squat-b'):
            self.ledger['external_reservations'].append({'reference': scope + name, 'at': '2026-09-22T10:00:00+00:00',
                                                         'requests': 1, 'download_bytes': 0, 'charged_days': ['2026-09-22']})
        engine.atomic(self.state / 'budget.json', self.ledger)
        door.reserve(34, 4_456_448, 'desktop-key-administration', END)
        door.reserve(1, 0, 'retry-session', END)
        self.refused('budget_exhausted', 1, 0, 'third-session')

    def test_the_command_reports_every_refusal_as_data(self):
        import contextlib, io
        argv = ['--requests', '1', '--download-bytes', '0', '--label', 'cli-check', '--session-end', END]
        for failure, code in ((renewal.Refusal('state_invalid'), 'state_invalid'),
                              (ValueError('corrupt status'), 'state_invalid'),
                              (engine.Refusal('lock_busy'), 'lock_busy'),
                              (AttributeError("'list' object has no attribute 'get'"), 'state_invalid')):
            with self.subTest(failure=failure):
                self.renewal_state.side_effect = failure
                before, out = self.ledger_bytes(), io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertEqual(door.cli(argv), 1)
                self.assertEqual(json.loads(out.getvalue()), {'complete': False, 'reason_code': code})
                self.assertEqual(self.ledger_bytes(), before)
        self.renewal_state.side_effect = None
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(door.cli(argv), 0)
        self.assertTrue(json.loads(out.getvalue())['complete'])

    def test_repeated_requests_cannot_double_charge_and_are_capped_per_expired_policy(self):
        door.reserve(34, 4_456_448, 'first-session', END)
        self.refused('state_invalid', 34, 4_456_448, 'first-session')
        door.reserve(10, 1_000_000, 'retry-session', END)
        self.refused('budget_exhausted', 1, 0, 'third-session')
        # a DIFFERENT expired policy is a different renewal and starts its own count
        self.historical.return_value = (self.limits, self.raw + b' ')
        door.reserve(1, 0, 'third-session', END)

    def test_concurrent_holder_of_the_canonical_lock_blocks_the_reservation(self):
        with engine.exclusion(self.state):
            self.refused('lock_busy', 34, 4_456_448, 'overlap')

    def test_another_process_holding_the_lock_blocks_the_reservation(self):
        import subprocess, sys, time
        holder = subprocess.Popen([sys.executable, '-c',
            'import fcntl,os,sys,time\n'
            'fd=os.open(sys.argv[1],os.O_CREAT|os.O_RDWR,0o600)\n'
            'fcntl.flock(fd,fcntl.LOCK_EX)\nprint("held",flush=True)\ntime.sleep(30)\n',
            str(self.state / 'execution.lock')], stdout=subprocess.PIPE, text=True)
        self.addCleanup(holder.stdout.close)
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline().strip(), 'held')
        self.refused('lock_busy', 34, 4_456_448, 'cross-process')
        holder.kill(); holder.wait()
        door.reserve(34, 4_456_448, 'cross-process', END)

    def test_simultaneous_requests_never_both_pass_the_cap(self):
        """Two reservations racing for the last slot: exactly one succeeds, the ledger stays valid."""
        import multiprocessing
        door.reserve(1, 0, 'first-session', END)
        context = multiprocessing.get_context('fork')
        results = context.Queue()

        def attempt(label):
            try:
                door.reserve(1, 0, label, END)
                results.put('ok')
            except engine.Refusal as refusal:
                results.put(refusal.code)
        workers = [context.Process(target=attempt, args=(name,)) for name in ('racer-a', 'racer-b')]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(10)
        outcomes = sorted(results.get(timeout=5) for _ in workers)
        self.assertEqual(outcomes.count('ok'), 1, outcomes)
        self.assertTrue(set(outcomes) - {'ok'} <= {'lock_busy', 'budget_exhausted'}, outcomes)
        value = json.loads(self.ledger_bytes())
        scoped = [e for e in value['external_reservations'] if e['reference'].startswith('renewal-administration:')]
        self.assertEqual(len(scoped), 2)
        self.assertEqual(value['days']['2026-09-22']['requests'], 285 + 2)

    def test_backup_traffic_stays_refused_under_the_expired_policy(self):
        budget = engine.Budget(self.state, self.limits, clock=lambda: self.now)
        before = self.ledger_bytes()
        patcher = patch.object(engine.Budget, 'assert_live', return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        for action in (lambda: budget.debit(1024), lambda: budget.preflight(1, 1),
                       lambda: budget.reserve_external(1, 1, 'ordinary-door')):
            with self.assertRaises(engine.Refusal) as caught:
                action()
            self.assertEqual(caught.exception.code, 'policy_expired')
        self.assertEqual(self.ledger_bytes(), before)

    def test_this_door_is_not_a_pinned_control_source(self):
        """Editing a pinned source breaks every policy validation, including renewal itself."""
        self.assertNotIn('rebuild/ops/offsite_renewal_administration.py', allocation.SOURCES)


if __name__ == '__main__':
    unittest.main()
